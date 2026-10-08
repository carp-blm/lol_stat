import json
import secrets
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit
from .collect import refresh
from .publish import build_site, save_edits, safe_json


def create_server(root, port=8765, publisher=False):
    if not (root / "site" / "index.html").exists():
        build_site(root)
    token = secrets.token_urlsafe(32)
    lock = threading.Lock()
    status = {"state": "idle", "message": "갱신 대기"}

    def run_refresh():
        try:
            refresh(root, force=True, progress=lambda text: status.update(message=text))
            build_site(root)
            status.update(state="done", message="Riot 통계를 갱신하고 배포 파일을 만들었습니다.")
        except Exception as error:
            status.update(state="error", message=str(error))
        finally:
            lock.release()

    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(root / "site"), **kwargs)

        def log_message(self, *_):
            pass

        def trusted(self):
            allowed = {f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}"}
            host = self.headers.get("Host", "")
            origin = self.headers.get("Origin")
            return host in allowed and (not origin or origin in {"http://" + h for h in allowed})

        def end_headers(self):
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            super().end_headers()

        def json_response(self, value, code=200):
            payload = json.dumps(value, ensure_ascii=False, allow_nan=False).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def do_GET(self):
            if not self.trusted():
                self.json_response({"error": "로컬 주소에서만 접근할 수 있습니다."}, 403)
                return
            path = urlsplit(self.path).path
            if path == "/api/status" and publisher:
                self.json_response(status.copy())
                return
            if path.startswith("/api/"):
                self.json_response({"error": "없는 API입니다."}, 404)
                return
            if publisher and path in ("/", "/index.html"):
                html = (root / "site" / "index.html").read_text(encoding="utf-8")
                html = html.replace('<script type="application/json" id="runtime-data">{"publisher":false}</script>', '<script type="application/json" id="runtime-data">' + safe_json({"publisher": True, "token": token}) + '</script>')
                content = html.encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(content)))
                self.end_headers()
                self.wfile.write(content)
                return
            super().do_GET()

        def do_POST(self):
            if not publisher or not self.trusted() or not secrets.compare_digest(self.headers.get("X-Counter-Token", ""), token):
                self.json_response({"error": "배포자 로컬 화면에서만 수정할 수 있습니다."}, 403)
                return
            path = urlsplit(self.path).path
            if path not in ("/api/refresh", "/api/edits"):
                self.json_response({"error": "없는 API입니다."}, 404)
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= 5 * 1024 * 1024:
                    raise ValueError("요청 크기가 올바르지 않습니다.")
                data = json.loads(self.rfile.read(length))
                if not isinstance(data, dict):
                    raise ValueError("JSON 객체가 필요합니다.")
            except (ValueError, UnicodeError):
                self.json_response({"error": "올바른 JSON 요청이 필요합니다."}, 400)
                return
            if not lock.acquire(blocking=False):
                self.json_response({"error": "현재 갱신 작업이 실행 중입니다."}, 409)
                return
            if path == "/api/refresh":
                status.update(state="running", message="Riot 데이터 갱신 시작")
                threading.Thread(target=run_refresh, daemon=True).start()
                self.json_response(status.copy(), 202)
                return
            try:
                result = save_edits(root, data.get("board"), data.get("revision"))
                self.json_response(result)
            except (ValueError, KeyError, TypeError) as error:
                self.json_response({"error": str(error)}, 409)
            except Exception:
                self.json_response({"error": "배포 파일 생성에 실패했습니다. 파일 권한과 설정을 확인하세요."}, 500)
            finally:
                lock.release()

    return ThreadingHTTPServer(("127.0.0.1", port), Handler)


def serve(root, port=8765, publisher=False):
    server = create_server(root, port, publisher)
    print(f"{'배포자 관리' if publisher else '방문자 미리보기'}: http://127.0.0.1:{server.server_port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
