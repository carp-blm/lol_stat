import copy
import io
import json
import os
import shutil
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from fixtures import record
from counter_note.config import ROOT, load_config, read_json, write_json
from counter_note.publish import build_site, save_edits, validate_board, empty_board
from counter_note.riot import RiotClient, RiotError, BudgetReached
from counter_note.storage import Store
from counter_note.collect import refresh
from counter_note.catalog import cached_version
from counter_note.server import create_server


class Response(io.StringIO):
    def __init__(self, value, headers=None):
        super().__init__(json.dumps(value))
        self.headers = headers or {}


class ClientTests(unittest.TestCase):
    def client(self, opener):
        self.now = 0
        self.delays = []
        def sleep(seconds):
            self.delays.append(seconds)
            self.now += seconds
        return RiotClient("PRIVATE-TEST-KEY", {"platform": "kr", "region": "asia", "max_requests": 20, "max_runtime_seconds": 500, "request_interval_seconds": 1.25}, opener=opener, clock=lambda: self.now, sleep=sleep)

    def test_key_in_header_only_and_throttling(self):
        def opener(request, timeout):
            self.assertNotIn("PRIVATE-TEST-KEY", request.full_url)
            self.assertEqual(request.get_header("X-riot-token"), "PRIVATE-TEST-KEY")
            return Response({"ok": True})
        client = self.client(opener)
        self.assertEqual(client.get("asia", "/lol/test"), {"ok": True})
        client.get("asia", "/lol/test")
        self.assertEqual(self.delays, [1.25])

    def test_retry_after_and_budget(self):
        attempts = []
        def opener(request, timeout):
            attempts.append(1)
            if len(attempts) == 1:
                raise HTTPError(request.full_url, 429, "rate limit", {"Retry-After": "3"}, None)
            return Response([])
        client = self.client(opener)
        self.assertEqual(client.get("asia", "/lol/test"), [])
        self.assertGreaterEqual(sum(self.delays), 3)
        client.config["max_requests"] = 2
        with self.assertRaises(BudgetReached):
            client.get("asia", "/lol/test")

    def test_expired_key_and_unsafe_host(self):
        def opener(request, timeout):
            raise HTTPError(request.full_url, 403, "forbidden", {}, None)
        client = self.client(opener)
        with self.assertRaisesRegex(RiotError, "인증 실패"):
            client.get("asia", "/lol/test")
        with self.assertRaises(RiotError):
            client.get("attacker.example", "/lol/test")


