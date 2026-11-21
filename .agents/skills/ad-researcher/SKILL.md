---
name: ad-researcher
description: >-
  YouTube Shorts 고조회수 영상(API 조회수·참여율·한국어 자막 대본·상위 댓글·썸네일)과
  Meta 광고 라이브러리(장기집행 활성 광고 카피·크리에이티브 캡처)를 2단계 파이프라인으로 수집·해부해
  4THEPT 전용 실전 훅·레이아웃·CTA 공식을 도출하고 ad_benchmark_db.md를 갱신하는 스킬.
  사용자가 "광고 영상 분석해줘", "고조회수 쇼츠 찾아서 분석해줘", "메타 광고 라이브러리 분석",
  "바이럴 숏폼 벤치마킹", "광고 분석 에이전트 돌려줘" 등을 요청할 때 활성화한다.
---

# 4THEPT 광고 · 고조회수 쇼츠 심층 분석 스킬 (`ad-researcher`)

업종에 제한을 두지 않고 국내 최상위 바이럴 광고 및 고조회수 쇼츠의 **0~3초 훅(Hook) · 말하기 속도(글자/초) · 시각 레이아웃 · 댓글 반응 · CTA**를 실측 해부해 [`ad_benchmark_db.md`](file:///c:/개발/자동화에이전트/promo_4thept/campaigns/ad_benchmark_db.md)에 누적 기록합니다.

## 기본 제외 및 준수 원칙
- **제외 대상**: 본인 채널(`@4thept`, `THEPT`) 및 물리치료·트레이너 운동 영상(`물리치료`, `도수치료`, `스트레칭`, `거북목`, `헬스트레이너`, `필라테스`, `재활운동`).
- **인증 및 접근 경계 보호**:
  - `자동화에이전트` 루트의 단일 `token.pickle`은 메모리 내에서만 갱신해 읽기 전용으로 사용합니다.
  - Meta Ad Library가 로그인·CAPTCHA 게이트를 띄울 경우 우회/해제를 시도하지 않고 `blocked_or_gated` 상태를 그대로 기록한 뒤 YouTube 결과 중심으로 분석을 진행합니다.
- **실증 정확성**: `ad_benchmark_data.json`과 `read_file`로 직접 확인한 썸네일/광고 캡처 이미지에 근거한 수치와 원문만 기록하며, 추측성 조회수·문구 창작을 금지합니다.

## Steps

1. **2단계 벤치마크 데이터 수집 실행**
   - 기본 전 업종 수집:
     ```powershell
     py promo_4thept/scripts/ad_research_collector.py --deep-top 8
     ```
   - 특정 주제 집중 수집 시 `--queries` 지정 가능:
     ```powershell
     py promo_4thept/scripts/ad_research_collector.py --queries "무료 AI 앱" "업무 자동화 툴" --deep-top 8
     ```

2. **수집 JSON 정량 데이터 로드 (`ad_benchmark_data.json`)**
   - [`promo_4thept/campaigns/ad_benchmark_data.json`](file:///c:/개발/자동화에이전트/promo_4thept/campaigns/ad_benchmark_data.json)을 읽어 `youtube.status`, `youtube.deep_winners`(조회수, 일일 유입, 참여율, `hook_0_3s`, `cta_last_5s`, `chars_per_sec`, `top_comments`), `meta_ad_library.status` 및 `ads`(`active_days`, `ad_copy`, `cta_label`)를 확인합니다.

3. **썸네일 및 광고 크리에이티브 시각 해부 (Visual Inspection)**
   - [`결과물/4THEPT마케팅/benchmark_captures/`](file:///c:/개발/자동화에이전트/결과물/4THEPT마케팅/benchmark_captures/)에 저장된 상위 `yt_*.jpg` 및 `meta_ad_*.png` 이미지를 `read_file`로 직접 열어 아래 요소를 측정·기록합니다.
     - **타이포그래피**: 썸네일/첫 화면 문구 글자 크기 비율, 한 줄 어절 수, 외곽선/박스 대비
     - **색상 & 주목 요소**: 배경 톤 대비(다크 vs 라이트), 강조색(형광 옐로우/레드/네온 그린), 인물 표정·물건·화면 줌 초점
     - **정보 밀도**: 한 화면에 동시에 배치된 시각 요소 개수(2~3개 심플 집중 vs 복합)

4. **누적 벤치마크 DB 작성·갱신 (`ad_benchmark_db.md`)**
   - [`promo_4thept/campaigns/ad_benchmark_db.md`](file:///c:/개발/자동화에이전트/promo_4thept/campaigns/ad_benchmark_db.md)를 아래 구조로 갱신합니다.
     - **수집 요약 & 메타 상태** (일시, YouTube 수집 편수, Meta 상태/광고 수)
     - **YouTube 고조회수 쇼츠 상위권 실측 해부표** (제목, 채널, 조회수, 일평균 조회수, 참여율, 0~3초 원문 훅, 말하기 속도, 시각 특징, 댓글 심리 요약)
     - **Meta 장기집행 광고 해부** (집행 일수 순 광고주, 카피 패턴, CTA, 크리에이티브 구성 — 차단 시 미수집 사유 투명 기재)
     - **4THEPT 즉시 이식 공식 5선** (`Track A 병원 물리치료사` & `Track B 트레이너·PT 센터` 각각에 바로 쓸 수 있는 훅/컷/자막/CTA 공식 — 퇴출 직군·SaMD 과장 금지)

5. **마케팅 컴플라이언스 검증 (필수)**
   - 저장 후 반드시 아래 명령으로 `ad_benchmark_db.md`에 금지 직군명이나 SaMD 과장 표현이 섞이지 않았는지 확인합니다.
     ```powershell
     py promo_4thept/scripts/check_marketing_copy.py promo_4thept/campaigns/ad_benchmark_db.md
     ```
