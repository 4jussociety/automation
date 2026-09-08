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

## 2. Google YouTube Data API v3 최신 설정 (쇼츠 자동 업로드)

유튜브는 **OAuth 2.0 클라이언트 ID** 방식을 사용하며, 1회 브라우저 로그인 승인 후 영구 갱신 가능한 `token.pickle`이 자동 생성됩니다.

---

### Step 1: Google Cloud Console 프로젝트 생성
1. [Google Cloud Console](https://console.cloud.google.com/)에 접속하여 구글 계정으로 로그인합니다.
2. 상단 네비게이션 바의 **프로젝트 선택 드롭다운** > **[새 프로젝트(New Project)]**를 클릭합니다.
3. 프로젝트 이름(예: `THEPT-Automation`)을 입력한 뒤 **[만들기]**를 클릭합니다.
4. 생성이 완료되면 상단 알림창 또는 프로젝트 드롭다운에서 방금 생성한 프로젝트를 **선택(활성화)**합니다.

---

### Step 2: YouTube Data API v3 활성화
1. 좌측 메뉴 **[API 및 서비스] > [라이브러리]**로 이동합니다. (또는 상단 검색창에 "YouTube Data API v3" 검색)
2. 검색 결과에서 **`YouTube Data API v3`**을 클릭합니다.
3. 파란색 **[사용(Enable)]** 버튼을 클릭하여 API를 활성화합니다.

---

### Step 3: OAuth 동의 화면(Google 인증 플랫폼) 구성
> 💡 **UI 참고**: Google Cloud Console 개편으로 메뉴명이 **[API 및 서비스] > [OAuth 동의 화면]** 또는 **[Google 인증 플랫폼(Google Auth Platform)]**으로 표시될 수 있습니다. 잘 보이지 않으면 상단 검색창에 **"OAuth 동의 화면"**을 검색하세요.

1. 좌측 메뉴에서 **[OAuth 동의 화면]**으로 이동합니다.
2. **User Type(사용자 유형)** 선택:
   - **[외부(External)]**를 선택하고 **[만들기(Create)]**를 클릭합니다.
3. **1단계: 앱 정보 (브랜딩)**:
   - **앱 이름**: `THEPT Shorts Uploader` (자유롭게 입력 가능)
   - **사용자 지원 이메일**: 본인의 Google 이메일 주소 선택
   - **개발자 연락처 정보**: 본인의 Google 이메일 주소 입력
   - 맨 아래 **[저장 후 계속]**을 클릭합니다.
4. **2단계: 범위(Scopes - 데이터 액세스)**:
   - **[범위 추가 또는 삭제]** 버튼을 클릭합니다.
   - 필터 검색창에 `youtube`를 입력하고 다음 2가지 필수 권한을 체크합니다:
     - `.../auth/youtube.upload` (YouTube 동영상 관리 및 업로드)
     - `.../auth/youtube.force-ssl` (YouTube 댓글 작성 및 채널 데이터 관리)
   - 맨 아래 **[업데이트]** > **[저장 후 계속]**을 클릭합니다.
5. **3단계: 테스트 사용자(Test Users - 잠재고객) ★가장 중요★**:
   > ⚠️ **주의**: 앱이 '테스트' 상태이므로 여기에 등록되지 않은 계정은 로그인 시 `오류 403: access_denied`가 발생합니다.
   - **[+ ADD USERS (사용자 추가)]**를 클릭합니다.
   - 업로드할 **유튜브 채널의 구글 계정 이메일**을 입력하고 **[추가]**를 누릅니다.
   - 하단의 **[저장 후 계속]**을 클릭합니다.
6. **4단계: 요약** 확인 후 **[대시보드로 돌아가기]**를 클릭합니다.

---

### Step 4: OAuth 클라이언트 ID(JSON 키) 생성 및 다운로드
1. 좌측 메뉴 **[API 및 서비스] > [사용자 인증 정보(Credentials)]**로 이동합니다.
2. 상단 메뉴 **[+ 사용자 인증 정보 만들기] > [OAuth 클라이언트 ID]**를 선택합니다.
3. **애플리케이션 유형**: 반드시 **[데스크톱 앱(Desktop App)]**을 선택합니다. (웹 애플리케이션 X)
4. 이름에 `THEPT Shorts CLI`를 입력하고 **[만들기(Create)]**를 클릭합니다.
5. 팝업창에서 **[JSON 다운로드]** 버튼을 클릭하여 컴퓨터로 저장합니다.
6. 다운로드한 파일의 이름을 **`client_secret.json`**으로 변경하고, 본 프로젝트의 **루트 폴더**로 복사합니다:
   ```
   c:\Users\myrea\OneDrive\바탕 화면\개발\자동화에이전트\client_secret.json
   ```

---

### Step 5: 1회 최초 인증 실행 (웹 브라우저 로그인)
터미널에서 아래 명령어를 실행하면 기본 웹 브라우저 창이 자동으로 열립니다:
```bash
python curate.py auth-yt
```

#### 🌐 브라우저 인증 시 보안 경고창 대처 방법:
1. 업로드할 유튜브 채널 구글 계정을 선택합니다.
2. **"Google에서 확인하지 않은 앱입니다 (This app isn't verified)"** 경고 화면이 나타납니다 (개인 개발용 앱의 정상적인 안내입니다).
3. 좌측 하단의 조그만 **[고급(Advanced)]** 글자를 클릭합니다.
4. 맨 아래에 나타나는 **`THEPT Shorts Uploader(으)로 이동(안전하지 않음)`** 링크를 클릭합니다.
5. 요청하는 권한(동영상 업로드, 채널 관리 등) 체크박스를 **모두 체크**하고 **[계속(Continue)]**을 클릭합니다.
6. 브라우저에 **"The authentication flow has completed."** 문구가 뜨면 인증 완료!

---

### Step 6: 인증 완료 확인
- 인증이 성공하면 프로젝트 루트에 **`token.pickle`** 파일이 자동 생성됩니다.
- 이후에는 추가 로그인이나 토큰 입력 없이 `token.pickle`이 만료 시 알아서 자동 갱신되며 영구적으로 자동 업로드됩니다:
  ```bash
  # 유튜브 쇼츠 업로드 시뮬레이션
  python curate.py upload --platform youtube --dry-run
  ```

---

## 3. Meta Instagram Graph API 최신 설정 (카드뉴스 & 릴스 자동 업로드)

인스타그램 공식 API는 **인스타그램 프로페셔널(비즈니스/크리에이터) 계정**과 **Facebook 페이지 연동**이 필수입니다.

---

### Step 1: 인스타그램 계정 전환 및 페이스북 페이지 연결
1. **인스타그램 프로페셔널 계정 전환**:
   - 모바일 인스타그램 앱 > [프로필] > 우측 상단 메뉴(≡) > [계정 유형 및 도구] > **[프로페셔널 계정으로 전환]** (크리에이터 또는 비즈니스 선택).
2. **페이스북 페이지 생성 및 연결 (PC 환경 권장)**:
   > 💡 **Tip**: 모바일 앱에서 연결 시 간혹 Meta 계정 센터와 분리되어 API가 계정을 인식하지 못할 수 있습니다. **PC 페이스북 웹사이트**에서 연결하는 것을 강력히 권장합니다.
   - [Facebook](https://www.facebook.com/)에서 전용 비즈니스 페이지(예: `THEPT`)를 생성합니다.
   - 생성한 페이스북 페이지 관리 화면 > 좌측 메뉴 **[설정] > [연결된 계정] > [Instagram]**으로 이동합니다.
   - **[계정 연결]** 버튼을 클릭하고 인스타그램 계정으로 로그인하여 페이스북 페이지와 상호 연결을 완료합니다.

---

### Step 2: Meta for Developers 앱 생성 (최신 UI)
1. [Meta for Developers](https://developers.facebook.com/)에 접속하여 로그인합니다.
2. 우측 상단 **[내 앱] > [앱 만들기]**를 클릭합니다.
3. **사용 사례(Use Case) 선택 화면**:
   - 화면 구성에 따라 다음 중 하나를 선택합니다:
     - **경로 A (가장 추천)**: 맨 아래 **[기타(Other)]** 선택 > [다음] 클릭 > 앱 유형에서 **[비즈니스(Business)]** 선택 후 [다음].
     - **경로 B (신규 사용 사례 화면인 경우)**: **[비즈니스에 맞춤형 솔루션 제공(Business)]** 또는 **[Instagram에서 다른 사람과 소통하거나 참여를 유도합니다]** 선택.
4. **앱 세부 정보 입력**:
   - 앱 이름(예: `THEPT-Automation`) 및 연락처 이메일을 입력합니다.
   - 비즈니스 포트폴리오(선택 사항) 지정 후 **[앱 만들기]**를 완료합니다.

---

### Step 3: Instagram Graph API 제품 추가
1. 앱이 생성되면 좌측 사이드바 메뉴에서 **[제품 추가(Add Product)]**를 클릭합니다.
2. 제품 목록 중 **Instagram Graph API**를 찾아 **[설정(Set up)]**을 클릭합니다.

---

### Step 4: 권한 부여 및 인스타그램 계정 ID 확인 (Graph API 탐색기)
1. 상단 메뉴 **[도구(Tools)] > [Graph API 탐색기(Graph API Explorer)]**로 이동합니다.
2. 우측 상단 설정 확인:
   - **Meta 앱**: 방금 생성한 앱 선택
   - **사용자 또는 페이지**: **사용자 토큰(User Token)** 선택
3. 우측 **[권한(Permissions)]** 드롭다운에서 아래 권한들을 모두 찾아 추가합니다:
   > ⚠️ **주의**: Meta의 최신 정책에 따라 권한 명칭이 `instagram_business_...`로 표시될 수 있습니다. 둘 중 검색되는 권한을 선택하세요.
   - **인스타그램 필수 권한**:
     - `instagram_basic` 또는 `instagram_business_basic` (프로필 및 미디어 기본 조회)
     - `instagram_content_publish` 또는 `instagram_business_content_publish` (카드뉴스/릴스 자동 발행)
     - `instagram_manage_comments` 또는 `instagram_business_manage_comments` (**첫 댓글 자동 작성 필수**)
   - **페이스북 페이지 필수 권한**:
     - `pages_show_list` (연결된 페이지 목록 조회)
     - `pages_read_engagement` (페이지 메타데이터 읽기)
     - `pages_manage_posts` 또는 `business_management` (페이지 권한 관리)
4. 권한을 모두 추가한 후 **[Generate Access Token]** (액세스 토큰 생성) 버튼을 클릭합니다.
   - 페이스북 팝업창에서 **"어떤 페이지를 연결하시겠습니까?"**와 **"어떤 인스타그램 계정을 연결하시겠습니까?"**가 나오면 **연결할 페이지와 인스타그램 계정을 모두 체크**하고 모든 권한을 허용합니다.
5. 상단 URL 입력창에 아래 쿼리를 입력하고 **[제출(Submit)]**을 클릭합니다:
   ```http
   GET me/accounts?fields=name,instagram_business_account{id,username}
   ```
6. 응답 JSON 결과 확인:
   ```json
   {
     "data": [
       {
         "name": "THEPT",
         "instagram_business_account": {
           "id": "17841400000000000",
           "username": "thept_official"
         },
         "id": "123456789012345"
       }
     ]
   }
   ```
   - 위 결과에서 `instagram_business_account` 안의 `id` (예: `17841400000000000`)가 바로 **`INSTAGRAM_ACCOUNT_ID`**입니다!
   > ❓ **트러블슈팅: `instagram_business_account`가 나오지 않거나 빈 값인 경우**
   > - 인스타그램이 일반 개인 계정인 경우 발생합니다. 프로페셔널(비즈니스/크리에이터) 계정인지 다시 확인하세요.
   > - 페이스북 페이지의 [설정] > [연결된 계정]에서 인스타그램 연동 상태가 정상인지 확인하세요.
   > - Step 4-4의 권한 승인 팝업에서 해당 페이지와 인스타그램 계정을 체크 해제했는지 확인 후 다시 토큰을 발급받으세요.

---

### Step 5: 토큰 발급 (선택: 60일 장기 토큰 vs 영구 시스템 사용자 토큰)

탐색기에서 생성된 토큰은 1~2시간만 유효한 임시 토큰입니다. 아래 두 가지 방식 중 하나를 선택하여 토큰을 발급받으세요:

#### 방법 A: 60일 장기 토큰 발급 (가장 빠르고 간편함)
1. 상단 메뉴 **[도구(Tools)] > [액세스 토큰 도구(Access Token Tool)]** 또는 [액세스 토큰 디버거](https://developers.facebook.com/tools/debug/accesstoken/)로 이동합니다.
2. Step 4에서 생성한 토큰을 붙여넣고 **[디버그(Debug)]**를 클릭합니다.
3. 정보 창 하단의 **[액세스 토큰 확장(Extend Access Token)]** 버튼을 클릭합니다.
4. 아래에 새로 생성된 긴 문자열이 바로 **60일간 유효한 장기 토큰**입니다. 이를 복사합니다.

#### 방법 B: 영구 시스템 사용자 토큰 발급 (자동화 파이프라인 권장, 만료 없음)
> 60일마다 토큰을 갱신하는 번거로움 없이 완전히 자동화하려면 시스템 사용자 토큰을 권장합니다.
1. [Meta Business Suite 설정](https://business.facebook.com/settings/)으로 이동합니다.
2. 좌측 메뉴 **[사용자] > [시스템 사용자(System Users)]**로 이동하여 [추가]를 누르고 시스템 사용자(역할: 관리자)를 생성합니다.
3. 생성된 시스템 사용자를 클릭하고 **[자산 할당(Assign Assets)]**을 눌러 본인의 Facebook 페이지와 Instagram 계정에 **모든 권한(전체 제어권)**을 부여합니다.
4. **[새 토큰 생성(Generate New Token)]** 버튼을 클릭합니다.
5. 본인의 앱을 선택하고, **토큰 만료 기간(Token expiration)을 '만료 없음(Never)'**으로 설정합니다.
6. Step 4-3에 명시된 권한들을 모두 체크한 뒤 토큰을 생성합니다.
7. 생성된 영구 토큰을 복사합니다.

---

### Step 6: `.env` 파일에 설정값 입력
프로젝트 루트의 `.env` 파일에 복사한 값들을 입력합니다:
```env
INSTAGRAM_ACCOUNT_ID=17841400000000000
INSTAGRAM_ACCESS_TOKEN=EAAG...
```

---

### Step 7: 인스타그램 연결 및 권한 진단 실행
터미널에서 아래 명령어를 실행하여 계정과 권한이 정상 연결되었는지 즉시 검증합니다:
```bash
python curate.py test-insta
```
정상 연동 시 다음과 같이 채널명과 ID가 표시됩니다:
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
