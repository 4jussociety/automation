# 이 모듈은 뉴스 수집부터 4:5 카드뉴스 및 9:16 쇼츠 영상 렌더링까지 전 과정을 일괄 실행합니다.
# 일자별 폴더에 카드뉴스, 음성, 쇼츠 비디오 및 커뮤니티 포스팅용 자료를 체계적으로 아카이빙합니다.

import sys
from pathlib import Path
import asyncio
from datetime import datetime, timedelta
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

from config import (
    OUTPUT_DIR, DEFAULT_BG_PATH, AI_TECH_BG_PATH,
    TEMPLATE_4X5, TEMPLATE_9X16,
    CARD_WIDTH, CARD_HEIGHT,
    VIDEO_WIDTH, VIDEO_HEIGHT
)
from modules.content_builder import build_daily_curated_package
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





# ==============================================================================
def match_day_filter(query: str, cat_key: str, day_name: str, folder_name: str) -> bool:
    """
    요일 검색어(query)가 특정 요일과 일치하는지 유연하게 판정합니다.
    - 날짜: '0910', '9/10', '9-10', '10', '10일' 등
    - 영문: 'mon', 'tue', 'wed', 'thu', 'fri', 'sat'
    - 한글: '월', '화', '수', '목', '금', '토', '월요일', '목요일' 등
    - 번호: '1', '2', '3', '4', '5', '6', '01', '02', '03', '04', '05', '06'
    - 폴더/카테고리명: '0910_Thu_Tech', '04_Thu_Tech', 'thu_tech', 'sports' 등
    """
    if not query:
        return True
    raw_q = query.strip().lower()

    # 쉼표(,) 구분자로 복수 요일 지정 지원 (예: 'thu,fri,sat', '목,금,토', '10,11,12')
    if "," in raw_q:
        return any(
            match_day_filter(part.strip(), cat_key, day_name, folder_name)
            for part in raw_q.split(",")
            if part.strip()
        )

    # 날짜 정규화 ('9/10', '09-10' -> '0910', '10일' -> '10')
    q = raw_q.replace("일", "").strip()
    m_date = re.match(r"^(\d{1,2})[/.-](\d{1,2})$", q)
    if m_date:
        q = f"{int(m_date.group(1)):02d}{int(m_date.group(2)):02d}"

    # 1. 4자리 MMDD 날짜 매칭 (예: '0910')
    if len(q) == 4 and q.isdigit():
        if q in folder_name.lower():
            return True

    # 2. 1~2자리 일(Day) 매칭 (예: '10' -> '0910_Thu_Tech'의 10일)
    if q.isdigit() and len(q) <= 2:
        m_folder_day = re.match(r"^\d{2}(\d{2})_", folder_name)
        if m_folder_day and int(m_folder_day.group(1)) == int(q):
            return True

    # 3. 요일별 키워드 매핑 테이블
    alias_map = {
        "mon_policy": ["mon", "월", "월요일", "1", "01", "policy", "정책", "수가"],
        "tue_clinical": ["tue", "화", "화요일", "2", "02", "clinical", "임상", "도수", "creator"],
        "wed_sports": ["wed", "수", "수요일", "3", "03", "sports", "스포츠", "운동"],
        "thu_tech": ["thu", "목", "목요일", "4", "04", "tech", "기술", "ai", "로봇"],
        "fri_celeb": ["fri", "금", "금요일", "5", "05", "celeb", "셀럽", "스타", "youtube", "유튜브"],
        "sat_global": ["sat", "토", "토요일", "6", "06", "global", "글로벌", "해외"],
    }

    # cat_key 기준 별칭 검사
    for key, aliases in alias_map.items():
        if key in cat_key or cat_key in key:
            if q in aliases or any(q == a for a in aliases):
                return True

    # 폴더명(0910_Thu_Tech) 등 문자열 포함 검사
    folder_low = folder_name.lower()
    day_low = day_name.lower()
    cat_low = cat_key.lower()

    if q in folder_low or q in day_low or q in cat_low:
        return True

    # 한글 요일 축약 매칭 (예: '목' in '목요일')
    for d_char in ["월", "화", "수", "목", "금", "토"]:
        if q == d_char and d_char in day_name:
            return True

    return False


