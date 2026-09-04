import sys
import argparse

# Windows cp949 콘솔 이모지 인코딩 지원
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from pathlib import Path

from config import OUTPUT_DIR, CURRENT_WEEK, GEMINI_API_KEY, DEFAULT_MODEL
from agents.agent1_curator import run_agent1
from agents.agent2_card_writer import run_agent2
from agents.agent3_shorts_writer import run_agent3
from agents.agent4_reviewer import run_agent4
from generators.card_renderer import render_cards
from generators.bg_generator import prepare_set_backgrounds
from generators.shorts_renderer import save_shorts_assets
from generators.video_renderer import render_shorts_video
from generators.insta_browser_uploader import InstagramBrowserUploader, generate_first_comment_text
from generators.youtube_uploader import YouTubeShortsUploader, generate_shorts_first_comment
from generators.schedule_calculator import get_next_weekly_schedule, print_weekly_schedule

def main(args=None):
    if args is None:
        args = parse_args()
    print("=" * 65)
    print(f" 🏥 물리치료 전문 뉴스 4-에이전트 자동화 시스템 가동")
    print(f" 📅 대상 주차: {CURRENT_WEEK} | 생성 목표: 매주 3세트 (쇼츠 3개, 카드뉴스 3개)")
    if not GEMINI_API_KEY:
        raise ValueError("❌ GEMINI_API_KEY가 설정되지 않았습니다. .env 파일에 API 키를 등록해야 시스템을 실행할 수 있습니다.")
    print(f" 🔑 Gemini API 연동 모드: 활성화됨 (모델: {DEFAULT_MODEL})")
    print("=" * 65)

    # 1. 에이전트 1 실행: 3개 세트 뉴스 리서치 및 큐레이션
    print("\n[Step 1/4] 🔍 Agent 1 (뉴스 큐레이터) 작업 시작...")
    batches = run_agent1()
    print(f"  -> {len(batches)}개 분야별 뉴스 세트 선별 완료!")
    for b in batches:
        print(f"     • [{b.get('batch_id')}] {b.get('batch_title')} ({len(b.get('news_items', []))}건)")

    week_output_dir = OUTPUT_DIR / CURRENT_WEEK
    week_output_dir.mkdir(parents=True, exist_ok=True)

    # 2~4. 각 세트별로 에이전트 2, 3, 4 및 렌더링 실행
    for idx, batch in enumerate(batches, start=1):
        batch_id = batch.get("batch_id", f"set{idx}")
        batch_folder = week_output_dir / batch_id
        batch_folder.mkdir(parents=True, exist_ok=True)

        print("\n" + "-" * 60)
        print(f"📦 [{idx}/3] 세트 처리 중: {batch.get('batch_title')}")
        print("-" * 60)

        # 에이전트 2: 카드뉴스 카피라이팅
        print("  ✍️ Agent 2: 인스타그램 6장 캐러셀 카드뉴스 작성 중...")
        raw_card_data = run_agent2(batch)

        # 에이전트 3: 쇼츠 대본 및 연출 기획
        print("  🎬 Agent 3: 40초 쇼츠 대본 및 연출 가이드 작성 중...")
        raw_shorts_data = run_agent3(batch)

        # 에이전트 4: 의료/법률 팩트체크 및 감수
        print("  ⚖️ Agent 4: 의료법 및 안전 가이드라인 감수 진행 중...")
        review_result = run_agent4(raw_card_data, raw_shorts_data)
        final_card = review_result.get("final_card_data", raw_card_data)
        final_shorts = review_result.get("final_shorts_data", raw_shorts_data)

        # 배경 에셋 준비: 이번 세트 맞춤 배경을 output/{CURRENT_WEEK}/{batch_id}/backgrounds/ 에 격리 배치 (수동 교체 가능)
        bg_dir = batch_folder / "backgrounds"
        bg_files = prepare_set_backgrounds(final_card, bg_dir)
        print(f"  🖼️ 배경 에셋: {bg_dir.name}/ 에 슬라이드 맞춤 배경 {len(bg_files)}장 배치 완료")

        # 미디어 렌더링 1: 고화질 카드뉴스 PNG 이미지 6장 생성 (세트 배경 기반 렌더링)
        cards_dir = batch_folder / "cards"
        print(f"  🎨 카드뉴스 렌더러: 1080x1350 및 1080x1920 초고화질 이미지 렌더링 중...")
        render_res = render_cards(final_card, cards_dir, bg_files=bg_files)

        # 미디어 렌더링 2: 쇼츠 음성(TTS mp3) 및 스토리보드 생성
        shorts_dir = batch_folder / "shorts"
        print(f"  🎙️ 쇼츠 렌더러: 한국어 AI 보이스(MP3) 및 스토리보드 생성 중...")
        shorts_assets = save_shorts_assets(final_shorts, shorts_dir)

        # 미디어 렌더링 3: 배경만 시네마틱 모션으로 움직이고 텍스트는 고정된 완성본 쇼츠 동영상(MP4) 생성
        fg_images = render_res.get("fg_images_9x16", [])
        if bg_files and fg_images and shorts_assets["audio_path"].exists():
            shorts_video_path = shorts_dir / "shorts_video.mp4"
            print(f"  🎬 레이어드 비디오 렌더러: 배경 독립 모션 쇼츠 동영상(MP4) 생성 중...")
            render_shorts_video(bg_files, fg_images, shorts_assets["audio_path"], shorts_video_path)

        # 인스타그램 캡션 텍스트 저장
        caption_path = batch_folder / "instagram_caption.txt"
        with open(caption_path, "w", encoding="utf-8") as f:
            f.write(final_card.get("caption", ""))
        print(f"  📝 인스타그램 캡션 저장: {caption_path.name}")

        # 세트별 스크랩 출처 및 링크 문서 저장
        sources_md_path = batch_folder / "sources_and_links.md"
        with open(sources_md_path, "w", encoding="utf-8") as f:
            f.write(f"# 📌 [{CURRENT_WEEK}] {batch.get('batch_title')} - 스크랩 출처 및 원문 링크\n\n")
            f.write(f"- **분야 ID**: `{batch_id}`\n")
            f.write(f"- **타겟 독자**: {batch.get('target_audience', '물리치료사, 도수치료사, 재활전문가')}\n\n")
            f.write("## 🎯 선별된 핵심 브리핑 뉴스\n\n")
            for n_idx, item in enumerate(batch.get("news_items", []), start=1):
                f.write(f"### {n_idx}. {item.get('headline')}\n")
                f.write(f"- **세부 분류**: {item.get('category', '-')}\n")
                f.write(f"- **언론사 / 출처**: {item.get('source', '전문 보도')}\n")
                link = item.get('link') or "https://news.google.com"
                f.write(f"- **원문 링크**: [{item.get('headline')}]({link})\n")
                f.write(f"- **핵심 요약**: {item.get('summary', '')}\n")
                f.write(f"- **임상 시사점**: {item.get('why_it_matters', '')}\n")
                f.write(f"- **실무 실천 팁**: {item.get('action_tip', '')}\n\n")
            
            source_articles = batch.get("source_articles", [])
            if source_articles:
                f.write("## 🌐 수집된 전체 후보 기사 목록 (참고용)\n\n")
                for s_idx, sa in enumerate(source_articles, start=1):
                    title = sa.get("title", "").strip()
                    s_link = sa.get("link", "")
                    f.write(f"{s_idx}. [{title}]({s_link})\n")
        print(f"  📑 스크랩 출처 및 링크 문서 저장: {sources_md_path.name}")

    # 주차 통합 전체 스크랩 출처 및 링크 문서 저장
    summary_sources_path = week_output_dir / "주간_스크랩_출처_및_원문링크.md"
    with open(summary_sources_path, "w", encoding="utf-8") as f:
        f.write(f"# 🏥 [{CURRENT_WEEK}] 주간 물리치료 전문 뉴스 스크랩 출처 및 원문 링크 총정리\n\n")
        f.write(f"> **발행 주차**: {CURRENT_WEEK}  \n")
        f.write(f"> **생성 세트**: 총 {len(batches)}개 세트 (쇼츠 3편, 카드뉴스 18장)  \n")
        f.write(f"> **타겟 독자**: 물리치료사, 도수치료사, 재활전문가, 작업치료사 등 임상 실무자\n\n")
        f.write("---\n\n")
        for b_idx, batch in enumerate(batches, start=1):
            f.write(f"## 📦 Set {b_idx}. {batch.get('batch_title')} (`{batch.get('batch_id')}`)\n\n")
            for n_idx, item in enumerate(batch.get("news_items", []), start=1):
                headline = item.get('headline')
                source = item.get('source', '전문 언론사')
                category = item.get('category', '')
                link = item.get('link') or "https://news.google.com"
                summary = item.get('summary', '')
                action_tip = item.get('action_tip', '')
                f.write(f"### {n_idx}. {headline}\n")
                f.write(f"- **출처/언론사**: {source} | **분류**: {category}\n")
                f.write(f"- **원문 링크**: [{headline}]({link})\n")
                f.write(f"- **핵심 요약**: {summary}\n")
                if action_tip:
                    f.write(f"- **💡 임상 팁**: {action_tip}\n")
                f.write("\n")
            f.write("---\n\n")
    print(f"\n📄 주간 통합 출처 및 링크 문서 생성: {summary_sources_path.name}")

    print("\n" + "=" * 65)
    print(f"🎉 축하합니다! 이번 주 3세트 전체 미디어 생성 완료!")
    print(f"📁 결과물 저장 경로: {week_output_dir.resolve()}")
    print("=" * 65)
    print("생성된 결과물:")
    print(f"  📄 {summary_sources_path.name} (전체 출처 및 원문 링크 총정리)")
    for b in batches:
        b_id = b.get("batch_id")
        print(f"  ▶ {week_output_dir / b_id}")
        print(f"     ├── backgrounds/ (슬라이드별 맞춤 배경 원본)")
        print(f"     ├── cards/feed_4x5/ (인스타그램 피드용 6장)")
        print(f"     ├── cards/reels_shorts_9x16/ (릴스/쇼츠 규격 6장)")
        print(f"     ├── shorts/ (shorts_video.mp4, narration.mp3, 스토리보드)")
        print(f"     ├── sources_and_links.md (세트별 스크랩 출처 및 링크)")
        print(f"     └── instagram_caption.txt")

    # 5. SNS 자동 업로드 파이프라인 (월수금 쇼츠/릴스 & 화목토 카드뉴스 오전 8시 예약)
    should_upload_insta = args.upload or args.upload_insta
    should_upload_yt = args.upload or args.upload_yt

    if should_upload_insta or should_upload_yt:
        print("\n" + "=" * 65)
        print(" 🚀 주간 SNS 자동 예약 업로드 & 첫댓글 파이프라인 가동")
        print("=" * 65)

        weekly_sch = get_next_weekly_schedule()
        print_weekly_schedule(weekly_sch)

        insta_uploader = InstagramBrowserUploader() if should_upload_insta else None
        yt_uploader = YouTubeShortsUploader() if should_upload_yt else None

        for idx, batch in enumerate(batches, start=1):
            batch_id = batch.get("batch_id", f"set{idx}")
            set_key = f"set{idx}"
            batch_folder = week_output_dir / batch_id
            batch_title = batch.get("batch_title", "")

            sch_info = weekly_sch.get(set_key, {})
            v_sch = sch_info.get("video", {})
            c_sch = sch_info.get("carousel", {})

            print(f"\n📦 [{idx}/{len(batches)}] {batch_title} SNS 예약 업로드 진행 중...")

            # 5-1. [화/목/토 08:00 AM] 인스타그램 피드 4:5 캐러셀 6장 예약 업로드
            if should_upload_insta:
                cards_4x5_dir = batch_folder / "cards" / "feed_4x5"
                card_images = sorted(list(cards_4x5_dir.glob("card_[0-9]*.png"))) or sorted(list(cards_4x5_dir.glob("card_slide_*.png")))
                caption_file = batch_folder / "instagram_caption.txt"
                caption = ""
                if caption_file.exists():
                    with open(caption_file, "r", encoding="utf-8") as cf:
                        caption = cf.read()

                if card_images:
                    first_comm = generate_first_comment_text(batch)
                    target_dt = c_sch.get("target_datetime")
                    day_name = c_sch.get("day_name", "화요일")
                    print(f"  📸 [{day_name} 08:00 AM] 인스타그램 카드뉴스 캐러셀 예약 중...")
                    insta_uploader.upload_carousel_post(
                        image_paths=card_images,
                        caption=caption,
                        first_comment=first_comm,
                        schedule_datetime=target_dt,
                        is_scheduled=True
                    )
                else:
                    print(f"  ⚠️ 업로드할 4:5 카드 이미지가 없습니다: {cards_4x5_dir}")

            # 5-2. [월/수/금 08:00 AM] 인스타그램 릴스(Reels) 예약 업로드
            video_path = batch_folder / "shorts" / "shorts_video.mp4"
            if should_upload_insta and video_path.exists():
                v_target_dt = v_sch.get("target_datetime")
                v_day_name = v_sch.get("day_name", "월요일")
                print(f"  🎬 [{v_day_name} 08:00 AM] 인스타그램 릴스(Reels) 예약 중...")
                reels_caption = f"[{batch_title}] 주간 핵심 요약 #물리치료 #릴스"
                reels_first_comm = generate_shorts_first_comment(batch_title)
                insta_uploader.upload_reels_video(
                    video_path=video_path,
                    caption=reels_caption,
                    first_comment=reels_first_comm,
                    schedule_datetime=v_target_dt,
                    is_scheduled=True
                )

            # 5-3. [월/수/금 08:00 AM] 유튜브 쇼츠(Shorts) 예약 업로드 & 첫댓글 등록
            if should_upload_yt:
                if video_path.exists():
                    v_day_name = v_sch.get("day_name", "월요일")
                    v_rfc3339 = v_sch.get("rfc3339")
                    lead_news = batch.get("news_items", [{}])[0]
                    lead_headline = lead_news.get("headline", batch_title)
                    yt_title = f"[물리치료사 필독] {lead_headline[:50]} #Shorts"
                    yt_desc = f"{batch_title} 주간 브리핑입니다.\n\n출처 및 원문 링크는 채널 공지 및 첫댓글을 확인하세요."
                    yt_first_comment = generate_shorts_first_comment(batch_title)

                    print(f"  🎬 [{v_day_name} 08:00 AM] 유튜브 쇼츠 예약 업로드 및 첫댓글 등록 중...")
                    yt_uploader.upload_shorts(
                        video_path=video_path,
                        title=yt_title,
                        description=yt_desc,
                        first_comment=yt_first_comment,
                        publish_at=v_rfc3339
                    )
                else:
                    print(f"  ⚠️ 업로드할 쇼츠 영상이 없습니다: {video_path}")
    else:
        print("\n" + "-" * 65)
        print(" 💡 [안내] SNS 자동 예약 업로드 및 첫댓글 작성을 실행하려면:")
        print("   • 인스타그램 1회 로그인: python main.py --login-insta")
        print("   • 유튜브 1회 인증:       python main.py --auth-yt")
        print("   • 전체 SNS 자동 예약:    python main.py --upload")
        print("   • 인스타그램만 예약발행: python main.py --upload-insta")
        print("   • 유튜브 쇼츠만 예약발행:python main.py --upload-yt")
        print("-" * 65)

def parse_args():
    parser = argparse.ArgumentParser(description="물리치료 전문 뉴스 올인원 자동화 파이프라인")
    parser.add_argument("--upload", action="store_true", help="월수금 릴스/쇼츠, 화목토 카드뉴스 오전 8시 일괄 예약 업로드")
    parser.add_argument("--upload-insta", action="store_true", help="인스타그램 릴스/피드 오전 8시 예약 업로드만 실행")
    parser.add_argument("--upload-yt", action="store_true", help="유튜브 쇼츠 월수금 오전 8시 예약 업로드 및 첫댓글만 실행")
    parser.add_argument("--login-insta", action="store_true", help="인스타그램 브라우저 1회 로그인 세션을 저장합니다.")
    parser.add_argument("--auth-yt", action="store_true", help="YouTube Data API v3 1회 구글 OAuth 인증을 수행합니다.")
    return parser.parse_args()

if __name__ == "__main__":
    args = parse_args()
    if args.login_insta:
        uploader = InstagramBrowserUploader()
        uploader.interactive_login()
    elif args.auth_yt:
        uploader = YouTubeShortsUploader()
        uploader.get_authenticated_service()
    else:
        main(args)
