import re
from .config import read_json, write_json
from .riot import public_json, RiotError


def patch_of(version):
    found = re.match(r"^(\d+)\.(\d+)(?:\.|$)", str(version))
    return ".".join(found.groups()) if found else None


def refresh_catalog(root, config):
    versions = public_json("https://ddragon.leagueoflegends.com/api/versions.json")
    versions = [v for v in versions if re.fullmatch(r"\d+\.\d+\.\d+", v)]
    wanted = config["patch"]
    version = next((v for v in versions if wanted == "current" or patch_of(v) == wanted), None)
    if not version:
        raise RiotError("설정한 패치의 Data Dragon 버전이 없습니다.")
    for kind in ("champion", "item"):
        path = root / "data" / "catalog" / f"{kind}-{version}.json"
        if not path.exists():
            payload = public_json(f"https://ddragon.leagueoflegends.com/cdn/{version}/data/ko_KR/{kind}.json")
            if not isinstance(payload.get("data"), dict) or payload.get("version") != version:
                raise RiotError("Data Dragon 응답 형식 또는 버전이 올바르지 않습니다.")
            write_json(path, payload)
    write_json(root / "data" / "catalog" / "current.json", {"version": version})
    return version


def cached_version(root, config):
    directory = root / "data" / "catalog"
    current = directory / "current.json"
    if current.exists():
        version = read_json(current)["version"]
        if (directory / f"champion-{version}.json").is_file() and (config["patch"] == "current" or patch_of(version) == config["patch"]):
            return version
    versions = [p.stem.removeprefix("champion-") for p in directory.glob("champion-*.json")]
    versions = [v for v in versions if re.fullmatch(r"\d+\.\d+\.\d+", v) and (config["patch"] == "current" or patch_of(v) == config["patch"])]
    if not versions:
        raise RiotError("챔피언 데이터가 없습니다. python -m counter_note catalog를 실행하세요.")
    return max(versions, key=lambda v: tuple(map(int, v.split("."))))


def load_catalog(root, version):
    directory = root / "data" / "catalog"
    champions = read_json(directory / f"champion-{version}.json")["data"]
    item_file = directory / f"item-{version}.json"
    items = read_json(item_file)["data"] if item_file.exists() else {}
    return champions, items


def core_item_ids(items, config):
    include = set(map(str, config["core_include"]))
    exclude = set(map(str, config["core_exclude"]))
    def available(item):
        return item.get("maps", {}).get("11", False) and item.get("gold", {}).get("purchasable", False) and item.get("inStore", True)
    for item_id, item in items.items():
        if not available(item) or set(item.get("tags", [])) & {"Boots", "Consumable", "Trinket"}:
            continue
        upgrades = [items[x] for x in item.get("into", []) if x in items]
        if item.get("gold", {}).get("total", 0) >= config["core_min_gold"] and not any(available(x) for x in upgrades):
            include.add(item_id)
    return include - exclude
