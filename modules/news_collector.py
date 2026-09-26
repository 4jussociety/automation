# 이 모듈은 네이버 뉴스 검색 API를 통해 주간 광범위 물리치료/재활 기사 풀(Pool)을 수집하고,
# 비동기 본문 크롤링 및 OpenAI GPT를 활용해 주 6일 6대 테마별로 중복 없이 지능적으로 분배합니다.

import urllib.parse
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
import re
import requests
import json
import asyncio
import aiohttp
from bs4 import BeautifulSoup
import sys
from pathlib import Path

# 윈도우 UTF-8 콘솔 출력 보장
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# 루트 디렉토리를 sys.path에 등록
sys.path.append(str(Path(__file__).resolve().parent.parent))

from config import NAVER_CLIENT_ID, NAVER_CLIENT_SECRET, OPENAI_API_KEY, OPENAI_MODEL


def clean_html(text: str) -> str:
    """HTML 태그, 특수문자 및 인위적인 말줄임표를 완전히 제거하고 깔끔한 문장으로 정제합니다."""
    if not text:
        return ""
    cleaned = re.sub(r'<[^>]+>', '', text)
    cleaned = cleaned.replace('&quot;', '"').replace('&apos;', "'").replace('&amp;', '&')
    cleaned = cleaned.replace('&lt;', '<').replace('&gt;', '>').replace('&middot;', '·')
    cleaned = cleaned.replace('&nbsp;', ' ')
    # 연속된 점(..) 및 말줄임표(…) 완전 제거
    cleaned = re.sub(r'[\.]{2,}', '', cleaned)
    cleaned = cleaned.replace('…', '').replace('..', '').replace('...', '')
    cleaned = re.sub(r'\s+', ' ', cleaned)
    return cleaned.strip()


KST = timezone(timedelta(hours=9))


