# 이 모듈은 수집된 뉴스 기사를 템플릿 및 쇼츠 대본 규격에 맞게 구조화합니다.
# 카드뉴스 슬라이드별 HTML 콘텐츠와 1분 분량의 고속 TTS 나레이션 대본을 생성합니다.

import sys
from pathlib import Path
import json
import re

sys.path.append(str(Path(__file__).resolve().parent.parent))

from config import DEFAULT_BG_PATH, AI_TECH_BG_PATH, DEFAULT_AD_CONFIG


def build_slide_html(slide_type: str, data: dict) -> str:
    """슬라이드 타입에 맞는 HTML 코드를 조립합니다."""
    if slide_type == "cover":
        items_html = "".join([
            f'<div class="cover-item-row"><div class="cover-num-bullet">{i}</div><div>{item}</div></div>'
            for i, item in enumerate(data.get("items", []), 1)
        ])
        return f"""
        <div class="cover-tag-box">{data.get('tag', '물리치료 NEWS 주간 브리핑')}</div>
        <div class="cover-huge-title">{data.get('title', '한눈에 보는 이번 주<br><span class="hl-yellow">물리치료 핵심 뉴스</span>')}</div>
        <div class="cover-desc-card">
            <div class="cover-desc-text">{data.get('desc', '한 주간의 주요 물리치료 및 재활 의료 소식을 빠르게 전해드립니다.')}</div>
        </div>
        <div class="cover-item-list">
            {items_html}
        </div>
        """

    elif slide_type == "news":
        bullets_html = "".join([
            f'<div class="news-body-bullet">• {b}</div>'
            for b in data.get("bullets", [])
        ])
        return f"""
        <div class="news-top-badge-row">
            <div class="news-index-badge">{data.get('index', '01')}</div>
            <div class="news-category-badge">{data.get('category', '심층 분석')}</div>
            <div class="news-source-badge">{data.get('source', '')}</div>
        </div>
        <div class="news-main-headline">{data.get('headline', '')}</div>
        <div class="news-glass-box">
            {bullets_html}
        </div>
        <div class="news-action-highlight">
            {data.get('highlight', '')}
        </div>
        """

    elif slide_type == "ad":
        bullets_html = "".join([
            f'<div class="ad-check-item">✨ {b}</div>'
            for b in data.get("bullets", [])
        ])
        cta_btn = data.get('cta_button', '').strip()
        cta_btn_html = f'<div class="ad-cta-btn">{cta_btn}</div>' if cta_btn else ''
        cta_html = f"""
        <div class="ad-cta-container">
            {cta_btn_html}
            <div class="ad-inquiry-text">{data.get('inquiry_text', '📢 광고 및 비즈니스 제휴 문의: teamthept@gmail.com')}</div>
        </div>
        """
        return f"""
        <div class="ad-top-tag">{data.get('badge', 'THEPT SPONSOR')}</div>
        <div class="ad-huge-title">{data.get('title', '방문재활 물리치료사 맞춤<br><span class="hl-yellow">AI음성 차팅</span>')}</div>
        <div class="ad-summary-card">
            {data.get('subtitle', '수작업 차팅 부담은 줄이고, 고객과의 소통에 더 집중하세요.')}
        </div>
        <div class="ad-checklist">
            {bullets_html}
        </div>
        {cta_html}
        """

    elif slide_type == "insight":
        checks_html = "".join([
            f'<div class="insight-check-item">✅ {c}</div>'
            for c in data.get("checklist", [])
        ])
        return f"""
        <div class="insight-top-tag">{data.get('tag', '주간 임상 인사이트')}</div>
        <div class="insight-huge-title">{data.get('title', '치료사가 주목할<br><span class="hl-yellow">임상 체크포인트</span>')}</div>
        <div class="insight-summary-card">
            {data.get('summary', '')}
        </div>
        <div class="insight-checklist">
            {checks_html}
        </div>
        """

    elif slide_type == "outro":
        is_shorts = data.get("is_shorts", False)
        sub_text = data.get("sub", "지금 저장해두고 동료 치료사와 함께 나눠보세요!")
        next_notice = f"""<div style="background: rgba(255, 204, 0, 0.15); border: 1px solid #ffcc00; border-radius: 12px; padding: 12px; margin-bottom: 20px; font-size: 20px; color: #ffeb3b; font-weight: 700; text-align: center;">
            {data.get('notice', '💡 내일 4:5 심층 카드뉴스로 이어집니다!')}
        </div>""" if is_shorts else ""

        return f"""
        <div class="outro-card-box">
            <div class="outro-header-text">{data.get('header', '더 많은 물리치료 소식이<br><span class="hl-yellow">궁금하다면?</span>')}</div>
            <div class="outro-sub-text">{sub_text}</div>
            {next_notice}
            <div class="outro-insta-buttons">
                <div class="insta-button highlight-save">
                    <span class="btn-icon">📌</span>
                    <span>게시물 저장하기</span>
                </div>
                <div class="insta-button">
                    <span class="btn-icon">✈️</span>
                    <span>동료에게 공유</span>
                </div>
                <div class="insta-button">
                    <span class="btn-icon">❤️</span>
                    <span>좋아요 응원</span>
                </div>
            </div>
            <div class="channels-card">
                <div class="channel-link-item">
                    <span>인스타그램 @teamthept</span>
                </div>
                <div class="channel-link-item">
                    <span>유튜브 더피티THEPT</span>
                </div>
            </div>
        </div>
        """
    else:
        raise ValueError(f"지원하지 않는 슬라이드 타입입니다: {slide_type}")



