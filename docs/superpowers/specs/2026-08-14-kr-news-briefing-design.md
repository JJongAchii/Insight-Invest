# KR 뉴스 브리핑 — 오늘의 중요 뉴스 설계

- 상태: 설계 승인 (2026-08-14 대화) — 구현 전
- 배경: 사용자가 네이버 앱에서 뉴스를 볼 때 중복 기사와 저품질 기사가 많아, 홈에서
  "정말 중요한 것만" 보고 싶다는 요구. 부수 목적: 사람들과의 얘깃거리.
- 결정(사용자 선택): ① 종합 + 경제 둘 다(섹션 구분) ② 하루 2회 배치 + 장중 라이브
  헤드라인 ③ Claude(Haiku) 큐레이션 사용 ④ 텔레그램 브리핑에 톱3 포함.

## 1. 소스 선정 근거 (리서치 결과)

| 소스 | 비용 | 중요도 신호 | 판정 |
|---|---|---|---|
| **Google News 한국판 RSS** | 무료, 키 불필요 | ✅ 클러스터 제공 | **채택** |
| 네이버 뉴스 검색 API | 무료 ~25,000회/일 | ❌ 키워드 검색만 | 미채택 |
| 언론사 개별 RSS | 무료 | ❌ 최신순 나열, 중복 직접 처리 | 미채택 |
| 빅카인즈 | 제휴 신청 | ✅ | 오버킬 |

Google News 한국판(`hl=ko&gl=KR&ceid=KR:ko`)의 결정적 장점 — 2026-08-14 실측:

- 주요뉴스 피드 ~34건, 경제 섹션 피드(`/rss/headlines/section/topic/BUSINESS`,
  302 리다이렉트 따라감) ~66건.
- **각 item의 description에 같은 사건을 다룬 타 언론사 기사 목록이 HTML `<ol>`로
  포함된다** (예: 한겨레·경향·문화일보가 쓴 같은 사건 기사 3건이 1 item으로).
  → 중복 제거가 소스 단계에서 해결되고, 클러스터 크기(보도 언론사 수)가
  객관적 중요도 지표가 된다.
- 피드 저작권 고지: 개인 비상업 피드리더 용도 — 개인 웹앱이므로 부합.
  기사 본문은 절대 수집하지 않는다(제목·링크·언론사·시각만).

## 2. 아키텍처 — 두 경로

```
[EC2 배치 09:00·19:00 KST]                    [Lambda 서빙]
scripts/build_news.py                          GET /news/briefing  ← 큐레이션 결과
  ① RSS 수집 (주요뉴스 + 경제)                  GET /news?region=kr ← 장중 라이브 헤드라인
  ② 클러스터 파싱·병합·규칙 랭킹                    (기존 라우터 확장, 5분 캐시)
  ③ Claude Haiku 큐레이션 (종합5+경제5)                │
  ④ APP_DATA/news_briefing.json 발행                  ▼
       │                                       [Next.js 홈]
       └→ send_briefing.py가 톱3 재사용         NewsBriefingCard (기존 뉴스 카드 대체)
```

- 배치는 `run_pipeline.sh`의 기존 훅(`build_insights.py` → **`build_news.py`(신규)**
  → `send_briefing.py` 순)에 한 줄 추가. 아침·저녁 사이클 모두 실행된다.
- 장중 신선함은 기존 라이브 RSS 라우터(`GET /news`)에 KR 리전을 추가해 해결.
  **장중 폴러(Lambda)와 그 IAM(파일 2개 잠금)은 건드리지 않는다.**

## 3. 수집·병합·규칙 랭킹 (`server/module/news_briefing.py` — 순수 로직)

폴러의 module/handler 분리 패턴을 따른다: 파싱·병합·랭킹·검증은 순수 함수로
`server/module/news_briefing.py`에 두고 테스트하며, `scripts/build_news.py`는
fetch·LLM 호출·S3 쓰기만 하는 얇은 스크립트다(스크립트는 `sys.path.insert`로
`server/`를 잡는 `build_insights.py` 관례를 따른다).

- **클러스터 파싱**: description의 `<li><a href="URL">제목</a>…<font>언론사</font></li>`
  반복을 정규식으로 추출 → `cluster_count`(li 수, 최소 1), `sources[]`(font 값),
  `cluster_urls[]`. `<ol>`이 없는 단독 기사 item은 cluster_count=1.
- **스토리 병합** (두 피드 간·피드 내): ⓐ guid(URL) 동일 → 동일 기사.
  ⓑ item A의 링크가 item B의 `cluster_urls`에 있으면 같은 스토리 → 병합
  (cluster_count 큰 쪽 유지, sources 합집합, 주요뉴스 피드 출신이면 general 태그 우선).
  ⓒ 제목 정규화(공백·기호 제거) 후 토큰 Jaccard ≥ 0.6 → 같은 스토리로 병합.
