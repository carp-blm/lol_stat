# 상성노트 · Python 프로젝트

한국 서버의 현재 패치 랭크 솔로/듀오 경기를 Riot 공식 API로 수집하고, SQLite에 필요한 통계 자료만 보관한 뒤 GitHub Pages용 정적 페이지를 생성합니다. Python 3.11 이상에서 외부 Python 패키지 없이 실행됩니다.

**저장소:** https://github.com/carp-blm/lol_stat

**공개 주소:** https://carp-blm.github.io/lol_stat/

현재는 Riot API 발급 대기 단계입니다. 선택지 추출·검정·강조·화면의 구축 준비를 마쳤으며, 실제 경기 통계는 수집 대기로 표시합니다. `catalog`와 `build`는 API 키 없이 실행할 수 있습니다. 테스트용 가상 통계를 공개 페이지에 넣지 않습니다.

## 무엇이 달라졌나요?

- 모두 우위 (추천) / 주도권 우위 / 솔킬 우위를 수집 통계로 자동 분류합니다.
- 초반 불리 삼각형은 챔피언 사진 왼쪽 위에 걸쳐 표시됩니다.
- 챔피언을 누르면 같은 라인·같은 상대의 선2/3/6레벨, 15분 전 솔로킬, 승률, 표본 수를 볼 수 있습니다.
- 시작 아이템 / 1~5코어 누적 빌드 / 룬 / 스펠 / 스킬트리별 선택 수 상위 10개를 표시합니다. 같은 챔피언·라인의 전체 수집 표본과 비교하고, **해당 상대에서 상대적 이점이 유의하게 커지는 선택지**를 FDR 보정 후 강조합니다.
- 배포자 관리 화면에서 기존 클릭·드래그 상성 편집, 라인별 티어 편집, 초반 불리 체크, 기존 JSON 가져오기를 사용할 수 있습니다.
- 배포자 수정은 `data/overrides.json`에 저장되며 자동 통계 갱신 후에도 유지됩니다.
- 방문자는 배포된 데이터를 읽습니다. 열린 페이지도 60초마다 새 배포를 확인하므로 이전의 개인별 localStorage가 배포자 변경을 가리지 않습니다.
- 패치, Data Dragon 버전, 통계 갱신 시각, 배포 시각을 구분해 기록합니다. 화면 시각은 한국 시간입니다.

## 먼저 알아야 하는 데이터 범위

Riot Match-V5는 플레이어별 경기 ID 목록과 개별 경기·타임라인을 제공하며, 한국 서버의 모든 경기를 한 번에 나열하는 전수 다운로드 API는 제공하지 않습니다. 이 프로젝트는 랭크 목록의 참가자 또는 지정한 Riot ID를 시작점으로 경기를 수집하고, **수집한 유효 경기 전체**를 분석합니다. 서버 전체 경기의 전수 통계나 무작위 표본이라고 표시하지 않습니다. lol.ps의 지표 의미를 참고했으며 그 사이트의 데이터·유료 지표를 복사하거나 크롤링하지 않습니다.

기본값은 최근 14일, 실행당 새 경기 최대 600개, 보관 최대 10,000개, API 요청 최대 1,800회, 실행 시간 최대 35분입니다. 같은 경기 ID는 중복 집계하지 않습니다. 모든 챔피언·상대 조합이 이 한도로 충분한 표본을 확보하는 것은 아닙니다. 최소 30경기 미만은 자동 추천을 보류하며 실제 표본 수를 보여줍니다.

개발 키는 24시간마다 만료됩니다. 공개 서비스는 Riot에 제품을 등록하고 **Production API 키**를 발급받아야 합니다. 개발/Personal 키로 공개 운영을 대체하지 마세요. API 키는 `.env` 또는 GitHub Actions Secrets에만 저장하며 웹페이지에 포함하지 않습니다.

## 로컬 실행

프로젝트 폴더에서 실행합니다.

```powershell
python --version
python -m counter_note build
python -m counter_note serve --publisher
```