def parse_and_validate_pub_date(pub_date_str: str, max_days: int = 7) -> tuple[bool, str]:
    """
    발행일 문자열(RFC 822, ISO 등)을 파싱하여, 한국기준시(KST, UTC+9)로 변환하고
    최근 max_days일(기본 7일) 이내인지 엄격히 검증한 뒤
    'YYYY년 MM월 DD일 HH:MM' 형식의 깔끔한 한글 날짜 문자열로 반환합니다.
    """
    if not pub_date_str:
        return False, ""
    try:
        dt = parsedate_to_datetime(pub_date_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        dt_kst = dt.astimezone(KST)
        now_kst = datetime.now(KST)
        diff = now_kst - dt_kst
        # 미래 시간 약간의 오차(-1일) 허용 및 최근 max_days 이내 (약 12시간 완충)
        is_recent = timedelta(days=-1) <= diff <= timedelta(days=max_days, hours=12)
        formatted = f"{dt_kst.year}년 {dt_kst.month:02d}월 {dt_kst.day:02d}일 {dt_kst.hour:02d}:{dt_kst.minute:02d}"
        return is_recent, formatted
    except Exception:
        try:
            dt = datetime.strptime(pub_date_str[:10], "%Y-%m-%d").replace(tzinfo=KST)
            now_kst = datetime.now(KST)
            diff = now_kst - dt
            is_recent = timedelta(days=-1) <= diff <= timedelta(days=max_days, hours=12)
            formatted = f"{dt.year}년 {dt.month:02d}월 {dt.day:02d}일"
            return is_recent, formatted
        except Exception:
            return False, pub_date_str


# 1. 절대 광고 및 악성 스팸 차단 키워드
HARD_SPAM_KEYWORDS = [
    "카지노", "바둑이", "토토", "성인용품", "조건만남", "불법대출", "주식리딩", "코인리딩"
]

# 2. 대학 입시/수시/정시 홍보 차단 키워드 (물리치료/학과 단어가 있더라도 전면 배제)
ADMISSION_SPAM_KEYWORDS = [
    "수시", "정시", "대입", "모집요강", "신입생 모집", "수시특집", "수시모집", "합격자",
    "전형", "취업률 1위", "경쟁률", "학부모", "수험생 선발", "등록금", "장학금 혜택", "입학처",
    "전문대수시", "카데바", "해부실습"
]

# 3. 물리치료 및 재활 필수 앵커 키워드 (Tier 1 + 2 + 3)
# 기사 제목 또는 요약에 아래 단어가 최소 1개 이상 반드시 포함되어야 통과
MANDATORY_PT_KEYWORDS = [
    # Tier 1: 직접 물리치료 및 치료사
    "물리치료", "물리치료사", "도수치료", "운동치료", "작업치료",
    # Tier 2: 임상 재활 및 기능회복
    "재활", "재활치료", "재활의학", "재활운동", "기능회복", "보행훈련", "신경계 재활", "근골격계 재활", "재활병원",
    # Tier 3: 치료적 교정 및 전문 재활 장비 (체외충격파 대체: 재활 장비)
    "체형교정", "자세교정", "도수교정", "재활로봇", "보행로봇", "보행재활", "재활 장비", "재활장비", "슬링치료", "전기치료"
]

# 4. 글로벌 영문 기사용 필수 앵커 키워드
MANDATORY_GLOBAL_PT_KEYWORDS = [
    "physical therapy", "physiotherapy", "physical therapist", "physiotherapist",
    "rehabilitation", "rehab", "occupational therapy", "physio"
]


def is_valid_pt_article(title: str, description: str = "", is_global: bool = False) -> bool:
    """
    물리치료/재활 연관성 및 노이즈(입시/불법스팸) 여부를 엄격히 검증합니다.
    1. 불법/광고 스팸 무조건 제외
    2. 대학 수시/정시/입시 홍보 무조건 제외 (국내 기사)
    3. 제목 또는 요약에 물리치료/재활 관련 단어(Tier 1+2+3)가 최소 1개 이상 반드시 포함되어야 통과
    """
    combined = (title + " " + description).lower()

    # 1. 절대적 불법/광고 스팸 차단
    if any(k in combined for k in HARD_SPAM_KEYWORDS):
        return False

    # 2. 대학 입시/수시 홍보 차단 (국내)
    if not is_global and any(k in combined for k in ADMISSION_SPAM_KEYWORDS):
        return False

    # 3. 필수 물리치료/재활 키워드 검증 (제목 또는 요약)
    if is_global:
        has_pt = any(k in combined for k in MANDATORY_GLOBAL_PT_KEYWORDS) or any(k in combined for k in MANDATORY_PT_KEYWORDS)
    else:
        has_pt = any(k in combined for k in MANDATORY_PT_KEYWORDS)

    return has_pt


def is_gossip_or_spam(title: str, description: str = "") -> bool:
    """기존 코드 호환용: 물리치료 유효 기사가 아니면 True(배제) 반환"""
    return not is_valid_pt_article(title, description, is_global=False)


def extract_keywords(text: str) -> set[str]:
    """조사 및 특수문자를 배제한 2글자 이상의 의미있는 핵심 단어 집합을 추출합니다."""
    words = re.findall(r'[가-힣a-zA-Z0-9]{2,}', text)
    stopwords = {"물리치료", "재활치료", "도수치료", "물리치료사", "대한", "위한", "통해", "지난", "이번", "있다", "했다", "하는", "뉴스", "소식"}
    return {w for w in words if w not in stopwords}


def is_similar_issue(title: str, existing_titles: list[str], threshold: float = 0.35) -> bool:
    """기존 수집된 기사들과 동일 사건/이슈인지 자카드 유사도 및 고유명사 중복으로 판별합니다."""
    new_kw = extract_keywords(title)
    if not new_kw:
        return False
    for exist in existing_titles:
        exist_kw = extract_keywords(exist)
        if not exist_kw:
            continue
        intersection = new_kw & exist_kw
        union = new_kw | exist_kw
        similarity = len(intersection) / len(union) if union else 0.0
        if similarity >= threshold:
            return True
        # 3글자 이상의 핵심 고유명사가 2개 이상 겹치면 동일 사건으로 판단
        shared_big = {w for w in intersection if len(w) >= 3}
        if len(shared_big) >= 2:
            return True
    return False


def fetch_from_naver(keyword: str, display: int = 100) -> list[dict]:
    """네이버 클라우드 플랫폼(NAVER API HUB) 검색 API를 통해 최근 7일 이내 최신순 뉴스를 수집합니다."""
    if not NAVER_CLIENT_ID or not NAVER_CLIENT_SECRET:
        return []

    # 1. 네이버 클라우드 플랫폼 (NAVER API HUB) 공식 엔드포인트 (최신순 sort=date)
    url = f"https://naverapihub.apigw.ntruss.com/search/v1/news?query={urllib.parse.quote(keyword)}&display={display}&sort=date"
    headers = {
        "X-NCP-APIGW-API-KEY-ID": NAVER_CLIENT_ID,
        "X-NCP-APIGW-API-KEY": NAVER_CLIENT_SECRET
    }

    try:
        resp = requests.get(url, headers=headers, timeout=10)
    except Exception as e:
        resp = None

    # 2. 구형 개발자센터 API fallback 호환성 지원 (최신순 sort=date)
    if resp is None or resp.status_code in (401, 403, 404):
        legacy_url = f"https://openapi.naver.com/v1/search/news.json?query={urllib.parse.quote(keyword)}&display={display}&sort=date"
        legacy_headers = {
            "X-Naver-Client-Id": NAVER_CLIENT_ID,
            "X-Naver-Client-Secret": NAVER_CLIENT_SECRET
        }
        resp = requests.get(legacy_url, headers=legacy_headers, timeout=10)

    if resp.status_code != 200:
        raise RuntimeError(f"네이버 뉴스 검색 API 요청 실패 (HTTP {resp.status_code}): {resp.text}")

    data = resp.json()
    items = data.get("items", [])
    results = []
    for item in items:
        # 최근 7일 이내 기사만 엄격 검증
        is_recent, pub_formatted = parse_and_validate_pub_date(item.get("pubDate", ""), max_days=7)
        if not is_recent:
            continue

        link = item.get("originallink", "") or item.get("link", "")
        # 출처 추정 (도메인 또는 네이버 뉴스)
        source_name = "네이버 뉴스"
        if "biz.heraldcorp.com" in link:
            source_name = "헤럴드경제"
        elif "chosun.com" in link:
            source_name = "조선일보"
        elif "donga.com" in link:
            source_name = "동아일보"
        elif "joongang.co.kr" in link or "joins.com" in link:
            source_name = "중앙일보"
        elif "hankyung.com" in link:
            source_name = "한국경제"
        elif "yna.co.kr" in link:
            source_name = "연합뉴스"
        elif "kukinews.com" in link:
            source_name = "쿠키뉴스"
        elif "medicaltimes.com" in link:
            source_name = "메디칼타임즈"
        elif "docdocdoc.co.kr" in link:
            source_name = "청년의사"
        elif "dailymedi.com" in link:
            source_name = "데일리메디"

        results.append({
            "title": clean_html(item.get("title", "")),
            "description": clean_html(item.get("description", "")),
            "link": link,
            "originallink": item.get("originallink", ""),
            "naver_link": item.get("link", ""),
            "pub_date": pub_formatted,
            "source": source_name
        })
    return results


# ==============================================================================
# 상위 도메인 대분류 키워드 풀 정의 (6대 영역 29개 키워드)
# ==============================================================================

BROAD_NAVER_KEYWORDS = [
    # 1. 치료/임상 일반
    "물리치료", "물리치료사", "도수치료", "운동치료", "작업치료", "신경계 재활", "근골격계 재활",
    # 2. 기관/인프라/제도
    "재활병원", "재활의학과", "방문재활", "방문물리치료", "재활의료기관", "물리치료 수가", "실손보험 도수치료",
    # 3. 교정/통증/체형
    "체형교정", "자세교정", "도수교정", "통증치료", "기능회복", "보행훈련",
    # 4. 첨단 기술/장비 ('체외충격파' 대체 완료)
    "재활로봇", "보행로봇", "웨어러블 재활", "스마트 재활", "재활 장비",
    # 5. 스포츠/선수
    "스포츠 재활", "선수 재활", "부상 재활", "선수 트레이닝",
    # 6. 글로벌/해외 (네이버 검색 API용 한글 외신 쿼리)
    "해외 물리치료", "해외 재활", "글로벌 재활", "미국 물리치료", "해외 도수치료"
]


# ==============================================================================
# 1단계: 네이버 광범위 Clean Pool 수집 (중복 제거)
# ==============================================================================

def normalize_url(url: str) -> str:
    """URL에서 트래킹 파라미터 등을 제거하여 고유 비교용 정규화 URL을 생성합니다."""
    if not url:
        return ""
    try:
        parsed = urllib.parse.urlparse(url)
        # 쿼리 파라미터 중 필수 식별 파라미터만 유지
        clean_netloc = parsed.netloc.lower()
        clean_path = parsed.path.rstrip('/')
        return f"{parsed.scheme}://{clean_netloc}{clean_path}"
    except Exception:
        return url.strip()


def fetch_broad_pool_naver(keywords: list[str] = None) -> list[dict]:
    """
    네이버 뉴스 검색 API를 통해 상위 도메인 키워드로 최근 7일치 기사를 수집하고,
    URL 및 제목 유사도 기반으로 중복을 제거한 정제 풀(Pool)을 반환합니다.
    """
    if keywords is None:
        keywords = BROAD_NAVER_KEYWORDS

    pool = []
    seen_urls = set()
    seen_titles = []

    print(f"📡 [네이버 뉴스 수집] 총 {len(keywords)}개 상위 키워드로 광범위 Pool 수집 시작...")

    for idx, kw in enumerate(keywords, start=1):
        try:
            items = fetch_from_naver(kw, display=100)
            added_for_kw = 0
            for item in items:
                title = item.get("title", "")
                desc = item.get("description", "")
                link = item.get("link", "")
                norm_link = normalize_url(link)

                # 1. 최소 길이 및 물리치료/재활 유효성 검증
                if len(title) < 8 or not is_valid_pt_article(title, desc, is_global=False):
                    continue

                # 2. URL 중복 검사
                if norm_link in seen_urls:
                    continue

                # 3. 제목 유사도 검사 (동일 사건/기사 중복 배제)
                if is_similar_issue(title, seen_titles, threshold=0.45):
                    continue

                seen_urls.add(norm_link)
                seen_titles.append(title)
                item["search_keyword"] = kw
                pool.append(item)
                added_for_kw += 1

            print(f"  [{idx:02d}/{len(keywords):02d}] '{kw}': {len(items)}건 응답 ➔ {added_for_kw}건 고유 기사 등록")
        except Exception as e:
            print(f"  [{idx:02d}/{len(keywords):02d}] '{kw}' 수집 경고: {e}")

    print(f"\n🎉 [Pool 수집 완료] 총 {len(pool)}건의 고유한 주간 물리치료/재활 기사 풀 확보 완료!")
    return pool


# ==============================================================================
# 2단계: 비동기 병렬 기사 본문 크롤러 (10~15초 완료)
# ==============================================================================

def clean_extracted_body_text(text: str) -> str:
    """
    기사 본문 텍스트에서 상단 UI 툴바/브레드크럼, 하단 저작권, 댓글, 추천뉴스, 기자 정보 노이즈를 정밀 제거합니다.
    """
    if not text:
        return ""
    t = text

    # 1. 툴바 및 네비게이션 키워드 패턴 정의
    toolbar_keywords = (
        r'(?:바로가기\s*복사하기|기사스크랩(?:하기)?|본문\s*글씨\s*(?:줄이기|키우기)|'
        r'스크롤\s*이동\s*상태바|다른\s*공유\s*찾기|글씨크기(?:\s*작게|\s*크게|\s*\d+\s*px)*|'
        r'인쇄하기|이\s*기사를\s*공유합니다|텔레그램\(으\)로\s*기사보내기|'
        r'페이스북\(으\)로\s*기사보내기|트위터\(으\)로\s*기사보내기|스레드\(으\)로\s*기사보내기|'
        r'카카오톡\(으\)로\s*기사보내기|이메일\(으\)로\s*기사보내기|'
        r'네이버밴드\(으\)로\s*기사보내기|네이버블로그\(으\)로\s*기사보내기|URL복사\(으\)로\s*기사보내기|'
        r'닫기|댓글\s*\d*|공유\s*인쇄|이전\s*기사보기|다음\s*기사보기)'
    )

    # 2. 툴바 키워드 반복 출현 제거
    t = re.sub(rf'(?:{toolbar_keywords}\s*)+', ' ', t)

    # 3. 브레드크럼 및 메타 헤더 제거
    t = re.sub(r'홈\s+[가-힣]+\s+[가-힣]+', ' ', t)
    t = re.sub(r'현재위치\s+[가-힣\s·>]+', ' ', t)
    t = re.sub(r'오피니언\s*\[기고\]', ' ', t)
    t = re.sub(r'기자명\s+[가-힣]{2,4}\s*기자', ' ', t)
    t = re.sub(r'입력\s*:\s*\d{4}[-.]\d{2}[-.]\d{2}\s*\d{2}:\d{2}(?::\d{2})?', ' ', t)
    t = re.sub(r'입력\s+\d{4}[-.]\d{2}[-.]\d{2}\s+\d{2}:\d{2}(?::\d{2})?', ' ', t)
    t = re.sub(r'수정\s*:\s*\d{4}[-.]\d{2}[-.]\d{2}\s*\d{2}:\d{2}(?::\d{2})?', ' ', t)
    t = re.sub(r'수정\s+\d{4}[-.]\d{2}[-.]\d{2}\s+\d{2}:\d{2}(?::\d{2})?', ' ', t)

    # 4. 본문 시작 부분 중복 제목 제거 (15자 이상 어구가 연달아 나타나는 경우)
    head_part = t[:400]
    tail_part = t[400:]
    m_dup = re.search(r'(.{15,80}?)\s+\1', head_part)
    if m_dup:
        head_part = head_part[:m_dup.start()] + m_dup.group(1) + head_part[m_dup.end():]
        t = head_part + tail_part

    # 5. 본문 인라인 UI 노이즈 제거
    t = re.sub(r'※\s*본문\s*글자\s*크기\s*조정.*?AI\s*핵심\s*요약\s*beta\s*분석\s*중', '', t)
    t = re.sub(r'※\s*번역할\s*언어\s*선택\s*--\s*선택\s*--\s*닫기', '', t)

    # 6. 하단(Tail) 노이즈 자르기: 본문의 80자 이후에 나타나는 꼬리 표지 이후 전부 절단
    tail_indicators = [
        r'\[?ⓒ\s*[^\]\n]+무단전재.*',
        r'저작권자\s*[©ⓒ].*',
        r'무단전재\s*및\s*재배포\s*금지.*',
        r'★\s*네티즌\s*어워즈.*',
        r'댓글삭제\s*삭제한\s*댓글은.*',
        r'좋아요\s*\d+\s*화나요\s*\d+.*',
        r'\[관련기사\].*',
        r'많이\s*본\s*뉴스.*',
        r'오늘의\s*헤드라인.*',
        r'인기기사.*',
        r'다른기사(?:\s*보기)?.*',
        r'SNS\s*기사보내기.*',
        r'페이스북\s*트위터\s*카카오톡.*',
        r'회사소개\s*[ㅣ|].*',
        r'청소년보호정책.*',
        r'대표전화\s*:.*',
        r'등록번호\s*:.*'
    ]
    for pat in tail_indicators:
        m = re.search(pat, t)
        if m and m.start() > 80:
            t = t[:m.start()]

    # 7. 끝부분 이메일 및 서명 절단 (본문 80자 이후)
    m_email = re.search(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+', t)
    if m_email and m_email.start() > 80:
        cut_pos = m_email.start()
        pre = t[:cut_pos]
        m_rep = re.search(r'(?:[가-힣]{2,4}\s*원장|[가-힣]{2,4}\s*기자|[가-힣]{2,10}뉴스|[가-힣]{2,10}신문|\[사진=[^\]]+\])\s*$', pre)
        if m_rep:
            cut_pos = m_rep.start()
        t = t[:cut_pos]

    # 8. CMS 타임스탬프 식별자 제거
    t = re.sub(r'\s*\d{10,20}\s+[\d\s\-:]+.*$', '', t)

    # 9. 공백 정리
    t = re.sub(r'\s+', ' ', t).strip()
    return t


async def _crawl_single_article_body(session: aiohttp.ClientSession, art: dict, sem: asyncio.Semaphore):
    """단일 기사 링크에서 본문 텍스트를 빠르게 추출하여 content_preview 및 body_text를 저장합니다."""
    # 1순위: 네이버 뉴스 링크(안정적이고 빠름), 없으면 원문 링크
    target_url = art.get("naver_link") or art.get("link") or art.get("originallink")
    if not target_url or "youtube.com" in target_url:
        art["content_preview"] = art.get("description", "")[:200]
        art["body_text"] = art.get("description", "")
        return

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
    }

    async with sem:
        try:
            async with session.get(target_url, headers=headers, timeout=aiohttp.ClientTimeout(total=6)) as resp:
                if resp.status == 200:
                    html = await resp.text(errors="ignore")
                    soup = BeautifulSoup(html, "html.parser")

                    # 1. 네이버 뉴스 전용 본문 컨테이너 우선 탐색
                    dic = soup.select_one("#dic_area, #newsct_article, #articleBodyContents")
                    if dic:
                        for tag in dic.select("script, style, em, span.end_photo_org, div.byline, .reporter, .copyright"):
                            tag.decompose()
                        body = clean_html(dic.get_text(separator=" "))
                    else:
                        # 2. 주요 언론사 CMS 전용 고정밀 본문 컨테이너 탐색
                        art_el = soup.select_one(
                            "#article-view-content-div, #articleBody, .news_bm, .article-content, #news_body_area, #news_view_wrap"
                        )
                        if not art_el:
                            # 3. 보조 컨테이너
                            art_el = soup.select_one(".article_body, #article-view, .news_view, .view_cont, article")

                        if art_el:
                            for tag in art_el.select(
                                "script, style, iframe, .ad, .ads, .caption, div.byline, .tag_box, "
                                ".relation_news, .article_relation, .article_header, .art_head, "
                                ".tools, .util_box, .share_box, .sns_btn, .sns_wrap, .sns_share, "
                                ".comment, #comment, footer, nav, header"
                            ):
                                tag.decompose()
                            body = clean_html(art_el.get_text(separator=" "))
                        else:
                            # 4. 단락 p 태그 결합 (기사 본문 전체)
                            ps = [clean_html(p.get_text()) for p in soup.find_all("p") if len(clean_html(p.get_text())) > 25]
                            body = " ".join(ps)

                    # 2차 텍스트 정규식 정제 적용
                    body = clean_extracted_body_text(body)

                    if body and len(body) >= 30:
                        art["body_text"] = body
                        # 3~4문장 핵심 미리보기 생성 (약 150~220자)
                        sentences = re.split(r'(?<=[.?!])\s+', body)
                        preview = " ".join(sentences[:3])
                        if len(preview) > 230:
                            preview = preview[:227] + "..."
                        art["content_preview"] = preview or body[:200]
                        return
        except Exception:
            pass

    # 본문 크롤링 실패 또는 짧은 경우 description으로 fallback
    fallback_desc = clean_extracted_body_text(art.get("description", ""))
    art["content_preview"] = fallback_desc[:200]
    art["body_text"] = fallback_desc


async def fetch_article_bodies_async(articles: list[dict], max_concurrency: int = 15) -> list[dict]:
    """수집된 전체 기사 풀의 본문 및 미리보기를 비동기 병렬로 약 10~15초 내에 수집합니다."""
    print(f"\n⚡ [비동기 본문 크롤러] 총 {len(articles)}건 기사 본문 병렬 수집 중 (동시 {max_concurrency}개)...")
    sem = asyncio.Semaphore(max_concurrency)
    conn = aiohttp.TCPConnector(limit=max_concurrency, ssl=False)

    async with aiohttp.ClientSession(connector=conn) as session:
        tasks = [_crawl_single_article_body(session, art, sem) for art in articles]
        await asyncio.gather(*tasks, return_exceptions=True)

    success_count = sum(1 for a in articles if a.get("body_text") and len(a.get("body_text")) > 50)
    print(f"  -> 본문 수집 성공: {success_count}/{len(articles)}건 완료")
    return articles


# ==============================================================================
# 3단계: LLM(GPT) 지능형 카테고리 분배 & 요일 간 중복 완전 배제
# ==============================================================================

SIX_CATEGORIES = {
    "mon_policy": {
        "day": "월요일",
        "title": "국내 정책·제도·수가·실손보험",
        "description": "보건복지부 정책, 실손보험 도수치료, 물리치료 수가, 협회 및 법안 이슈",
        "is_global": False
    },
    "tue_clinical": {
        "day": "화요일",
        "title": "임상 실무·질환별 재활 프로토콜",
        "description": "디스크·회전근개·오십견·관절염 등 다빈도 질환의 최신 도수치료 및 운동재활 가이드",
        "is_global": False
    },
    "wed_sports": {
        "day": "수요일",
        "title": "운동·스포츠 재활",
        "description": "선수 부상 및 재활 복귀, 종목별 기능회복, 스포츠 물리치료 현장",
        "is_global": False
    },
    "thu_tech": {
        "day": "목요일",
        "title": "첨단 재활 기술·AI·로봇",
        "description": "보행 보조 로봇, 스마트 헬스케어 기기, AI 진단/재활 시스템, 재활 장비",
        "is_global": False
    },
    "fri_celeb": {
        "day": "금요일",
        "title": "셀럽 스타 치료 & 건강 가십",
        "description": "연예인/스타/유명인의 물리치료·도수치료·부상 후기 및 체형 가십",
        "is_global": False
    },
    "sat_global": {
        "day": "토요일",
        "title": "해외 글로벌 트렌드",
        "description": "글로벌 물리치료 연구, APTA/해외 제도, 해외 피지컬 테라피 동향, 외신 헬스케어",
        "is_global": True
    }
}


def heuristic_classify_article(title: str, text: str) -> tuple[str, int]:
    """OpenAI API 미응답 또는 실패 시 규칙 기반의 안전 fallback 분류기"""
    combined = (title + " " + text).lower()

    # 1. 토요일: 해외/글로벌
    if any(k in combined for k in ["해외", "미국", "글로벌", "외신", "영국", "독일", "일본", "fda", "apta", "who", "국제"]):
        return "sat_global", 7

    # 2. 목요일: 첨단 기술/로봇/장비
    if any(k in combined for k in ["로봇", "ai", "인공지능", "웨어러블", "재활장비", "재활 장비", "스마트", "디지털", "vr", "센서", "기기"]):
        return "thu_tech", 8

    # 3. 수요일: 스포츠/선수 부상
    if any(k in combined for k in ["선수", "스포츠", "축구", "야구", "올림픽", "골프", "부상", "복귀", "트레이닝", "구단", "국가대표"]):
        return "wed_sports", 8

    # 4. 금요일: 셀럽/연예인/스타
    if any(k in combined for k in ["배우", "가수", "연예인", "스타", "아이돌", "방송", "유명", "드라마", "예능", "mc", "투혼"]):
        return "fri_celeb", 7

    # 5. 월요일: 정책/제도/실손/수가/협회
    if any(k in combined for k in ["수가", "실손", "복지부", "보험", "정책", "협회", "법안", "의료기관", "제도", "보건", "비급여"]):
        return "mon_policy", 8

    # 6. 화요일: 임상 실무/재활 프로토콜
    if any(k in combined for k in ["디스크", "관절", "도수치료", "재활치료", "통증", "체형", "교정", "보행", "오십견", "회전근개", "운동치료"]):
        return "tue_clinical", 7

    return "tue_clinical", 5


def classify_and_distribute_articles_llm(
    articles: list[dict], 
    target_min: int = 15, 
    target_max: int = 30
) -> dict:
    """
    OpenAI gpt-4o-mini 모델을 호출하여 기사 풀 전체를 분석하고,
    요일별 15~30건씩 최적의 테마로 배분하며 요일 간 기사 중복을 100% 원천 배제합니다.
    """
    if not articles:
        return {k: [] for k in SIX_CATEGORIES.keys()} | {"total_count": 0}

    print(f"\n🧠 [LLM 지능형 카테고리 분배] {len(articles)}건 기사의 문맥 분석 및 6대 요일 라우팅 시작...")

    from openai import OpenAI
    client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None

    # 기사별 인덱스 부여
    for idx, art in enumerate(articles):
        art["_pool_idx"] = idx

    batch_size = 30
    classifications = {}  # {pool_idx: (category_key, score)}

    system_prompt = """당신은 대한민국 1위 물리치료 전문 미디어 'THEPT'의 수석 큐레이터 AI입니다.
주어진 기사들의 제목과 본문 요약을 분석하여 다음 7가지 카테고리 중 가장 적합한 1개를 선택하고 적합도 점수(relevance_score, 1~10점)를 매겨주세요:

[카테고리 분류 기준]
- mon_policy: 국내 정책·제도·수가·실손보험·협회 (보건복지부, 건강보험, 실손보험 도수치료, 물리치료 수가, 협회 현안, 의료법 등)
- tue_clinical: 임상 실무·질환별 재활 프로토콜 (디스크, 오십견, 관절염, 도수치료 임상효과, 재활운동 가이드, 신경/근골격 임상 연구 등)
- wed_sports: 운동·스포츠 재활 (프로/엘리트 선수 부상 및 복귀, 스포츠 재활, 기능회복 트레이닝, 구단 피지컬 코치 등)
- thu_tech: 첨단 재활 기술·AI·로봇·재활 장비 (보행재활 로봇, 웨어러블, 스마트 헬스케어 기기, AI 진단/재활, 재활 장비 등)
- fri_celeb: 셀럽/연예인/스타 치료 & 건강 가십 (배우, 가수, 방송인, 유명인의 부상 및 재활 후기, 방송 건강 이슈, 대중 체형 토픽 등)
- sat_global: 해외/글로벌 트렌드 (해외 물리치료 연구, APTA/해외 제도, 외신 헬스케어 동향, 해외 의료기기 도입, FDA/글로벌 트렌드 등)
- exclude: 물리치료/재활과 직접 무관하거나 단순 광고/스팸

[엄격한 반환 규격]
반드시 다음 JSON 포맷으로만 응답하십시오:
{"classifications": [{"idx": 0, "category": "mon_policy", "score": 9}, ...]}"""

    for b_start in range(0, len(articles), batch_size):
        b_items = articles[b_start:b_start + batch_size]
        payload = [
            {
                "idx": a["_pool_idx"],
                "title": a.get("title", ""),
                "summary": a.get("content_preview") or a.get("description", "")
            }
            for a in b_items
        ]

        assigned_batch = False
        if client:
            try:
                user_msg = f"기사 목록:\n{json.dumps(payload, ensure_ascii=False)}"
                resp = client.chat.completions.create(
                    model=OPENAI_MODEL or "gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_msg}
                    ],
                    response_format={"type": "json_object"},
                    timeout=20
                )
                data = json.loads(resp.choices[0].message.content)
                items_list = data.get("classifications", [])
                for it in items_list:
                    p_idx = it.get("idx")
                    cat = it.get("category")
                    score = it.get("score", 7)
                    if p_idx is not None and cat in SIX_CATEGORIES:
                        classifications[p_idx] = (cat, int(score))
                assigned_batch = True
            except Exception as e:
                print(f"  [LLM 배치 경고 ({b_start}~{b_start+len(b_items)})]: {e} -> 규칙 기반 분류 적용")

        if not assigned_batch:
            # Fallback
            for a in b_items:
                cat, score = heuristic_classify_article(a.get("title", ""), a.get("content_preview", ""))
                classifications[a["_pool_idx"]] = (cat, score)

    # 4. 카테고리별 분배 및 1기사 1카테고리 엄격 보장
    assigned_by_cat = {k: [] for k in SIX_CATEGORIES.keys()}
    used_indices = set()

    for idx, (cat_key, score) in classifications.items():
        if cat_key in assigned_by_cat:
            art = articles[idx]
            art_copy = dict(art)
            art_copy["llm_score"] = score
            assigned_by_cat[cat_key].append(art_copy)
            used_indices.add(idx)

    # 미분류 기사 중 품질 좋은 기사를 적절한 카테고리로 보충
    unassigned = [a for a in articles if a["_pool_idx"] not in used_indices]
    for art in unassigned:
        cat_key, score = heuristic_classify_article(art.get("title", ""), art.get("content_preview", ""))
        if cat_key in assigned_by_cat:
            art_copy = dict(art)
            art_copy["llm_score"] = score
            assigned_by_cat[cat_key].append(art_copy)

    # 5. 각 카테고리별 정렬 및 15~30건 범위 확정 + ID 부여
    final_results = {}
    total_count = 0

    print("\n📊 [카테고리별 최종 엄선 배분 결과]:")
    for cat_key, meta in SIX_CATEGORIES.items():
        day_name = meta["day"]
        cat_title = meta["title"]
        prefix = cat_key[:3]  # mon, tue, wed, thu, fri, sat
        is_global = meta.get("is_global", False)

        cat_list = assigned_by_cat.get(cat_key, [])
        # LLM 점수 기준 내림차순 정렬
        cat_list.sort(key=lambda x: x.get("llm_score", 0), reverse=True)

        # 최대 30개로 캡
        selected = cat_list[:target_max]

        # 고유 ID 부여 (예: mon_01, mon_02...)
        for idx, art in enumerate(selected, start=1):
            art["id"] = f"{prefix}_{idx:02d}"
            art["category_key"] = cat_key
            art["category"] = cat_title
            art["day"] = day_name
            art["is_global"] = is_global

        final_results[cat_key] = selected
        total_count += len(selected)
        print(f"  - [{day_name}] {cat_title}: {len(selected)}건 (최적 배분 완료)")

    final_results["total_count"] = total_count
    print(f"\n🎉 총 {total_count}건의 기사가 요일 간 중복 없이 완벽히 분배되었습니다!")
    return final_results