- **규칙 점수**: `score = cluster_count × exp(−age_hours / 24)`.
  age는 pubDate(GMT) 기준. 점수순 상위 **60건**만 LLM 후보로 넘긴다.
- 피드 태그: 주요뉴스 출신 `feed="general"`, 경제 섹션 출신 `feed="economy"`
  (병합 시 general 우선). LLM이 섹션 배정 시 참고 신호로 쓴다.

## 4. Claude 큐레이션 계약

- 모델: `claude-haiku-4-5-20251001`, `max_tokens=1500`, `temperature=0.2`.
- 입력: 후보 60건의 JSON `[{id, title, source, cluster_count, published_at, feed}]`
  — 제목·메타만 준다. 본문 없음.
- 지시: "오늘 꼭 알아야 할 뉴스를 종합(정치·사회·국제) 5건 + 경제·금융 5건 선정.
  id로만 지목하고 제목을 다시 쓰지 마라. 같은 사건 중복 금지. 각 항목에
  왜 중요한지(파급력·시장 영향·대화 소재 가치)를 한국어 80자 이내 한 줄(`why`)로."
- 출력(JSON only): `{"general": [{"id", "why"}×5], "economy": [{"id", "why"}×5]}`.
- **검증**(순수 함수): id가 후보에 실존, 섹션 간·내 중복 없음, why 비어있지 않음,
  각 섹션 최대 5건(후보가 적으면 그 이하 허용). 실패 → 검증 오류를 덧붙여 1회 재시도.
- **폴백**: 재시도도 실패(또는 API 호출 자체 실패) → 규칙 점수 상위로
  general 5 + economy 5(feed 태그 기준)를 채워 발행하고 `curated: false`, why 생략.
  **LLM 실패가 발행을 막는 일은 없다.**
- 비용: 후보 60건 ≈ 입력 5~7k tok + 출력 ~1k tok × 하루 2회 → **월 1천 원 미만**.
- API 키: `ANTHROPIC_API_KEY` — EC2의 기존 env 파일(`$BASE/quant-data/.env`,
  `BRIEFING_ENV_FILE`로 전달됨)에서 `send_briefing.py`의 `_load_env_file` 패턴으로
  로드. **키 등록은 사용자가 직접**(§10).

## 5. 발행 스키마 — `APP_DATA/news_briefing.json` (앱 평면 1파일)

```json
{
  "as_of": "2026-08-14T09:00:12+09:00",
  "edition": "morning",            // KST 시각 < 12 → morning, else evening
  "curated": true,                  // LLM 성공 여부 (폴백이면 false)
  "sections": {
    "general": [
      {"title": "...", "url": "...", "source": "한겨레",
       "published_at": "...", "cluster_count": 12,
       "sources": ["한겨레", "경향신문", "..."], "why": "..."}
    ],
    "economy": [ "...같은 형태 5건..." ]
  }
}
```

`datastore/storage.py`에 `read_json`/`write_json` 헬퍼를 추가한다(s3fs 경유,
기존 `path()`/`app_data_root()` 재사용).

## 6. 서빙 — `GET /news/briefing` (기존 `routers/news.py`에 추가)

- JSON을 읽어 그대로 반환하되 `active` 판정을 얹는다:
  `as_of`가 **72시간** 이내면 `active: true`. 초과·파일 없음·읽기 실패 →
  `{"active": false}` 200. **500 금지** — 장중 대시보드와 동일한 강등 철학.
  72h인 이유: 금 19시 발행분이 월 09시 발행 전까지(62h) 주말 내내 유지되도록.
- 라이브 헤드라인: 기존 `GET /news`에 `NewsRegion.KR = "kr"` 추가
  (module/config.py + app/schemas.py 양쪽), `REGION_CONFIG[KR] = ("ko", "KR")`.
  `DOMAIN_TO_SOURCE`에 국내 주요 언론사 도메인 추가. 기존 5분 캐시 유지.

## 7. 화면 — 홈 `NewsBriefingCard` (기존 `NewsCompactList` 대체)

- 헤더: **"오늘의 중요 뉴스"** + edition 배지(`아침판 08/14 09:00` / `저녁판 …`) +
  `[종합 | 경제]` 탭.
- 항목(섹션당 5건): 제목(클릭 → 원문 새 탭) + 언론사 칩 +
  **`📰 N개 언론사` 클러스터 배지**(N ≥ 3일 때만 표시) + 아래 muted 한 줄 `why`
  (curated=false면 why 줄 없음).
- 하단 접이식 **"최신 헤드라인"**: `GET /news?region=kr&category=topnews` 5건 —
  장중 신선함 담당. RTK Query 기존 훅 재사용, 클라 폴링 없음(카드 열 때 fetch).