`http://127.0.0.1:8765`에서 배포자 관리 화면을 엽니다. Python이 `py` 명령으로 설치되어 있으면 `python` 대신 `py -3`을 사용하세요. 별도 패키지 설치는 필요하지 않습니다. `start-publisher.ps1`로도 실행할 수 있습니다.

Riot 데이터를 실제로 수집하려면 `.env.example`을 `.env`로 복사하고 직접 키를 입력합니다. `.env`는 Git에서 제외됩니다. 키를 채팅이나 소스 파일에 붙여넣지 마세요.

```text
RIOT_API_KEY=본인의_키
```

관리 화면의 **Riot 데이터 갱신** 버튼을 누르거나 아래 명령을 실행합니다.

```powershell
python -m counter_note refresh --force
```

갱신 진행 상황이 화면에 표시됩니다. 인증 실패·호출 제한·불완전 타임라인을 처리하며, 수집 실패 시 기존 공개 배포를 덮어쓰지 않습니다. 갱신 중에는 다른 저장·갱신 요청을 막습니다. API 키를 변경했다면 로컬 관리 서버를 다시 시작하세요.

참가자 검색이 제한되면 `.env`에 시작점을 지정할 수 있습니다.

```text
RIOT_SEED_IDS=["게임이름#태그", "다른이름#태그"]
```

또는 `RIOT_SEED_PUUIDS`를 문자열 JSON 배열로 설정할 수 있습니다. 시드는 메모리에서만 사용합니다. 공개 웹페이지와 SQLite 사실 테이블에는 Riot ID, PUUID, API 키를 저장하지 않습니다.

## 무료 GitHub Pages 배포

현재 저장소는 빈 공개 저장소를 기준으로 준비했습니다. 프로젝트 파일 전체를 저장소 루트에 올리세요. `.github/workflows/update.yml`이 저장소 루트의 `.github` 폴더 안에 있어야 합니다.

1. 저장소 **Settings → Pages → Build and deployment → Source**를 **GitHub Actions**로 설정합니다.
2. **Settings → Secrets and variables → Actions → New repository secret**에서 `RIOT_API_KEY`를 등록합니다.
3. 필요할 때만 `RIOT_SEED_IDS` 또는 `RIOT_SEED_PUUIDS` Secret을 추가합니다.
4. 기본 브랜치를 `main`으로 사용합니다. 다른 이름이면 workflow의 `push.branches`도 바꾸세요.
5. `main`에 코드를 push합니다. Python 테스트 → 경기 수집 → 통계 생성 → Pages 배포가 실행됩니다.
6. **Actions → Update and deploy → Run workflow**에서 `refresh`를 체크하면 배포자가 즉시 갱신할 수 있습니다.

```powershell
git add .
git commit -m "Build Python matchup statistics and Pages deployment"
git branch -M main
git push -u origin main
```

처음 push할 때 Secret이 없으면 경기 통계가 없는 프로토타입만 배포하고 Actions에 경고를 남깁니다. 키 없는 예약/수동 갱신은 실패로 표시합니다. 키 설정 후 다시 실행하세요.

워크플로는 매일 12:37 KST에 실행 여부를 확인하고, 최근 성공한 수집 시작으로부터 약 48시간이 지나면 갱신합니다. 스케줄 지연을 고려해 최대 10분의 허용 오차를 둡니다. `매월 홀수 날짜` 방식이 아니므로 월말의 1일 간격 문제를 피합니다. GitHub 스케줄은 실행 지연·누락이 가능하고, 공개 저장소에 60일간 활동이 없으면 예약 실행이 비활성화될 수 있습니다. 필요할 때 Actions에서 다시 활성화하거나 Run workflow를 사용하세요.

표준 `ubuntu-latest` 러너, 공개 저장소, 기본 `github.io` 주소만 사용합니다. 유료 러너·외부 서버·유료 DB·유료 도메인이 필요하지 않습니다. 이 구성은 GitHub의 현재 무료 범위 안에서 운영하도록 데이터 수와 파일 크기를 제한합니다. 서비스의 무료 정책이나 사용 한도를 영구 보장하는 것은 아닙니다. Pages 산출물은 최대 50MB, artifact 보관은 1일로 제한하며 캐시는 작은 SQLite와 카탈로그만 포함합니다. 유료 사용량 증액을 활성화할 필요가 없습니다.

