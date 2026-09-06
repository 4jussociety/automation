<!-- 이 문서는 THEPT 주간 물리치료 뉴스 6일 연계 자동화 콘텐츠 생성 시스템 가이드입니다. -->
<!-- 월수금 1분 쇼츠 & 화목토 4:5 심층 카드뉴스 주간 3대 브리핑 세트 일괄 생성법을 제공합니다. -->

# THEPT 주간 물리치료 뉴스 6일 연계 콘텐츠 생성기

한 주간의 국내 및 해외 최신 **'물리치료/재활치료/도수치료'** 뉴스를 수집하여 3개 브리핑 배치(총 9건)로 편성하고, **월·수·금 1분 브리핑 쇼츠(9:16)**와 **화·목·토 4:5 심층 카드뉴스**를 요일별 6개 전용 폴더에 일괄 자동 생성하는 시스템입니다.

---

## 📅 주간 발행 스케줄 및 콘텐츠 구조

| 요일 | 콘텐츠 유형 | 규격 | 다루는 브리핑 세트 | 구성 내용 |
| :--- | :--- | :--- | :--- | :--- |
| **월요일** | **1분 고속 쇼츠** | 9:16 비디오 (1080x1920) | **배치 1 (국내 정책·제도 A, 3건)** | 48~52초 압축 브리핑 (수가, 실손보험, 제도) |
| **화요일** | **심층 카드뉴스** | 4:5 피드 (1080x1350) | **배치 1 (국내 정책·제도 A, 3건)** | 6장 슬라이드 PNG + 인스타 캡션 + 기사 출처 |
| **수요일** | **1분 고속 쇼츠** | 9:16 비디오 (1080x1920) | **배치 2 (임상 연구·첨단 B, 3건)** | 48~52초 압축 브리핑 (로봇재활, 임상효과, 논문) |
| **목요일** | **심층 카드뉴스** | 4:5 피드 (1080x1350) | **배치 2 (임상 연구·첨단 B, 3건)** | 6장 슬라이드 PNG + 인스타 캡션 + 기사 출처 |
| **금요일** | **1분 고속 쇼츠** | 9:16 비디오 (1080x1920) | **배치 3 (해외 글로벌 C, 3건)** | 48~52초 글로벌 브리핑 (한국어 완벽 번역) |
| **토요일** | **심층 카드뉴스** | 4:5 피드 (1080x1350) | **배치 3 (해외 글로벌 C, 3건)** | 6장 슬라이드 PNG + 인스타 캡션 + 기사 출처 |

---

## 🌟 핵심 특징

1. **주간 3대 브리핑 세트 자동 편성 (주제 완벽 분리)**:
   - 배치 1: 국내 의료 정책 & 제도 & 수가 현안 3건
   - 배치 2: 최신 재활 임상 연구 & 첨단 치료 기술 3건 (배치 1과 중복 원천 차단)
   - 배치 3: 글로벌 물리치료 & APTA 해외 연구 트렌드 3건 (한국어 완벽 번역)
2. **말줄임표(...) 없는 완성형 문장 & 자연스러운 대본**:
   - 인위적인 말줄임표 없이 문맥이 살아있는 온전한 문장과 헤드라인으로 카드뉴스와 나레이션을 구성합니다.
3. **자카드 유사도 기반 중복 기사 & 가십 완벽 배제**:
   - 동일 이슈 및 어뷰징 기사, 연예 가십을 지능적으로 필터링하여 전문성 높은 기사만 엄선합니다.
4. **실제 보도 사진 우선 크롤링 (Playwright)**:
   - 기사 원문 페이지의 오픈그래프(`og:image`) 및 본문 대표 사진을 자동 크롤링하여 카드 배경으로 최우선 반영합니다.

---

## 📁 프로젝트 구조

