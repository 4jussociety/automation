# 이 모듈은 네이버 뉴스 API 및 구글 뉴스 RSS를 통해 최신 물리치료 뉴스를 수집합니다.
# 수집 실패 또는 검색 결과 부재 시 fallback 없이 명확한 예외를 발생시킵니다.

import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
import re
import requests

import sys
from pathlib import Path

# 루트 디렉토리를 sys.path에 등록
sys.path.append(str(Path(__file__).resolve().parent.parent))

from config import NAVER_CLIENT_ID, NAVER_CLIENT_SECRET


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
    # Tier 3: 치료적 교정 및 전문 재활 장비
    "체형교정", "자세교정", "도수교정", "재활로봇", "보행로봇", "보행재활", "체외충격파", "슬링치료", "전기치료"
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
        # 영문 원문 키워드 또는 한국어 번역 키워드 검증
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


def fetch_from_naver(keyword: str, display: int = 20) -> list[dict]:
    """네이버 클라우드 플랫폼(NAVER API HUB) 검색 API를 통해 최근 7일 이내 최신순 뉴스를 수집합니다."""
    if not NAVER_CLIENT_ID or not NAVER_CLIENT_SECRET:
        return []

    # 1. 네이버 클라우드 플랫폼 (NAVER API HUB) 공식 엔드포인트 (최신순 sort=date)
    url = f"https://naverapihub.apigw.ntruss.com/search/v1/news?query={urllib.parse.quote(keyword)}&display={display}&sort=date"
    headers = {
        "X-NCP-APIGW-API-KEY-ID": NAVER_CLIENT_ID,
        "X-NCP-APIGW-API-KEY": NAVER_CLIENT_SECRET
    }

    resp = requests.get(url, headers=headers, timeout=10)

    # 2. 구형 개발자센터 API fallback 호환성 지원 (최신순 sort=date)
    if resp.status_code == 401 or resp.status_code == 403:
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

        results.append({
            "title": clean_html(item.get("title", "")),
            "description": clean_html(item.get("description", "")),
            "link": link,
            "pub_date": pub_formatted,
            "source": source_name
        })
    return results


def fetch_from_google_rss(keyword: str, max_items: int = 15) -> list[dict]:
    """구글 뉴스 RSS를 통해 최근 7일 이내 최신 뉴스를 수집합니다."""
    query_with_time = f"{keyword} when:7d"
    encoded_query = urllib.parse.quote(query_with_time)
    url = f"https://news.google.com/rss/search?q={encoded_query}&hl=ko&gl=KR&ceid=KR:ko"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    resp = requests.get(url, headers=headers, timeout=10)
    if resp.status_code != 200:
        raise RuntimeError(f"구글 뉴스 RSS 요청 실패 (HTTP {resp.status_code}): {url}")

    root = ET.fromstring(resp.content)
    channel = root.find("channel")
    if channel is None:
        raise RuntimeError(f"구글 뉴스 RSS 파싱 실패: channel 요소를 찾을 수 없습니다. (URL: {url})")

    results = []
    for item in channel.findall("item"):
        title_elem = item.find("title")
        desc_elem = item.find("description")
        link_elem = item.find("link")
        pub_elem = item.find("pubDate")
        source_elem = item.find("source")

        title = title_elem.text if title_elem is not None and title_elem.text else ""
        desc = desc_elem.text if desc_elem is not None and desc_elem.text else ""
        link = link_elem.text if link_elem is not None and link_elem.text else ""
        pub_date = pub_elem.text if pub_elem is not None and pub_elem.text else ""
        source = source_elem.text if source_elem is not None and source_elem.text else "뉴스"

        is_recent, pub_formatted = parse_and_validate_pub_date(pub_date, max_days=7)
        if not is_recent:
            continue

        results.append({
            "title": clean_html(title),
            "description": clean_html(desc),
            "link": link,
            "pub_date": pub_formatted,
            "source": source
        })
        if len(results) >= max_items:
            break

    return results


