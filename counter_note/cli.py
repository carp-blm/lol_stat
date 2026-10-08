import argparse
import json
import sys
from pathlib import Path
from .catalog import refresh_catalog
from .collect import refresh
from .config import ROOT, load_config, load_env
from .publish import build_site
from .server import serve
from .storage import Store


def main():
    parser = argparse.ArgumentParser(description="상성노트 Python 수집·분석·배포 도구")
    parser.add_argument("--root", type=Path, default=ROOT)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("catalog", help="공식 한국어 챔피언·아이템 갱신")
    update = commands.add_parser("refresh", help="경기 수집·통계·웹페이지 갱신")
    update.add_argument("--force", action="store_true")
    commands.add_parser("build", help="보관된 데이터로 정적 사이트 생성")
    server = commands.add_parser("serve", help="로컬 미리보기 또는 배포자 관리")
    server.add_argument("--port", type=int, default=8765)
    server.add_argument("--publisher", action="store_true")
    backup = commands.add_parser("backup-db", help="SQLite 데이터 안전 백업")
    backup.add_argument("destination", type=Path)
    args = parser.parse_args()
    root = args.root.resolve()
    try:
        load_env(root)
        if args.command == "catalog":
            print(refresh_catalog(root, load_config(root)))
        elif args.command == "refresh":
            result = refresh(root, force=args.force, progress=lambda text: print(text, flush=True))
            if not result.get("skipped"):
                build_site(root)
            print(json.dumps(result, ensure_ascii=False))
        elif args.command == "build":
            payload = build_site(root)
            print(f"site/index.html 생성 · 패치 {payload['metadata']['patch']} · {payload['metadata']['games']}경기")
        elif args.command == "serve":
            serve(root, args.port, args.publisher)
        elif args.command == "backup-db":
            if args.destination.resolve() == (root / "data" / "matches.sqlite3").resolve():
                raise ValueError("원본과 다른 백업 경로를 지정하세요.")
            args.destination.parent.mkdir(parents=True, exist_ok=True)
            with Store(root / "data" / "matches.sqlite3") as store:
                store.backup(args.destination)
            print("SQLite 백업 완료")
    except Exception as error:
        print(f"오류: {error}", file=sys.stderr)
        return 1
    return 0
