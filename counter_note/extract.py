from collections import Counter
from .catalog import core_item_ids
from .config import LANES


def events_of(timeline, duration_ms):
    seen = set()
    events = []
    for frame in timeline.get("info", {}).get("frames", []):
        for event in frame.get("events", []):
            timestamp = event.get("timestamp")
            if not isinstance(timestamp, (int, float)) or not 0 <= timestamp <= duration_ms:
                continue
            if event.get("type") in ("LEVEL_UP", "CHAMPION_KILL"):
                identity = (event.get("type"), timestamp, event.get("participantId"), event.get("level"), event.get("killerId"), event.get("victimId"))
                if identity in seen:
                    continue
                seen.add(identity)
            events.append(event)
    return sorted(events, key=lambda e: e["timestamp"])


def level_interval(pid, level, events, frames):
    exact = [e["timestamp"] for e in events if e.get("type") == "LEVEL_UP" and e.get("participantId") == pid and e.get("level") == level and e["timestamp"] > 0]
    if exact:
        return min(exact), min(exact), "event"
    previous = None
    for frame in sorted(frames, key=lambda f: f.get("timestamp", 0)):
        point = frame.get("participantFrames", {}).get(str(pid), {})
        value = point.get("level")
        timestamp = frame.get("timestamp")
        if not isinstance(value, int) or not isinstance(timestamp, (int, float)):
            continue
        if value >= level:
            if previous is None:
                return None
            return previous, timestamp, "frame"
        previous = timestamp
    return None


def first_level(own, enemy):
    if own is None or enemy is None:
        return None, "missing"
    source = "event" if own[2] == enemy[2] == "event" else "frame"
    if own[2] == enemy[2] == "event":
        return (1 if own[0] < enemy[0] else -1 if own[0] > enemy[0] else 0), source
    if own[1] < enemy[0] or own[1] == enemy[0] and enemy[2] == "frame":
        return 1, source
    if enemy[1] < own[0] or enemy[1] == own[0] and own[2] == "frame":
        return -1, source
    return None, "ambiguous"


def item_build(pid, events, items, core_ids, cutoff):
    inventory = Counter()
    start = None
    purchases = []
    for event in events:
        if start is None and event["timestamp"] >= cutoff:
            start = inventory.copy()
        if event.get("participantId") != pid:
            continue
        kind, item_id = event.get("type"), str(event.get("itemId", 0))
        if kind == "ITEM_PURCHASED":
            inventory[item_id] += 1
            purchases.append({"id": item_id, "active": True})
        elif kind in ("ITEM_SOLD", "ITEM_DESTROYED"):
            inventory[item_id] = max(0, inventory[item_id] - 1)
        elif kind == "ITEM_UNDO":
            before, after = str(event.get("beforeId", 0)), str(event.get("afterId", 0))
            if before != "0":
                inventory[before] = max(0, inventory[before] - 1)
                for purchase in reversed(purchases):
                    if purchase["active"] and purchase["id"] == before:
                        purchase["active"] = False
                        break
            if after != "0":
                inventory[after] += 1
    if start is None:
        start = inventory
    starters = sorted(item_id for item_id, count in start.items() for _ in range(count) if item_id in items and "Trinket" not in items[item_id].get("tags", []))
    cores = []
    for purchase in purchases:
        if purchase["active"] and purchase["id"] in core_ids and purchase["id"] not in cores:
            cores.append(purchase["id"])
    builds = {"start": starters} if starters else {}
    builds.update({str(i): cores[:i] for i in range(1, min(len(cores), 5) + 1)})
    return builds


def extract_match(match, timeline, champions, items, config):
    info = match.get("info", {})
    duration = info.get("gameDuration", 0)
    if info.get("queueId") != config["queue"] or info.get("mapId") != 11 or duration < config["min_match_seconds"] or duration > 14400:
        return []
    if timeline.get("metadata", {}).get("matchId") != match.get("metadata", {}).get("matchId"):
        raise ValueError("경기와 타임라인의 ID가 다릅니다.")
    frames = timeline.get("info", {}).get("frames", [])
    if not frames or max(f.get("timestamp", 0) for f in frames) < duration * 1000 - 65000:
        raise ValueError("타임라인이 불완전합니다.")
    events = events_of(timeline, duration * 1000 + 1000)
    known = {int(c["key"]): c["id"] for c in champions.values()}
    participants = info.get("participants", [])
    core_ids = core_item_ids(items, config)
    records = []
    for role, lane in LANES.items():
        pair = [p for p in participants if p.get("teamPosition") == role]
        if len(pair) != 2 or {p.get("teamId") for p in pair} != {100, 200}:
            continue
        if any(p.get("championId") not in known or type(p.get("win")) is not bool for p in pair) or pair[0]["championId"] == pair[1]["championId"]:
            continue
        for own, enemy in (pair, pair[::-1]):
            pid, eid = own["participantId"], enemy["participantId"]
            if pid not in range(1, 11) or eid not in range(1, 11):
                continue
            levels = {}
            for level in (2, 3, 6):
                outcome, source = first_level(level_interval(pid, level, events, frames), level_interval(eid, level, events, frames))
                levels[str(level)] = {"outcome": outcome, "source": source}
            solo = sum(1 for e in events if e.get("type") == "CHAMPION_KILL" and e["timestamp"] < 900000 and e.get("killerId") == pid and e.get("victimId") == eid and not e.get("assistingParticipantIds", []))
            against = sum(1 for e in events if e.get("type") == "CHAMPION_KILL" and e["timestamp"] < 900000 and e.get("killerId") == eid and e.get("victimId") == pid and not e.get("assistingParticipantIds", []))
            records.append({"lane": lane, "own": known[own["championId"]], "enemy": known[enemy["championId"]], "win": own["win"], "levels": levels, "solo": solo, "soloAgainst": against, "builds": item_build(pid, events, items, core_ids, config["starting_items_before_ms"])})
    return records