def fetch_from_google_rss_global(keyword: str, max_items: int = 15) -> list[dict]:
    """구글 글로벌 뉴스 RSS에서 최근 7일 이내 영문 물리치료 기사를 수집하고 한국어로 번역합니다."""
    from modules.translator import translate_to_korean

    query_with_time = f"{keyword} when:7d"
    encoded_query = urllib.parse.quote(query_with_time)
    url = f"https://news.google.com/rss/search?q={encoded_query}&hl=en-US&gl=US&ceid=US:en"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    resp = requests.get(url, headers=headers, timeout=10)
    if resp.status_code != 200:
        raise RuntimeError(f"구글 글로벌 RSS 요청 실패 (HTTP {resp.status_code}): {url}")

    root = ET.fromstring(resp.content)
    channel = root.find("channel")
    if channel is None:
        raise RuntimeError(f"구글 글로벌 RSS 파싱 실패: {url}")

    results = []
    for item in channel.findall("item"):
        title_elem = item.find("title")
        desc_elem = item.find("description")
        link_elem = item.find("link")
        pub_elem = item.find("pubDate")
        source_elem = item.find("source")

        title_en = clean_html(title_elem.text if title_elem is not None and title_elem.text else "")
        desc_en = clean_html(desc_elem.text if desc_elem is not None and desc_elem.text else "")
        link = link_elem.text if link_elem is not None and link_elem.text else ""
        pub_date = pub_elem.text if pub_elem is not None and pub_elem.text else ""
        source_name = source_elem.text if source_elem is not None and source_elem.text else "Global Media"

        # 최근 7일 이내 검증
        is_recent, pub_formatted = parse_and_validate_pub_date(pub_date, max_days=7)
        if not is_recent:
            continue

        # 불량 기사(에러 페이지, 404, 500 등) 필터링
        lower_t = title_en.lower()
        if len(title_en) < 12 or any(err in lower_t for err in ["error", "500", "404", "server error", "captcha"]):
            continue

        # 한국어로 번역
        title_ko = title_en
        desc_ko = desc_en
        try:
            if title_en:
                translated = translate_to_korean(title_en)
                if translated and not any(err in translated.lower() for err in ["error 500", "server error", "500.that"]):
                    title_ko = translated
            if desc_en:
                translated_desc = translate_to_korean(desc_en[:300])
                if translated_desc and not any(err in translated_desc.lower() for err in ["error 500", "server error", "500.that"]):
                    desc_ko = translated_desc
        except Exception as e:
            print(f"  [번역 경고] 영문 기사 번역 실패 ({title_en[:30]}...): {e}")

        results.append({
            "title": title_ko,
            "title_en": title_en,
            "description": desc_ko,
            "description_en": desc_en,
            "link": link,
            "pub_date": pub_formatted,
            "source": f"{source_name} (글로벌)",
            "category": "해외 연구/트렌드",
            "is_global": True
        })
        if len(results) >= max_items:
            break

    return results


def load_target_youtube_channels() -> list[dict]:
    """data/youtube_channels.json 파일에서 활성화된 추천 유튜브 채널 목록을 로드합니다."""
    import json
    from config import YOUTUBE_CHANNELS_FILE, DEFAULT_YOUTUBE_CHANNELS
    if YOUTUBE_CHANNELS_FILE.exists():
        try:
            with open(YOUTUBE_CHANNELS_FILE, "r", encoding="utf-8") as f:
                channels = json.load(f)
                return [c for c in channels if c.get("enabled", True)]
        except Exception as e:
            print(f"⚠️ [YouTube Channels] JSON 로드 실패, 기본 목록 사용: {e}")
    return DEFAULT_YOUTUBE_CHANNELS


