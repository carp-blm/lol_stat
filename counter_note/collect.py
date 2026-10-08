import hashlib
import json
import os
import time
from collections import deque
from datetime import datetime, timezone
from urllib.parse import quote
from .catalog import refresh_catalog, load_catalog, patch_of
from .config import load_config, load_env
from .extract import extract_match
from .riot import RiotClient, RiotError, BudgetReached
from .storage import Store


def env_list(key):
    text = os.environ.get(key, "").strip()
    if not text:
        return []
    if text.startswith("["):
        result = json.loads(text)
        if not isinstance(result, list) or any(not isinstance(x, str) for x in result):
            raise ValueError(f"{key}는 문자열 JSON 배열이어야 합니다.")
        return result
    return [x.strip() for x in text.split(",") if x.strip()]


def discover(client, config):
    players = set(env_list("RIOT_SEED_PUUIDS"))
    for riot_id in env_list("RIOT_SEED_IDS"):
        if "#" not in riot_id:
            raise ValueError("RIOT_SEED_IDS에는 게임이름#태그가 필요합니다.")
        account = client.account(*riot_id.rsplit("#", 1))
        if account and account.get("puuid"):
            players.add(account["puuid"])
    if players:
        return list(players)
    queue = "RANKED_SOLO_5x5" if config["queue"] == 420 else "RANKED_FLEX_SR"
    epoch = int(time.time() // 172800)
    for tier in config["discovery_tiers"]:
        if tier not in {"IRON", "BRONZE", "SILVER", "GOLD", "PLATINUM", "EMERALD", "DIAMOND"}:
            raise ValueError("discovery_tiers에는 IRON~DIAMOND를 설정하세요. 특정 상위권 수집은 Riot ID 시드를 사용할 수 있습니다.")
        for division in config["discovery_divisions"]:
            if division not in {"I", "II", "III", "IV"}:
                raise ValueError("잘못된 discovery_divisions입니다.")
            entries = client.get(config["platform"], f"/lol/league/v4/entries/{queue}/{tier}/{division}", {"page": 1}) or []
            available = sorted((entry["puuid"] for entry in entries if entry.get("puuid")), key=lambda p: hashlib.sha256(f"{epoch}:{p}".encode()).hexdigest())
            players.update(available[:max(1, config["max_players"] // max(1, len(config["discovery_tiers"]) * len(config["discovery_divisions"])) )])
    return sorted(players, key=lambda p: hashlib.sha256(f"{epoch}:{p}".encode()).hexdigest())[:config["max_players"]]


def refresh(root, force=False, progress=lambda message: None):
    config = load_config(root)
    load_env(root)
    with Store(root / "data" / "matches.sqlite3") as store:
        last = store.get("last_refresh", {})
        scope = f"{config['platform']}:{config['queue']}:{config['patch']}"
        interval = config["refresh_hours"] * 3600
        if not force and last.get("scope") == scope and time.time() - last.get("startedEpoch", last.get("finishedEpoch", 0)) < interval - min(600, interval * 0.01):
            return {"skipped": True, "message": "최근 성공한 갱신으로부터 48시간이 지나지 않았습니다."}
        client = RiotClient(os.environ.get("RIOT_API_KEY", ""), config)
        progress("Riot 공식 챔피언·아이템 데이터를 확인하고 있습니다.")
        version = refresh_catalog(root, config)
        patch = patch_of(version)
        champions, items = load_catalog(root, version)
        since = int(time.time()) - config["lookback_days"] * 86400
        stats = {"newMatches": 0, "invalidMatches": 0, "playersVisited": 0, "requests": 0, "limited": False, "patch": patch, "version": version, "scope": scope, "startedEpoch": int(time.time())}
        seen_players, seen_matches = set(), set()
        try:
            progress("랭크 참가자 시드와 최근 경기 목록을 조회하고 있습니다.")
            seeds = discover(client, config)
            if not seeds:
                raise RiotError("수집할 PUUID를 찾지 못했습니다. .env의 RIOT_SEED_IDS 또는 RIOT_SEED_PUUIDS를 설정하세요.")
            players = deque(seeds)
            while players and len(seen_players) < config["max_players"] and stats["newMatches"] < config["max_new_matches"]:
                puuid = players.popleft()
                if puuid in seen_players:
                    continue
                seen_players.add(puuid)
                stats["playersVisited"] += 1
                for start in (0, 100, 200):
                    ids = client.get(config["region"], f"/lol/match/v5/matches/by-puuid/{quote(puuid, safe='')}/ids", {"queue": config["queue"], "startTime": since, "start": start, "count": 100}) or []
                    for match_id in ids:
                        if stats["newMatches"] >= config["max_new_matches"]:
                            stats["limited"] = True
                            break
                        if match_id in seen_matches or store.seen(match_id):
                            continue
                        seen_matches.add(match_id)
                        match = client.get(config["region"], f"/lol/match/v5/matches/{quote(match_id, safe='')}")
                        if not match:
                            continue
                        info = match.get("info", {})
                        if patch_of(info.get("gameVersion")) != patch:
                            continue
                        if info.get("queueId") != config["queue"] or info.get("mapId") != 11 or info.get("gameDuration", 0) < config["min_match_seconds"]:
                            store.skip(match_id)
                            continue
                        timeline = client.get(config["region"], f"/lol/match/v5/matches/{quote(match_id, safe='')}/timeline")
                        if not timeline:
                            continue
                        try:
                            facts = extract_match(match, timeline, champions, items, config)
                        except (ValueError, KeyError, TypeError):
                            stats["invalidMatches"] += 1
                            continue
                        if not facts:
                            store.skip(match_id)
                            continue
                        started = int(info.get("gameStartTimestamp", info.get("gameCreation", 0)) / 1000)
                        if started < since:
                            continue
                        store.add(match_id, patch, started, config["platform"], config["queue"], facts)
                        stats["newMatches"] += 1
                        if len(players) < config["max_players"] * 2:
                            players.extend(p["puuid"] for p in info.get("participants", []) if p.get("puuid") and p["puuid"] not in seen_players)
                        if stats["newMatches"] % 20 == 0:
                            progress(f"새 경기 {stats['newMatches']}개 분석 완료 · API 요청 {client.requests}회")
                    if len(ids) < 100 or stats["limited"]:
                        break
        except BudgetReached:
            stats["limited"] = True
        stats["requests"] = client.requests
        if not seen_players and not stats["newMatches"]:
            raise RiotError("경기를 수집하기 전에 실행 한도에 도달했습니다. 수집 설정을 확인하세요.")
        stats["finishedEpoch"] = int(time.time())
        stats["updatedAt"] = datetime.now(timezone.utc).isoformat()
        store.prune(config)
        stats["storedMatches"] = store.count(config["platform"], config["queue"], patch, since)
        store.set("last_refresh", stats)
        progress(f"갱신 완료 · 현재 패치의 유효 경기 {stats['storedMatches']}개")
        return stats
