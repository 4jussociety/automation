<!-- 이 파일은 워크스페이스 전역 규칙 및 가드레일을 정의합니다. -->
<!-- AI 어시스턴트가 프로젝트 작업을 수행할 때 반드시 준수해야 하는 행동 지침을 포함합니다. -->

# 워크스페이스 개발 및 운영 규칙

## 1. 렌더링 실행 제약 규칙 (Rendering Guardrail)

- **원칙**: 카드뉴스 이미지 렌더링(`modules/card_renderer.py`, `promo_4thept/scripts/export_card_news_pngs.py`) 및 비디오 렌더링(`modules/video_renderer.py`, `promo_4thept/scripts/build_real_promo_shorts.py`, `build_cinematic_short_v2.py`)은 **사용자가 명시적으로 렌더링을 요청한 경우에만 실행**합니다. (`scripts/hooks/pre_tool_guard.py`가 `force_ask`로 보호)
- **허용 범위**:
  - 뉴스 수집, 기사 분석, 대본 생성, 텍스트 검수, 메타데이터 생성, 단위 테스트 등은 사용자의 일반 요청 시 자동 수행 가능합니다.
- **제한 범위**:
  - 사용자가 명시적으로 "렌더링해줘", "카드뉴스 뽑아줘", "영상 만들어줘", "쇼츠 렌더링 진행해" 등으로 지시하기 전에는 렌더링 단계(이미지/영상 파일 생성)를 임의로 실행하지 않습니다.
  - 전체 파이프라인(`pipeline.py`) 실행이 필요한 경우에도 렌더링 진행 여부를 사용자에게 먼저 확인하거나, 사용자의 렌더링 요청이 있을 때만 렌더링 단계를 가동합니다.

## 2. 특정 날짜 부분 작업 처리 지침 (Granular Execution Guideline)

- **원칙**: 사용자가 "목요일 것만 대본 뽑아줘", "9월 17일 카드뉴스만 렌더링해줘", "17일 것만 업로드해줘" 등 특정 날짜를 지정하여 요청한 경우, **전체 6일을 무의미하게 재실행하지 않고 반드시 `--day <MMDD>` (또는 `--date <MMDD>`) 인자를 활용하여 해당 날짜만 핀포인트로 실행**합니다.
- **주요 실행 매핑**:
  - 특정 날짜 빌드/대본 생성: `python curate.py build --day 0917`
  - 특정 날짜 미디어 렌더링: `python curate.py build --day 0917 --render` (사용자의 명시적 렌더링 요청 시에만)
  - 특정 날짜 SNS 업로드: `python curate.py upload --day 0917` (테스트 시 `--dry-run`)
- **지원 날짜 포맷**:
  - 4자리 MMDD: `0917`, `0914` 등
  - 슬래시/하이픈/점 구분자: `9/17`, `09-17`, `9.17` 등 (시스템 내부에서 4자리 MMDD로 자동 정규화되어 폴더명 접두어와 정확히 매칭됨)

## 3. 주간 큐레이션 파이프라인 개시 및 사용자 큐레이션 보장 규칙 (Curation Initiation Rule)

- **의도 해석 원칙**: 사용자가 **"컨텐츠 만들어줘"**, **"이번주 컨텐츠 만들어줘"**, **"큐레이션 시작해"** 등으로 발화하는 것은 전체 과정을 전자동으로 끝까지 수행하라는 의미가 아니라, **주간 큐레이션 파이프라인의 1단계(`python curate.py fetch`)를 시작하자는 신호**로만 해석합니다.
- **사용자 선별(큐레이션) 권한 절대 보장 (Human-in-the-Loop)**:
  - 기사 후보 대량 수집(`fetch`), 본문 크롤링(`review`), 패키지/대본 생성(`build`) 등 기술적 보조 작업은 AI가 수행합니다.
  - **어떤 기사를 최종 선택할지 결정(`[ ]` -> `[x]` 체크)하는 행위는 반드시 사용자(인간 편집자)의 고유 권한**입니다. AI가 임의로 기사 체크박스를 대신 체크하여 다음 단계로 자동 진행해서는 안 됩니다.