- `active: false` → 큐레이션 영역 없이 라이브 헤드라인만 보이는 축소 모드.
- 언론사 칩 색: `SOURCE_COLORS`에 국내 언론사(연합뉴스·한국경제·매일경제·조선·중앙·
  동아·한겨레·경향·KBS·MBC·SBS·YTN·머니투데이·서울경제) 추가, 나머지 default.

## 8. 텔레그램 톱3

`send_briefing.py`에 `_section_news()` 추가 — 발행 직후의 `news_briefing.json`을
읽어(실행 순서가 build_news 뒤이므로 항상 최신) `general` 상위 3건의 제목만
`📰 오늘의 뉴스` 섹션으로 덧붙인다. 실패 시 섹션 생략(`_try` 패턴).

## 9. 불변식

1. 뉴스 데이터는 **앱 평면 JSON 1파일**(`news_briefing.json`)에만 존재한다.
   레이크·백테스트·전략·신호 경로와 무관하며 그쪽에서 읽지 않는다.
2. 장중 폴러 Lambda·IAM(파일 2개 잠금)·EventBridge는 **변경하지 않는다**.
3. 서빙은 어떤 실패에도 500을 내지 않는다 — `{"active": false}` 200 강등.
4. LLM 실패는 발행을 막지 않는다(규칙 폴백, `curated: false`).
5. 기사 **본문을 수집·저장하지 않는다** — 제목·링크·언론사·시각·클러스터 메타만.
6. `build_news.py` 실패는 파이프라인을 죽이지 않는다(`|| echo "[warn]"`).
7. API 키는 코드·레포에 넣지 않는다 — EC2 env 파일과 (로컬 테스트 시) 셸 env만.

## 10. 사용자 준비물 (유일한 수동 단계)

console.anthropic.com에서 API 키 발급 후 **SSM SecureString으로 등록**한다:

    aws ssm put-parameter --name /qdata/ANTHROPIC_API_KEY --type SecureString --value 'sk-ant-…'

파이프라인이 매 실행 `.env`를 SSM에서 재생성하므로(`run_pipeline.sh` `: > "$ENVF"`),
`.env`에 직접 넣은 키는 다음 실행 때 지워진다 — 반드시 SSM에 넣어야 한다
(2026-08-14 최종 리뷰에서 발견, KEY 루프에 ANTHROPIC_API_KEY 추가됨).
키가 없으면 폴백(규칙 랭킹, `curated: false`)으로 동작하므로 배포 순서 제약은 없다.

## 11. 변경 파일 목록

| 레포 | 파일 | 변경 |
|---|---|---|
| Insight-Invest | `server/module/news_briefing.py` | 신규 — 파싱·병합·랭킹·검증 순수 로직 |
| Insight-Invest | `scripts/build_news.py` | 신규 — fetch·LLM·발행 스크립트 |
| Insight-Invest | `server/datastore/storage.py` | `read_json`/`write_json` 추가 |
| Insight-Invest | `server/app/routers/news.py` | `GET /news/briefing` 추가 |
| Insight-Invest | `server/module/news/config.py`, `app/schemas.py` | `NewsRegion.KR`, 국내 언론사 도메인 |
| Insight-Invest | `server/requirements.txt` | `anthropic` 추가 |
| Insight-Invest | `scripts/send_briefing.py` | `_section_news()` 톱3 |
| Insight-Invest | `client/src/app/home/NewsBriefingCard.tsx` | 신규 (NewsCompactList 대체) |
| Insight-Invest | `client/src/app/home/page.tsx`, `state/api.ts` | 카드 교체, 타입·엔드포인트 |
| Insight-Invest | `server/tests/test_news_briefing*.py` | 신규 테스트 |
| quant-data | `scripts/server/run_pipeline.sh` | build_news 스텝 1줄 |

## 12. 테스트 전략

- **module**: 실측 RSS XML 픽스처로 클러스터 파싱(ol 있는/없는 item), 스토리 병합
  3규칙, 규칙 점수·정렬, LLM 출력 검증(정상/실존하지 않는 id/중복/빈 why), 폴백 구성.
- **router**: 정상 active, 72h 초과 stale → inactive, 파일 없음 → inactive,
  NaN·직렬화 안전(500 금지 회귀).
- **client**: `npm run lint && npx tsc --noEmit`.
- **script**: LLM 호출은 mock — 실 API 테스트는 배포 후 EC2 1회 수동 실행으로 검증.

## 13. 비범위 (이번에 하지 않는 것)

- 뉴스 전용 페이지, 무한 스크롤 — 홈 카드로 충분해질 때까지 보류.
- 종목·포트폴리오와 뉴스 매칭(내 보유 종목 관련 뉴스), 감성 분석.
- 기사 본문 요약(본문 미수집 원칙과 충돌), firecrawl 재사용.
- 장중 뉴스 폴링(라이브 헤드라인은 요청 시 fetch로 충분).
