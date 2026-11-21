---
name: marketing-planner
description: >-
  4THEPT 인스타그램(릴스·카드뉴스) 및 유튜브 쇼츠 주간/월간 홍보 기획,
  투트랙(병원 PT + 트레이너·PT 센터) 주제·훅 A/B 설계,
  콘텐츠 캘린더 갱신을 수행하는 스킬.
  사용자가 "홍보 기획해줘", "이번 주 콘텐츠 짜줘", "인스타/유튜브 주제 추천해줘",
  "마케팅 전략 잡아줘" 등을 요청할 때 활성화한다.
---

# 4THEPT 홍보 기획 스킬 (`marketing-planner`)

사용자가 주간/월간 SNS 홍보 기획, 주제 추천, 훅(Hook) 설계, 캠페인 전략 수립을 요청하면 아래 4단계 절차를 수행합니다.

## Steps

1. **현행 마케팅 컨텍스트 및 실시간 성과 데이터 로드**
   - 먼저 최신 SNS 성과 데이터와 중복 발행 경고를 수집하거나 오늘 스냅샷을 확인합니다.
     ```powershell
     py promo_4thept/scripts/sns_analytics.py --save-report
     ```
   - 이어서 아래 기준 문서를 읽어 최근 발행 내역, 3대 고정 시리즈 규격, 투트랙 원칙을 확인합니다.
     - [promo_4thept/AGENTS.md](file:///c:/개발/자동화에이전트/promo_4thept/AGENTS.md)
     - [promo_4thept/campaigns/quality_rubric.md](file:///c:/개발/자동화에이전트/promo_4thept/campaigns/quality_rubric.md)
     - [promo_4thept/campaigns/ad_benchmark_db.md](file:///c:/개발/자동화에이전트/promo_4thept/campaigns/ad_benchmark_db.md)
     - [결과물/4THEPT마케팅/analytics_snapshot.md](file:///c:/개발/자동화에이전트/결과물/4THEPT마케팅/analytics_snapshot.md)
     - [promo_4thept/campaigns/brand_messaging_kit.md](file:///c:/개발/자동화에이전트/promo_4thept/campaigns/brand_messaging_kit.md)
     - [promo_4thept/campaigns/content_calendar.md](file:///c:/개발/자동화에이전트/promo_4thept/campaigns/content_calendar.md)
     - [promo_4thept/campaigns/publish_log.md](file:///c:/개발/자동화에이전트/promo_4thept/campaigns/publish_log.md)

2. **트렌드 · 키워드 리서치 (선택)**
   - 최신 임상·피트니스 숏폼 트렌드나 해시태그 키워드 조사가 필요한 요청이면 `search_web`으로 1~2회 짧게 조회해 기획 근거에 반영합니다.

3. **투트랙 + 80/20 고정 시리즈 주간/캠페인 기획안 도출**
   - 반드시 **Track A(병원 물리치료사 PT 60~70%)**와 **Track B(트레이너·운동·PT 센터 30~40%)**의 비중과 용어를 철저히 구분하고, `analytics_snapshot.md`의 상위 훅/경고(예: 중복 업로드 주의)를 반영해 기획합니다.
   - 각 슬롯마다 아래 요소를 명시합니다.
     - 고정 시리즈: `Series A (저장형 치트시트)` / `Series B (현장 공감·썰)` / `Series C (실구동 5초 쇼크)`
     - 플랫폼·포맷: `Instagram 캐러셀` / `Instagram 릴스 + YouTube Shorts`
     - 타겟 직군·트랙: `Track A (hospital)` vs `Track B (center)`
     - **80/20 구성**: 가치·공감 80% 내용(제품명 미노출) + 4THEPT 20% 전환 지점
     - 0~2초 비광고성 훅 A/B 안 (체류/저장/프로필 클릭을 노리는 2가지 변형)
     - 표준 UTM 캠페인 슬러그 (`utm_campaign=<series>_<track>_<slug>`)
     - 에셋 구분: `기존 완성 프리셋(즉시 DRY-RUN 가능)` vs `신규 제작 필요`

4. **콘텐츠 캘린더 반영 및 다음 액션 제안**
   - 사용자 요청이 캘린더 등록까지 포함하거나 제안안 승인 후에는 [promo_4thept/campaigns/content_calendar.md](file:///c:/개발/자동화에이전트/promo_4thept/campaigns/content_calendar.md)를 갱신하고 `py promo_4thept/scripts/check_marketing_copy.py`로 금지 표현이 없는지 확인합니다.
   - 기획안 보고 끝에는 바로 실행할 수 있는 다음 단계(예: `marketing-producer`로 대본/카드뉴스 생성 또는 `sns-publish`로 기존 프리셋 DRY-RUN)를 구체적으로 제안합니다.
