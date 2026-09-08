<!-- 이 문서는 THEPT 주간 물리치료 뉴스 6대 카테고리 자동화 콘텐츠 생성 시스템 가이드입니다. -->
<!-- 월~토 6대 카테고리 2단계 마크다운 큐레이션 및 주간 콘텐츠 자동 발행법을 제공합니다. -->

# THEPT 주 6일 물리치료 전문 콘텐츠 자동화 파이프라인

한 주간의 국내외 최신 **'물리치료/재활치료/도수치료/전문 유튜버 소식'**을 수집·스크리닝하여, **월~토 매일 [4:5 심층 카드뉴스 + 최대 2분 쇼츠 비디오 + SNS 캡션]**을 요일별 6개 전용 폴더에 일괄 자동 생성하고 유튜브/인스타그램에 자동 예약 발행하는 시스템입니다.

---

## 📅 주간 6대 카테고리 발행 스케줄 및 콘텐츠 구조

| 요일 | 카테고리 | 콘텐츠 유형 | 다루는 주제 | 수집 소스 |
| :--- | :--- | :--- | :--- | :--- |
| **월요일** | **국내 정책·제도·수가·실손보험** | 카드뉴스 + 쇼츠 | 보건복지부 정책, 도수치료 실손보험, 물리치료 수가, 협회/법안 | 네이버 뉴스 / 구글 RSS |
| **화요일** | **임상 실무·질환별 재활 프로토콜** | 카드뉴스 + 쇼츠 | 디스크·회전근개·오십견·관절염 등 다빈도 질환 도수 및 운동재활 | 네이버 뉴스 / 구글 RSS |
| **수요일** | **운동·스포츠 재활** | 카드뉴스 + 쇼츠 | 선수 부상 재활, 스포츠 물리치료, 종목별 기능회복 트레이닝 | 네이버 뉴스 / 구글 RSS |
| **목요일** | **첨단 재활 기술·AI·로봇** | 카드뉴스 + 쇼츠 | 보행 보조 로봇, 스마트 헬스케어 기기, AI 재활 시스템 | 네이버 뉴스 / 구글 RSS |
| **금요일** | **운동/재활 유튜버 소식** | 카드뉴스 + 쇼츠 | 인기 재활·운동 전문 유튜버 최신 영상 스크랩, 핵심 치료 팁 | YouTube Data API (금요일 전용) |
| **토요일** | **해외 글로벌 트렌드** | 카드뉴스 + 쇼츠 | 글로벌 물리치료 최신 연구 논문, APTA 동향 (한국어 번역) | 구글 글로벌 RSS + DeepL/Google 번역 |

---

## 🌟 핵심 특징

1. **주 6일 6대 전문 카테고리 특화**:
   - 요일별 고유 테마를 통해 청중의 요일별 관심사에 최적화된 콘텐츠를 매일 연속성 있게 제공합니다.
2. **2단계 마크다운 큐레이션 (Human-in-the-Loop)**:
   - `python curate.py fetch`로 요일별 약 15~18건(총 100건)을 대량 수집하고, 마크다운에서 `[x]` 체크만으로 최적의 기사를 선별합니다.
3. **금요일 전용 유튜브 스크랩 & 보도사진 크롤링**:
   - 금요일에는 등록된 전문 채널([data/youtube_channels.json](file:///c:/Users/myrea/OneDrive/바탕%20화면/개발/자동화에이전트/data/youtube_channels.json)) 및 영상을 집중 스크랩하며, 월~목/토에는 순수 기사만 선별 수집합니다.
4. **쇼츠 비디오 + 4:5 카드뉴스 원스톱 조립**:
   - 매일 카드뉴스(1080x1350)와 쇼츠 비디오(1080x1920)가 동시 제작되며, 타임라인 및 SNS 맞춤형 캡션이 자동 작성됩니다.
5. **YouTube & Instagram 자동 예약 발행**:
   - 제작된 콘텐츠를 오전 8시(KST) 황금 시간대에 맞춰 릴스, 캐러셀 피드, 쇼츠로 자동 예약 업로드합니다.

---

## 📁 프로젝트 구조

```
automatic/
├── curate.py                        # 주간 큐레이션 및 파이프라인 총괄 CLI (fetch/review/build/upload)
├── main.py                          # 메인 CLI 진입점 (curate.py로 일원화)
├── pipeline.py                      # 6일 통합 미디어 조립 및 렌더링 파이프라인
├── config.py                        # 해상도, TTS 속도, API 키 및 경로 설정
├── data/
│   └── youtube_channels.json        # [금요일 전용] 추천 운동/재활 전문 유튜브 채널 목록
│
├── modules/
│   ├── news_collector.py            # [기능 1] 6대 카테고리 대량 수집 (네이버, 구글 RSS, YouTube API)
│   ├── article_image_fetcher.py     # [기능 2] 원문 실제 보도사진 및 유튜브 고화질 썸네일 크롤러
│   ├── curation_manager.py          # [기능 3] 2단계 마크다운(titles -> detail) 큐레이션 관리자
│   ├── content_builder.py           # [기능 4] 일별 통합 콘텐츠 패키지 및 대본 빌더
│   ├── card_renderer.py             # [기능 5] Playwright 기반 4:5 카드뉴스 PNG 렌더러
│   ├── tts_synthesizer.py           # [기능 6] Edge-TTS 한국어 고속(+22%) 음성 합성 모듈
│   ├── video_renderer.py            # [기능 7] FFmpeg 기반 9:16 쇼츠 MP4 영상 렌더러
│   ├── youtube_uploader.py          # [기능 8] YouTube Data API v3 쇼츠 예약 업로더
│   ├── instagram_graph_uploader.py  # [기능 9] Instagram Graph API 캐러셀/릴스 예약 업로더
│   └── sns_scheduler.py             # [기능 10] 월~토 08:00 KST 최적화 통합 스케줄러
│
└── output/
    └── YYYY-MM-DD_curated_weekly/   # 주간 통합 마스터 폴더
        ├── backgrounds/             # 크롤링된 실제 보도 사진 및 유튜브 썸네일 풀
        ├── 01_Mon_Policy/           # 월요일 정책/제도 카드뉴스 + 쇼츠
        ├── 02_Tue_Clinical/         # 화요일 임상 실무 카드뉴스 + 쇼츠
        ├── 03_Wed_Sports/           # 수요일 스포츠 재활 카드뉴스 + 쇼츠
        ├── 04_Thu_Tech/             # 목요일 첨단 로봇/AI 카드뉴스 + 쇼츠
        ├── 05_Fri_YouTube/          # 금요일 유튜버 소식 카드뉴스 + 쇼츠
        └── 06_Sat_Global/           # 토요일 해외 글로벌 트렌드 카드뉴스 + 쇼츠
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