- **단계별 엄격한 실행 흐름 (핵심 4단계 라이프사이클)**:
  1. **"컨텐츠 만들어줘" / "스크랩 시작해" 요청 시**:
     - `python curate.py fetch`만 실행합니다.
     - 완료 후 생성된 `결과물/THEPT뉴스/YYYY-MM-DD_curated_weekly/candidates_titles.md` 파일 경로를 안내하며, *"관심 기사에 [x] 표시를 직접 진행해 주세요"*라고 안내한 뒤 **즉시 작업을 멈추고 대기**합니다.
  2. **사용자가 `candidates_titles.md` 선별 후 "빌드해줘", "패키지 만들어줘" 등 요청 시**:
     - `python curate.py build`를 실행합니다. (`candidates_titles.md`의 `[x]` 선택을 직접 파싱하며, 미디어 렌더링 없이 대본/패키지만 생성)
     - *(참고: 사용자가 명시적으로 "리뷰해줘", "크롤링해줘"를 요청한 경우에만 선택적으로 `python curate.py review`를 실행하고 `candidates_detail.md` 검토를 안내합니다.)*
  3. **사용자가 "렌더링해줘", "영상 만들어줘" 등 명시적 요청 시**:
     - `python curate.py build --render`를 실행합니다.
  4. **렌더링 완료 후 (GitHub 동기화 또는 요청 시 당일 즉시 업로드)**:
     - 기본 권장 마무리 단계는 **GitHub 동기화(`python curate.py sync`)**입니다.
     - AI가 임의로 "전체 업로드"나 미래 요일 일괄 발행을 제안하지 않으며, 사용자가 특정 날짜 업로드를 명시 요청한 경우에만 `--dry-run` 확인 후 `curate.py upload`를 실행합니다.

## 4. SNS 발행 방식 · 공유 계정 슬롯 분리 · 승인 가드레일 (Publishing Guardrail)

- **결과물 통합 구조 (`결과물/`)**:
  - **`결과물/THEPT뉴스/`**: 주간 6일 뉴스 브리핑(후보·대본·4:5 카드뉴스·9:16 쇼츠·리포트)
  - **`결과물/4THEPT마케팅/`**: 4THEPT 카드뉴스(`cards/`), 쇼츠/릴스(`videos/`), 기획 초안(`drafts/`), 벤치마크 캡처(`benchmark_captures/`), 성과 스냅샷(`analytics_snapshot.md`)
- **이중 발행 경로 지원 (GitHub Actions 자동 + 로컬 즉시 업로드)**:
  - **정기 무인 발행**: 매일 아침 GitHub Actions(`daily_sns_publish.yml`)가 당일 요일 뉴스 콘텐츠 1건만 자동 공개(`upload --today-only`).
  - **로컬 즉시 업로드**: 사용자가 요청한 경우 로컬에서도 `python curate.py upload --day <MMDD>` 또는 `--today-only`로 즉시 발행할 수 있습니다. (단, `.agents/hooks.json` 및 `scripts/hooks/pre_tool_guard.py`가 `force_ask`로 사용자 최종 승인을 강제합니다.)
- **공유 계정 슬롯 분리 원칙**:
  - **YouTube (`THEPT`, `UCbwC2jK9J-179R2Un3T0xPA`)**: 주간 뉴스 ➔ `PLTEYR_IZibwI`(`뉴스`) / `4THEPT` 제품 홍보 ➔ `PLMJFgpIEDRBA`(`4THEPT`). (`python curate.py test-yt`로 채널 일치 상시 점검)
  - **Instagram (`@teamthept`)**: 주간 뉴스 ➔ 오전 정기 슬롯(월~토 07:00~12:00 KST) / `4THEPT` 제품 홍보 ➔ 저녁·비정기 슬롯. `upload` 시 당일 동일 브리핑 중복 방지 가드가 자동 작동합니다.
