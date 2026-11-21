# 🚀 THEPT 주간 콘텐츠 2단계 직통 자동화 마스터 가이드

THEPT 주간 물리치료 콘텐츠(4:5 카드뉴스 + 9:16 쇼츠 비디오 + SNS 캡션)를 **단 2단계의 명령어(스크랩 → 직통 제작·동기화)로 100% 완결**짓는 실전 운영 매뉴얼입니다.

---

## ⚡ [한눈에 보는 2단계 마스터 치트시트]

| 단계 | 명칭 | 터미널 실행 명령어 | AI 채팅 프롬프트 명령어 | 작업자(인간) 할 일 |
|:---:|---|---|---|---|
| **1단계** | **스크랩** | `python curate.py fetch` | `"이번주 컨텐츠 만들어줘"`<br>`"이번주 스크랩 시작해보자"` | `candidates_titles.md` 열고 최종 기사 `[x]` 체크 (18건) |
| **2단계** | **직통 제작·동기화** | `python curate.py build --render --sync` | `"빌드해줘"` *(대본만)*<br>`"제작하고 깃허브에 올려줘"` | **컴퓨터가 원스톱 완결!** (사진/본문 크롤링+대본+렌더링+GitHub 푸시) |
| *(선택)* | *(상세 검토)* | `python curate.py review` | `"리뷰해줘"` | *(필요 시에만 `candidates_detail.md` 별도 확인 후 `--from-detail` 빌드)* |
| ── | ── | ── | ── | ── |
| **무인** | **SNS 자동발행** | *(GitHub Actions 자동 실행)* | *(조작 불필요)* | **매일 아침 KST 06:50 트리거 (07:30~08:00경 자동 공개)** |

---

## 📖 단계별 상세 가이드

### 1️⃣ 1단계: 기사 대량 스크랩 (Scrap)

* **실행 방식 (택1)**:
  * **터미널 명령어**:
    ```bash
    python curate.py fetch
    ```
  * **AI 채팅 프롬프트**:
    > *"이번주 컨텐츠 만들어줘"* 또는 *"1단계 스크랩 시작해줘"*
* **내부 동작**:
  * 네이버 뉴스, 구글 RSS 등에서 주 6일 6대 카테고리 기사 후보 약 100건을 자동 수집합니다.
  * 수집 결과 파일 `output/{날짜}_curated_weekly/candidates_titles.md`가 생성됩니다.
* **작업자(편집자) 행동**:
  1. 에디터에서 `candidates_titles.md` 파일을 엽니다. (기사 전문이 궁금할 때는 `candidates_fulltext.md`를 함께 열어 확인)
  2. 월~토 각 요일별로 마음에 드는 기사 3건씩(총 18건)의 `[ ]`를 `[x]`로 체크하고 저장합니다.

---

### 2️⃣ 2단계: 직통 제작, 렌더링, 깃허브 푸시 원스톱 (Build, Render & Sync)

* **실행 방식 (택1)**:
  * **터미널 명령어**:
    ```bash
    python curate.py build --render --sync
    ```
  * **AI 채팅 프롬프트**:
    > *"빌드해줘"* (대본/패키지만 생성) 또는 *"제작하고 깃허브에 올려줘"*
* **내부 동작 (인간 개입 없이 컴퓨터가 한 번에 완료)**:
  1. **직통 파싱 및 크롤링**: `candidates_titles.md`의 `[x]` 선택 기사를 읽어 보도사진 다운로드 및 원문 본문·제목 복원 수행
  2. **대본 빌드**: OpenAI LLM으로 3~4문장 고품질 쇼츠 대본(130~160자) 작성 + 4THEPT 광고 결합
  3. **미디어 렌더링**: 4:5 고화질 카드뉴스 36장 PNG + 고속 TTS 음성(`+30%`) + BGM(`Final_Bulletin.mp3`) 결합 9:16 쇼츠 비디오 6편 인코딩
  4. **GitHub 푸시**: 완성된 모든 미디어와 메타데이터를 GitHub 원격 저장소(`main`)로 자동 커밋 및 `git push`
* **결과**: 이 단계가 완료되면 **사용자의 주간 작업은 100% 완전히 끝납니다!**
* *(참고: 별도의 `candidates_detail.md` 검토 파일을 만들고 싶을 때만 선택적으로 `python curate.py review` 후 `python curate.py build --from-detail`을 사용할 수 있습니다.)*

---

### 🤖 무인 자동 발행: 매일 아침 KST 06:50 트리거 (GitHub Actions)

* **동작 원리**:
  * 3단계에서 GitHub에 푸시된 결과물을 바탕으로, GitHub Actions 클라우드 러너([daily_sns_publish.yml](file:///.github/workflows/daily_sns_publish.yml))가 **매주 월~토 아침 KST 06:50**에 깨어납니다.
  * GitHub Actions의 러너 대기 큐 지연(약 40분~1시간)을 감안하여 06:50에 시작되므로, **오전 07:30~08:00경 정시**에 당일 요일 콘텐츠 1건이 YouTube Shorts 및 Instagram(피드+릴스)에 자동으로 공개 발행되고 공식 첫 댓글이 등록됩니다.
* **사용자 조작**: **전혀 필요 없음 (100% 무인 자동)**

---

## 🛠️ 유용한 보조 명령어 및 프롬프트 치트시트

### 1. 특정 날짜만 핀포인트로 다시 만들고 싶을 때
* **터미널 명령어**: `python curate.py build --day 0917 --render`
* **AI 채팅 프롬프트**: *"9월 17일(또는 목요일) 것만 영상 다시 만들어줘"*

### 2. 렌더링 전에 대본을 눈으로 먼저 확인하고 싶을 때 (분리 모드)
* **대본만 생성**: `python curate.py build` (프롬프트: *"대본만 먼저 뽑아줘"*)
* **대본 확인 후 렌더 & 푸시**: `python curate.py build --render --sync` (프롬프트: *"확인했으니 렌더링하고 깃허브에 올려줘"*)

### 3. 수동으로 GitHub 동기화만 따로 실행하고 싶을 때
* **터미널 명령어**: `python curate.py sync`
* **AI 채팅 프롬프트**: *"동기화해줘"* 또는 *"깃허브 푸시해줘"*

### 4. SNS 발행 매핑 시뮬레이션 및 성과·채널 진단
* **업로드 시뮬레이션**: `python curate.py upload --dry-run` (프롬프트: *"업로드 시뮬레이션 테스트해줘"*)
* **채널·토큰 진단**: `python curate.py test-yt` · `python curate.py test-insta`
* **SNS 성과·중복 리포트**: `python curate.py analytics --save-report`
* **컴플라이언스·60초 규격 검사**: `python curate.py check`
* **공유 계정 슬롯 분리**: YouTube는 `THEPT` 채널(`PLTEYR_IZibwI`), Instagram(`@teamthept`)은 오전 뉴스 브리핑 슬롯(07:00~12:00 KST)으로 4THEPT 제품 홍보 슬롯과 분리 운영됩니다.
* *(※ 로컬 환경에서는 실제 발행이 코드 및 훅 레벨에서 차단되어 있으므로 오직 `--dry-run`만 실행 가능합니다.)*
