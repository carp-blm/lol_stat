import json
import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if not (ROOT / "config.json").is_file():
    ROOT = Path.cwd()
LANES = {"TOP": "top", "JUNGLE": "jungle", "MIDDLE": "mid", "BOTTOM": "bottom", "UTILITY": "support"}
CATEGORIES = ("both", "pressure", "solo")
ROUTES = {"kr": "asia", "jp1": "asia", "na1": "americas", "br1": "americas", "la1": "americas", "la2": "americas", "euw1": "europe", "eun1": "europe", "tr1": "europe", "ru": "europe", "oc1": "sea", "ph2": "sea", "sg2": "sea", "th2": "sea", "tw2": "sea", "vn2": "sea"}


def load_env(root=ROOT):
    file = root / ".env"
    if file.exists():
        for line in file.read_text(encoding="utf-8-sig").splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                key, value = line.split("=", 1)
                if key.strip().startswith("RIOT_"):
                    os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


def load_config(root=ROOT):
    value = json.loads((root / "config.json").read_text(encoding="utf-8-sig"))
    if ROUTES.get(value.get("platform")) != value.get("region"):
        raise ValueError("platform과 region의 Riot 라우팅 조합이 잘못되었습니다.")
    for key in ("lookback_days", "retention_days", "refresh_hours", "max_new_matches", "max_stored_matches", "max_players", "max_requests", "max_runtime_seconds", "min_match_seconds", "min_matchup_games", "min_level_observations", "min_build_games", "starting_items_before_ms", "core_min_gold", "poll_seconds"):
        if type(value.get(key)) is not int or value[key] <= 0:
            raise ValueError(f"{key}: 양의 정수가 필요합니다.")
    if value["retention_days"] < value["lookback_days"]:
        raise ValueError("retention_days는 lookback_days 이상이어야 합니다.")
    if not 0 < value["fdr_alpha"] < 1 or value["fdr_method"] not in ("bh", "by"):
        raise ValueError("FDR 설정을 확인하세요.")
    if value["patch"] != "current" and not re.fullmatch(r"\d+\.\d+", value["patch"]):
        raise ValueError("patch는 current 또는 16.20 형식이어야 합니다.")
    if value["queue"] not in (420, 440):
        raise ValueError("지원 큐는 랭크 솔로/듀오 420, 랭크 자유 440입니다.")
    if not 0 <= value["request_interval_seconds"] <= 120:
        raise ValueError("request_interval_seconds 범위를 확인하세요.")
    if value["github_repository"] and not re.fullmatch(r"[\w.-]+/[\w.-]+", value["github_repository"]):
        raise ValueError("github_repository는 소유자/저장소 형식이어야 합니다.")
    return value


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False), encoding="utf-8")
    temp.replace(path)