from modules.article_compressor import compress_article_content
from modules.text_verifier import refine_text_for_tts


def clean_sentence(text: str, max_len: int = 70) -> str:
    """말줄임표 없이 자연스럽게 완결되는 문장을 정제합니다."""
    if not text:
        return ""
    t = text.replace('...', '').replace('…', '').replace('..', '').strip()
    sentences = re.split(r'[\.\?\!]\s*', t)
    for s in sentences:
        s = s.strip()
        if len(s) >= 15:
            return s + ("." if not s.endswith(".") else "")
    if len(t) > max_len:
        words = t[:max_len].split()
        if len(words) > 1:
            t = " ".join(words[:-1])
    return t + ("." if not t.endswith((".", "!", "?")) else "")


def clean_title_for_narration(title: str, max_len: int = 45) -> str:
    """나레이션에서 또박또박 발음할 수 있도록 대괄호/특수문자 및 띄어쓰기, 쉼표를 정제합니다."""
    t = re.sub(r'\[.*?\]|\(.*?\)|<.*?>', '', title)
    t = t.replace('...', '').replace('…', '').replace('..', '').strip()
    if len(t) > max_len:
        words = t[:max_len].split()
        if len(words) > 1:
            t = " ".join(words[:-1])
    # TTS 발음용 띄어쓰기/문장부호 정제 후 끝의 마침표만 제거(문맥에 맞게 결합하기 위함)
    refined = refine_text_for_tts(t).rstrip('.!?').strip()
    return refined


