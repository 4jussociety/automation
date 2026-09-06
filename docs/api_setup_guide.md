<!-- 이 문서는 YouTube Data API v3 및 Instagram Graph API 연동을 위한 상세 발급 및 설정 가이드입니다. -->
<!-- 개발자 콘솔 설정부터 토큰 발급, .env 등록 및 예약 업로드 테스트 전 과정을 단계별로 안내합니다. -->

# 🚀 YouTube & Instagram 자동 예약 업로드 API 설정 가이드

본 프로젝트는 주간 6일 콘텐츠(쇼츠 비디오, 4:5 카드뉴스 캐러셀, 인스타그램 릴스)를 유튜브와 인스타그램에 요일별로 자동 예약 발행하는 공식 API 연동 시스템을 포함하고 있습니다.

아래 단계에 따라 API 자격 증명을 1회 발급받아 프로젝트에 등록해 주세요.

---

## 📑 목차
1. [사전 준비 (.env 파일)](#1-사전-준비-env-파일)
2. [YouTube Data API v3 설정 (쇼츠 자동 업로드)](#2-youtube-data-api-v3-설정-쇼츠-자동-업로드)
3. [Meta Instagram Graph API 설정 (카드뉴스 & 릴스 자동 업로드)](#3-meta-instagram-graph-api-설정-카드뉴스--릴스-자동-업로드)
4. [연동 테스트 및 업로드 실행 방법](#4-연동-테스트-및-업로드-실행-방법)

---

## 1. 사전 준비 (.env 파일)

프로젝트 루트 디렉토리의 `.env` 파일에 다음 환경 변수 항목을 추가하거나 수정합니다:

```env
# ==========================================
# 4. GitHub 저장소 (인스타그램 공개 미디어 URL 매핑)
# ==========================================
GITHUB_REPO=4jussociety/automation
GITHUB_BRANCH=main

# ==========================================
# 5. SNS 자동 발행 스케줄 설정
# ==========================================
PUBLISH_HOUR_KST=8

# ==========================================
# 6. YouTube Data API v3 설정
# ==========================================
YOUTUBE_CLIENT_SECRET_FILE=client_secret.json

# ==========================================
# 7. Meta Instagram Graph API 설정
# ==========================================
INSTAGRAM_ACCOUNT_ID=
INSTAGRAM_ACCESS_TOKEN=
```

---

## 2. YouTube Data API v3 설정 (쇼츠 자동 업로드)

유튜브는 **OAuth 2.0 클라이언트 ID** 방식을 사용하며, 1회 브라우저 로그인 후 영구 갱신 가능한 `token.pickle`이 생성됩니다.

### Step 1: Google Cloud Console 프로젝트 생성
1. [Google Cloud Console](https://console.cloud.google.com/)에 접속하여 로그인합니다.
2. 상단 프로젝트 선택 메뉴에서 **[새 프로젝트]**를 클릭하고 프로젝트 이름(예: `THEPT-Automation`)을 입력한 뒤 생성합니다.

### Step 2: YouTube Data API v3 사용 설정
1. 좌측 메뉴 **[API 및 서비스] > [라이브러리]**로 이동합니다.
2. 검색창에 **`YouTube Data API v3`**을 검색하고 클릭합니다.
3. **[사용(Enable)]** 버튼을 클릭합니다.

### Step 3: OAuth 동의 화면 구성
1. 좌측 메뉴 **[API 및 서비스] > [OAuth 동의 화면]**으로 이동합니다.
2. User Type을 **[외부(External)]**로 선택하고 [만들기]를 클릭합니다.
3. 필수 항목을 입력합니다:
   - 앱 이름: `THEPT Shorts Uploader`
   - 사용자 지원 이메일: 본인 구글 이메일
   - 개발자 연락처 정보: 본인 구글 이메일
4. **[저장 후 계속]**을 누르고, **[범위(Scopes)]** 단계에서:
   - **[범위 추가 또는 삭제]** 클릭 후 `.../auth/youtube.upload` 및 `.../auth/youtube.force-ssl` 권한을 선택합니다.
5. **[테스트 사용자(Test Users)]** 단계에서:
   - 본인의 유튜브 채널 구글 계정 이메일을 **테스트 사용자로 반드시 추가**합니다.
6. 저장을 완료합니다.

### Step 4: OAuth 클라이언트 ID 생성 및 다운로드
1. 좌측 메뉴 **[API 및 서비스] > [사용자 인증 정보]**로 이동합니다.
2. 상단 **[+ 사용자 인증 정보 만들기] > [OAuth 클라이언트 ID]**를 선택합니다.
3. 애플리케이션 유형으로 **[데스크톱 앱(Desktop App)]**을 선택하고 이름(예: `THEPT CLI`)을 지정한 후 [만들기]를 클릭합니다.
4. 생성된 클라이언트 ID 창에서 **[JSON 다운로드]** 버튼을 클릭합니다.
5. 다운로드한 파일의 이름을 **`client_secret.json`**으로 변경하고, 본 프로젝트 루트 폴더에 복사합니다:
   ```
   c:\Users\myrea\OneDrive\바탕 화면\개발\automatic\client_secret.json
   ```

### Step 5: 1회 최초 인증 실행
터미널에서 아래 명령어를 실행하면 웹 브라우저가 열립니다:
```bash
python curate.py auth-yt
```
- 브라우저에서 유튜브 채널 계정으로 로그인 후 권한을 승인합니다.
- 승인이 완료되면 프로젝트 루트에 `token.pickle`이 자동 생성되며, 이후부터는 추가 로그인 없이 자동 업로드됩니다.

---

## 3. Meta Instagram Graph API 설정 (카드뉴스 & 릴스 자동 업로드)

인스타그램 공식 API는 **인스타그램 비즈니스/크리에이터 계정**과 **Facebook 페이지 연동**이 필요합니다.

### Step 1: 계정 전환 및 페이스북 페이지 연결
1. **인스타그램 계정 전환**:
   - 모바일 인스타그램 앱 > [프로필 편집] 또는 [설정 및 개인정보] > [계정 유형 및 도구] > **[프로페셔널/비즈니스 계정으로 전환]**을 완료합니다.
2. **페이스북 페이지 연동**:
   - 페이스북에서 새로운 비즈니스 페이지(예: `THEPT`)를 생성합니다.
   - 인스타그램 앱의 [프로필 편집] > [공개 비즈니스 정보] > [페이지]에서 생성한 페이스북 페이지를 연결합니다.

### Step 2: Meta for Developers 앱 생성
1. [Meta for Developers](https://developers.facebook.com/)에 접속하여 로그인합니다.
2. 우측 상단 **[내 앱] > [앱 만들기]**를 클릭합니다.
3. 사용 사례로 **[기타] > [비즈니스(Business)]** 유형을 선택합니다.
4. 앱 이름을 입력하고 앱 생성을 완료합니다.

### Step 3: Instagram Graph API 제품 추가
1. 생성된 앱 대시보드 좌측 메뉴에서 **[제품 추가]**를 클릭합니다.
2. **Instagram Graph API** 항목을 찾아 [설정]을 클릭합니다.

### Step 4: 액세스 토큰 생성 및 인스타그램 계정 ID 확인
1. 상단 메뉴 **[도구(Tools)] > [Graph API 탐색기(Graph API Explorer)]**로 이동합니다.
2. 우측 [권한(Permissions)] 드롭다운에서 아래 권한들을 추가합니다:
   - `instagram_basic`
   - `instagram_content_publish`
   - `pages_show_list`
   - `pages_read_engagement`
   - `business_management`
3. **[Generate Access Token]** 버튼을 클릭하고 페이스북 로그인 및 페이지/인스타그램 계정 선택 권한을 모두 허용합니다.
4. 탐색기 URL 창에 아래 쿼리를 입력하고 [제출(Submit)]을 누릅니다:
   ```http
   GET me/accounts?fields=instagram_business_account{id,username}
   ```
5. 결과 JSON에서 `instagram_business_account`의 `id` (예: `17841400000000000`)를 복사합니다. 이것이 **`INSTAGRAM_ACCOUNT_ID`**입니다.

### Step 5: 60일 장기 액세스 토큰(Long-lived Token) 발급
탐색기에서 생성된 단기 토큰을 60일간 유지되는 장기 토큰으로 변환합니다:
1. 상단 메뉴 **[도구] > [액세스 토큰 도구(Access Token Tool)]**로 이동합니다.
2. 방금 발급받은 토큰 옆의 **[디버그(Debug)]**를 클릭합니다.
3. 맨 아래의 **[액세스 토큰 확장(Extend Access Token)]** 버튼을 클릭하여 생성된 60일 장기 토큰을 복사합니다.
4. 복사한 토큰이 **`INSTAGRAM_ACCESS_TOKEN`**입니다.

### Step 6: `.env` 파일에 값 입력
프로젝트 루트의 `.env` 파일에 붙여넣습니다:
```env
INSTAGRAM_ACCOUNT_ID=17841400000000000
INSTAGRAM_ACCESS_TOKEN=EAAG...
```

### Step 7: 인스타그램 연결 진단 실행
터미널에서 아래 명령어를 실행하여 계정 연동을 확인합니다:
```bash
python curate.py test-insta
```
정상 연동 시 아래와 같이 출력됩니다:
```
✅ 계정 연결 정상: @thept_official (ID: 17841400000000000, 이름: THEPT)
🎉 [진단 통과] Instagram Graph API가 정상적으로 연동되어 있습니다!
```

---

## 4. 연동 테스트 및 업로드 실행 방법

### A. 시뮬레이션 테스트 (DRY-RUN)
실제 API를 호출하지 않고 예약 스케줄, GitHub Raw URL, 캡션 매핑이 완벽한지 먼저 확인합니다:
```bash
# 전체 플랫폼(유튜브+인스타) 시뮬레이션
python curate.py upload --dry-run

# 유튜브 쇼츠만 시뮬레이션
python curate.py upload --platform youtube --dry-run

# 인스타그램 캐러셀만 시뮬레이션
python curate.py upload --platform instagram --type carousel --dry-run
```

### B. 실제 자동 예약 업로드 실행
1. 생성된 콘텐츠(카드뉴스 이미지 및 쇼츠 영상)를 GitHub 저장소로 푸시합니다 (인스타그램 이미지/영상 다운로드 지원):
   ```bash
   git add .
   git commit -m "feat: 주간 콘텐츠 생성 및 업로드 준비"
   git push origin main
   ```

2. 업로드 커맨드를 실행하여 월~토 자동 예약 발행을 완료합니다:
   ```bash
   # 주간 전체 콘텐츠(쇼츠 6편 + 캐러셀 6편 + 릴스 6편) 자동 예약 발행
   python curate.py upload

   # 유튜브 쇼츠만 예약 업로드
   python curate.py upload --platform youtube

   # 인스타그램만 예약 업로드
   python curate.py upload --platform instagram
   ```

### C. 주간 빌드와 동시에 자동 업로드 연동
큐레이션 검토가 끝난 후 빌드와 업로드를 원스톱으로 진행할 때:
```bash
# 렌더링 완료 즉시 유튜브/인스타 예약 발행까지 한 번에 완료
python curate.py build --render --upload
```
