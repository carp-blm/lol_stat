import copy
import time


def configuration():
    return {"queue": 420, "min_match_seconds": 900, "starting_items_before_ms": 90000, "core_min_gold": 1500, "core_include": [], "core_exclude": [], "min_matchup_games": 30, "min_level_observations": 30, "min_build_games": 10, "fdr_alpha": 0.05, "fdr_method": "by"}


def item(name, gold=3000, tags=None, into=None):
    return {"name": name, "gold": {"total": gold, "purchasable": True}, "maps": {"11": True}, "tags": tags or [], "into": into or [], "image": {"full": name + ".png"}}


def items():
    return {"1055": item("도란의 검", 450), "2003": item("체력 물약", 50, ["Consumable"]), "1001": item("장화", 300, ["Boots"]), "3006": item("광전사의 군화", 1100, ["Boots"]), "1036": item("롱소드", 350, [], ["3031"]), **{str(i): item("테스트 아이템 " + str(i)) for i in (3031, 3085, 3094, 3036, 3072, 3001)}}


def match_and_timeline():
    champions = {"Ashe": {"id": "Ashe", "key": "22"}, "Tristana": {"id": "Tristana", "key": "18"}}
    match = {"metadata": {"matchId": "KR_TEST_1"}, "info": {"queueId": 420, "mapId": 11, "gameDuration": 1800, "gameVersion": "16.20.1", "gameStartTimestamp": int(time.time() * 1000), "participants": [{"participantId": 1, "teamId": 100, "championId": 22, "teamPosition": "BOTTOM", "win": True, "puuid": "PRIVATE-TEST-PUUID-1"}, {"participantId": 6, "teamId": 200, "championId": 18, "teamPosition": "BOTTOM", "win": False, "puuid": "PRIVATE-TEST-PUUID-6"}]}}
    events = [{"type": "LEVEL_UP", "participantId": pid, "level": level, "timestamp": timestamp} for pid, level, timestamp in [(1, 2, 150000), (6, 2, 140000), (1, 3, 220000), (6, 3, 210000), (1, 6, 360000), (6, 6, 380000)]]
    events += [{"type": "ITEM_PURCHASED", "participantId": 1, "itemId": item_id, "timestamp": t} for item_id, t in [(1055, 1000), (2003, 2000), (3031, 500000), (3085, 700000), (3094, 900000), (3036, 1200000), (3072, 1500000)]]
    events += [{"type": "CHAMPION_KILL", "killerId": 1, "victimId": 6, "assistingParticipantIds": [], "timestamp": 600000}]
    timeline = {"metadata": {"matchId": "KR_TEST_1"}, "info": {"frameInterval": 60000, "frames": [{"timestamp": 0, "participantFrames": {"1": {"level": 1}, "6": {"level": 1}}, "events": events}, {"timestamp": 1800000, "participantFrames": {"1": {"level": 18}, "6": {"level": 18}}, "events": []}]}}
    return match, timeline, champions


def record(win=True, build="3031"):
    return {"lane": "bottom", "own": "Ashe", "enemy": "Tristana", "win": win, "levels": {"2": {"outcome": -1, "source": "event"}, "3": {"outcome": -1, "source": "event"}, "6": {"outcome": 1, "source": "event"}}, "solo": 1, "soloAgainst": 0, "builds": {"start": ["1055", "2003"], "1": [build]}}