def build_content_package(
    articles: list[dict],
    custom_script: dict = None,
    bg_dir: Path = None,
    article_photos: dict = None,
    title_theme: str = None,
    tag_theme: str = None,
    is_global: bool = False,
    content_type: str = "shorts",
    assigned_bgs: dict = None
) -> dict:
    """
    수집된 뉴스 기사 3건을 바탕으로 브리핑 카드뉴스 슬라이드(6장) 및 2분 미만의 고품질 쇼츠 대본 패키지를 구성합니다.
    말줄임표(...) 없이 완성형 문장으로 구성하며, 100% 실제 기사 보도 사진 풀을 배경으로 매칭합니다.
    """
    if not articles or len(articles) < 3:
        raise RuntimeError(f"콘텐츠 생성을 위한 기사가 부족합니다. (필요: 최소 3건, 현재: {len(articles) if articles else 0}건)")

    # 1. 6대 슬라이드 배경 사진 매칭 (assigned_bgs 우선 적용)
    if assigned_bgs:
        bg_cover = assigned_bgs.get("cover")
        bg_n1 = assigned_bgs.get("news1")
        bg_n2 = assigned_bgs.get("news2")
        bg_n3 = assigned_bgs.get("news3")
        bg_insight = assigned_bgs.get("insight")
        bg_outro = assigned_bgs.get("outro")
    else:
        photo_map = article_photos or {}
        default_p = str(photo_map.get(1, DEFAULT_BG_PATH))
        bg_n1 = str(photo_map.get(1, default_p))
        bg_n2 = str(photo_map.get(2, default_p))
        bg_n3 = str(photo_map.get(3, default_p))
        bg_cover = default_p
        bg_insight = default_p
        bg_outro = default_p

    # 2. 3대 주요 기사 선정 및 전문 압축 엔진 가동
    top3 = articles[:3]
    c1 = compress_article_content(top3[0], is_global=is_global)
    c2 = compress_article_content(top3[1], is_global=is_global)
    c3 = compress_article_content(top3[2], is_global=is_global)

    if custom_script:
        package = custom_script
    else:
        n1 = top3[0]
        n2 = top3[1]
        n3 = top3[2]

        main_title = title_theme or ("글로벌 물리치료 & APTA 해외 트렌드 TOP 3" if is_global else "국내 물리치료 핵심 정책 & 제도 이슈 TOP 3")
        tag_text = tag_theme or ("물리치료 NEWS | 글로벌 트렌드 C" if is_global else "물리치료 NEWS | 정책·제도 현안")

        t1 = c1["headline"]
        t2 = c2["headline"]
        t3 = c3["headline"]

        package = {
            "title": main_title,
            "is_global": is_global,
            "content_type": content_type,
            "sources": [
                {
                    "index": "01",
                    "title": t1,
                    "source": n1["source"],
                    "link": n1["link"]
                },
                {
                    "index": "02",
                    "title": t2,
                    "source": n2["source"],
                    "link": n2["link"]
                },
                {
                    "index": "03",
                    "title": t3,
                    "source": n3["source"],
                    "link": n3["link"]
                }
            ],
            "slides": [
                # 슬라이드 1: 표지 (약 7~8초)
                {
                    "type": "cover",
                    "header_tag": "THEPT GLOBAL" if is_global else "THEPT WEEKLY",
                    "swipe_label": "밀어서 보기 👉",
                    "background": bg_cover,
                    "data": {
                        "tag": tag_text,
                        "title": f"<span class=\"hl-yellow\">{main_title}</span>",
                        "desc": "물리치료 및 재활 의료계의 주요 최신 소식을 빠르게 전달해드립니다.",
                        "items": [t1, t2, t3]
                    },
                    "narration": f"물리치료사 필독! 이번 주 가장 뜨거운, { '글로벌 재활 트렌드' if is_global else '물리치료 핵심 정책과 임상 소식' } 3가지. 지금 바로 상세히 브리핑해 드립니다!"
                },
                # 슬라이드 2: 뉴스 1 (약 18~22초)
                {
                    "type": "news",
                    "header_tag": "ISSUE 01",
                    "swipe_label": "다음 뉴스 👉",
                    "background": bg_n1,
                    "data": {
                        "index": "01",
                        "category": n1.get("category", "해외 연구" if is_global else "정책·제도"),
                        "source": n1["source"],
                        "headline": t1,
                        "bullets": c1["bullets"],
                        "highlight": c1["highlight"]
                    },
                    "narration": f"첫 번째 소식입니다. {clean_title_for_narration(t1)}. {c1['narration_body']}"
                },
                # 슬라이드 3: 뉴스 2 (약 18~22초)
                {
                    "type": "news",
                    "header_tag": "ISSUE 02",
                    "swipe_label": "다음 뉴스 👉",
                    "background": bg_n2,
                    "data": {
                        "index": "02",
                        "category": n2.get("category", "글로벌 임상" if is_global else "임상·연구"),
                        "source": n2["source"],
                        "headline": t2,
                        "bullets": c2["bullets"],
                        "highlight": c2["highlight"]
                    },
                    "narration": f"두 번째 소식입니다. {clean_title_for_narration(t2)}. {c2['narration_body']}"
                },
                # 슬라이드 4: 뉴스 3 (약 18~22초)
                {
                    "type": "news",
                    "header_tag": "ISSUE 03",
                    "swipe_label": "인사이트 보기 👉",
                    "background": bg_n3,
                    "data": {
                        "index": "03",
                        "category": n3.get("category", "첨단 재활" if is_global else "학술·현안"),
                        "source": n3["source"],
                        "headline": t3,
                        "bullets": c3["bullets"],
                        "highlight": c3["highlight"]
                    },
                    "narration": f"세 번째 소식입니다. {clean_title_for_narration(t3)}. {c3['narration_body']}"
                },
                # 슬라이드 5: 광고/프로모션 페이지 (4THEPT 임상차팅 서비스 & 광고문의)
                {
                    "type": "ad",
                    "header_tag": "THEPT SPONSOR",
                    "swipe_label": "마무리 👉",
                    "background": bg_insight,
                    "data": DEFAULT_AD_CONFIG,
                    "narration": DEFAULT_AD_CONFIG["narration"]
                },
                # 슬라이드 6: 아웃트로 (약 8~10초)
                {
                    "type": "outro",
                    "header_tag": "THEPT LAB",
                    "swipe_label": "저장 & 공유 📌",
                    "background": bg_outro,
                    "data": {
                        "header": "더 많은 물리치료 소식이<br><span class=\"hl-yellow\">궁금하다면?</span>",
                        "sub": "지금 바로 저장하고 동료 물리치료사와 함께 보세요!"
                    },
                    "narration": (
                        "더 자세한 분석과 상세 자료는, 내일 업로드되는 4:5 카드뉴스에서 확인하실 수 있습니다. 게시물 저장과 동료 공유 부탁드리며, 구독과 좋아요로 매주 최신 소식을 받아보세요!"
                        if content_type == "shorts" else
                        "도움이 되셨다면, 게시물 저장과 동료 공유 부탁드립니다! 다음 주에도 더욱 알차고 깊이 있는 물리치료 소식으로 찾아오겠습니다."
                    )
                }
            ]
        }

    return package