## 수정 사항을 사용자에게 반영하기

1. 로컬에서 `python -m counter_note serve --publisher`를 실행합니다.
2. 상성·티어를 수정하고 **수정 사항 저장**을 누릅니다. 로컬 저장과 정적 페이지 생성까지 수행합니다.
3. `data/overrides.json`의 변경을 commit/push합니다. GitHub Actions가 다시 배포합니다.
4. 방문자는 같은 주소에서 최신 데이터를 받습니다. 열린 페이지도 60초 이내 다음 확인 시 반영합니다.

로컬의 저장 버튼만 누른 상태는 인터넷 배포 완료가 아닙니다. GitHub에 push하거나 workflow를 실행해야 합니다. 브라우저에 GitHub/Riot 비밀키를 넣는 직접 배포 방식을 사용하지 않습니다.

초기 HTML 파일의 기록은 원래 페이지에서 **데이터 백업**을 저장한 후 로컬 관리 화면의 **기존 상성 불러오기 → 수정 사항 저장**으로 옮깁니다. 파일의 브라우저 저장 공간을 자동으로 읽어 옮길 수는 없습니다. 최초의 `라인전/게임/모두` 형식은 앞서 요청한 초기화 정책을 유지합니다. 직전 `모두/주도권/솔킬` 형식은 그대로 가져옵니다.

특정 상대의 자동 통계를 다시 사용하려면 `data/overrides.json`에서 해당 라인·상대의 `matchups` 및 `earlyDisadvantage` 항목을 삭제하고 다시 build합니다. 빈 분류 배열은 ‘수동으로 비워 둠’을 뜻하므로 자동 분류가 덮어쓰지 않습니다. 수정할 당시보다 새 배포가 먼저 만들어졌다면 저장 요청을 거절해 오래된 화면으로 덮어쓰는 것을 막습니다.

## 계산 기준

### 라인·경기

- Match-V5 `teamPosition`의 TOP/JUNGLE/MIDDLE/BOTTOM/UTILITY를 사용합니다. 같은 역할의 반대 팀 두 명이 명확한 경우만 매칭합니다. 실제 위치 기반 라인 스왑 판별은 하지 않습니다.
- 소환사의 협곡(mapId 11), 선택 큐, 선택 패치, 15분 이상 경기만 포함합니다. 15분 미만 경기에서 관측 기간이 짧아 생기는 편향을 피하기 위한 기준입니다.
- 현재 패치는 Data Dragon 최신 버전의 앞 두 자리로 판단합니다. Data Dragon은 라이브 패치 직후 갱신이 지연될 수 있습니다.
- 기본 시드는 IRON~DIAMOND의 티어·디비전별 목록 일부입니다. 참가자들의 경기 상대가 추가되므로 전체 티어를 균일하게 대표하는 표본은 아닙니다. 이 도구에서 말하는 ‘티어’ UI는 배포자가 정한 챔피언 순위이며 경기 참가자의 랭크 필터가 아닙니다.

### 선2/3/6레벨과 솔로킬

- 유효한 `LEVEL_UP` 이벤트의 타임스탬프를 비교합니다. 스킬 포인트를 찍는 `SKILL_LEVEL_UP`을 레벨업으로 세지 않습니다.
- 레벨업 이벤트가 없으면 `participantFrames`의 레벨 변화 구간을 사용합니다. 구간이 겹쳐 순서를 확정할 수 없으면 판단 불가로 제외합니다. 동시 시각은 동률로 표시하며 양쪽 유효 비율 분모에 포함합니다.
- 15분 전 솔로킬은 `timestamp < 900000`, 킬러가 내 챔피언, 희생자가 맞상대, 어시스트가 없는 `CHAMPION_KILL`입니다. 다른 상대 킬과 갱킹 킬은 제외합니다.
- 주도권 우위: 선6레벨 ‘내가 먼저’ 횟수 > ‘상대가 먼저’ 횟수.
- 솔킬 우위: 경기당 15분 전 맞상대 솔로킬 평균 > 상대의 같은 지표.
- 모두 우위: 두 조건 모두 충족. 초반 불리: 선2 또는 선3 중 하나라도 내 비율 < 상대 비율.
- 최소 경기 30개, 레벨 비교는 유효 관측 30개가 기본입니다. 동률은 우위로 분류하지 않습니다. 표본 수 기준은 `config.json`에서 변경합니다.

