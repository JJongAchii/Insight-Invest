# 오늘의 신호 종목 (마켓 스포트라이트) 설계

- 작성일: 2026-07-31
- 상태: 구현 완료 (2026-07-31)
- 선행: `2026-07-27-signal-baseline-design.md` §10 후속 과제 "오늘의 중요 종목",
  브리프 폐기 커밋 `4273184`의 지적("등록해둔 종목만 봤다")

## 1. 배경

앱의 발굴 경로가 없다. `GET /attention`은 관심 ∪ 보유만 스캔하고, 등록하지 않은
종목에서 기회를 찾으려면 사용자가 stocksearch를 직접 뒤져야 한다. 브리프 기능을
폐기할 때 이 한계가 명시적으로 기록됐다.

재료는 이미 있다.

- `flows_signals.parquet`은 유동성 유니버스(시총≥100억) **전 종목** 스냅샷이다 —
  attention이 내 종목으로 필터할 뿐이다.
- 텔레그램 `_section_signals`는 이미 전시장을 스캔한다(매집형·연속매수) —
  웹에 대응물이 없다.
- `signal_study`가 신호별 기준선 대비 실측치를 갖고 있다.

빠진 것 하나: 측정에서 **유일하게 뚜렷한 양의 신호**였던 유지형 52주 신고가가
빌더에 없다. 기준선 설계 §1.1 실측(2016~2026, 20일 지평선, 기준선 대비):

| 신호 | 중앙값 | 승률 | 상태 |
|---|---|---|---|
| near_52w_high (유지형) | **+0.54%p** (60일 +0.94%p) | **+3.0%p** | **미구현** — entry형만 있음 |
| frgn_streak10 | +0.51%p | — | 구현됨 |
| bull_divergence | −0.29%p | — | 구현됨 (우위 없음) |
| high_intensity | −0.96%p | — | 구현됨 (역방향) |
| 급등 계열 5종 | −2.4 ~ −6.4%p | — | 구현됨 (전부 마이너스) |

## 2. 목표

1. 유지형 52주 신고가를 `signal_study`에 추가한다 (`near_52w_high_hold`).
2. 전시장 스캔을 배치에서 돌려 `insight/spotlight.parquet` 하나로 떨어뜨린다.
3. 웹(홈 레인)과 텔레그램이 **같은 parquet**을 읽어 일관되게 노출한다.
4. 모든 그룹에 기준선 대비 실측치를 병기한다 — 가치판단 라벨은 붙이지 않는다.

## 3. 비목표

- **매수 추천이 아니다.** 그룹별 실측치 병기까지만. 판단은 사용자가 한다.
- **새 신호 연구 없음** — 교차분석·레짐 조건부·거래비용 반영은 후속(§14).
- **결합 점수 없음** — 신고가∩수급 교집합은 배지로만 표시한다. 측정하지 않은
  결합에 숫자를 붙이지 않는다.
- **전시장 과열(급등) 리스트 없음** — 후속. 보유·워치 종목의 급등은 이미
  attention이 실측치와 함께 커버한다.

## 4. 변경 1 — `build_signal_study()`에 `near_52w_high_hold`

조건식은 entry형과 **동일한 DataFrame을 재사용**한다.

```python
cond_52w = (P >= hi_252 * 0.98) & liquid
state_conds["near_52w_high_entry"] = cond_52w          # crossing + cooldown (기존)
daily_conds["near_52w_high_hold"]  = cond_52w          # 조건 그대로 — 유지 일수 전체
```

유지형은 "고점 근처에 머문 모든 날"의 분포이므로 crossing/cooldown 없이
daily_conds에 넣는다. 행 36 → 39. 스키마 불변, 기존 소비자 안 깨진다.

**검증 앵커**: cooldown이 없으므로 §1.1 사전 측정과 **정확히 일치해야 한다** —
20일 +0.54%p, 60일 +0.94%p, 20일 승률 +3.0%p (N≈282,143). 어긋나면 구현이 틀린 것.

`test_signal_vocab`의 어휘 목록에 새 이름을 추가한다.

## 5. 변경 2 — `build_spotlight()` (신규 빌더)

### 5.1 그룹 정의 — signal_study와 같은 조건식

| group | 조건 | 정렬 | 표시 지표 |
|---|---|---|---|
| `near_52w_high_hold` | adj_close ≥ 252일 max × 0.98 (min_periods 200) | 유지일수 desc | dist_pct, hold_days, ret_20d |
| `frgn_streak10` | 외인 streak ≥ 10 | streak desc | streak, intensity_20d |
| `bull_divergence` | ret_20d < −5 & intensity_20d > 0.3 | intensity desc | intensity_20d, ret_20d |

