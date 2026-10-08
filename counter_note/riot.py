import json
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, quote
from urllib.request import Request, urlopen


class RiotError(RuntimeError):
    pass


class BudgetReached(RiotError):
    pass


class RiotClient:
    def __init__(self, key, config, opener=urlopen, sleep=time.sleep, clock=time.monotonic):
        if not key:
            raise RiotError("RIOT_API_KEY가 없습니다. .env 또는 GitHub Actions Secret에 설정하세요.")
        self.key, self.config, self.opener, self.sleep, self.clock = key, config, opener, sleep, clock
        self.requests = 0
        self.deadline = clock() + config["max_runtime_seconds"]
        self.next_request = 0.0

    def get(self, route, endpoint, params=None):
        if route not in (self.config["platform"], self.config["region"]) or not endpoint.startswith(("/lol/", "/riot/")):
            raise RiotError("허용되지 않은 Riot API 경로입니다.")
        url = f"https://{route}.api.riotgames.com{endpoint}"
        if params:
            url += "?" + urlencode(params)
        for attempt in range(5):
            if self.requests >= self.config["max_requests"] or self.clock() >= self.deadline:
                raise BudgetReached("이번 실행의 수집 한도에 도달했습니다.")
            self._wait(max(0, self.next_request - self.clock()))
            request = Request(url, headers={"X-Riot-Token": self.key, "Accept": "application/json", "User-Agent": "CounterNote/3.0"})
            self.requests += 1
            self.next_request = self.clock() + self.config["request_interval_seconds"]
            try:
                with self.opener(request, timeout=30) as response:
                    self._limits(response.headers)
                    return json.load(response)
            except HTTPError as error:
                if error.code in (401, 403):
                    raise RiotError("Riot API 인증 실패: 키 만료 또는 권한을 확인하세요. 공개 운영에는 Production 키가 필요합니다.") from None
                if error.code == 404:
                    return None
                if error.code == 429:
                    try:
                        delay = max(1, float(error.headers.get("Retry-After", "120")))
                    except ValueError:
                        delay = 120
                    self._wait(delay + 0.2)
                elif error.code >= 500:
                    self._wait(min(30, 2 ** attempt))
                else:
                    raise RiotError(f"Riot API HTTP {error.code}: 요청 설정을 확인하세요.") from None
            except (URLError, TimeoutError, OSError, json.JSONDecodeError):
                self._wait(min(30, 2 ** attempt))
        raise RiotError("Riot API 재시도에 실패했습니다. 기존 공개 데이터는 유지됩니다.")

    def _wait(self, seconds):
        if self.clock() + seconds >= self.deadline:
            raise BudgetReached("이번 실행의 시간 한도에 도달했습니다.")
        if seconds > 0:
            self.sleep(seconds)

    def _limits(self, headers):
        for prefix in ("X-App", "X-Method"):
            try:
                limits = {int(period): int(count) for count, period in (item.split(":") for item in headers.get(prefix + "-Rate-Limit", "").split(",") if item)}
                counts = {int(period): int(count) for count, period in (item.split(":") for item in headers.get(prefix + "-Rate-Limit-Count", "").split(",") if item)}
                for period, count in counts.items():
                    if count >= limits.get(period, float("inf")):
                        self.next_request = max(self.next_request, self.clock() + period + 0.2)
            except (ValueError, TypeError):
                pass

    def account(self, game_name, tag):
        return self.get(self.config["region"], f"/riot/account/v1/accounts/by-riot-id/{quote(game_name, safe='')}/{quote(tag, safe='')}")


def public_json(url):
    if not url.startswith("https://ddragon.leagueoflegends.com/"):
        raise RiotError("공식 Data Dragon 주소만 허용합니다.")
    for attempt in range(3):
        try:
            with urlopen(Request(url, headers={"User-Agent": "CounterNote/3.0"}), timeout=30) as response:
                return json.load(response)
        except (HTTPError, URLError, TimeoutError, OSError, json.JSONDecodeError):
            if attempt == 2:
                raise RiotError("Data Dragon 데이터를 받지 못했습니다. 네트워크를 확인하세요.") from None
            time.sleep(2 ** attempt)