class PipelineTests(unittest.TestCase):
    def setUp(self):
        (ROOT / "test-results").mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=ROOT / "test-results")
        self.root = Path(self.temp.name)
        self.assertEqual(self.root.resolve().parent, (ROOT / "test-results").resolve())
        shutil.copy(ROOT / "config.json", self.root / "config.json")
        shutil.copytree(ROOT / "web", self.root / "web")
        (self.root / "data" / "catalog").mkdir(parents=True)
        shutil.copy(ROOT / "data" / "catalog" / "champion-16.19.1.json", self.root / "data" / "catalog" / "champion-16.19.1.json")
        write_json(self.root / "data" / "overrides.json", {"schemaVersion": 1, "matchups": {}, "earlyDisadvantage": {}, "tiers": {}})
        self.config = load_config(self.root)

    def tearDown(self):
        self.temp.cleanup()

    def add_records(self):
        with Store(self.root / "data" / "matches.sqlite3") as store:
            for i in range(40):
                store.add("KR_" + str(i), "16.19", int(time.time()), "kr", 420, [record(i < 30)])
            store.set("last_refresh", {"patch": "16.19", "updatedAt": "2026-10-08T03:00:00+00:00"})

    def test_duplicate_and_queue_patch_isolation(self):
        with Store(self.root / "data" / "matches.sqlite3") as store:
            args = ("KR_A", "16.19", int(time.time()), "kr", 420, [record()])
            store.add(*args)
            store.add(*args)
            self.assertEqual(store.count("kr", 420, "16.19", 0), 1)
            self.assertEqual(store.count("kr", 440, "16.19", 0), 0)
            self.assertEqual(store.count("kr", 420, "16.20", 0), 0)
            self.assertTrue(store.seen("KR_A"))
            store.backup(self.root / "backup.sqlite3")
        with Store(self.root / "backup.sqlite3") as backup:
            self.assertEqual(backup.count("kr", 420, "16.19", 0), 1)

    def test_empty_build_has_no_fabricated_matches_or_keys(self):
        public = build_site(self.root)
        self.assertEqual(public["metadata"]["games"], 0)
        self.assertIsNone(public["metadata"]["updatedAt"])
        self.assertEqual(public["matchupIndex"], {})
        html = (self.root / "site" / "index.html").read_text(encoding="utf-8")
        self.assertNotIn("__PUBLIC_DATA__", html)
        self.assertIn('id="runtime-data">{"publisher":false}', html)
        self.assertNotIn("PRIVATE-TEST", html)

    def test_direction_and_details_export(self):
        self.add_records()
        public = build_site(self.root)
        self.assertEqual(public["board"]["matchups"]["bottom"]["Tristana"]["both"], ["Ashe"])
        details = read_json(self.root / "site" / public["detailRoot"] / "bottom-Tristana.json")
        self.assertEqual(details["Ashe"]["games"], 40)
        self.assertTrue(details["Ashe"]["early"])
        self.assertEqual(details["Ashe"]["recommendations"]["features"]["runes"]["observedGames"], 0)
        self.assertEqual(details["Ashe"]["recommendations"]["fdr"]["tests"], 0)

    def test_optional_choice_catalogs_export_korean_names_and_official_images(self):
        public = build_site(self.root)
        self.assertEqual(public["choiceCatalogs"], {"runes": {}, "spells": {}})
        write_json(self.root / "data/catalog/summoner-16.19.1.json", {"data": {"SummonerFlash": {"key": "4", "name": "점멸", "image": {"full": "SummonerFlash.png"}}}})
        write_json(self.root / "data/catalog/runesReforged-16.19.1.json", [{"id": 8000, "name": "정밀", "icon": "style.png", "slots": [{"runes": [{"id": 8005, "name": "집중 공격", "icon": "perk.png"}]}]}])
        public = build_site(self.root)
        self.assertEqual(public["choiceCatalogs"]["spells"]["4"]["name"], "점멸")
        self.assertEqual(public["choiceCatalogs"]["runes"]["8005"]["image"], "https://ddragon.leagueoflegends.com/cdn/img/perk.png")
        self.assertEqual(public["comparison"]["minGames"], 20)
        self.assertEqual(public["metadata"]["games"], 0)

    def test_comparison_configuration_requires_positive_integers(self):
        for key in ("min_comparison_games", "min_comparison_outcomes"):
            for value in (0, -1, True, 1.5):
                configuration = {**self.config, key: value}
                write_json(self.root / "config.json", configuration)
                with self.assertRaisesRegex(ValueError, key):
                    load_config(self.root)

    def test_manual_changes_survive_rebuild_and_conflict_rejected(self):
        self.add_records()
        public = build_site(self.root)
        board = copy.deepcopy(public["board"])
        board["matchups"]["bottom"]["Tristana"] = {"both": [], "pressure": ["Ashe"], "solo": []}
        board["earlyDisadvantage"]["bottom"]["Tristana"] = []
        board["tiers"] = {"bottom": {"1": ["Ashe", "Tristana"]}}
        result = save_edits(self.root, board, public["revision"])
        self.assertEqual(result["board"]["matchups"]["bottom"]["Tristana"]["pressure"], ["Ashe"])
        self.assertEqual(build_site(self.root)["board"], result["board"])
        with self.assertRaisesRegex(ValueError, "새 통계"):
            save_edits(self.root, board, public["revision"])

    def test_duplicate_groups_and_unknown_warnings_rejected(self):
        board = empty_board()
        board["matchups"] = {"bottom": {"Tristana": {"both": ["Ashe"], "pressure": ["Ashe"]}}}
        with self.assertRaises(ValueError):
            validate_board(board, {"Ashe", "Tristana"})
        board = empty_board()
        board["earlyDisadvantage"] = {"bottom": {"Tristana": ["Ashe"]}}
        with self.assertRaises(ValueError):
            validate_board(board, {"Ashe", "Tristana"})

    def test_missing_key_does_not_mark_success(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(RiotError, "RIOT_API_KEY"):
                refresh(self.root, force=True)
        with Store(self.root / "data" / "matches.sqlite3") as store:
            self.assertIsNone(store.get("last_refresh"))

    def test_schedule_skips_fresh_data(self):
        with Store(self.root / "data" / "matches.sqlite3") as store:
            store.set("last_refresh", {"scope": "kr:420:current", "startedEpoch": time.time() - 3600, "finishedEpoch": time.time()})
        with patch.dict(os.environ, {}, clear=True):
            self.assertTrue(refresh(self.root)["skipped"])

    def test_missing_current_catalog_uses_available_seed(self):
        write_json(self.root / "data" / "catalog" / "current.json", {"version": "99.99.1"})
        self.assertEqual(cached_version(self.root, self.config), "16.19.1")
        self.assertEqual(build_site(self.root)["metadata"]["patch"], "16.19")

    def test_local_publisher_http_save_and_csrf(self):
        public = build_site(self.root)
        server = create_server(self.root, port=0, publisher=True)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        url = f"http://127.0.0.1:{server.server_port}"
        try:
            with urlopen(url, timeout=3) as response:
                html = response.read().decode()
                self.assertEqual(response.headers["Cache-Control"], "no-store")
            runtime = json.loads(html.split('id="runtime-data">', 1)[1].split('</script>', 1)[0])
            self.assertTrue(runtime["publisher"])
            body = copy.deepcopy(public["board"])
            body["tiers"] = {"bottom": {"1": ["Ashe"]}}
            payload = json.dumps({"board": body, "revision": public["revision"]}).encode()
            with self.assertRaises(HTTPError) as denied:
                urlopen(Request(url + "/api/edits", data=payload), timeout=3)
            self.assertEqual(denied.exception.code, 403)
            headers = {"X-Counter-Token": runtime["token"], "Content-Type": "application/json", "Origin": "https://untrusted.example"}
            with self.assertRaises(HTTPError) as denied:
                urlopen(Request(url + "/api/edits", data=payload, headers=headers), timeout=3)
            self.assertEqual(denied.exception.code, 403)
            headers["Origin"] = url
            with urlopen(Request(url + "/api/edits", data=payload, headers=headers), timeout=3) as response:
                saved = json.load(response)
            self.assertEqual(saved["board"]["tiers"]["bottom"]["1"], ["Ashe"])
            with self.assertRaises(HTTPError) as stale:
                urlopen(Request(url + "/api/edits", data=payload, headers=headers), timeout=3)
            self.assertEqual(stale.exception.code, 409)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)

    def test_public_server_has_no_mutation_access(self):
        build_site(self.root)
        server = create_server(self.root, port=0, publisher=False)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        url = f"http://127.0.0.1:{server.server_port}"
        try:
            with urlopen(url, timeout=3) as response:
                self.assertIn('id="runtime-data">{"publisher":false}', response.read().decode())
            with self.assertRaises(HTTPError) as denied:
                urlopen(Request(url + "/api/refresh", data=b"{}"), timeout=3)
            self.assertEqual(denied.exception.code, 403)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)


if __name__ == "__main__":
    unittest.main()