def allocate_batch_backgrounds(
    current_photos: dict,
    all_photos_pool: list[str]
) -> dict:
    """
    배치별 6개 슬라이드에 들어갈 실제 보도 사진을 배분합니다.
    - 뉴스 1, 2, 3: 해당 기사의 실제 보도 사진 (1:1 매칭)
    - 표지, 인사이트, 아웃트로: 당일 기사 3장을 제외한 나머지 6장 풀에서 랜덤 선택
    - 사진 부족 시: 수집된 전체 보도 사진 내에서 재사용하여 100% 실제 사진으로 구성
    """
    import random

    p1 = str(current_photos.get(1)) if 1 in current_photos else None
    p2 = str(current_photos.get(2)) if 2 in current_photos else None
    p3 = str(current_photos.get(3)) if 3 in current_photos else None

    # 해당 기사 사진이 누락된 경우 전체 풀에서 보충
    if not p1 and all_photos_pool:
        p1 = all_photos_pool[0]
    if not p2 and all_photos_pool:
        p2 = all_photos_pool[1] if len(all_photos_pool) > 1 else p1
    if not p3 and all_photos_pool:
        p3 = all_photos_pool[2] if len(all_photos_pool) > 2 else p1

    cur_set = {p for p in [p1, p2, p3] if p}

    # 나머지 6장 풀 (현재 배치 3개 기사 사진 제외)
    other_pool = [p for p in all_photos_pool if p not in cur_set]

    # 슬라이드 1(표지), 5(인사이트), 6(아웃트로)용 3장 무작위 추출
    if len(other_pool) >= 3:
        chosen = random.sample(other_pool, 3)
    elif other_pool:
        # 부족할 경우 전체 보도사진 풀과 합쳐서 3장 확보 (기본 배경 사용 안 함)
        combined = other_pool + [p for p in all_photos_pool if p not in other_pool]
        chosen = random.choices(combined, k=3) if len(combined) < 3 else random.sample(combined, 3)
    else:
        # 전체 사진 풀에서 재사용
        chosen = random.choices(all_photos_pool or [str(DEFAULT_BG_PATH)], k=3)

    return {
        "cover": chosen[0],
        "news1": p1 or chosen[0],
        "news2": p2 or chosen[1],
        "news3": p3 or chosen[2],
        "insight": chosen[1],
        "outro": chosen[2]
    }