### 빌드와 FDR

- 시작 아이템: 90초 직전 실제 보유 아이템 조합. 장신구 제외, 같은 아이템 여러 개는 개수를 유지합니다. 구매·판매·소멸·구매 취소 이벤트를 반영합니다.
- 코어: Data Dragon상 협곡에서 구매 가능한 완성 아이템 중 기본 총 가격 1,500골드 이상. 신발·소모품·장신구·구매 가능한 상위 아이템이 남은 하위 재료는 제외합니다. 특별한 아이템은 `core_include`/`core_exclude`로 보정할 수 있습니다.
- 코어 순서는 처음 유효하게 구매한 서로 다른 완성 아이템의 순서입니다. 나중에 팔아도 이전 빌드 선택으로 집계하며 구매 취소된 거래는 제외합니다. 2코어는 첫 두 아이템의 순서 조합, 5코어는 첫 다섯 아이템의 순서 조합입니다. 자동 변환·오른 강화 등 구매 이벤트가 없는 특수 변환은 원래 구매한 아이템 기준입니다.
- 각 단계까지 도달하고 빌드가 관측된 경기만 선택률·승률 분모에 포함합니다. 상위 10개는 선택 경기 수, 승률 순으로 정렬합니다. 후보가 10개 미만이면 있는 만큼만 표시합니다.
- 기존 `builds`/`fdr` 출력은 호환을 위해 유지합니다. 이는 같은 매치업 안의 빌드 간 Fisher 검정 결과이며, 새 화면의 “매치업 특화” 강조에는 아래의 `recommendations` 결과를 사용합니다.

## 전체 대비 매치업 특화 검정

비교 범위는 **같은 내 챔피언·같은 라인·서버·큐·패치·조회 기간**입니다. 전체 승률은 현재 상대를 포함한 요약 정보로 보여주되, 실제 검정의 기준군은 **현재 상대를 제외한 다른 상대 경기**입니다. 내 매치업 표본을 자기 자신과 중복 비교하지 않습니다. 단순히 원래 승률이 높은 선택지에 매치업 특화 표시를 붙이지 않습니다.

각 선택지·단계에서 아래 네 집단의 승리/패배 수를 계산합니다. 다른 선택지는 같은 항목과 단계의 확인 가능한 모든 대안입니다.

| 집단 | 상대 범위 | 선택 |
|---|---|---|
| A | 현재 상대 | 해당 선택지 |
| B | 현재 상대 | 나머지 선택지 |
| C | 다른 상대 | 해당 선택지 |
| D | 다른 상대 | 나머지 선택지 |

`OR_target = odds(A) / odds(B)`, `OR_other = odds(C) / odds(D)`, `R = OR_target / OR_other`로 계산합니다. 로그 오즈비 차이의 표준오차는 여덟 승패 셀의 역수 합의 제곱근입니다. `log(R) / SE`에 대한 단측 정규근사 Wald 검정으로 상대적 이점 증가를 확인하고, A 대 B 단측 Fisher 정확검정으로 해당 매치업 안에서도 유리한지 확인합니다. 두 조건을 모두 요구하는 교집합 검정의 p는 **두 p 중 큰 값**입니다. 증가 비율 R은 승률의 배수가 아닙니다.