async def run_curated_6days_pipeline(
    daily_articles_map: dict,
    render_media: bool = True,
    target_dir: Path = None,
    day_filter: str = None
) -> dict:
    """
    큐레이션된 6대 카테고리(월~토) 기사(각 2~3건)를 바탕으로,
    매일 [4:5 카드뉴스 + 최대 2분 쇼츠 비디오 + SNS 캡션]을 동시 생성하여 요일별 6개 폴더에 저장합니다.
    (render_media=False 시 이미지/비디오 인코딩을 건너뛰고 대본, 요약, 패키지 메타데이터만 고속 생성합니다.)
    day_filter 지정 시 해당 요일(예: 'thu', '목요일')만 단독 실행합니다.
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
    print(f"🚀 [THEPT] 주간 큐레이션 기반 통합 콘텐츠 자동 생성 ({today_str})")
    if day_filter:
        print(f"   🎯 [지정 요일 모드] '{day_filter}' 필터와 일치하는 요일만 단독 실행합니다.")
    print(f"   📅 제작 모드: [4:5 카드뉴스 + 최대 2분 쇼츠 비디오 + SNS 캡션] (미디어 렌더링: {'ON' if render_media else '대기 (패키지만 생성)'})")
    print("=" * 70)

    # 주간 기준 시작 날짜(월요일) 계산 (weekly_dir 폴더명의 날짜로부터 해당 주의 실제 월요일을 정확히 역산)
    m_dir_date = re.search(r"(\d{4})-(\d{2})-(\d{2})", weekly_dir.name)
    if m_dir_date:
        parsed_dt = datetime(int(m_dir_date.group(1)), int(m_dir_date.group(2)), int(m_dir_date.group(3)))
        base_monday = parsed_dt - timedelta(days=parsed_dt.weekday())
    else:
        now_dt = datetime.now()
        base_monday = now_dt - timedelta(days=now_dt.weekday())

    # 요일별 폴더 및 카테고리 정의 (MMDD_요일_카테고리: 예: 0907_Mon_Policy, 0910_Thu_Tech)
    base_day_defs = [
        ("mon_policy", "월요일", "Mon_Policy", "국내 정책·제도·수가·실손보험", False),
        ("tue_clinical", "화요일", "Tue_Clinical", "임상 실무·질환별 재활 프로토콜", False),
        ("wed_sports", "수요일", "Wed_Sports", "운동·스포츠 재활", False),
        ("thu_tech", "목요일", "Thu_Tech", "첨단 재활 기술·AI·로봇", False),
        ("fri_celeb", "금요일", "Fri_Celeb", "셀럽 스타 치료 & 건강 가십", False),
        ("sat_global", "토요일", "Sat_Global", "해외 글로벌 트렌드", True),
    ]
    day_configs = []
    for i, (cat_key, day_name, suffix, cat_title, is_global) in enumerate(base_day_defs):
        day_date = base_monday + timedelta(days=i)
        mmdd = day_date.strftime("%m%d")
        folder_name = f"{mmdd}_{suffix}"
        weekday_kr = ["월", "화", "수", "목", "금", "토", "일"][day_date.weekday()]
        date_text = f"{day_date.strftime('%y')}년 {day_date.month}월 {day_date.day}일 ({weekday_kr})"
        day_configs.append((cat_key, day_name, folder_name, cat_title, is_global, date_text, day_date))

    results_by_day = []

    for cat_key, day_name, folder_name, cat_title, is_global, date_text, day_date in day_configs:
        # 요일 필터가 지정된 경우 일치하지 않는 요일은 건너뜀
        if day_filter and not match_day_filter(day_filter, cat_key, day_name, folder_name):
            continue

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
        pkg["date_text"] = date_text
        pkg["target_date"] = day_date.strftime("%Y-%m-%d")

        (day_dir / "package_data.json").write_text(
            json.dumps(pkg, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )

        card_paths = []
        audio_results = []
        total_sec = 0.0

        if render_media:
            # 3. 4:5 인스타그램 피드 카드뉴스 렌더링 (1080x1350)
            print(f"  🎨 4:5 고화질 카드뉴스 렌더링 중 (1080x1350)...")
            card_paths = await render_cards_to_images(
                pkg, cards_dir,
                template_path=TEMPLATE_4X5,
                width=CARD_WIDTH,
                height=CARD_HEIGHT
            )
            print(f"  ✅ 카드뉴스 완성 ({len(card_paths)}장 PNG)")

            # 4. 고품질 남녀 듀오 TTS 나레이션 합성 (총 ~55초 1분 브리핑)
            print(f"  🎙️ 남녀 듀오 고속 나레이션 합성 중 (SunHi + InJoon, +20%)...")
            audio_results = await synthesize_all_narration(pkg, audio_dir)
            total_sec = sum(a["duration"] for a in audio_results)

            # 5. 9:16 쇼츠 비디오 렌더링 (1080x1920 방송형 프레임 캡처 후 인코딩)
            print(f"  🎬 9:16 쇼츠 방송형 프레임 캡처 및 비디오 합성 중 (1080x1920)...")
            shorts_frames_dir = day_dir / "shorts_frames_9x16"
            shorts_frame_paths = await render_cards_to_images(
                pkg, shorts_frames_dir,
                template_path=TEMPLATE_9X16,
                width=VIDEO_WIDTH,
                height=VIDEO_HEIGHT
            )
            render_shorts_video(shorts_frame_paths, audio_results, video_path)
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

        clean_title = f"{day_name} THEPT 물리치료 1분 브리핑"

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
                f"📢 {day_name} THEPT 물리치료 1분 브리핑\n\n"
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
                f"📢 {day_name} THEPT 물리치료 1분 브리핑\n\n"
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
    print("=" * 70)
    print("ℹ️  [안내] 콘텐츠 수집 및 제작 파이프라인은 'curate.py'로 통합되었습니다.")
    print("   아래 명령어를 사용하여 3단계 큐레이션을 진행하세요:")
    print("   1. 후보 기사 수집   : python curate.py fetch")
    print("   2. 본문 및 사진 검토: python curate.py review")
    print("   3. 콘텐츠 제작/렌더링: python curate.py build --render")
    print("=" * 70)