def build_weekly_3batches_schedule(
    batches: dict,
    bg_dir: Path = None,
    batch_photos: dict = None
) -> list[dict]:
    """
    3개 브리핑 배치(국내 정책 A 3건, 국내 임상 B 3건, 해외 C 3건)를 기반으로
    요일별 6개 전용 폴더용 패키지 목록을 생성합니다.
    - 9장의 보도 사진 풀에서 슬라이드 2, 3, 4는 해당 기사 사진, 1, 5, 6은 나머지 6장 풀에서 랜덤 배분합니다.
    - 동일 배치의 쇼츠(월/수/금)와 카드뉴스(화/목/토)는 100% 동일한 6장의 배경을 공유합니다.
    """
    photos = batch_photos or {}

    b1_photos = photos.get("batch_1", {})
    b2_photos = photos.get("batch_2", {})
    b3_photos = photos.get("batch_3", {})

    # 전체 수집된 보도 사진 목록 구축 (중복 제거된 고유 파일 경로들)
    all_photos_pool = []
    for b_dict in [b1_photos, b2_photos, b3_photos]:
        for p in b_dict.values():
            p_str = str(p)
            if p_str and Path(p_str).exists() and p_str not in all_photos_pool:
                all_photos_pool.append(p_str)

    # 배치 1, 2, 3 각각에 대해 6대 슬라이드 배경 사전 할당 (쇼츠와 카드뉴스가 완벽히 동일한 배경 공유)
    b1_bg_map = allocate_batch_backgrounds(b1_photos, all_photos_pool)
    b2_bg_map = allocate_batch_backgrounds(b2_photos, all_photos_pool)
    b3_bg_map = allocate_batch_backgrounds(b3_photos, all_photos_pool)

    schedule = [
        # (요일, 폴더명, 콘텐츠타입, 배치데이터, 할당된 배경맵, 제목, 태그, is_global)
        (
            "월요일", "01_Mon_Shorts", "shorts",
            batches["batch_1"], b1_bg_map,
            "국내 물리치료 핵심 정책 & 제도 이슈 TOP 3", "물리치료 NEWS | 정책·제도 현안", False
        ),
        (
            "화요일", "02_Tue_CardNews", "cardnews",
            batches["batch_1"], b1_bg_map,
            "국내 물리치료 핵심 정책 & 제도 이슈 TOP 3", "물리치료 NEWS | 정책·제도 현안", False
        ),
        (
            "수요일", "03_Wed_Shorts", "shorts",
            batches["batch_2"], b2_bg_map,
            "최신 재활 임상 연구 & 첨단 치료 기술 TOP 3", "물리치료 NEWS | 임상·학술 연구", False
        ),
        (
            "목요일", "04_Thu_CardNews", "cardnews",
            batches["batch_2"], b2_bg_map,
            "최신 재활 임상 연구 & 첨단 치료 기술 TOP 3", "물리치료 NEWS | 임상·학술 연구", False
        ),
        (
            "금요일", "05_Fri_Shorts_Global", "shorts",
            batches["batch_3"], b3_bg_map,
            "글로벌 물리치료 & APTA 해외 트렌드 TOP 3", "물리치료 NEWS | 글로벌 트렌드 C", True
        ),
        (
            "토요일", "06_Sat_CardNews_Global", "cardnews",
            batches["batch_3"], b3_bg_map,
            "글로벌 물리치료 & APTA 해외 트렌드 TOP 3", "물리치료 NEWS | 글로벌 트렌드 C", True
        ),
    ]

    packages = []
    for day, folder, c_type, arts, bg_map, title, tag, is_g in schedule:
        pkg = build_content_package(
            articles=arts,
            bg_dir=bg_dir,
            title_theme=title,
            tag_theme=tag,
            is_global=is_g,
            content_type=c_type,
            assigned_bgs=bg_map
        )
        pkg["day_name"] = day
        pkg["folder_name"] = folder
        pkg["content_type"] = c_type
        packages.append(pkg)

    return packages


# ==============================================================================
# 주 6일 큐레이션 전용 패키지 빌더 (일별 2~3개 기사 기반 쇼츠 + 카드뉴스 통합 패키지)
# ==============================================================================

