# 이 모듈은 뉴스 수집부터 4:5 카드뉴스 및 9:16 쇼츠 영상 렌더링까지 전 과정을 일괄 실행합니다.
# 일자별 폴더에 카드뉴스, 음성, 쇼츠 비디오 및 커뮤니티 포스팅용 자료를 체계적으로 아카이빙합니다.

import sys
from pathlib import Path
import asyncio
from datetime import datetime
import json
import re
import shutil

# 윈도우 콘솔 유니코드(이모지 등) 인코딩 처리
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

sys.path.append(str(Path(__file__).resolve().parent))

from config import OUTPUT_DIR, DEFAULT_BG_PATH, AI_TECH_BG_PATH
from modules.news_collector import collect_weekly_3batches
from modules.content_builder import build_weekly_3batches_schedule, build_daily_curated_package
from modules.card_renderer import render_cards_to_images
from modules.tts_synthesizer import synthesize_all_narration
from modules.video_renderer import render_shorts_video
from modules.article_image_fetcher import fetch_article_images

# 공식 첫 댓글(고정 댓글) 템플릿
FIRST_COMMENT_TEXT = (
    "📌 [THEPT 추천] 물리치료사를 위한 실전 솔루션 & 창업 가이드!\n\n"
    "1️⃣ 방문재활 물리치료사 맞춤 AI 음성 차팅\n"
    "• 수기 차팅 부담은 줄이고 환자 관리에 집중하세요! (매월 무료 체험)\n"
    "👉 바로가기: https://4thept.com\n\n"
    "2️⃣ 크몽 전자책 『병원밖 물리치료사 - 가성비 소규모 센터창업 가이드』\n"
    "• 병원 밖 독립을 꿈꾸는 물리치료사를 위한 소규모 센터 창업 실전 노하우!\n"
    "👉 크몽 바로가기: https://kmong.com/gig/813101\n\n"
    "💬 최신 물리치료 임상·정책 자료와 동료 치료사 커뮤니티: https://thept.co.kr\n"
    "📢 광고 및 비즈니스 제휴 문의: teamthept@gmail.com"
)