- **금지 행위 (Strict Guardrails)**:
  - AI가 사용자에게 "주간 6일 일괄 실시간 업로드" 등을 임의로 제안해 피드를 도배해서는 안 됩니다.

## 5. 플래닝 모드 필수 적용 규칙 (Mandatory Planning Mode Guardrail)

- **원칙**: 기능 추가, 로직 수정, 버그 패치 등 모든 개발 및 코드 변경 작업 시, AI는 소스 코드를 임의로 바로 수정하지 않고 **반드시 플래닝 모드(`implementation_plan.md`)를 먼저 가동**합니다.
- **엄격한 실행 절차**:
  1. **계획서 작성 (1단계)**: 변경 대상 파일, 수정 상세 내용(Diff/로직 설계), 검증 방안을 담은 `implementation_plan.md` 아티팩트를 작성하고, 사용자 승인(`request_feedback=True`)을 요청합니다.
  2. **작업 즉시 중단 및 대기**: 계획서 작성 후 즉시 응답을 종료하고 멈춥니다. 사용자가 UI의 **[Proceed]** 버튼을 누르거나 채팅으로 **"진행해"**, **"적용해"**, **"개발해"** 등의 명시적 승인을 내릴 때까지 코드를 1줄도 건드리지 않습니다.
  3. **승인 후 실행 (2단계)**: 사용자의 명시적 승인이 확인된 후에만 비로소 계획서에 정의된 파일 수정 및 명령어 실행을 진행합니다.

## 6. 인증 단일 보관 및 형제 폴더(`4THEPT`) 참조 원칙

- **인증·설정 단일 관리**: `c:\개발\자동화에이전트` 루트의 `.env`, `client_secret.json`, `token.pickle`을 주간 뉴스(`curate.py`)와 `4THEPT` 제품 홍보(`promo_4thept/`) 양 트랙의 단일 인증 소스로 사용합니다.
- **형제 폴더(`c:\개발\4THEPT`) 참조**: `4THEPT` 서비스 개발은 `c:\개발\4THEPT`에서 전담하고, `자동화에이전트`에서는 스펙 문서(`c:\개발\4THEPT\docs\*.md`) 읽기 및 배포 사이트(`https://www.4thept.com`) 실사 녹화·캡처만 참조합니다.

---

## 7. `4THEPT` 제품 홍보 트랙(`promo_4thept/`) × `결과물/4THEPT마케팅/` 운영 규칙

- **공통 GitHub 동기화 & GitHub Raw URL 서빙**: `THEPT뉴스`(`결과물/THEPT뉴스/`)와 `4THEPT마케팅` 완성 산출물(`결과물/4THEPT마케팅/`) 모두 `python curate.py sync`를 통해 GitHub 원격 저장소(`4jussociety/automation`)에 함께 커밋·푸시하고, Instagram Graph API 업로드 시에도 양쪽 모두 **GitHub Raw URL**을 기본 서빙 경로로 사용합니다. *(원천 촬영용 무거운 중간 소스 `promo_4thept/media_library/`, `real_assets/`, `data/tts_cache/`만 `.gitignore`로 로컬 유지)*
- **유일한 발행 게이트**: `curate.py upload` 및 `promo_4thept/scripts/sns_publisher.py --publish` 모두 `--dry-run` 검증 및 사용자 명시적 최종 승인(`force_ask`) 후 실행합니다.
- **최신 TTS · 오디오 · 컴플라이언스 통합**: `THEPT뉴스` 파이프라인은 `promo_4thept`의 최신 TTS(Gemini 3.8 Flash TTS + 해시 캐시 + Edge TTS 폴백, 양방향 무음 트리밍, ~6.5 CPS 속도 보정), 스튜디오 보이스 EQ/컴프레서, 통합 컴플라이언스(`modules/marketing_compliance.py`) 및 통합 성과 분석(`modules/sns_analytics.py`)을 공유합니다.
- **전용 스킬 (`.agents/skills/`)**: `weekly-curation`, `sns-analytics`, `channel-health`, `marketing-planner`, `marketing-producer`, `sns-publish`, `ad-researcher`.
