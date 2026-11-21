---
name: weekly-curation
description: >-
  THEPT 주간 6대 카테고리 뉴스 큐레이션 파이프라인(fetch -> candidates_titles.md [x] -> build -> build --render -> sync)을
  AGENTS.md 가드레일에 맞춰 안전하게 실행하는 스킬.
  사용자가 "이번주 스크랩", "컨텐츠 만들어줘", "빌드해줘", "렌더링해줘", "동기화해줘" 등을 요청할 때 활성화한다.
---

# THEPT 주간 큐레이션 파이프라인 스킬 (`weekly-curation`)

## 핵심 가드레일
- **Human-in-the-Loop**: AI는 절대 `candidates_titles.md`의 `[ ]` 체크박스를 임의로 체크하지 않습니다.
- **렌더링 가드**: 사용자가 명시적으로 `"렌더링해줘"`, `"영상 만들어줘"`를 지시하기 전에는 `--render`를 붙이지 않습니다.
- **부분 실행**: 특정 날짜 지정 시 반드시 `--day <MMDD>`를 사용합니다.
- **발행 승인 게이트**: 주간 파이프라인 기본 종착역은 `python curate.py sync`이며, 사용자가 특정 날짜 즉시 업로드를 명시 요청할 때만 `force_ask` 승인을 받아 `python curate.py upload`를 실행합니다.

## Steps
1. **1단계 스크랩 (`fetch`)**: `python curate.py fetch` 실행 후 `결과물/THEPT뉴스/{주차}/candidates_titles.md`와 `candidates_fulltext.md` 경로를 안내하고 대기합니다.
2. **2단계 직통 빌드 (`build`)**: 사용자가 `[x]` 선택을 마친 뒤 요청하면 `python curate.py build` 실행(대본/패키지 생성 + `check_package_compliance` 자동 검수).
3. **3단계 렌더링 (`build --render`)**: 명시적 렌더링 요청 시 `python curate.py build --render` 실행(4THEPT 최신 Gemini/Edge TTS + 스튜디오 오디오 마스터링) 후 `cardnews/` 및 `weekly_summary.md` 확인.
4. **4단계 동기화 (`sync`)**: 사용자가 동의하면 `python curate.py sync`로 `결과물/THEPT뉴스`와 `결과물/4THEPT마케팅`을 GitHub 원격 저장소에 푸시합니다.