- `bull_divergence`는 **측정된 조건(ret_20d < −5)** 을 빌더에서 직접 건다.
  현재 `send_briefing._section_signals`가 서빙 시점에 재필터하는 로직이
  빌더로 이동해 소멸한다 — 정의 지점이 하나가 된다.
- 유니버스: KRX 주식, 시총 ≥ 100억 (signal_study와 동일). ETF·US 제외.
- **그룹당 상한 5. 잘린 종목 수를 로깅한다** — 조용한 절삭 금지.
- 교집합은 `also_in`으로 표시하고 어느 그룹에서도 제거하지 않는다.
- 개인 데이터(보유·관심)는 조인하지 않는다 — 마킹은 서빙·발송 시점의 일이다.
  시장 스냅샷 parquet에 개인 상태를 굽지 않는다.

### 5.2 입력과 메모리

- 수급·가격 필드: `build_flows_signals` 결과(모듈 `_cache` 재사용)와
  `_latest_price_snapshot()`.
- 52주 신고가 상태: 최근 520거래일 adj_close 패널 자체 로드
  (~520일 × 2,800종목 ≈ 12MB — signal_study의 전 기간 패널과 무관하게 가볍다).
  hold_days는 이 창 안에서 계산되므로 최대 ~268일에서 포화된다 — 표시는 "268+".

### 5.3 스키마 — `insight/spotlight.parquet`

```
as_of, signal_type, rank, ticker, name, market, close, chg_pct, mktcap,
streak, intensity_20d, ret_20d, hold_days, dist_pct, also_in(json)
```

**실측치(기준선 대비 %p)는 넣지 않는다.** 그 뺄셈은 `signal_stats`가 유일한
지점이고, 서빙·발송 시 `signal_study`와 조인해 얻는다. 통계를 두 곳에 복제하면
빌더 순서에 따라 어긋난 값이 박제될 수 있다.

## 6. 변경 3 — API `GET /insight/spotlight`

insight 라우터에 추가. Lambda는 읽기만 한다.

```
spotlight.parquet + signal_study 로드
→ meta_df()로 ticker → meta_id/link 조인
→ 워치리스트·보유 여부 마킹 (mine: "holding" | "watchlist" | null)
→ {as_of, groups: [{signal_type, title, evidence, items: [...]}]}
```

- `evidence`는 `signal_stats.evidence_phrase(signal_type, 20, df=study)` 그대로.
- 그룹 순서는 20일 기준선 대비 중앙값 내림차순 — 우위 있는 신호가 먼저 보인다.
- parquet 부재 시 `{as_of: today, groups: []}` — **500을 내지 않는다**
  (attention과 같은 계약).

## 7. 변경 4 — 홈 `SpotlightLane`

`AttentionLane`("오늘 주목" — 내 종목) 바로 아래 "오늘의 신호 종목"(전시장) 레인.

- 그룹 헤더: 신호 한글명 + 실측치 한 줄 (`과거 28.2만건 · 20일 뒤 기준선 대비 +0.5%p …`).
- 카드: 종목명·티커·등락률 + 그룹별 지표(유지일수/연속일수/강도), 배지
  (`보유`/`관심`/교집합), 클릭 시 `/stock/{meta_id}`.
- 데이터 없거나 에러면 레인 자체를 렌더하지 않는다 (AttentionLane 관례).
- 스타일은 AttentionLane 카드 프리미티브 재사용 — 새 디자인 언어를 만들지 않는다.

## 8. 변경 5 — 텔레그램 `_section_signals` 대체

`spotlight.parquet`을 읽어 그룹별 top 3 + 실측치 줄(`└`)로 재구성한다.
기존 두 그룹(매집형·연속매수)에 신고가 유지 그룹이 추가되는 셈이고, 웹과
텔레그램이 같은 종목을 보여주게 된다.

트레이드오프: 현재 섹션은 `flows_signals`만 있으면 동작하는데, 대체 후에는
spotlight 빌더 실패 시 신호 섹션이 통째로 빠진다. 이중 폴백은 만들지 않는다 —
섹션별 `_try()` 격리 관례상 한 섹션 결손은 발송을 막지 않고, 빌더 실패는
파이프라인 로그로 드러난다.

## 9. 에러 처리