def fetch_from_youtube(query: str, max_items: int = 5, max_days: int = 7) -> list[dict]:
    """
    YouTube Data API v3를 통해 최근 max_days일(기본 7일) 이내 최신 운동/재활 동영상을 수집합니다.
    - 고화질 썸네일, 제목, 설명글, 업로드 일시, 채널명 및 비디오 ID를 추출합니다.
    """
    from modules.youtube_uploader import YouTubeShortsUploader

    results = []
    try:
        uploader = YouTubeShortsUploader()
        service = uploader.get_service()
        if not service:
            return []

        now_dt = datetime.now(timezone.utc)
        published_after = (now_dt - timedelta(days=max_days)).strftime("%Y-%m-%dT%H:%M:%SZ")

        req = service.search().list(
            q=query,
            part="snippet",
            type="video",
            order="date",
            publishedAfter=published_after,
            maxResults=max_items
        )
        resp = req.execute()
        items = resp.get("items", [])

        for item in items:
            vid = item.get("id", {}).get("videoId")
            if not vid:
                continue
            snip = item.get("snippet", {})
            title = clean_html(snip.get("title", ""))
            desc = clean_html(snip.get("description", ""))
            channel_title = snip.get("channelTitle", "유튜브 채널")
            pub_date_raw = snip.get("publishedAt", "")

            is_recent, pub_formatted = parse_and_validate_pub_date(pub_date_raw, max_days=max_days)
            if not is_recent:
                continue

            # 고화질 썸네일 확보 (maxresdefault 우선, 없으면 hqdefault)
            thumbs = snip.get("thumbnails", {})
            img_url = (
                thumbs.get("maxres", {}).get("url") or
                thumbs.get("standard", {}).get("url") or
                thumbs.get("high", {}).get("url") or
                f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg"
            )

            results.append({
                "title": f"[{channel_title}] {title}",
                "description": desc or f"{channel_title} 채널의 최신 재활/운동 영상입니다.",
                "link": f"https://www.youtube.com/watch?v={vid}",
                "pub_date": pub_formatted,
                "source": f"유튜브 ({channel_title})",
                "image_url": img_url,
                "video_id": vid,
                "channel_name": channel_title,
                "is_youtube": True
            })
    except Exception as e:
        print(f"  [유튜브 검색 경고 ({query})]: {e}")

    return results


def collect_themed_batch(
    keywords: list[str],
    category: str,
    target_count: int = 3,
    existing_titles: list[str] = None
) -> list[dict]:
    """
    지정된 키워드 풀에서 네이버 API HUB(1순위) 및 구글 RSS를 통해 기사를 수집하고,
    가십/스팸 필터 및 자카드 유사도 기반 중복 배제를 거쳐 엄선된 기사 리스트를 반환합니다.
    """
    if existing_titles is None:
        existing_titles = []

    collected = []
    seen_in_batch = list(existing_titles)

    for kw in keywords:
        arts = []
        if NAVER_CLIENT_ID and NAVER_CLIENT_SECRET:
            try:
                arts = fetch_from_naver(kw, display=10)
            except Exception as e:
                print(f"  [네이버 검색 경고 ({kw})]: {e}")
        if not arts:
            arts = fetch_from_google_rss(kw, max_items=10)

        for a in arts:
            title = a["title"]
            desc = a.get("description", "")
            # 1. 길이 및 기본 유효성 검사
            if len(title) < 10:
                continue
            # 2. 연예 가십 및 단순 비전문 기사 필터링
            if is_gossip_or_spam(title, desc):
                continue
            # 3. 기존 수집된 기사들과의 중복/유사성 검사
            if is_similar_issue(title, seen_in_batch):
                continue

            a["is_global"] = False
            a["category"] = category
            collected.append(a)
            seen_in_batch.append(title)

            if len(collected) >= target_count:
                return collected

    return collected