def build_daily_curated_package(
    day_name: str,
    category_title: str,
    articles: list[dict],
    bg_dir: Path = None,
    article_photos: dict = None,
    is_global: bool = False
) -> dict:
    """
    큐레이션된 일별 2~3개 기사를 바탕으로,
    1편의 통합 쇼츠 비디오(최대 2분 분량) 대본 및 4:5 고화질 카드뉴스(5~6장) 패키지를 조립합니다.
    """
    if not articles or len(articles) < 1:
        raise RuntimeError(f"{day_name} 콘텐츠 생성을 위한 기사가 없습니다.")

    # 1. 기사 수 (2건 또는 3건)
    curated_articles = articles[:3]
    num_arts = len(curated_articles)

    # 2. 각 기사 압축
    compressed_items = [
        compress_article_content(art, is_global=is_global or art.get("is_global", False))
        for art in curated_articles
    ]

    # 3. 배경 이미지 배분
    photo_map = article_photos or {}
    default_bg = str(DEFAULT_BG_PATH)

    # 4. 소스 목록 및 표지 미리보기 목록 구성
    sources = []
    cover_items = []
    for idx, (art, comp) in enumerate(zip(curated_articles, compressed_items), start=1):
        h = comp["headline"]
        sources.append({
            "index": f"{idx:02d}",
            "title": h,
            "source": art.get("source", "뉴스"),
            "link": art.get("link", "#")
        })
        cover_items.append(h)

    main_title = f"{day_name} 물리치료 브리핑 | <span class=\"hl-yellow\">{category_title}</span>"
    tag_text = f"THEPT WEEKLY | {day_name} 브리핑"

    # 5. 슬라이드 목록 조립
    # 슬라이드 1: 표지
    cover_bg = str(photo_map.get(1, default_bg))
    slides = [
        {
            "type": "cover",
            "header_tag": "THEPT GLOBAL" if is_global else "THEPT WEEKLY",
            "swipe_label": "밀어서 보기 👉",
            "background": cover_bg,
            "data": {
                "tag": tag_text,
                "title": f"<span class=\"hl-yellow\">{day_name} {category_title}</span>",
                "desc": f"오늘 꼭 살펴봐야 할 {category_title} 주요 뉴스 {num_arts}가지를 전해드립니다.",
                "items": cover_items
            },
            "narration": f"오직 물리치료사를 위한 커뮤니티, THEPT입니다. {day_name}에 전해드리는 {category_title} 핵심 뉴스 {num_arts}가지, 지금 바로 시작합니다!"
        }
    ]

    # 슬라이드 2..N: 기사 슬라이드
    ordinal_korean = ["첫 번째", "두 번째", "세 번째"]
    for idx, (art, comp) in enumerate(zip(curated_articles, compressed_items), start=1):
        bg_art = str(photo_map.get(idx, photo_map.get(1, default_bg)))
        art_headline = comp["headline"]
        narration_headline = clean_title_for_narration(art_headline)
        ord_word = ordinal_korean[idx - 1]

        slides.append({
            "type": "news",
            "header_tag": f"NEWS {idx:02d}",
            "swipe_label": "다음 소식 👉" if idx < num_arts else "핵심 정리 👉",
            "background": bg_art,
            "data": {
                "index": f"{idx:02d}",
                "category": category_title,
                "source": f"{art.get('source', '뉴스')} ({art.get('pub_date', '')})",
                "headline": art_headline,
                "bullets": comp["bullets"],
                "highlight": comp["highlight"]
            },
            "narration": f"{ord_word} 소식입니다. {narration_headline}. {comp['narration_body']}"
        })

    # 슬라이드 5: 광고/프로모션 페이지 (4THEPT 임상차팅 서비스 & 광고문의)
    from config import DEFAULT_AD_CONFIG
    ad_cfg = DEFAULT_AD_CONFIG.copy()
    ad_bg = str(photo_map.get(2, cover_bg))
    slides.append({
        "type": "ad",
        "header_tag": "THEPT SPONSOR",
        "swipe_label": "마무리 👉",
        "background": ad_bg,
        "data": ad_cfg,
        "narration": ad_cfg["narration"]
    })

    # 슬라이드 6: 아웃트로 슬라이드
    outro_bg = str(photo_map.get(num_arts, cover_bg))
    slides.append({
        "type": "outro",
        "header_tag": "THEPT NEWS",
        "swipe_label": "저장 & 공유 📌",
        "background": outro_bg,
        "data": {
            "header": "더 많은 물리치료 소식이<br><span class=\"hl-yellow\">궁금하다면?</span>",
            "sub": "지금 바로 게시물을 저장하고 동료 물리치료사와 함께 나눠보세요!"
        },
        "narration": "오늘 전해드린 소식이 도움 되셨다면 게시물 저장과 공유 부탁드립니다. 내일도 유익하고 알찬 물리치료 소식으로 찾아오겠습니다. 감사합니다!"
    })

    # 인스타그램 캡션 생성
    tags_line = f"#{category_title.replace('·', '').replace(' ', '_')} #물리치료 #도수치료 #재활치료 #물리치료사 #4THEPT #THEPT"
    items_summary = "\n".join([f"📌 {s['index']}. {s['title']} ({s['source']})" for s in sources])
    caption_text = f"""[THEPT 주간 브리핑] {day_name}: {category_title}

{items_summary}

💡 [4THEPT] 방문재활 물리치료사 맞춤 AI음성 차팅:
- AI음성분석 기반 SOAP차팅, 라포데이터 차팅 지원 (4thept.com)
- THEPT회원은 매월 무료 5시간 사용 가능!
- 수작업 차팅 부담은 줄이고, 고객과의 소통에 더 집중하세요!
📢 광고 및 비즈니스 제휴 문의: teamthept@gmail.com

👉 유익하셨다면 동료 선생님들과 공유하고 저장해두세요!

{tags_line}
"""

    return {
        "day_name": day_name,
        "category_title": category_title,
        "title": main_title,
        "is_global": is_global,
        "sources": sources,
        "slides": slides,
        "caption": caption_text
    }




