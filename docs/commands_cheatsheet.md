# THEPT 자동화 에이전트 실행 명령어 모음집 (Cheat Sheet)

이 문서는 THEPT 주 6일 콘텐츠(카드뉴스 및 쇼츠) 큐레이션, 렌더링, SNS 자동 예약 업로드의 전체 실행 명령어를 정리한 요약 치트시트입니다.

---

## 📌 1. 주간 표준 워크플로 (권장 루틴: 일요일 1회 실행)

| 단계 | 실행 명령어 | 설명 |
| :--- | :--- | :--- |
| **1단계: 후보 수집** | `python curate.py fetch` | 6개 카테고리 최신 기사 약 100건 수집 및 마크다운 생성 |
| **2단계: 검토 준비** | `python curate.py review` | 1단계 체크 기사의 고화질 보도사진 크롤링 및 본문 요약 파싱 |
| **3단계: 제작 및 업로드** | `python curate.py build --render --upload` | 카드뉴스 PNG + 쇼츠 MP4 렌더링 후 **유튜브/인스타 자동 예약 발행** |

> 💡 **가장 빠른 루틴**:
> 1. `python curate.py fetch` 실행
> 2. `output/{날짜}_curated_weekly/candidates_titles.md` 열고 마음에 드는 기사에 `[x]` 체크
> 3. `python curate.py review` 실행
> 4. `output/{날짜}_curated_weekly/candidates_detail.md` 열고 최종 채택 기사에 `[x]` 체크 및 이유 작성
> 5. `git add . && git commit -m "feat: 주간 콘텐츠 생성" && git push origin main` (인스타 이미지 URL 제공용)
> 6. `python curate.py build --render --upload` 실행 ➔ **끝!**

---

## 🧪 2. 사전 진단 및 시뮬레이션 (DRY-RUN) 명령어

실제 SNS에 등록하지 않고 연결 상태 및 예약 스케줄을 미리 검증할 때 사용합니다.

```bash
# 인스타그램 API 연결 및 토큰 유효성 진단
python curate.py test-insta

# 유튜브 OAuth 로그인 1회 인증 도우미
python curate.py auth-yt

# 전체 플랫폼(유튜브 + 인스타그램) 업로드 가상 시뮬레이션
python curate.py upload --dry-run

# 유튜브 쇼츠만 가상 시뮬레이션
python curate.py upload --platform youtube --dry-run

# 인스타그램 카드뉴스 캐러셀만 가상 시뮬레이션
python curate.py upload --platform instagram --type carousel --dry-run

# 인스타그램 릴스 비디오만 가상 시뮬레이션
python curate.py upload --platform instagram --type video --dry-run
```

---

## 🚀 3. 실제 SNS 자동 예약 업로드 명령어

콘텐츠 빌드가 이미 끝난 상태에서 업로드만 별도로 실행할 때 사용합니다.

```bash
# 전체 플랫폼(쇼츠 6편 + 캐러셀 6편 + 릴스 6편) 자동 예약 업로드
python curate.py upload

# 유튜브 쇼츠 6편만 예약 업로드
python curate.py upload --platform youtube

# 오늘 요일(KST) 인스타그램 콘텐츠만 1건 즉시 발행 (GitHub Actions에서 매일 아침 자동 실행)
python curate.py upload --platform instagram --today-only

# 특정 요일(예: 수요일) 인스타그램 콘텐츠만 지정하여 즉시 발행
python curate.py upload --platform instagram --day wed

# 인스타그램 콘텐츠(캐러셀 + 릴스) 전체 업로드
python curate.py upload --platform instagram

# 인스타그램 카드뉴스 캐러셀만 업로드
python curate.py upload --platform instagram --type carousel

# 인스타그램 릴스만 업로드
python curate.py upload --platform instagram --type video

# 주간 큐레이션 결과물을 GitHub 원격 저장소로 스마트 동기화 (4주 롤링 슬림화 자동 적용)
python curate.py sync
```

---

## 🛠️ 4. 단계별 세부 제어 및 개발자 명령어

```bash
# [1단계] 카테고리당 수집 기사 개수 조정 (기본값: 17개, 총 102개)
python curate.py fetch --count 25

# [3단계] 렌더링(이미지/영상 파일 생성) 없이 대본 및 메타데이터 JSON만 빌드 (고속 검수용)
python curate.py build

# [3단계] 렌더링만 진행하고 업로드는 나중에 수동으로 할 때
python curate.py build --render

# [3단계] 렌더링 후 업로드는 시뮬레이션(DRY-RUN)으로만 안전 점검
python curate.py build --render --upload --dry-run

# 특정 날짜 폴더를 지정하여 작업할 때 (YYYY-MM-DD)
python curate.py fetch --date 2026-09-13
python curate.py review --date 2026-09-13
python curate.py build --date 2026-09-13 --render
python curate.py upload --date 2026-09-13

# 누적 큐레이션 데이터셋 통계 확인 (AI 파인튜닝용 히스토리)
python curate.py stats
```

---

## 📅 5. 요일별 실행 동작 메커니즘 (일요일 vs 평일)

### Q. 일요일에 실행하면? (표준 주간 루틴)
- 예약 알고리즘이 **내일(월요일)부터 토요일까지 6일 치 전체를 순차적으로** 오전 8시 예약으로 배정합니다.
  - 월: 내일 오전 8시 KST 예약
  - 화: 내일 모레 오전 8시 KST 예약
  - 수~토: 이번 주 수~토 오전 8시 KST 예약
- **결과**: 다가오는 주간(월~토) 6일 치가 순서대로 1주일 단위로 완벽 예약됩니다.

### Q. 일요일이 아닌 평일에 실행하면? (스마트 즉시 업로드 & 잔여 요일 예약)
- 사용자가 평일 중 언제 시작하든 주간 콘텐츠 흐름이 끊기지 않도록 다음과 같이 자동 분기됩니다:
  - **오늘 및 이미 지난 요일의 콘텐츠**: 대기 없이 **⚡ 즉시 업로드(공개 발행)**
  - **아직 오지 않은 이번 주 남은 요일의 콘텐츠**: 원래대로 **⏰ 이번 주 해당 요일 오전 8시 예약 발행**

#### 💡 요일별 실행 예시:
- **월요일에 시작 시**:
  - `월요일`: **즉시 업로드**
  - `화, 수, 목, 금, 토`: 이번 주 화~토 **오전 8시 예약**
- **화요일에 시작 시**:
  - `월요일, 화요일`: **즉시 업로드**
  - `수, 목, 금, 토`: 이번 주 수~토 **오전 8시 예약**
- **수요일에 시작 시**:
  - `월요일, 화요일, 수요일`: **즉시 업로드**
  - `목, 금, 토`: 이번 주 목~토 **오전 8시 예약**
- **목요일 / 금요일에 시작 시**:
  - 오늘까지의 요일은 모두 **즉시 업로드**, 남은 요일만 **오전 8시 예약**
- **토요일에 시작 시**:
  - 주간 6일 치(월~토) 전체 **즉시 업로드**