def collect_weekly_3batches(
    domestic_keywords_a: list[str] = None,
    domestic_keywords_b: list[str] = None,
    global_keywords: list[str] = None
) -> dict:
    """
    주간 3대 브리핑 세트(배치 1, 2, 3)를 주제별로 완벽히 분리하고 중복 없이 총 9건의 기사를 엄선합니다.
    - 배치 1 (월 쇼츠 / 화 카드뉴스): 국내 물리치료 핵심 정책 & 제도 이슈 (수가, 실손보험, 정책 등)
    - 배치 2 (수 쇼츠 / 목 카드뉴스): 최신 재활 임상 연구 & 첨단 치료 기술 (로봇재활, 임상효과, 신경계 등)
    - 배치 3 (금 쇼츠 / 토 카드뉴스): 글로벌 물리치료 연구 & 해외 트렌드 (한국어 번역)
    """
    # 1. 배치 1 전용 키워드: 국내 정책 / 제도 / 수가 / 협회
    if domestic_keywords_a is None:
        domestic_keywords_a = [
            "물리치료사 정책",
            "도수치료 실손보험",
            "물리치료 수가",
            "재활의료기관 물리치료",
            "물리치료사 협회"
        ]

    # 2. 배치 2 전용 키워드: 임상 연구 / 첨단 기술 / 학술 / 논문
    if domestic_keywords_b is None:
        domestic_keywords_b = [
            "물리치료 임상 연구",
            "로봇 재활치료",
            "도수치료 임상 효과",
            "신경계 물리치료",
            "근골격계 재활치료"
        ]

    # 3. 배치 3 전용 키워드: 해외 글로벌 연구 / APTA
    if global_keywords is None:
        global_keywords = [
            "physical therapy rehabilitation",
            "sports physical therapy",
            "physiotherapy clinical research"
        ]

    # [배치 1 수집]: 국내 정책 & 제도 이슈 3건
    batch_1 = collect_themed_batch(
        keywords=domestic_keywords_a,
        category="국내 정책/제도",
        target_count=3,
        existing_titles=[]
    )
    if len(batch_1) < 3:
        # 백업 키워드 풀
        fallback_a = ["물리치료 제도", "물리치료 의료보험"]
        more_a = collect_themed_batch(fallback_a, "국내 정책/제도", 3 - len(batch_1), [a["title"] for a in batch_1])
        batch_1.extend(more_a)

    if len(batch_1) < 3:
        raise RuntimeError(f"배치 1 (국내 정책 이슈) 기사가 부족합니다. (수집: {len(batch_1)}건)")

    # [배치 2 수집]: 임상 재활 & 첨단 기술 이슈 3건 (배치 1의 기사와 절대 중복 불가)
    b1_titles = [a["title"] for a in batch_1]
    batch_2 = collect_themed_batch(
        keywords=domestic_keywords_b,
        category="임상 재활/연구",
        target_count=3,
        existing_titles=b1_titles
    )
    if len(batch_2) < 3:
        # 백업 키워드 풀
        fallback_b = ["재활치료 효과", "물리치료 학술"]
        more_b = collect_themed_batch(fallback_b, "임상 재활/연구", 3 - len(batch_2), b1_titles + [a["title"] for a in batch_2])
        batch_2.extend(more_b)

    if len(batch_2) < 3:
        raise RuntimeError(f"배치 2 (임상 연구 이슈) 기사가 부족합니다. (수집: {len(batch_2)}건)")

    # [배치 3 수집]: 해외 글로벌 연구 및 트렌드 3건
    batch_3 = []
    seen_global_titles = set()
    for kw in global_keywords:
        g_arts = fetch_from_google_rss_global(kw, max_items=5)
        for ga in g_arts:
            t = ga["title"]
            if t and t not in seen_global_titles and len(t) > 10:
                # 에러 문자열 및 중복 체크
                if not is_similar_issue(t, list(seen_global_titles)):
                    seen_global_titles.add(t)
                    batch_3.append(ga)
                    if len(batch_3) >= 3:
                        break
        if len(batch_3) >= 3:
            break

    if len(batch_3) < 3:
        raise RuntimeError(f"배치 3 (해외 글로벌 기사)가 부족합니다. (수집: {len(batch_3)}건)")

    total_count = len(batch_1) + len(batch_2) + len(batch_3)

    return {
        "batch_1": batch_1[:3],
        "batch_2": batch_2[:3],
        "batch_3": batch_3[:3],
        "total_collected": total_count,
        "all_domestic": batch_1 + batch_2,
        "all_global": batch_3
    }