| 계층 | 처리 |
|---|---|
| 빌더 | try/except → None, 파이프라인 비중단 (기존 관례) |
| API | parquet 부재 → 빈 그룹, 500 금지 |
| 프론트 | 에러·빈 데이터 → 레인 미렌더 |
| 텔레그램 | parquet 부재 → 섹션 생략, 발송은 정상 |

## 10. 테스트

| 대상 | 방식 |
|---|---|
| `near_52w_high_hold` 통계 | 회귀 앵커 — §1.1 측정치와 3개 지평선 정확 일치 (빌더 실행 후 대조) |
| spotlight 선정 로직 | 픽스처 패널 단위 테스트 — 0.98 경계, hold_days 연속 계산, 정렬·상한·also_in, 시총 필터 |
| 어휘 드리프트 | `test_signal_vocab`에 신규 signal_type 추가 |
| API | spotlight 부재 시 빈 응답 계약 테스트 |

선정 로직은 순수 함수로 분리해 TDD로 작성한다 — 틀리면 조용히 그럴듯한
종목이 나오는 지점이다.

## 11. 비용

- 배치: +수 초 (520일 패널 로드·피벗). 40분 창 → 영향 무시 가능.
- Lambda: spotlight.parquet(<100KB) 읽기 추가 — 콜드스타트 영향 없음.
- LLM 없음. 인프라·CFN·EventBridge 변경 없음.

## 12. 변경 파일

**수정**
- `scripts/build_insights.py` — §4 조건 추가, `build_spotlight()` + BUILDERS 등록
- `scripts/send_briefing.py` — `_section_signals` 대체
- `server/app/routers/insight.py` — `GET /insight/spotlight`
- `server/tests/test_signal_vocab.py` — 어휘 추가
- `client/src/state/api.ts` — spotlight 엔드포인트·타입
- `client/src/app/home/page.tsx` — 레인 배치

**신규**
- `client/src/app/home/SpotlightLane.tsx`
- `server/tests/test_spotlight.py`

## 13. 한계

- **N 비교 금지** — hold형(cooldown 없음)과 상태형(있음)의 N이 섞여 있다.
  중앙값·승률만 비교한다 (기존 문서화 유지).
- **거래정지·관리종목 미필터** — 시총 필터만 있다. 신고가 유지 그룹에
  거래정지 직전 종목이 낄 수 있다.
- **frgn_streak10 +0.51%p는 거래비용 미반영** — 왕복 비용에 상당 부분 잠식된다.
  "발굴 후보"이지 매매 신호가 아니다 (기준선 설계 §9와 동일한 한계).
- **교집합의 결합 성과는 미측정** — 배지만 달고 숫자는 붙이지 않는다.

## 14. 후속 (이번 범위 밖)

- 전시장 과열(급등) 리스트 — spike 계열 실측치가 이미 있다
- 레짐 조건부·거래비용 반영 연구 → 그룹 구성 재검토
- insight 페이지 배치 (SignalsSection 연계)
- Decision Journal — 발굴 → 판단 기록 → 회고 루프의 다음 조각

## 15. 구현 중 변경 (2026-07-31)

### 스팩 제외 — 유니버스 정정

실물 검증에서 신고가 근접 유지 상위 5개가 전부 스팩이었다. 스팩은 공모가
(청산가치) 부근에 구조적으로 고정돼 이 신호의 의도(꾸준한 상대 강세)와
무관하고, 수익률이 0 근처라 음수 중앙값 기준선 대비 델타를 부풀리는
방향으로 통계를 오염시킨다.

정정: 선정(module/spotlight)과 통계(build_signal_study) **모두** 유니버스에서
스팩을 제외한다. 스터디 쪽은 시점별 이름 기준(스팩은 합병 시 티커를 유지한 채
사명만 바뀌므로 '한 번이라도 스팩'이 아니라 '그 시점에 스팩')이다. baseline을
포함한 전 신호가 같은 유니버스를 공유한다.

재실측 (기준선 대비, ex-SPAC): §1의 표를 대체한다.

| 지평선 | Δ중앙값 | Δ승률 |
|---|---|---|
| 5일 | +0.115%p | +1.63%p |
| 20일 | +0.447%p | +2.91%p |
| 60일 | +0.787%p | +2.18%p |

신호는 스팩 제거 후에도 세 지평선 모두 양(+)으로 유지된다. 2026-07-27 측정치
(+0.54%p 등)는 스팩 포함 모집단이라 소폭 부풀려져 있었다.