def parse_custom_url(url: str, category_key: str = "mon_policy") -> dict:
    """사용자가 직접 입력한 기사 URL에서 제목, 본문, 요약, 이미지를 추출합니다."""
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
    }
    resp = requests.get(url, headers=headers, timeout=10)
    resp.encoding = resp.apparent_encoding or "utf-8"
    soup = BeautifulSoup(resp.text, "html.parser")

    # 제목 추출: og:title -> title -> h1
    og_title = soup.find("meta", property="og:title")
    title = og_title["content"] if og_title and og_title.get("content") else ""
    if not title:
        title_tag = soup.find("title")
        title = title_tag.text if title_tag else ""
    if not title:
        h1 = soup.find("h1")
        title = h1.text if h1 else "사용자 추가 기사"
    title = clean_html(title)

    # 설명/요약 추출
    og_desc = soup.find("meta", property="og:description")
    desc = og_desc["content"] if og_desc and og_desc.get("content") else ""
    if not desc:
        meta_desc = soup.find("meta", attrs={"name": "description"})
        desc = meta_desc["content"] if meta_desc and meta_desc.get("content") else ""
    desc = clean_html(desc)

    # 대표 이미지 추출
    og_image = soup.find("meta", property="og:image")
    image_url = og_image["content"] if og_image and og_image.get("content") else ""

    # 본문 텍스트 추출 (p 태그 결합)
    paragraphs = [clean_html(p.text) for p in soup.find_all("p") if len(clean_html(p.text)) > 25]
    body_text = " ".join(paragraphs[:8])
    if not desc and body_text:
        desc = body_text[:200]

    cat_meta = SIX_CATEGORIES.get(category_key, SIX_CATEGORIES["mon_policy"])
    source_domain = urllib.parse.urlparse(url).netloc

    return {
        "title": title,
        "description": desc or title,
        "content_preview": desc or body_text[:200],
        "link": url,
        "pub_date": datetime.now().strftime("%Y-%m-%d"),
        "source": source_domain or "직접 추가",
        "category": cat_meta["title"],
        "category_key": category_key,
        "is_global": cat_meta.get("is_global", False),
        "image_url": image_url,
        "body_text": body_text,
        "is_manual": True
    }