```
automatic/
├── main.py                          # 주간 6일 연계 파이프라인 메인 진입점
├── pipeline.py                      # 수집->사진크롤링->대본->카드뉴스->TTS->영상 일괄 파이프라인
├── config.py                        # 해상도, TTS 속도, API 키 및 경로 설정
├── requirements.txt                 # 필수 파이썬 라이브러리 목록
│
├── modules/
│   ├── news_collector.py            # [기능 1] 네이버 API HUB 9건 수집 & 주제 분리 & 번역
│   ├── article_image_fetcher.py     # [기능 2] 기사 원문 실제 보도 사진 병렬 크롤러 (Playwright)
│   ├── content_builder.py           # [기능 3] 요일별 6개 콘텐츠 패키지 및 1분 나레이션 빌더
│   ├── card_renderer.py             # [기능 4] Playwright 기반 4:5 카드뉴스 PNG 렌더러
│   ├── tts_synthesizer.py           # [기능 5] Edge-TTS 한국어 고속(+22%) 음성 합성 모듈
│   └── video_renderer.py            # [기능 6] FFmpeg 기반 9:16 쇼츠 MP4 영상 렌더러
│
├── templates/
│   ├── card_4x5.html                # 4:5 인스타그램 피드 템플릿
│   └── card_9x16.html               # 9:16 세로형 템플릿
│
└── output/
    └── YYYY-MM-DD_weekly/           # 주간 마스터 폴더
        ├── backgrounds/             # 크롤링된 실제 보도 사진 9건 및 배경 이미지
        ├── weekly_sources_and_links.txt # 전체 기사 출처 및 주간 발행 시간표
        ├── 01_Mon_Shorts/           # 월요일 1분 쇼츠 영상 및 음성
        ├── 02_Tue_CardNews/         # 화요일 4:5 카드뉴스 PNG 6장 & 인스타 캡션
        ├── 03_Wed_Shorts/           # 수요일 1분 쇼츠 영상 및 음성
        ├── 04_Thu_CardNews/         # 목요일 4:5 카드뉴스 PNG 6장 & 인스타 캡션
        ├── 05_Fri_Shorts_Global/    # 금요일 해외 1분 쇼츠 영상 및 음성
        └── 06_Sat_CardNews_Global/  # 토요일 해외 4:5 카드뉴스 PNG 6장 & 인스타 캡션
```

---

## 🚀 사용 방법

### 1. 환경 설정
`.env` 파일에 네이버 클라우드 플랫폼(NAVER API HUB) 검색 API 키를 설정합니다:
```env
NAVER_CLIENT_ID=your_client_id
NAVER_CLIENT_SECRET=your_client_secret
```

### 2. 주간 마크다운 큐레이션 워크플로 (`curate.py`)
```bash
# 1단계: 6대 카테고리 기사 대량 수집 및 제목 스크리닝 파일 생성
python curate.py fetch

# [중간 작업] candidates_titles.md를 에디터로 열어 관심 기사에 [x] 표시

# 2단계: 1차 선택 기사 상세 본문 및 보도 사진 크롤링
python curate.py review

# [중간 작업] candidates_detail.md를 에디터로 열어 최종 기사 확정 [x] 표시

# 3단계: 주 6일 콘텐츠 일괄 제작 및 미디어 렌더링 (원스톱 업로드 가능)
python curate.py build --render
# (빌드와 동시에 업로드 예약까지 원스톱 실행: python curate.py build --render --upload)
```

---

## 📡 유튜브 & 인스타그램 자동 예약 업로드 파이프라인

본 시스템은 **YouTube Data API v3** 및 **Meta Instagram Graph API v20.0**을 통해 제작된 콘텐츠를 월~토 지정 시간(오전 8시 KST)에 자동 예약 발행합니다.

- **상세 API 발급 가이드**: [docs/api_setup_guide.md](file:///c:/Users/myrea/OneDrive/바탕%20화면/개발/automatic/docs/api_setup_guide.md)

### 주요 CLI 명령어
```bash
# 1. YouTube 1회 브라우저 OAuth 인증
python curate.py auth-yt

# 2. Instagram Graph API 연결 상태 진단
python curate.py test-insta

# 3. 예약 발행 시뮬레이션 (API 호출 없는 검증)
python curate.py upload --dry-run

# 4. 주간 콘텐츠 실제 예약 업로드 실행 (YouTube 쇼츠 + Instagram 캐러셀 + 릴스)
python curate.py upload

# 5. 특정 플랫폼 또는 콘텐츠 유형만 업로드
python curate.py upload --platform youtube
python curate.py upload --platform instagram --type carousel
```

