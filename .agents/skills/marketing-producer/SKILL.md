---
name: marketing-producer
description: >-
  4THEPT 인스타그램 카드뉴스·릴스 및 유튜브 쇼츠 대본, 캡션, 첫 댓글, 해시태그 작성과
  실사 캡처·PNG·MP4 제작 및 컴플라이언스 검수를 수행하는 스킬.
  사용자가 "카드뉴스 만들어줘", "쇼츠 대본 써줘", "릴스 기획/제작해줘",
  "신규 기능 홍보물 만들어줘" 등을 요청할 때 활성화한다.
---

# 4THEPT 홍보 제작 스킬 (`marketing-producer`)

사용자가 카드뉴스 카피, 릴스/쇼츠 대본, 캡션, 실사 스크린샷 또는 영상 에셋 제작을 요청하면 아래 5단계 절차를 수행합니다.

## Steps

1. **트랙·시리즈 확정 및 브랜드·품질 가이드 로드**
   - [promo_4thept/AGENTS.md](file:///c:/개발/자동화에이전트/promo_4thept/AGENTS.md), [promo_4thept/campaigns/quality_rubric.md](file:///c:/개발/자동화에이전트/promo_4thept/campaigns/quality_rubric.md), [promo_4thept/campaigns/ad_benchmark_db.md](file:///c:/개발/자동화에이전트/promo_4thept/campaigns/ad_benchmark_db.md), [promo_4thept/campaigns/brand_messaging_kit.md](file:///c:/개발/자동화에이전트/promo_4thept/campaigns/brand_messaging_kit.md)를 읽습니다.
   - 제작물의 타겟 트랙(`hospital` vs `center`)과 **고정 시리즈(`Series A / B / C`)**를 먼저 확정합니다. (`center` 트랙에서는 의료 표현 사용을 엄격히 금지합니다.)

2. **80/20 구조 카피·대본 패키지 초안 작성**
   - 결과물을 `결과물/4THEPT마케팅/drafts/YYYY-MM-DD_<slug>.md`로 저장합니다.
   - 필수 포함 항목:
     - **시리즈 & 80/20 구성비율 명시** (0~2초 제품 소개 금지, 가치·공감 80% 완결 후 마지막 20%에서만 4THEPT 연결)
     - **0~2초 훅(A/B 2안)** 및 썸네일/상단 고정 텍스트
     - **슬라이드별 카피**(캐러셀 5장 안팎) 또는 **타임라인 대본**(쇼츠/릴스 18~25초 고속 템포 기준, 화면 연출 + 내레이션 + 자막)
     - **본문 캡션**: 트랙별 표준 컴플라이언스 고지문(`[초안]` + 직접 검수) 및 표준 UTM 링크(`https://www.4thept.com/intro?utm_source=...&utm_medium=...&utm_campaign=...`) 포함
     - **첫 댓글(고정 댓글)** 및 **해시태그 10~15개**(퇴출 직군 zero)

3. **3인 가상 심사위원 자체 비평 & 100점 품질 게이트 (Mandatory Quality Gate)**
   - [quality_rubric.md](file:///c:/개발/자동화에이전트/promo_4thept/campaigns/quality_rubric.md)의 5개 항목(각 20점, 총 100점) 기준으로 **① 10년차 병원 물리치료사, ② PT·트레이닝 센터 관리자, ③ 숏폼 PD** 3인 시점에서 초안을 채점합니다.
   - **통과 기준**: 총점 **85점 이상** AND **모든 개별 항목 14점 이상**.
   - 기준 미달 시 감점 원인을 반영해 **내부에서 최대 2회 리라이트**한 뒤 최종 통과본으로 덮어씁니다.
   - 초안 파일 하단에 `## 품질 자체 평가표 (초안 점수 -> 최종 점수)`와 3인 한줄 코멘트 및 수정 내역을 반드시 남깁니다.

4. **자동 컴플라이언스 검사 실행 (필수)**
   - 작성 완료된 초안 파일에 대해 아래 명령을 실행해 exit code `0`을 확보합니다. 위반이 발견되면 0건이 될 때까지 즉시 수정합니다.
   ```powershell
   py promo_4thept/scripts/check_marketing_copy.py --track <hospital|center> 결과물/4THEPT마케팅/drafts/YYYY-MM-DD_<slug>.md
   ```

5. **시각·영상 에셋 렌더링 (필요 시 · 사용자 명시적 요청 필수)**
   - 사용자가 실사 캡처, 카드뉴스 PNG, 세로형 쇼츠 MP4 생성까지 명시 요청한 경우 `결과물/4THEPT마케팅/{cards,videos}`에 생성합니다.
     - 실사 캡처/GIF: `py promo_4thept/scripts/generate_real_promo_assets.py`
     - 카드뉴스 PNG 추출: `py promo_4thept/scripts/export_card_news_pngs.py` (`promo_4thept/pt_hospital_viral_kit.html` 기반)
     - 9:16 쇼츠 MP4 생성: `py promo_4thept/scripts/build_real_promo_shorts.py` / `py promo_4thept/scripts/build_cinematic_short_v2.py`
   - 직접 바로 발행 가능한 프리셋으로 편입할 경우 `promo_4thept/scripts/sns_publisher.py`의 `PRESETS`를 갱신한 뒤 `py promo_4thept/scripts/check_marketing_copy.py`를 다시 실행합니다.

6. **미리보기 요약 및 다음 단계 확인**
   - 생성된 초안/에셋 파일 경로, 핵심 훅 A/B, **품질 채점 결과(초안 -> 최종 점수)**, 컴플라이언스 검증 통과(`0건`) 결과를 간결하게 보고하고, `sns-publish` (`DRY-RUN`) 진행 여부를 사용자에게 묻습니다.