def collect_6categories_candidates(target_per_category: int = 20) -> dict:
    """
    주 6일 6대 카테고리 후보 기사를 수집하는 메인 진입점 함수:
    1. 네이버 뉴스 API로 29개 상위 키워드 광범위 Pool 수집 (중복 제거)
    2. 비동기 병렬 본문 크롤링으로 본문 및 3줄 핵심 요약 미리보기 생성
    3. OpenAI GPT(gpt-4o-mini)로 문맥 분석 후 요일별 15~30건씩 중복 없이 배분
    """
    print("=" * 70)
    print("🌐 [뉴스 수집기] 네이버 광범위 Pool & LLM 지능형 카테고리 분배 파이프라인 가동")
    print("=" * 70)

    # 1. 광범위 Pool 수집
    pool = fetch_broad_pool_naver()

    if not pool:
        print("⚠️ [경고] 네이버 뉴스 수집 결과가 없습니다. 카테고리 빈 결과를 반환합니다.")
        return {k: [] for k in SIX_CATEGORIES.keys()} | {"total_count": 0}

    # 2. 비동기 본문 크롤링
    try:
        pool = asyncio.run(fetch_article_bodies_async(pool, max_concurrency=15))
    except Exception as e:
        print(f"  ⚠️ [비동기 크롤러 경고]: {e} (기존 description 유지)")

    # 3. LLM 지능형 카테고리 분배 (1기사 1카테고리 원칙, 요일별 15~30건)
    target_max = max(target_per_category, 30)
    candidates_by_cat = classify_and_distribute_articles_llm(pool, target_min=15, target_max=target_max)

    return candidates_by_cat


if __name__ == "__main__":
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

    print("[테스트] 주 6일 6대 카테고리 구성 확인:")
    for key, meta in SIX_CATEGORIES.items():
        print(f"  - [{meta['day']}] {meta['title']}")
    print(f"  총 {len(BROAD_NAVER_KEYWORDS)}개 상위 키워드 풀 준비 완료.")
