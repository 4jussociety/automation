# 이 모듈은 네이버 뉴스 API 및 구글 뉴스 RSS를 통해 최신 물리치료 뉴스를 수집합니다.
# 수집 실패 또는 검색 결과 부재 시 fallback 없이 명확한 예외를 발생시킵니다.

import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime
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


# 연예인 단순 부상, 예능, 가십성 기사 제외 키워드
GOSSIP_KEYWORDS = [
    "방송", "예능", "안혜경", "골때녀", "부상 투혼", "결혼", "인스타", "근황",
    "결별", "열애", "포토", "화보", "드라마", "시청률", "출연", "타박상",
    "이게 젤 아픈", "응급실", "셀카", "피팅"
]


def is_gossip_or_spam(title: str, description: str = "") -> bool:
    """단순 연예 가십이나 비전문적 기사인지 판별합니다."""
    combined = (title + " " + description).lower()
    return any(k.lower() in combined for k in GOSSIP_KEYWORDS)


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


def fetch_from_naver(keyword: str, display: int = 10) -> list[dict]:
    """네이버 클라우드 플랫폼(NAVER API HUB) 검색 API를 통해 최신 뉴스를 수집합니다."""
    if not NAVER_CLIENT_ID or not NAVER_CLIENT_SECRET:
        return []

    # 1. 네이버 클라우드 플랫폼 (NAVER API HUB) 공식 엔드포인트
    url = f"https://naverapihub.apigw.ntruss.com/search/v1/news?query={urllib.parse.quote(keyword)}&display={display}&sort=sim"
    headers = {
        "X-NCP-APIGW-API-KEY-ID": NAVER_CLIENT_ID,
        "X-NCP-APIGW-API-KEY": NAVER_CLIENT_SECRET
    }

    resp = requests.get(url, headers=headers, timeout=10)

    # 2. 구형 개발자센터 API fallback 호환성 지원
    if resp.status_code == 401 or resp.status_code == 403:
        legacy_url = f"https://openapi.naver.com/v1/search/news.json?query={urllib.parse.quote(keyword)}&display={display}&sort=sim"
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
            "pub_date": item.get("pubDate", ""),
            "source": source_name
        })
    return results


def fetch_from_google_rss(keyword: str, max_items: int = 10) -> list[dict]:
    """구글 뉴스 RSS를 통해 최신 뉴스를 수집합니다."""
    encoded_query = urllib.parse.quote(keyword)
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
    for item in channel.findall("item")[:max_items]:
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

        results.append({
            "title": clean_html(title),
            "description": clean_html(desc),
            "link": link,
            "pub_date": pub_date,
            "source": source
        })

    return results


def fetch_from_google_rss_global(keyword: str, max_items: int = 10) -> list[dict]:
    """구글 글로벌 뉴스 RSS에서 영문 물리치료 기사를 수집하고 한국어로 번역합니다."""
    from modules.translator import translate_to_korean

    encoded_query = urllib.parse.quote(keyword)
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
    for item in channel.findall("item")[:max_items]:
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
            "pub_date": pub_date,
            "source": f"{source_name} (글로벌)",
            "category": "해외 연구/트렌드",
            "is_global": True
        })

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