# ==============================================================================
# 주 6일 6대 카테고리 체계 정의 및 100건 대량 수집 함수
# ==============================================================================

SIX_CATEGORIES = {
    "mon_policy": {
        "day": "월요일",
        "title": "국내 정책·제도·수가·실손보험",
        "description": "보건복지부 정책, 실손보험 도수치료, 물리치료 수가, 협회 및 법안 이슈",
        "keywords": [
            "도수치료 실손보험",
            "물리치료 수가",
            "물리치료 정책",
            "도수치료 비급여",
            "물리치료사 협회",
            "재활의료기관 물리치료",
            "실손보험 비급여 도수치료",
            "방문 물리치료",
            "물리치료 법안"
        ],
        "is_global": False
    },
    "tue_clinical": {
        "day": "화요일",
        "title": "임상 실무·질환별 재활 프로토콜",
        "description": "디스크·회전근개·오십견·관절염 등 다빈도 질환의 최신 도수치료 및 운동재활 가이드",
        "keywords": [
            "도수치료 효과",
            "회전근개 재활",
            "허리디스크 운동치료",
            "오십견 도수치료",
            "체형교정 운동치료",
            "거북목 교정치료",
            "근골격계 물리치료",
            "관절염 재활",
            "물리치료 임상"
        ],
        "is_global": False
    },
    "wed_sports": {
        "day": "수요일",
        "title": "운동·스포츠 재활",
        "description": "선수 부상 및 재활 복귀, 종목별 기능회복, 스포츠 물리치료 현장",
        "keywords": [
            "스포츠 물리치료",
            "선수 부상 재활",
            "선수 재활치료",
            "스포츠 재활훈련",
            "스포츠 도수치료",
            "선수 복귀 재활",
            "프로선수 물리치료",
            "기능회복 재활운동"
        ],
        "is_global": False
    },
    "thu_tech": {
        "day": "목요일",
        "title": "첨단 재활 기술·AI·로봇",
        "description": "보행 보조 로봇, 스마트 헬스케어 기기, AI 진단/재활 시스템",
        "keywords": [
            "보행 재활 로봇",
            "재활로봇 치료",
            "AI 물리치료",
            "스마트 재활치료",
            "웨어러블 재활로봇",
            "디지털 재활 치료 기기",
            "신경계 재활 로봇",
            "보행훈련 로봇 물리치료"
        ],
        "is_global": False
    },
    "fri_youtube": {
        "day": "금요일",
        "title": "운동/재활 유튜버 소식",
        "description": "인기 재활·운동 전문 유튜버 최신 영상 스크랩, 핵심 치료 팁 및 운동 이슈 브리핑",
        "keywords": [
            "물리치료사 유튜브",
            "재활운동 유튜버",
            "체형교정 스트레칭 유튜브",
            "도수치료 운동 팁",
            "피지컬갤러리 재활",
            "자세요정 스트레칭"
        ],
        "is_global": False,
        "is_youtube": True
    },
    "sat_global": {
        "day": "토요일",
        "title": "해외 글로벌 트렌드",
        "description": "글로벌 물리치료 연구, APTA/해외 제도, 해외 피지컬 테라피 동향",
        "keywords": [
            "physical therapy",
            "physiotherapy clinical",
            "sports physical therapy",
            "physical therapy rehabilitation",
            "physical therapist practice",
            "rehabilitation exercise physical therapy"
        ],
        "is_global": True
    }
}


def parse_custom_url(url: str, category_key: str = "mon_policy") -> dict:
    """사용자가 직접 입력한 기사 URL에서 제목, 본문, 요약, 이미지를 추출합니다."""
    from bs4 import BeautifulSoup
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


