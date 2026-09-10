# 이 모듈은 수집된 뉴스 기사를 템플릿 및 쇼츠 대본 규격에 맞게 구조화합니다.
# 카드뉴스 슬라이드별 HTML 콘텐츠와 1분 분량의 고속 TTS 나레이션 대본을 생성합니다.

import sys
from pathlib import Path
import json
import re

sys.path.append(str(Path(__file__).resolve().parent.parent))

import base64

from config import DEFAULT_BG_PATH, AI_TECH_BG_PATH, DEFAULT_AD_CONFIG, OUTRO_IMG_PATH, get_day_intro_image


def get_image_data_uri(img_path) -> str:
    """이미지 파일 경로를 받아 base64 Data URI로 변환합니다."""
    if not img_path:
        return ""
    if str(img_path).startswith("data:"):
        return str(img_path)
    p = Path(img_path) if isinstance(img_path, (str, Path)) else None
    if not p or not p.exists():
        return ""
    suffix = p.suffix.lower().replace(".", "")
    mime = "jpeg" if suffix in ["jpg", "jpeg"] else "png"
    try:
        raw = p.read_bytes()
        encoded = base64.b64encode(raw).decode("utf-8")
        return f"data:image/{mime};base64,{encoded}"
    except Exception:
        return ""


def build_slide_html(slide_type: str, data: dict) -> str:
    """슬라이드 타입에 맞는 HTML 코드를 조립합니다."""
    if slide_type == "cover":
        items = data.get("items", [])[:3]  # 하루 3개 뉴스 규격
        items_html = "".join([
            f'<div class="cover-item-row"><div class="cover-num-bullet">{i}</div><div>{item}</div></div>'
            for i, item in enumerate(items, 1)
        ])
        media_img = data.get("media_image", "")
        media_uri = get_image_data_uri(media_img)
        bg_style = f"background-image: url('{media_uri}');" if media_uri else "background: linear-gradient(135deg, #1e293b, #0f172a);"
        return f"""
        <div class="cover-media-frame">
            <div class="cover-media-img" style="{bg_style}"></div>
        </div>
        <div class="cover-item-list" style="gap: 14px;">
            {items_html}
        </div>
        """

    elif slide_type == "news":
        bullets_html = "".join([
            f'<div class="news-body-bullet">• {b}</div>'
            for b in data.get("bullets", [])
        ])
        # 방송형 템플릿의 경우 기사 보도사진 프레임 지원 (중앙 프레임 내 선명한 사진 노출)
        media_img = data.get("media_image", "") or data.get("image_path", "")
        media_frame_html = ""
        if media_img:
            media_uri = get_image_data_uri(media_img)
            if media_uri:
                media_frame_html = f"""
                <div class="news-media-frame">
                    <div class="news-media-img" style="background-image: url('{media_uri}');"></div>
                </div>
                """
        # 최상단 보도사진 -> 바로 아래 메인 헤드라인 (01 인덱스 뱃지 + 기사제목 + 출처 태그) -> 3줄 요약
        source_val = data.get('source', '').strip()
        source_html = f'<span class="news-source-inline">{source_val}</span>' if source_val else ''
        return f"""
        {media_frame_html}
        <h2 class="news-main-headline">
            <span class="news-index-badge">{data.get('index', '01')}</span>{data.get('headline', '')}{source_html}
        </h2>
        <div class="news-glass-box">
            {bullets_html}
        </div>
        """

    elif slide_type == "ad":
        cats = data.get("categories", [])
        if cats:
            cat_blocks = []
            for c in cats:
                b_html = "".join([f'<p class="ad-cat-bullet">{b}</p>' for b in c.get("bullets", [])])
                sub_html = f'<span style="font-size: 26px; color: #cbd5e1; font-weight: 700; margin-top: 4px;">{c.get("subname", "")}</span>' if c.get("subname") else ""
                tag_html = f'<span class="ad-cat-tag">{c.get("tag", "")}</span>' if c.get("tag") else ""
                cat_blocks.append(f"""
                <div class="ad-category-block">
                  <div class="ad-cat-header">
                    <div class="ad-cat-title-wrap">
                      <span class="ad-cat-num">{c.get('num', '01')}</span>
                      <div style="display: flex; flex-direction: column;">
                        <span class="ad-cat-name">{c.get('name', '')}</span>
                        {sub_html}
                      </div>
                    </div>
                    {tag_html}
                  </div>
                  <div class="ad-cat-bullets">
                    {b_html}
                  </div>
                </div>
                """)
            split_html = f'<div class="ad-split-container">{"".join(cat_blocks)}</div>'
        else:
            bullets_html = "".join([f'<p class="ad-cat-bullet">✨ {b}</p>' for b in data.get("bullets", [])])
            split_html = f'<div class="news-glass-box">{bullets_html}</div>'

        cta_text = data.get("cta_text", "👉 두 서비스 모두 하단 고정 댓글 링크에서 지금 확인하세요!")
        return f"""
        <div style="display: flex; flex-direction: column; justify-content: space-between; height: 100%;">
          <div>
            <div class="ad-top-badge-row">
              <span class="ad-sponsor-badge">{data.get('badge', 'THEPT SPONSOR')}</span>
              <span style="font-size: 28px; font-weight: 800; color: #facc15;">{data.get('sub_badge', '물리치료사 필수 솔루션')}</span>
            </div>
            <h2 class="news-main-headline" style="font-size: 46px; margin-bottom: 12px; line-height: 1.3;">
              {data.get('title', '병원 밖 독립을 위한 <span style="color: #facc15;">핵심 솔루션 2가지</span>')}
            </h2>
          </div>
          {split_html}
          <div class="ad-hot-cta" style="margin-top: 4px; font-size: 32px; padding: 22px 24px;">
            {cta_text}
          </div>
        </div>
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
        sub_text = data.get("sub", "도움이 되셨다면 좋아요를 누르고 동료 물리치료사와 함께 공유해보세요!")
        media_img = data.get("media_image", "") or (str(OUTRO_IMG_PATH) if OUTRO_IMG_PATH.exists() else "")
        media_frame_html = ""
        if media_img:
            media_frame_html = f"""
            <div class="news-media-frame" style="margin-bottom: 24px;">
                <div class="news-media-img" style="background-image: url('{media_img}');"></div>
            </div>
            """
        return f"""
        <div style="display: flex; flex-direction: column; justify-content: space-between; height: 100%;">
            <div class="main-body" style="justify-content: flex-start;">
                {media_frame_html}
                <h2 class="news-main-headline" style="text-align: center; margin-bottom: 20px;">
                    {data.get('header', '더 많은 물리치료 소식이<br><span class="hl-yellow">궁금하다면?</span>')}
                </h2>
                <div class="news-glass-box" style="text-align: center; align-items: center;">
                    <p class="news-body-bullet">❤️ {sub_text}</p>
                    <p class="news-body-bullet">🔔 구독과 알림 설정으로 매일 최신 재활 소식을 가장 빠르게 받아보세요!</p>
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
                    "swipe_label": "좋아요 & 공유 ❤️",
                    "background": bg_outro,
                    "data": {
                        "header": "더 많은 물리치료 소식이<br><span class=\"hl-yellow\">궁금하다면?</span>",
                        "sub": "도움이 되셨다면 좋아요를 누르고 동료 물리치료사와 함께 공유해보세요!"
                    },
                    "narration": "오늘 전해드린 소식이 유익하셨다면 구독과 좋아요 부탁드립니다. 내일도 알찬 소식으로 찾아오겠습니다. 감사합니다!"
                }
            ]
        }

    return package


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
            "link": art.get("link", "#"),
            "story_summary": comp.get("story_summary", "")
        })
        cover_items.append(h)

    main_title = f"{day_name} THEPT 물리치료 1분 브리핑"
    tag_text = f"THEPT WEEKLY | {day_name} 브리핑"

    # 5. 슬라이드 목록 조립
    # 슬라이드 1: 표지 (요일별 전용 시그니처 인트로 사진 우선 적용)
    day_intro_img = get_day_intro_image(day_name)
    if day_intro_img and day_intro_img.exists():
        cover_bg = str(day_intro_img)
    else:
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
                "items": cover_items,
                "media_image": cover_bg
            },
            "narration": f"{day_name} 더피티 뉴스 1분 브리핑 시작합니다."
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
                "media_image": bg_art,
                "bullets": comp["bullets"],
                "highlight": comp["highlight"],
                "story_summary": comp.get("story_summary", "")
            },
            "narration": f"{ord_word} 소식입니다. {narration_headline}. {comp['narration_body']}"
        })

    # 슬라이드 5: 광고/프로모션 페이지 (4THEPT 임상차팅 서비스 & 창업 전자책)
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

    # 슬라이드 6: 아웃트로 슬라이드 (남녀 듀오 물리치료사 대표 이미지 적용)
    outro_bg = str(photo_map.get(num_arts, cover_bg))
    outro_narration = "오늘 소식이 유익하셨다면 구독과 좋아요 부탁드립니다. 내일도 알찬 소식으로 찾아오겠습니다. 감사합니다!"
    slides.append({
        "type": "outro",
        "header_tag": "THEPT NEWS",
        "swipe_label": "좋아요 & 공유 ❤️",
        "background": outro_bg,
        "data": {
            "media_image": str(OUTRO_IMG_PATH) if OUTRO_IMG_PATH.exists() else "",
            "header": "더 많은 물리치료 소식이<br><span class=\"hl-yellow\">궁금하다면?</span>",
            "sub": "도움이 되셨다면 좋아요를 누르고 동료 물리치료사와 함께 공유해보세요!"
        },
        "narration": outro_narration
    })

    # 인스타그램 캡션 생성
    clean_cat = category_title.replace('·', '').replace(' ', '_')
    tags_line = f"#{clean_cat} #물리치료 #도수치료 #재활치료 #물리치료사 #THEPT #더피티 #카드뉴스"

    if is_global:
        # 글로벌 기사 전용: [헤드라인 + 4~6문장 상세 스토리텔링 번역 브리핑 + 원문 출처 + 링크]
        def build_global_sources_block(max_summary_len: int = 500) -> str:
            blocks = []
            for s in sources:
                summ = s.get("story_summary", "").strip()
                if len(summ) > max_summary_len:
                    summ = summ[:max_summary_len].rstrip() + "..."

                # 인스타그램 캡션은 하이퍼링크가 작동하지 않으므로 수백 자의 구글 RSS URL 대신 간결한 출처로 최적화
                link_url = s.get("link", "")
                if "news.google.com" in link_url and len(link_url) > 80:
                    link_line = f"🔗 원문 출처: {s['source']} (상세 링크는 유튜브 설명란 참조)\n"
                elif link_url and link_url != "#":
                    link_line = f"🔗 원문 링크: {link_url}\n"
                else:
                    link_line = f"🔗 원문 출처: {s['source']}\n"

                b = f"🌐 [{s['index']}] {s['title']} ({s['source']})\n"
                if summ:
                    b += f"• 상세 번역 브리핑:\n  {summ}\n"
                b += link_line
                blocks.append(b)
            return "\n".join(blocks) + "\n"

        # 인스타그램 2,200자 제한 안전 가드레일 (기사 요약 길이 동적 조정, 최대 2,150자 이내 보장)
        summary_limit = 500
        caption_text = ""
        while summary_limit >= 150:
            sources_text = build_global_sources_block(summary_limit)
            caption_text = (
                f"📋 [THEPT 글로벌 주간 브리핑 - {day_name}]\n"
                f"{day_name} THEPT 물리치료 1분 브리핑\n\n"
                f"해외 최신 임상 가이드라인과 재활 연구 등 주요 뉴스 {num_arts}가지의 상세 번역 브리핑을 전해드립니다.\n"
                f"카드뉴스를 넘겨보신 후 아래 상세 내용을 확인해보세요! 👉\n\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"🌐 [글로벌 뉴스 심층 번역 브리핑 & 원문 출처]\n\n"
                f"{sources_text}"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"💬 더 많은 글로벌 임상 연구 자료와 동료 치료사들의 토론은\n"
                f"'THEPT 커뮤니티' (https://thept.co.kr) 에서 확인하실 수 있습니다!\n\n"
                f"📌 방문재활 AI 음성 차팅 무료 체험: https://4thept.com\n"
                f"📘 [크몽 전자책] 병원밖 물리치료사 - 가성비 소규모 센터창업 가이드: https://kmong.com/gig/813101\n"
                f"📢 광고 및 비즈니스 제휴 문의: teamthept@gmail.com\n\n"
                f"도움이 되셨다면 좋아요 ❤️ 와 동료 치료사에게 공유 ✈️ 부탁드립니다!\n"
                f"{tags_line}\n"
            )
            if len(caption_text) <= 2150:
                break
            summary_limit -= 50
    else:
        sources_text = ""
        for s in sources:
            sources_text += f"{s['index']}. {s['title']} ({s['source']})\n   🔗 {s['link']}\n\n"

        caption_text = (
            f"📋 [THEPT 주간 브리핑 - {day_name}]\n"
            f"{day_name} THEPT 물리치료 1분 브리핑\n\n"
            f"주요 핵심 뉴스 {num_arts}가지의 상세 카드뉴스입니다.\n"
            f"슬라이드를 넘겨 각 뉴스의 핵심 포인트를 확인해보세요! 👉\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📰 [기사 원문 출처 및 링크]\n"
            f"{sources_text}"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"💬 더 많은 임상 연구 자료와 동료 치료사들의 토론은\n"
            f"'THEPT커뮤니티' (https://thept.co.kr) 에서 확인하실 수 있습니다!\n\n"
            f"📌 방문재활 AI 음성 차팅 무료 체험: https://4thept.com\n"
            f"📘 [크몽 전자책] 병원밖 물리치료사 - 가성비 소규모 센터창업 가이드: https://kmong.com/gig/813101\n"
            f"📢 광고 및 비즈니스 제휴 문의: teamthept@gmail.com\n\n"
            f"도움이 되셨다면 좋아요 ❤️ 와 동료 치료사에게 공유 ✈️ 부탁드립니다!\n"
            f"{tags_line}\n"
        )

    return {
        "day_name": day_name,
        "category_title": category_title,
        "title": main_title,
        "is_global": is_global,
        "sources": sources,
        "slides": slides,
        "caption": caption_text
    }