- 기본 적격 조건은 네 집단 각각 `min_comparison_games=20`경기 이상, 각 집단의 승리와 패배 각각 `min_comparison_outcomes=5`건 이상입니다. 0셀을 임의로 보정하지 않으며, 조건을 못 채우면 p/q를 계산하거나 강조하지 않습니다.
- 같은 라인·상대·내 챔피언의 **시작·1~5코어·룬·스펠·첫 3/6/9 스킬 포인트 전체 적격 후보**가 하나의 검정군입니다. 선택 수 상위 10개를 고르기 **전**에 공동 보정합니다. 서로 다른 챔피언·매치업까지 한꺼번에 보정한 결과는 아닙니다.
- 기본 FDR 방식은 **Benjamini–Yekutieli (BY)**이며, 보정 q < 0.05, R > 1, A 승률 > B 승률인 후보만 강조합니다. `fdr_method=bh`로 변경할 수 있지만 BH의 독립성/양의 의존 조건을 고려해야 합니다.
- 선택 수·선택률, 매치업/전체/다른 상대 승률, 원 p와 보정 q, R과 95% 구간을 제공합니다. 승률 구간은 Wilson, R 구간은 로그 오즈비 정규근사 구간으로 서로 다릅니다. 구간은 개별 후보의 비보정 구간입니다.
- 이 검정은 관측 표본을 사용한 탐색 통계입니다. 실력, 플레이어 반복 참가, 기간 내 메타 변화, 상대 조합, 구매 시점·경기 길이에 따른 선택 편향을 보정한 인과 효과가 아닙니다. 다른 상대들을 합친 기준군의 구성에도 영향을 받습니다. FDR 보정이 이러한 편향이나 정규근사 오차를 없애지는 않습니다.

### 항목별 수집·제외 기준

| 항목 | 공식 데이터와 분석 단위 | 제외 또는 제한 |
|---|---|---|
| 시작 아이템 | Timeline 구매·판매·파괴·취소 이벤트, 90초 직전 보유 조합 | 장신구 제외, 확인 가능한 조합이 없는 경기 제외 |
| 아이템 빌드 | Timeline, 1~5코어까지의 누적 구매 순서 | 해당 단계 미도달 경기 제외, 위의 코어 정의 적용 |
| 룬 | Match-V5 `perks.styles`, 주 룬 4개 + 보조 룬 2개 조합 | 능력치 파편 제외, 누락·중복·잘못된 스타일 조합 제외 |
| 스펠 | Match-V5 `summoner1Id`/`summoner2Id`, D/F 순서 무관한 두 스펠 조합 | 동일·누락 ID 제외. 시작 스펠과 결과 ID의 혼동을 피하도록 봉인 풀린 주문서 및 룬 확인 불가 경기 제외 |
| 스킬트리 | Timeline `SKILL_LEVEL_UP`의 NORMAL Q/W/E/R 투자 순서, 첫 3/6/9포인트 | 정확히 같은 이벤트 중복 제거 후 총 포인트가 최종 `champLevel`과 맞아야 함. 불완전·잘못된 슬롯·같은 시각의 순서 불명·특수 이벤트 제외 |

스킬트리는 **포인트를 투자한 순서**이며 레벨별 투자 시점 또는 마스터 우선순위를 추정한 값이 아닙니다. 기본 초기 구현은 아펠리오스·엘리스·제이스·카르마·니달리·우디르의 특수 스킬 체계를 제외합니다. 레벨에 비해 스킬을 덜 찍고 종료했거나 의심되는 추가 이벤트가 있으면 스킬 항목만 제외합니다. Riot에서 보고된 중복/특수 이벤트를 추측으로 보완하지 않습니다.

항목별 유효 경기, 누락/미도달/제외 경기 수를 표시합니다. 룬·스펠·스킬이 없어도 유효한 아이템·선레벨·솔로킬 통계는 유지합니다. 이름과 아이콘은 한국어 Data Dragon의 `summoner.json`/`runesReforged.json`에서 가져오며, 오프라인으로 카탈로그가 없을 때는 ID를 대신 표시합니다. API 발급 후 기존 갱신 명령을 실행하면 추가 수동 연결 없이 이 추출·집계 경로를 사용합니다.

## 저장·유지보수

