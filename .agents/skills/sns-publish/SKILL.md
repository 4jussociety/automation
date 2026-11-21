---
name: sns-publish
description: >-
  4THEPT 홍보 콘텐츠의 Instagram(캐러셀·릴스) 및 YouTube Shorts 안전 발행 절차
  (계정 점검, 컴플라이언스 검증, DRY-RUN 시뮬레이션, 사용자 최종 승인 후 --publish 및 발행 로그 기록)를
  수행하는 스킬. 사용자가 "인스타 올려줘", "유튜브 쇼츠 업로드해줘",
  "예약 발행해줘", "SNS 연동 확인해줘" 등을 요청할 때 활성화한다.
---

# 4THEPT SNS 안전 발행 스킬 (`sns-publish`)

실제 외부 계정(Instagram, YouTube) 업로드 실수와 컴플라이언스 사고를 막기 위해 아래 5단계 게이트를 **예외 없이 순서대로** 준수합니다.

## Steps

1. **연동 계정 상태 점검 (`--check`)**
   - `자동화에이전트` 루트의 단일 인증(`.env` · `token.pickle`) 기반 YouTube(`THEPT` 채널 / `4THEPT` 재생목록 `PLMJFgpIEDRBA`) 및 Instagram(`@teamthept`) 상태를 확인합니다.
   ```powershell
   py promo_4thept/scripts/sns_publisher.py --check
   ```
   - 토큰 만료 시 사용자에게 재인증 명령(`py promo_4thept/scripts/sns_publisher.py --auth-yt` 또는 Meta 토큰 갱신)을 안내하고 중단합니다.

2. **마케팅 컴플라이언스 정적 검사**
   - 발행 프리셋과 홍보 문구 전체가 금칙어·과장 광고 규칙에 걸리지 않는지 검증합니다.
   ```powershell
   py promo_4thept/scripts/check_marketing_copy.py
   ```

3. **시뮬레이션 실행 (`--dry-run`)**
   - 지정된 프리셋·플랫폼·예약 시각으로 `DRY-RUN`을 먼저 실행해 `결과물/4THEPT마케팅/` 에셋과 GitHub Raw URL(`4jussociety/automation`) 매핑을 검증합니다.
   ```powershell
   py promo_4thept/scripts/sns_publisher.py --preset <key> --platform <all|instagram|youtube> --dry-run
   ```
   - 예약 발행 시 `--schedule "YYYY-MM-DD HH:MM"`을 추가합니다. (Instagram 예약 발행은 현재 시각 KST 기준 최소 +20분 이후, 최대 75일 이내만 허용)
   - Instagram 대상 신규 파일이 원격 저장소에 아직 없다면 `--publish` 시 자동 GitHub 푸시되거나 `python curate.py sync`로 먼저 동기화합니다. (`--use-supabase` 옵션 시 Supabase Storage 사용)

4. **사용자 최종 승인 요청 (Mandatory Gate — `--publish` 임의 실행 절대 금지)**
   - 아래 항목을 표 또는 요약 목록으로 사용자에게 제시하고 명시적인 실행 승인을 받습니다.
     - 발행 대상: 프리셋 키 / 플랫폼(`Instagram` · `YouTube`) / 발행 일정(즉시 또는 KST 예약 시각)
     - 미디어 자산: 파일명 및 공개 URL `200 OK` 검증 결과
     - 제목·본문 캡션·첫 댓글 미리보기 및 컴플라이언스 통과 확인
   - 사용자가 명확히 승인("응 올려줘", "승인", "발행 진행해" 등)하기 전에는 절대 `--publish`를 실행하지 않습니다. (`scripts/hooks/pre_tool_guard.py`도 `sns_publisher.py --publish` 명령을 `force_ask`로 차단합니다.)

5. **실제 발행(`--publish`) 및 발행 이력 기록**
   - 승인 후 `--publish` 명령을 실행하고, 반환된 `video_url` / `video_id` / `post_id` / `reels_id`를 확인합니다.
   - 발행 결과를 즉시 [promo_4thept/campaigns/publish_log.md](file:///c:/개발/자동화에이전트/promo_4thept/campaigns/publish_log.md) 및 [promo_4thept/campaigns/content_calendar.md](file:///c:/개발/자동화에이전트/promo_4thept/campaigns/content_calendar.md)에 기록합니다.