def collect_6categories_candidates(target_per_category: int = 17) -> dict:
    """
    주 6일 6대 카테고리별로 각 15~18건 내외, 총 최대 약 100건의 후보 뉴스를 수집합니다.
    물리치료/재활 필수 키워드가 포함되고 입시/스팸이 배제된 기사만 엄격히 수집합니다.
    """
    results_by_cat = {}
    global_seen_titles = []
    total_count = 0

    print("=" * 70)
    print("🌐 [뉴스 수집기] 물리치료/재활 특화 6대 카테고리 후보 뉴스 수집 시작")
    print("=" * 70)

    for cat_key, meta in SIX_CATEGORIES.items():
        day_name = meta["day"]
        cat_title = meta["title"]
        keywords = meta["keywords"]
        is_global = meta.get("is_global", False)
        prefix = cat_key[:3]  # mon, tue, wed, thu, fri, sat

        print(f"\n🔍 [{day_name}] {cat_title} 후보 수집 중...")
        cat_articles = []
        seen_in_cat = list(global_seen_titles)

        if is_global:
            # 글로벌 영문 RSS 수집 및 한국어 번역
            for kw in keywords:
                if len(cat_articles) >= target_per_category:
                    break
                try:
                    g_arts = fetch_from_google_rss_global(kw, max_items=10)
                    for ga in g_arts:
                        t = ga.get("title", "")
                        d = ga.get("description", "")
                        t_en = ga.get("title_en", "")
                        d_en = ga.get("description_en", "")
                        combined_all = f"{t} {d} {t_en} {d_en}"
                        if len(t) < 10 or not is_valid_pt_article(t, combined_all, is_global=True) or is_similar_issue(t, seen_in_cat):
                            continue
                        seen_in_cat.append(t)
                        global_seen_titles.append(t)
                        ga["category_key"] = cat_key
                        ga["category"] = cat_title
                        ga["day"] = day_name
                        cat_articles.append(ga)
                        if len(cat_articles) >= target_per_category:
                            break
                except Exception as e:
                    print(f"  - 글로벌 검색 실패 ({kw}): {e}")
        elif meta.get("is_youtube") or cat_key == "fri_youtube":
            # 금요일: 운동/재활 추천 유튜브 채널 및 영상 전문 스크랩
            channels = load_target_youtube_channels()
            print(f"  📺 [유튜브 채널 스크랩] 등록된 {len(channels)}개 추천 채널 및 영상 탐색 중...")
            
            # 1. 등록된 전문 채널별 최신 영상 우선 수집
            for ch in channels:
                if len(cat_articles) >= target_per_category:
                    break
                ch_query = ch.get("query", ch.get("name", ""))
                try:
                    yt_arts = fetch_from_youtube(ch_query, max_items=4)
                    for ya in yt_arts:
                        t = ya.get("title", "")
                        if len(t) < 5 or is_similar_issue(t, seen_in_cat):
                            continue
                        seen_in_cat.append(t)
                        global_seen_titles.append(t)
                        ya["category_key"] = cat_key
                        ya["category"] = cat_title
                        ya["day"] = day_name
                        cat_articles.append(ya)
                        if len(cat_articles) >= target_per_category:
                            break
                except Exception as e:
                    print(f"  - 유튜브 채널 검색 실패 ({ch.get('name')}): {e}")

            # 2. 재활/운동 유튜브 키워드 보충 수집
            for kw in keywords:
                if len(cat_articles) >= target_per_category:
                    break
                try:
                    yt_arts = fetch_from_youtube(kw, max_items=5)
                    for ya in yt_arts:
                        t = ya.get("title", "")
                        if len(t) < 5 or is_similar_issue(t, seen_in_cat):
                            continue
                        seen_in_cat.append(t)
                        global_seen_titles.append(t)
                        ya["category_key"] = cat_key
                        ya["category"] = cat_title
                        ya["day"] = day_name
                        cat_articles.append(ya)
                        if len(cat_articles) >= target_per_category:
                            break
                except Exception as e:
                    print(f"  - 유튜브 키워드 검색 실패 ({kw}): {e}")

            # 3. 유튜브 수집이 부족할 경우 네이버/구글 RSS 보완 수집
            if len(cat_articles) < target_per_category:
                for kw in keywords:
                    if len(cat_articles) >= target_per_category:
                        break
                    backup_arts = fetch_from_naver(f"{kw} 유튜브", display=10) or fetch_from_google_rss(f"{kw} 유튜브", max_items=10)
                    for a in backup_arts:
                        t = a.get("title", "")
                        d = a.get("description", "")
                        if len(t) < 8 or not is_valid_pt_article(t, d, is_global=False) or is_similar_issue(t, seen_in_cat):
                            continue
                        seen_in_cat.append(t)
                        global_seen_titles.append(t)
                        a["category_key"] = cat_key
                        a["category"] = cat_title
                        a["day"] = day_name
                        a["is_global"] = False
                        cat_articles.append(a)
                        if len(cat_articles) >= target_per_category:
                            break
        else:
            # 국내 네이버 및 구글 RSS 수집
            for kw in keywords:
                if len(cat_articles) >= target_per_category:
                    break
                arts = []
                if NAVER_CLIENT_ID and NAVER_CLIENT_SECRET:
                    try:
                        arts = fetch_from_naver(kw, display=20)
                    except Exception as e:
                        print(f"  - 네이버 API 경고 ({kw}): {e}")

                # 네이버 수집 건수가 부족할 경우 구글 RSS 보완 수집
                if len(arts) < 10:
                    try:
                        g_arts = fetch_from_google_rss(kw, max_items=15)
                        arts.extend(g_arts)
                    except Exception as e:
                        print(f"  - 구글 RSS 경고 ({kw}): {e}")

                for a in arts:
                    t = a.get("title", "")
                    d = a.get("description", "")
                    if len(t) < 8 or not is_valid_pt_article(t, d, is_global=False) or is_similar_issue(t, seen_in_cat):
                        continue
                    seen_in_cat.append(t)
                    global_seen_titles.append(t)
                    a["category_key"] = cat_key
                    a["category"] = cat_title
                    a["day"] = day_name
                    a["is_global"] = False
                    cat_articles.append(a)
                    if len(cat_articles) >= target_per_category:
                        break

        # 고유 ID 부여 (예: mon_01, mon_02 ...)
        for idx, art in enumerate(cat_articles, start=1):
            art["id"] = f"{prefix}_{idx:02d}"

        results_by_cat[cat_key] = cat_articles
        total_count += len(cat_articles)
        print(f"  -> {len(cat_articles)}건 엄선 수집 완료")

    results_by_cat["total_count"] = total_count
    print(f"\n🎉 총 {total_count}건의 6대 카테고리 후보 기사 수집 완료!")
    return results_by_cat


if __name__ == "__main__":
    import sys
    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding="utf-8")

    print("[테스트] 주간 3대 브리핑 세트(주제별 분리 수집 및 중복 배제) 실행 중...")
    batches = collect_weekly_3batches()
    print("\n✅ 배치 1 (월/화 - 국내 정책·제도 A, 3건):")
    for i, a in enumerate(batches["batch_1"], 1):
        print(f"   {i}. {a['title']} ({a['source']})")

    print("\n✅ 배치 2 (수/목 - 임상 연구·첨단 B, 3건):")
    for i, a in enumerate(batches["batch_2"], 1):
        print(f"   {i}. {a['title']} ({a['source']})")

    print("\n✅ 배치 3 (금/토 - 해외 글로벌 C, 3건):")
    for i, a in enumerate(batches["batch_3"], 1):
        print(f"   {i}. {a['title']} ({a['source']})")