- `data/matches.sqlite3`: 중복 제거용 경기 ID, 패치/큐/날짜, 방향별 집계 기초값. 원시 타임라인과 선수 식별자는 보관하지 않습니다.
- `data/catalog/`: 패치별 공식 카탈로그 캐시.
- `data/overrides.json`: 배포자의 수동 수정. Git으로 보관합니다.
- `site/`: 자동 생성된 공개 파일. DB·키는 포함되지 않습니다.
- Actions 캐시는 영구 DB가 아닙니다. 삭제/퇴거되면 최근 범위를 다시 수집하므로 표본 수가 줄 수 있습니다. 장기 보존이 필요하면 로컬 DB를 별도로 백업하세요.

```powershell
python -m counter_note backup-db backups/matches.sqlite3
python -m unittest discover -s tests -v
```

화면 동작 테스트에만 Node.js 24와 개발용 `jsdom`을 사용합니다. 서비스 실행에는 Node.js가 필요하지 않습니다. GitHub Actions는 아래 검사도 자동으로 실행합니다.

```powershell
npm ci --ignore-scripts --no-audit --no-fund
python tests/build_ui_fixture.py
npm test
```

UI 테스트의 가상 경기 데이터는 `test-results/`에만 만들며 실제 통계 DB나 공개 페이지에 섞이지 않습니다.

계산 정의(`starting_items_before_ms`, 코어 포함/제외, 최소 경기 길이)를 바꾸면 기존 기초값과 혼합하지 않도록 로컬 DB를 백업한 뒤 새 DB로 다시 수집하세요. GitHub에서는 설정/추출 코드 해시가 바뀌면 새 캐시를 사용합니다.

## 코드 구성

| 경로 | 역할 |
|---|---|
| `counter_note/riot.py` | 공식 API 요청, 429/5xx 재시도, 호출 한도 |
| `counter_note/collect.py` | 참가자 발견, 경기·타임라인 수집 |
| `counter_note/extract.py` | 라인 매칭, 선레벨, 맞상대 솔로킬, 구매 순서 |
| `counter_note/choices.py` | 룬·스펠·스킬 추출, 누락·특수 이벤트 제외 |
| `counter_note/statistics.py` | 집계, Fisher 검정, BH/BY FDR, Wilson 구간 |
| `counter_note/recommendations.py` | 전체 대비 매치업 상호작용 검정, 공동 FDR, 상위 10개 |
| `counter_note/storage.py` | SQLite 중복 제거·보관·백업 |
| `counter_note/publish.py` | 수동 수정 병합, 정적 파일 생성 |
| `counter_note/server.py` | localhost 전용 관리 화면과 갱신 API |
| `web/` | 한국어 UI, 클릭·드래그 편집, 상세 통계 |
| `.github/workflows/update.yml` | 예약/수동 갱신과 Pages 배포 |

## 참고 자료

- [Riot 공식 API 및 Data Dragon](https://developer.riotgames.com/docs/lol)
- [키 종류·만료·호출 제한](https://developer.riotgames.com/docs/portal)
- [Match-V5 API](https://developer.riotgames.com/apis#match-v5/GET_getTimeline)
- [Riot 개발자가 공개한 타임라인 예시](https://gist.github.com/RiotTuxedo/ab04ac027546f711ce820faed394295b)
- [lol.ps의 맞상대 지표 설명 예시](https://lol.ps/en/stats/counter/sample)
- [Fisher 정확검정 설명](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.fisher_exact.html)
- [BH/BY FDR 설명](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.false_discovery_control.html)
- [로그 오즈비 표준오차](https://www.statsmodels.org/stable/generated/statsmodels.stats.contingency_tables.Table2x2.log_oddsratio_se.html)
- [Riot 개발자 저장소의 SKILL_LEVEL_UP 중복 보고](https://github.com/RiotGames/developer-relations/issues/1100)
- [GitHub Pages 배포](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages)
- [GitHub Actions 무료 범위](https://docs.github.com/en/actions/concepts/billing-and-usage)
- [GitHub 예약 실행의 지연·60일 제한](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows)

상성노트 is not endorsed by Riot Games and does not reflect the views or opinions of Riot Games or anyone officially involved in producing or managing Riot Games properties. Riot Games and all associated properties are trademarks or registered trademarks of Riot Games, Inc.
