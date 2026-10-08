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
        with Store(test.root / "data" / "matches.sqlite3") as store:
            for i in range(80):
                good = i < 40
                entry = record(i < 38 if good else i < 45, "3031" if good else "3001")
                cores = [entry["builds"]["1"][0], "3085", "3094", "3036", "3072"]
                entry["builds"].update({str(n): cores[:n] for n in range(1, 6)})
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
