import copy
import hashlib
import json
import re
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path
from .catalog import cached_version, load_catalog, patch_of
from .config import CATEGORIES, LANES, load_config, read_json, write_json
from .statistics import aggregate
from .storage import Store


def safe_json(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False).replace("<", "\\u003c")


def empty_board():
    return {"schemaVersion": 2, "id": "counter-note-published-v3", "matchups": {}, "earlyDisadvantage": {}, "tiers": {}, "rosterSort": "tier"}


def validate_board(value, champions):
    if not isinstance(value, dict) or value.get("schemaVersion") != 2:
        raise ValueError("현재 형식의 상성노트 백업이 필요합니다.")
    known = set(champions)
    result = empty_board()
    result["rosterSort"] = value.get("rosterSort", "tier")
    if result["rosterSort"] not in ("alpha", "tier"):
        raise ValueError("잘못된 정렬 방식입니다.")
    for name in ("matchups", "earlyDisadvantage", "tiers"):
        if not isinstance(value.get(name, {}), dict):
            raise ValueError("상성 데이터 형식이 잘못되었습니다.")
        for lane, entries in value.get(name, {}).items():
            if lane not in LANES.values() or not isinstance(entries, dict):
                raise ValueError("잘못된 라인입니다.")
            result[name][lane] = {}
            seen_tiers = set()
            for key, groups in entries.items():
                if name == "matchups":
                    if key not in known or not isinstance(groups, dict) or set(groups) - set(CATEGORIES):
                        raise ValueError("잘못된 챔피언 또는 상성 분류입니다.")
                    seen = set()
                    clean = {}
                    for cat in CATEGORIES:
                        ids = groups.get(cat, [])
                        if not isinstance(ids, list) or any(not isinstance(i, str) or i not in known or i == key or i in seen for i in ids) or len(set(ids)) != len(ids):
                            raise ValueError("중복되거나 잘못된 상성 챔피언입니다.")
                        seen.update(ids)
                        clean[cat] = ids[:]
                    if seen:
                        result[name][lane][key] = clean
                else:
                    if not isinstance(groups, list) or any(not isinstance(i, str) or i not in known for i in groups) or len(set(groups)) != len(groups):
                        raise ValueError("챔피언 목록 형식이 잘못되었습니다.")
                    if name == "tiers":
                        if key not in ("1", "2", "3", "4", "5") or seen_tiers.intersection(groups):
                            raise ValueError("잘못된 티어 배치입니다.")
                        seen_tiers.update(groups)
                    elif key not in known:
                        raise ValueError("잘못된 상대 챔피언입니다.")
                    result[name][lane][key] = groups[:]
    for lane, enemies in result["earlyDisadvantage"].items():
        for enemy, ids in enemies.items():
            registered = {i for group in result["matchups"].get(lane, {}).get(enemy, {}).values() for i in group}
            if set(ids) - registered:
                raise ValueError("등록된 상성에만 초반 불리를 표시할 수 있습니다.")
    return result


def apply_overrides(board, overrides, champions):
    result = copy.deepcopy(board)
    if overrides.get("schemaVersion") != 1:
        raise ValueError("배포자 수정 파일 형식이 잘못되었습니다.")
    for name in ("matchups", "earlyDisadvantage", "tiers"):
        for lane, entries in overrides.get(name, {}).items():
            result[name].setdefault(lane, {}).update(copy.deepcopy(entries))
    result["rosterSort"] = overrides.get("rosterSort", board["rosterSort"])
    for lane, enemies in result["earlyDisadvantage"].items():
        for enemy, ids in enemies.items():
            allowed = {i for group in result["matchups"].get(lane, {}).get(enemy, {}).values() for i in group}
            enemies[enemy] = [i for i in ids if i in allowed]
    return validate_board(result, champions)


def save_edits(root, value, revision):
    public = read_json(root / "site" / "data" / "site.json")
    if revision != public["revision"]:
        raise ValueError("새 통계가 먼저 배포되었습니다. 페이지를 새로고침한 뒤 다시 수정하세요.")
    champions = {c["id"] for c in public["catalog"]["champions"]}
    changed = validate_board(value, champions)
    base = public["board"]
    path = root / "data" / "overrides.json"
    overrides = read_json(path)
    for name in ("matchups", "earlyDisadvantage"):
        for lane in LANES.values():
            keys = set(base[name].get(lane, {})) | set(changed[name].get(lane, {}))
            default = {cat: [] for cat in CATEGORIES} if name == "matchups" else []
            for enemy in keys:
                before = base[name].get(lane, {}).get(enemy, default)
                after = changed[name].get(lane, {}).get(enemy, default)
                if before != after:
                    overrides.setdefault(name, {}).setdefault(lane, {})[enemy] = after
    for lane in LANES.values():
        if base["tiers"].get(lane, {}) != changed["tiers"].get(lane, {}):
            overrides.setdefault("tiers", {})[lane] = {tier: changed["tiers"].get(lane, {}).get(tier, []) for tier in ("1", "2", "3", "4", "5")}
    overrides["rosterSort"] = changed["rosterSort"]
    original = read_json(path)
    write_json(path, overrides)
    try:
        return build_site(root)
    except Exception:
        write_json(path, original)
        raise