async def run_weekly_pipeline(
    domestic_keywords_a: list[str] = None,
    domestic_keywords_b: list[str] = None,
    global_keywords: list[str] = None
) -> dict:
    """
    주간 3대 브리핑 세트(총 9개 기사: 국내 정책 3 + 국내 임상 3 + 해외 글로벌 3)를 기반으로
    월·수·금 1분 쇼츠 3편 및 화·목·토 4:5 카드뉴스 3편을 요일별 6개 폴더에 일괄 생성합니다.
    """
    today_str = datetime.now().strftime("%Y-%m-%d")
    weekly_dir = OUTPUT_DIR / f"{today_str}_weekly"
    bg_dir = weekly_dir / "backgrounds"

    weekly_dir.mkdir(parents=True, exist_ok=True)
    bg_dir.mkdir(parents=True, exist_ok=True)

    # 기본/생성 배경 복사
    if DEFAULT_BG_PATH.exists():
        shutil.copy(DEFAULT_BG_PATH, bg_dir / "pt_clinic_bg.jpg")
    if AI_TECH_BG_PATH.exists():
        shutil.copy(AI_TECH_BG_PATH, bg_dir / "ai_rehab_bg.jpg")

    print("=" * 70)
    print(f"🚀 [THEPT] 주간 3대 브리핑 세트 기반 6일 연계 콘텐츠 자동 생성 ({today_str})")
    print("   📅 월·수·금: 3기사 1분 브리핑 쇼츠 | 화·목·토: 3기사 4:5 심층 카드뉴스")
    print("   💡 배치 1: 국내 정책·제도 | 배치 2: 임상 연구·기술 | 배치 3: 해외 트렌드")
    print("=" * 70)

    # 1. 뉴스 대량 수집 및 3대 브리핑 배치(총 9건 기사) 편성
    print("\n[단계 1/5] 주간 국내 정책/임상 및 글로벌 뉴스 수집 및 3대 배치 편성 중...")
    batches = collect_weekly_3batches(
        domestic_keywords_a=domestic_keywords_a,
        domestic_keywords_b=domestic_keywords_b,
        global_keywords=global_keywords
    )
    print(f"  -> 총 {batches['total_collected']}건 기사 수집 완료")
    print(f"  -> [배치 1] 국내 정책·제도 A (월/화): {len(batches['batch_1'])}건")
    for i, a in enumerate(batches["batch_1"], 1):
        print(f"     {i}. {a['title']} ({a['source']})")
    print(f"  -> [배치 2] 임상 연구·첨단 B (수/목): {len(batches['batch_2'])}건")
    for i, a in enumerate(batches["batch_2"], 1):
        print(f"     {i}. {a['title']} ({a['source']})")
    print(f"  -> [배치 3] 해외 글로벌 C (금/토): {len(batches['batch_3'])}건")
    for i, a in enumerate(batches["batch_3"], 1):
        print(f"     {i}. {a['title']} ({a['source']})")

    # 2. 9개 기사 실제 보도 사진 병렬 크롤링 (Playwright)
    print("\n[단계 2/5] 9개 기사 실제 원문 보도 사진 크롤링 중 (Playwright)...")
    print("  -> 배치 1 보도 사진 크롤링:")
    b1_photos = await fetch_article_images(batches["batch_1"], bg_dir, prefix="b1")
    print("  -> 배치 2 보도 사진 크롤링:")
    b2_photos = await fetch_article_images(batches["batch_2"], bg_dir, prefix="b2")
    print("  -> 배치 3 (글로벌) 보도 사진 크롤링:")
    b3_photos = await fetch_article_images(batches["batch_3"], bg_dir, prefix="b3")

    batch_photos = {
        "batch_1": b1_photos,
        "batch_2": b2_photos,
        "batch_3": b3_photos
    }
    total_photos = len(b1_photos) + len(b2_photos) + len(b3_photos)
    print(f"  -> 총 {total_photos}/9건 실제 보도 사진 획득 완료 (전체 보도 사진 풀에서 슬라이드 배경 자동 배분)")

    # 3. 요일별 6개 콘텐츠 패키지 빌드
    print("\n[단계 3/5] 요일별 6개 전용 패키지 및 1분 나레이션 대본 구조화 중...")
    weekly_packages = build_weekly_3batches_schedule(
        batches=batches,
        bg_dir=bg_dir,
        batch_photos=batch_photos
    )
    print(f"  -> 총 {len(weekly_packages)}개 패키지 준비 완료")

    # 4. 콘텐츠 렌더링: 1단계 마스터 카드뉴스(화·목·토) -> 2단계 쇼츠 비디오(월·수·금)
    print("\n[단계 4/5] 2단계 파이프라인 렌더링 시작...")
    results_by_day = []

    # 패키지 매핑 (월-화: b1, 수-목: b2, 금-토: b3)
    # weekly_packages 순서: 0(월), 1(화), 2(수), 3(목), 4(금), 5(토)
    pkg_mon = weekly_packages[0]
    pkg_tue = weekly_packages[1]
    pkg_wed = weekly_packages[2]
    pkg_thu = weekly_packages[3]
    pkg_fri = weekly_packages[4]
    pkg_sat = weekly_packages[5]

    card_master_pairs = [
        ("화요일", pkg_tue, "02_Tue_CardNews", "batch_1"),
        ("목요일", pkg_thu, "04_Thu_CardNews", "batch_2"),
        ("토요일", pkg_sat, "06_Sat_CardNews_Global", "batch_3"),
    ]

    master_card_paths = {}

    # [1단계] 화·목·토 4:5 마스터 카드뉴스 3세트 (총 18장) 우선 렌더링
    print("\n  ▶ [1단계] 화·목·토 마스터 4:5 카드뉴스 3세트(총 18장) 렌더링...")
    for day_name, pkg, folder_name, b_key in card_master_pairs:
        day_dir = weekly_dir / folder_name
        day_dir.mkdir(parents=True, exist_ok=True)
        print(f"\n     🎨 [{day_name}] 카드뉴스 원본 제작 -> {folder_name}...")

        # 패키지 메타데이터 저장
        (day_dir / "package_data.json").write_text(
            json.dumps(pkg, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )

        cards_dir = day_dir / "card_images_4x5"
        card_paths = await render_cards_to_images(pkg, cards_dir)
        master_card_paths[b_key] = card_paths

        # 인스타그램 피드 캡션 및 출처 저장
        sources = pkg.get("sources", [])
        insta_caption = (
            f"📋 [THEPT 주간 브리핑 카드뉴스 - {day_name}]\n"
            f"{pkg['title']}\n\n"
            f"주요 핵심 뉴스 3가지의 상세 카드뉴스입니다.\n"
            f"슬라이드를 넘겨 각 뉴스의 핵심 포인트를 확인해보세요! 👉\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📰 [기사 원문 출처 및 링크]\n"
        )
        for s in sources:
            insta_caption += f"{s['index']}. {s['title']} ({s['source']})\n   🔗 {s['link']}\n\n"
        insta_caption += (
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"💬 더 많은 임상 연구 자료와 동료 치료사들의 의견은\n"
            f"'THEPT커뮤니티' (https://thept.co.kr) 에서 확인하실 수 있습니다!\n\n"
            f"📌 방문재활 AI 음성 차팅 무료 체험: https://4thept.com\n"
            f"📘 [크몽 전자책] 병원밖 물리치료사 - 가성비 소규모 센터창업 가이드: https://kmong.com/gig/813101\n"
            f"📢 광고 및 비즈니스 제휴 문의: teamthept@gmail.com\n\n"
            f"도움이 되셨다면 게시물 저장 📌 과 동료 치료사에게 공유 ✈️ 부탁드립니다!\n"
            f"#물리치료 #도수치료 #재활치료 #물리치료사 #THEPT #더피티 #카드뉴스 #피지컬테라피\n"
        )
        (day_dir / "instagram_caption.txt").write_text(insta_caption, encoding="utf-8")
        (day_dir / "sources_and_links.txt").write_text(insta_caption, encoding="utf-8")
        (day_dir / "first_comment.txt").write_text(FIRST_COMMENT_TEXT, encoding="utf-8")

        results_by_day.append({
            "day": day_name,
            "type": "cardnews",
            "folder": day_dir,
            "cards_count": len(card_paths)
        })
        print(f"     ✅ 4:5 마스터 카드뉴스 완성 ({len(card_paths)}장 PNG)")

    # [2단계] 월·수·금 1분 쇼츠 비디오 3편 (마스터 카드 이미지 직접 참조하여 고속 제작)
    print("\n  ▶ [2단계] 월·수·금 1분 쇼츠 3편 고속 영상화 (카드 재렌더링 없이 원본 이미지 직접 참조)...")
    shorts_pairs = [
        ("월요일", pkg_mon, "01_Mon_Shorts", "batch_1"),
        ("수요일", pkg_wed, "03_Wed_Shorts", "batch_2"),
        ("금요일", pkg_fri, "05_Fri_Shorts_Global", "batch_3"),
    ]

    for day_name, pkg, folder_name, b_key in shorts_pairs:
        day_dir = weekly_dir / folder_name
        day_dir.mkdir(parents=True, exist_ok=True)
        print(f"\n     🎬 [{day_name}] 쇼츠 비디오 제작 -> {folder_name}...")

        # 패키지 메타데이터 저장
        (day_dir / "package_data.json").write_text(
            json.dumps(pkg, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )

        audio_dir = day_dir / "audio"
        video_path = day_dir / "shorts_1080x1920.mp4"

        # 마스터 카드뉴스 이미지를 그대로 소스로 활용 (중복 렌더링 0회)
        card_paths = master_card_paths[b_key]

        # 고속 나레이션 TTS 합성
        audio_results = await synthesize_all_narration(pkg, audio_dir)
        total_sec = sum(a["duration"] for a in audio_results)

        # 9:16 세로형 쇼츠 비디오 렌더링
        render_shorts_video(card_paths, audio_results, video_path)

        # 유튜브 쇼츠 설명란 (타임라인 + 기사 1줄 요약 + 원문 링크)
        cum_sec = 0.0
        timestamps = []
        for a in audio_results:
            m = int(cum_sec // 60)
            s = int(cum_sec % 60)
            timestamps.append(f"{m:02d}:{s:02d}")
            cum_sec += a.get("duration", 0.0)

        t_intro = timestamps[0] if len(timestamps) > 0 else "00:00"
        t_n1 = timestamps[1] if len(timestamps) > 1 else "00:07"
        t_n2 = timestamps[2] if len(timestamps) > 2 else "00:23"
        t_n3 = timestamps[3] if len(timestamps) > 3 else "00:39"
        t_outro = timestamps[-1] if len(timestamps) > 4 else "00:52"

        sources = pkg.get("sources", [])
        slides = pkg.get("slides", [])
        news_slides = [s for s in slides if s.get("type") == "news"]

        def get_summary(idx):
            if idx < len(news_slides):
                sdata = news_slides[idx].get("data", {})
                hl = sdata.get("highlight", "")
                if hl:
                    return hl
                bullets = sdata.get("bullets", [])
                if bullets:
                    return bullets[0]
            return ""

        s1_summary = get_summary(0)
        s2_summary = get_summary(1)
        s3_summary = get_summary(2)

        s1 = sources[0] if len(sources) > 0 else {"title": "", "source": "", "link": ""}
        s2 = sources[1] if len(sources) > 1 else {"title": "", "source": "", "link": ""}
        s3 = sources[2] if len(sources) > 2 else {"title": "", "source": "", "link": ""}

        raw_title = pkg.get("title", f"{day_name} 물리치료 브리핑")
        clean_title = re.sub(r"<[^>]+>", "", raw_title).strip()

        shorts_caption = (
            f"📢 [{day_name}] {clean_title} #Shorts\n\n"
            f"한 주간 가장 주목할 물리치료 최신 뉴스 3가지를 1분 만에 전해드립니다!\n\n"
            f"⏱️ [타임라인 & 기사 원문 요약]\n"
            f"{t_intro} 인트로\n"
            f"{t_n1} [1] {s1['title']} ({s1['source']})\n"
            f"  • {s1_summary}\n"
            f"  🔗 원문 링크: {s1['link']}\n\n"
            f"{t_n2} [2] {s2['title']} ({s2['source']})\n"
            f"  • {s2_summary}\n"
            f"  🔗 원문 링크: {s2['link']}\n\n"
            f"{t_n3} [3] {s3['title']} ({s3['source']})\n"
            f"  • {s3_summary}\n"
            f"  🔗 원문 링크: {s3['link']}\n\n"
            f"{t_outro} 아웃트로\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📌 물리치료사를 위한 전문 플랫폼 THEPT\n"
            f"• 방문재활 AI 음성 차팅: https://4thept.com\n"
            f"• [크몽 전자책] 병원밖 물리치료사 - 가성비 소규모 센터창업 가이드: https://kmong.com/gig/813101\n"
            f"• THEPT 공식 커뮤니티: https://thept.co.kr\n"
            f"• 광고 및 비즈니스 제휴: teamthept@gmail.com\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"#물리치료 #물리치료사 #쇼츠 #Shorts #더피티 #THEPT #도수치료 #재활치료\n"
        )
        (day_dir / "youtube_shorts_caption.txt").write_text(shorts_caption, encoding="utf-8")
        (day_dir / "first_comment.txt").write_text(FIRST_COMMENT_TEXT, encoding="utf-8")

        results_by_day.append({
            "day": day_name,
            "type": "shorts",
            "folder": day_dir,
            "video_path": video_path,
            "duration": total_sec
        })
        print(f"     ✅ 쇼츠 비디오 완성 ({total_sec:.2f}초, {video_path.stat().st_size / (1024*1024):.2f} MB)")

    # 5. 주간 통합 출처 및 링크 문서 작성
    print("\n[단계 5/5] 주간 전체 통합 출처 및 발행 가이드 저장 중...")
    sources_summary = (
        f"📌 [THEPT 주간 3대 브리핑 세트 통합 출처 및 스케줄 - {today_str}]\n"
        f"월~토 콘텐츠 배포 시 댓글 및 설명란에 활용하세요.\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📅 [주간 요일별 6대 폴더 구성]\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    )
    for res in results_by_day:
        d = res["day"]
        t = res["type"].upper()
        f = res["folder"].name
        sources_summary += f"• [{d}] {t} -> {f}\n"

    sources_summary += "\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    sources_summary += "📰 [배치 1: 국내 A 3기사 원문 출처 (월 쇼츠 / 화 카드뉴스)]\n"
    sources_summary += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    for idx, art in enumerate(batches["batch_1"], 1):
        sources_summary += f"{idx}. {art['title']} ({art['source']})\n   🔗 {art['link']}\n\n"

    sources_summary += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    sources_summary += "📰 [배치 2: 국내 B 3기사 원문 출처 (수 쇼츠 / 목 카드뉴스)]\n"
    sources_summary += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    for idx, art in enumerate(batches["batch_2"], 1):
        sources_summary += f"{idx}. {art['title']} ({art['source']})\n   🔗 {art['link']}\n\n"

    sources_summary += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    sources_summary += "📰 [배치 3: 해외 C 3기사 원문 출처 (금 쇼츠 / 토 카드뉴스)]\n"
    sources_summary += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    for idx, art in enumerate(batches["batch_3"], 1):
        sources_summary += f"{idx}. {art['title']} ({art['source']})\n   🔗 {art['link']}\n\n"

    weekly_sources_file = weekly_dir / "weekly_sources_and_links.txt"
    weekly_sources_file.write_text(sources_summary, encoding="utf-8")

    # 결과 출력
    print("\n" + "=" * 70)
    print("🎉 [THEPT] 주간 3대 브리핑 세트 기반 6일 연계 콘텐츠 자동 생성 완료!")
    print(f"📁 주간 마스터 저장 위치: {weekly_dir}")
    print(f"   ├─ 📂 01_Mon_Shorts/ (월요일 국내 A 브리핑 쇼츠 영상)")
    print(f"   ├─ 📂 02_Tue_CardNews/ (화요일 국내 A 심층 카드뉴스 6장)")
    print(f"   ├─ 📂 03_Wed_Shorts/ (수요일 국내 B 브리핑 쇼츠 영상)")
    print(f"   ├─ 📂 04_Thu_CardNews/ (목요일 국내 B 심층 카드뉴스 6장)")
    print(f"   ├─ 📂 05_Fri_Shorts_Global/ (금요일 해외 C 브리핑 쇼츠 영상)")
    print(f"   ├─ 📂 06_Sat_CardNews_Global/ (토요일 해외 C 심층 카드뉴스 6장)")
    print(f"   ├─ 🌄 backgrounds/ (수집된 실제 보도 사진 9건 풀)")
    print(f"   └─ 🔗 weekly_sources_and_links.txt (주간 전체 출처 및 링크 모음)")
    print("=" * 70)

    return {
        "weekly_dir": weekly_dir,
        "results_by_day": results_by_day,
        "batches": batches,
        "sources_file": weekly_sources_file
    }


# ==============================================================================
# 주 6일 큐레이션 통합 파이프라인 (월~토 매일 쇼츠 + 카드뉴스 동시 생성)
# ==============================================================================

async def run_curated_6days_pipeline(daily_articles_map: dict, render_media: bool = True, target_dir: Path = None) -> dict:
    """
    큐레이션된 6대 카테고리(월~토) 기사(각 2~3건)를 바탕으로,
    매일 [4:5 카드뉴스 + 최대 2분 쇼츠 비디오 + SNS 캡션]을 동시 생성하여 요일별 6개 폴더에 저장합니다.
    (render_media=False 시 이미지/비디오 인코딩을 건너뛰고 대본, 요약, 패키지 메타데이터만 고속 생성합니다.)
    """
    today_str = datetime.now().strftime("%Y-%m-%d")
    weekly_dir = Path(target_dir) if target_dir else (OUTPUT_DIR / f"{today_str}_curated_weekly")
    bg_dir = weekly_dir / "backgrounds"

    weekly_dir.mkdir(parents=True, exist_ok=True)
    bg_dir.mkdir(parents=True, exist_ok=True)

    # 기본 배경 복사
    if DEFAULT_BG_PATH.exists():
        shutil.copy(DEFAULT_BG_PATH, bg_dir / "pt_clinic_bg.jpg")
    if AI_TECH_BG_PATH.exists():
        shutil.copy(AI_TECH_BG_PATH, bg_dir / "ai_rehab_bg.jpg")

    print("=" * 70)
    print(f"🚀 [THEPT] 주 6일 큐레이션 기반 통합 콘텐츠 자동 생성 ({today_str})")
    print(f"   📅 월~토 매일: [4:5 카드뉴스 + 최대 2분 쇼츠 비디오 + SNS 캡션] 동시 조립 (미디어 렌더링: {'ON' if render_media else '대기 (패키지만 생성)'})")
    print("=" * 70)

    # 요일별 폴더 및 카테고리 정의
    day_configs = [
        ("mon_policy", "월요일", "01_Mon_Policy", "국내 정책·제도·수가·협회", False),
        ("tue_creator", "화요일", "02_Tue_Creator", "유튜버·인플루언서·운동이슈", False),
        ("wed_sports", "수요일", "03_Wed_Sports", "운동·스포츠 재활", False),
        ("thu_tech", "목요일", "04_Thu_Tech", "첨단 재활 기술·AI·로봇", False),
        ("fri_celeb", "금요일", "05_Fri_Celeb", "셀럽 스타 치료 & 건강 가십", False),
        ("sat_global", "토요일", "06_Sat_Global", "해외 글로벌 트렌드", True),
    ]

    results_by_day = []

    for cat_key, day_name, folder_name, cat_title, is_global in day_configs:
        articles = daily_articles_map.get(cat_key, [])
        if not articles:
            print(f"\n⚠️ [{day_name}] 선택된 기사가 없어 건너뜁니다.")
            continue

        day_dir = weekly_dir / folder_name
        day_dir.mkdir(parents=True, exist_ok=True)
        cards_dir = day_dir / "card_images_4x5"
        audio_dir = day_dir / "audio"
        video_path = day_dir / "shorts_1080x1920.mp4"

        print(f"\n[{day_name}] {cat_title} ({len(articles)}개 기사) 제작 시작 -> {folder_name}")

        # 1. 보도 사진 확보
        prefix = cat_key[:3]
        day_photos = await fetch_article_images(articles, bg_dir, prefix=prefix)

        # 2. 일별 통합 패키지 조립 (LLM 요약 및 TTS 정밀 정제 반영)
        pkg = build_daily_curated_package(
            day_name=day_name,
            category_title=cat_title,
            articles=articles,
            bg_dir=bg_dir,
            article_photos=day_photos,
            is_global=is_global
        )

        (day_dir / "package_data.json").write_text(
            json.dumps(pkg, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )

        card_paths = []
        audio_results = []
        total_sec = 0.0

        if render_media:
            # 3. 4:5 카드뉴스 렌더링
            print(f"  🎨 4:5 고화질 카드뉴스 렌더링 중...")
            card_paths = await render_cards_to_images(pkg, cards_dir)
            print(f"  ✅ 카드뉴스 완성 ({len(card_paths)}장 PNG)")

            # 4. 고품질 TTS 나레이션 합성 (최대 2분 분량 호흡)
            print(f"  🎙️ TTS 음성 나레이션 합성 중...")
            audio_results = await synthesize_all_narration(pkg, audio_dir)
            total_sec = sum(a["duration"] for a in audio_results)

            # 5. 9:16 쇼츠 비디오 렌더링
            print(f"  🎬 9:16 쇼츠 비디오 합성 중...")
            render_shorts_video(card_paths, audio_results, video_path)
            print(f"  ✅ 쇼츠 완성 ({total_sec:.2f}초, {video_path.stat().st_size / (1024*1024):.2f} MB)")
        else:
            print(f"  ℹ️ [렌더링 가드레일] 카드뉴스/비디오 미디어 파일 렌더링은 대기합니다. (대본 및 패키지 데이터 생성 완료)")

        # 6. 인스타그램 및 유튜브 캡션, 첫 댓글 저장
        (day_dir / "instagram_caption.txt").write_text(pkg["caption"], encoding="utf-8")

        # 유튜브 쇼츠 설명란 생성 (타임라인 + 기사 1줄 요약 + 원문 링크)
        cum_sec = 0.0
        timestamps = []
        if audio_results:
            for a in audio_results:
                m = int(cum_sec // 60)
                s = int(cum_sec % 60)
                timestamps.append(f"{m:02d}:{s:02d}")
                cum_sec += a.get("duration", 0.0)
        else:
            timestamps = ["00:00", "00:07", "00:23", "00:39", "00:52"]

        t_intro = timestamps[0] if len(timestamps) > 0 else "00:00"
        t_n1 = timestamps[1] if len(timestamps) > 1 else "00:07"
        t_n2 = timestamps[2] if len(timestamps) > 2 else "00:23"
        t_n3 = timestamps[3] if len(timestamps) > 3 else "00:39"
        t_outro = timestamps[-1] if len(timestamps) > 4 else "00:52"

        sources = pkg.get("sources", [])
        slides = pkg.get("slides", [])
        news_slides = [s for s in slides if s.get("type") == "news"]

        def get_summary(idx):
            if idx < len(news_slides):
                sdata = news_slides[idx].get("data", {})
                hl = sdata.get("highlight", "")
                if hl:
                    return hl
                bullets = sdata.get("bullets", [])
                if bullets:
                    return bullets[0]
            return ""

        s1_summary = get_summary(0)
        s2_summary = get_summary(1)
        s3_summary = get_summary(2)

        s1 = sources[0] if len(sources) > 0 else {"title": "", "source": "", "link": ""}
        s2 = sources[1] if len(sources) > 1 else {"title": "", "source": "", "link": ""}
        s3 = sources[2] if len(sources) > 2 else {"title": "", "source": "", "link": ""}

        raw_title = pkg.get("title", f"{day_name} 물리치료 브리핑")
        clean_title = re.sub(r"<[^>]+>", "", raw_title).strip()

        if is_global:
            # 글로벌 기사 전용 유튜브 쇼츠 설명란: 상세 번역 브리핑 전문 수록
            articles_briefing_text = ""
            for idx, s in enumerate(sources, 1):
                t_stamp = timestamps[idx] if idx < len(timestamps) else f"00:{idx*15:02d}"
                summ = s.get("story_summary", "")
                articles_briefing_text += f"{t_stamp} [{idx}] {s['title']} ({s['source']})\n"
                if summ:
                    articles_briefing_text += f"  • 상세 번역 브리핑:\n    {summ}\n"
                articles_briefing_text += f"  🔗 원문 링크: {s['link']}\n\n"

            shorts_caption = (
                f"📢 [{day_name}] {clean_title} #Shorts\n\n"
                f"해외 최신 물리치료 임상 가이드라인과 글로벌 트렌드 {len(articles)}가지를 전해드립니다!\n\n"
                f"⏱️ [타임라인 & 글로벌 뉴스 심층 번역 브리핑]\n"
                f"{t_intro} 인트로\n"
                f"{articles_briefing_text}"
                f"{t_outro} 아웃트로\n\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"📌 물리치료사를 위한 전문 플랫폼 THEPT\n"
                f"• 방문재활 AI 음성 차팅: https://4thept.com\n"
                f"• [크몽 전자책] 병원밖 물리치료사 - 가성비 소규모 센터창업 가이드: https://kmong.com/gig/813101\n"
                f"• THEPT 공식 커뮤니티: https://thept.co.kr\n"
                f"• 광고 및 비즈니스 제휴: teamthept@gmail.com\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"#물리치료 #물리치료사 #쇼츠 #Shorts #THEPT #더피티 #재활 #해외물리치료\n"
            )
        else:
            shorts_caption = (
                f"📢 [{day_name}] {clean_title} #Shorts\n\n"
                f"한 주간 가장 주목할 물리치료 최신 뉴스 {len(articles)}가지를 1분 만에 전해드립니다!\n\n"
                f"⏱️ [타임라인 & 기사 원문 요약]\n"
                f"{t_intro} 인트로\n"
                f"{t_n1} [1] {s1['title']} ({s1['source']})\n"
                f"  • {s1_summary}\n"
                f"  🔗 원문 링크: {s1['link']}\n\n"
                f"{t_n2} [2] {s2['title']} ({s2['source']})\n"
                f"  • {s2_summary}\n"
                f"  🔗 원문 링크: {s2['link']}\n\n"
                f"{t_n3} [3] {s3['title']} ({s3['source']})\n"
                f"  • {s3_summary}\n"
                f"  🔗 원문 링크: {s3['link']}\n\n"
                f"{t_outro} 아웃트로\n\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"📌 물리치료사를 위한 전문 플랫폼 THEPT\n"
                f"• 방문재활 AI 음성 차팅: https://4thept.com\n"
                f"• [크몽 전자책] 병원밖 물리치료사 - 가성비 소규모 센터창업 가이드: https://kmong.com/gig/813101\n"
                f"• THEPT 공식 커뮤니티: https://thept.co.kr\n"
                f"• 광고 및 비즈니스 제휴: teamthept@gmail.com\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"#물리치료 #물리치료사 #쇼츠 #Shorts #THEPT #더피티 #재활\n"
            )
        (day_dir / "youtube_shorts_caption.txt").write_text(shorts_caption, encoding="utf-8")
        (day_dir / "first_comment.txt").write_text(FIRST_COMMENT_TEXT, encoding="utf-8")

        # 7. 기사 출처 및 선택 이유 저장
        curation_notes = f"📌 [{day_name} 큐레이션 기사 및 선택 이유]\n\n"
        for idx, a in enumerate(articles, 1):
            curation_notes += f"{idx}. {a.get('title')}\n"
            curation_notes += f"   - 출처: {a.get('source')} ({a.get('pub_date')})\n"
            curation_notes += f"   - 링크: {a.get('link')}\n"
            curation_notes += f"   - 선택 이유: {a.get('selection_reason', '(미입력)')}\n\n"
        (day_dir / "curation_notes.txt").write_text(curation_notes, encoding="utf-8")

        results_by_day.append({
            "day": day_name,
            "category": cat_title,
            "folder": day_dir,
            "cards_count": len(card_paths),
            "video_duration": total_sec,
            "video_path": video_path
        })

    # 주간 요약 문서 작성
    summary_path = weekly_dir / "weekly_summary.md"
    summary_lines = [
        f"# 📊 THEPT 주 6일 큐레이션 통합 콘텐츠 제작 결과 ({today_str})",
        "",
        "| 요일 | 카테고리 | 카드뉴스 | 쇼츠 비디오 길이 | 저장 폴더 |",
        "|---|---|---|---|---|"
    ]
    for r in results_by_day:
        summary_lines.append(
            f"| {r['day']} | {r['category']} | {r['cards_count']}장 | {r['video_duration']:.1f}초 | `{r['folder'].name}` |"
        )
    summary_path.write_text("\n".join(summary_lines), encoding="utf-8")

    print("\n" + "=" * 70)
    print("🎉 [주간 6일 일괄 제작 성공] 모든 요일의 쇼츠와 카드뉴스가 생성되었습니다!")
    for r in results_by_day:
        print(f"  • [{r['day']}] {r['category']}: 카드뉴스 {r['cards_count']}장 + 쇼츠 {r['video_duration']:.1f}초 ({r['folder'].name})")
    print(f"👉 전체 결과 요약: {summary_path}")
    print("=" * 70)

    return {
        "weekly_dir": weekly_dir,
        "results": results_by_day,
        "summary_file": summary_path
    }


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="THEPT 주간 파이프라인")
    parser.add_argument("--weekly", action="store_true", default=True, help="주간 6일 일괄 생성 모드 (기본값)")
    args = parser.parse_args()

    if args.weekly:
        asyncio.run(run_weekly_pipeline())
    else:
        asyncio.run(run_pipeline())

