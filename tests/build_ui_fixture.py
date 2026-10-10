import sys
from pathlib import Path
import time

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fixtures import record, items
from test_pipeline import PipelineTests
from counter_note.config import ROOT, write_json, read_json
from counter_note.publish import build_site
from counter_note.storage import Store


def main():
    test = PipelineTests()
    test.setUp()
    try:
        write_json(test.root / "data" / "catalog" / "item-16.19.1.json", {"data": items()})
        write_json(test.root / "data" / "catalog" / "summoner-16.19.1.json", {"data": {str(i): {"key": str(i), "name": name, "image": {"full": file}} for i, name, file in ((4, "점멸", "SummonerFlash.png"), (7, "회복", "SummonerHeal.png"), (21, "방어막", "SummonerBarrier.png"))}})
        write_json(test.root / "data" / "catalog" / "runesReforged-16.19.1.json", [{"id": 8000, "name": "정밀", "icon": "perk-images/Styles/7201_Precision.png", "slots": []}, {"id": 8200, "name": "마법", "icon": "perk-images/Styles/7202_Sorcery.png", "slots": []}])
        with Store(test.root / "data" / "matches.sqlite3") as store:
            for i in range(160):
                target, group_index = i < 80, i % 80
                good = group_index < 40
                won = group_index < 34 if target and good else group_index < 50 if target else group_index % 40 < 20
                entry = record(won, "3031" if good else "3001")
                entry["enemy"] = "Tristana" if target else "Caitlyn"
                entry["builds"]["start"] = ["1055", "2003"] if good else ["1036", "2003"]
                cores = [entry["builds"]["1"][0], "3085", "3094", "3036", "3072"]
                entry["builds"].update({str(n): cores[:n] for n in range(1, 6)})
                entry["choices"] = {"spells": ["4", "7"] if good else ["4", "21"], "runes": ["8000", "8005" if good else "8008", "9111", "9104", "8014", "8200", "8234", "8236"], **{f"skills{n}": list("QWEQQRQWQ" if good else "WQEWWRWQW")[:n] for n in (3, 6, 9)}}
                store.add(f"KR_UI_TEST_{i}", "16.19", int(time.time()), "kr", 420, [entry])
        public = build_site(test.root)
        out = ROOT / "test-results" / "ui-fixture"
        out.mkdir(parents=True, exist_ok=True)
        (out / "index.html").write_text((test.root / "site" / "index.html").read_text(encoding="utf-8"), encoding="utf-8")
        write_json(out / "site.json", public)
        write_json(out / "details.json", read_json(test.root / "site" / public["detailRoot"] / "bottom-Tristana.json"))
    finally:
        test.tearDown()


if __name__ == "__main__":
    main()