def build_site(root):
    config = load_config(root)
    version = cached_version(root, config)
    champions, items = load_catalog(root, version)
    patch = patch_of(version)
    since = int(time.time()) - config["lookback_days"] * 86400
    with Store(root / "data" / "matches.sqlite3") as store:
        board, index, details = aggregate(store.records(config["platform"], config["queue"], patch, since), config)
        games = store.count(config["platform"], config["queue"], patch, since)
        refresh = store.get("last_refresh", {})
    overrides = read_json(root / "data" / "overrides.json")
    board = apply_overrides(board, overrides, champions)
    catalog = {"version": version, "champions": [{"id": c["id"], "name": c["name"], "title": c["title"], "image": f"https://ddragon.leagueoflegends.com/cdn/{version}/img/champion/{c['image']['full']}"} for c in champions.values()]}
    item_catalog = {item_id: {"name": item["name"], "image": f"https://ddragon.leagueoflegends.com/cdn/{version}/img/item/{item['image']['full']}"} for item_id, item in items.items()}
    now = datetime.now(timezone.utc).isoformat()
    metadata = {"patch": patch, "dataDragonVersion": version, "publishedAt": now, "updatedAt": refresh.get("updatedAt") if refresh.get("patch") == patch else None, "games": games, "platform": config["platform"], "queue": config["queue"], "windowDays": config["lookback_days"], "since": datetime.fromtimestamp(since, timezone.utc).isoformat(), "minGames": config["min_matchup_games"], "minLevels": config["min_level_observations"], "minBuildGames": config["min_build_games"], "fdrMethod": config["fdr_method"], "fdrAlpha": config["fdr_alpha"], "limited": refresh.get("limited", False), "refreshHours": config["refresh_hours"], "coverage": "API로 수집한 랭크 경기 표본 · 서버 전체 경기 전수 아님", "buildDefinition": "시작: 90초 직전 보유 아이템, 코어: 신발·소모품 제외 완성 아이템 구매 순서", "manualPairs": sum(len(v) for v in overrides.get("matchups", {}).values())}
    payload = {"schemaVersion": 3, "metadata": metadata, "catalog": catalog, "items": item_catalog, "board": board, "matchupIndex": index, "pollSeconds": max(30, config["poll_seconds"]), "githubRepository": config["github_repository"]}
    digest = hashlib.sha256((safe_json(payload) + safe_json(details) + (root / "web" / "app.js").read_text(encoding="utf-8-sig") + (root / "web" / "app.css").read_text(encoding="utf-8-sig")).encode()).hexdigest()[:20]
    payload["revision"] = digest
    payload["detailRoot"] = f"data/releases/{digest}"
    directory = root / "site"
    directory.mkdir(parents=True, exist_ok=True)
    for lane, enemies in details.items():
        for enemy, stats in enemies.items():
            write_json(directory / "data" / "releases" / digest / f"{lane}-{enemy}.json", stats)
    html = (root / "web" / "index.template.html").read_text(encoding="utf-8-sig")
    replacements = {"__CSS__": (root / "web" / "app.css").read_text(encoding="utf-8-sig"), "__CATALOG__": safe_json(catalog), "__BOARD_DATA__": safe_json(board), "__PUBLIC_DATA__": safe_json(payload), "__JAVASCRIPT__": (root / "web" / "app.js").read_text(encoding="utf-8-sig")}
    for key, value in replacements.items():
        if key not in html:
            raise ValueError(f"HTML 템플릿에 {key}가 없습니다.")
        html = html.replace(key, value)
    write_json(directory / "data" / "site.json", payload)
    temporary = directory / "index.html.tmp"
    temporary.write_text(html, encoding="utf-8")
    temporary.replace(directory / "index.html")
    write_json(directory / "release.json", {"revision": digest, "updatedAt": metadata["updatedAt"], "publishedAt": now})
    (directory / ".nojekyll").touch()
    releases = directory / "data" / "releases"
    if releases.exists():
        old = sorted((p for p in releases.iterdir() if p.is_dir() and re.fullmatch(r"[0-9a-f]{20}", p.name)), key=lambda p: p.stat().st_mtime, reverse=True)
        for folder in old[2:]:
            target = folder.resolve()
            if target.parent != releases.resolve():
                raise ValueError("릴리스 정리 경로가 올바르지 않습니다.")
            shutil.rmtree(target)
    size = sum(p.stat().st_size for p in directory.rglob("*") if p.is_file())
    if size > 50 * 1024 * 1024:
        raise ValueError("배포 파일이 50MB를 넘었습니다. 보관 경기 수를 줄이세요.")
    return payload
