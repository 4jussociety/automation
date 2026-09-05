import sys
import os
import json
import argparse
from datetime import datetime
from pathlib import Path

# Windows cp949 콘솔 이모지 인코딩 지원
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from config import (
    OUTPUT_DIR, CURRENT_WEEK, GEMINI_API_KEY, DEFAULT_MODEL,
    CONTENTS_DIR, HISTORY_FILE
)
from agents.agent1_curator import run_agent1
from agents.agent2_card_writer import run_agent2
from agents.agent3_shorts_writer import run_agent3
from agents.agent4_reviewer import run_agent4
from generators.card_renderer import render_cards
from generators.bg_generator import prepare_set_backgrounds
from generators.shorts_renderer import save_shorts_assets
from generators.video_renderer import render_shorts_video

def main(args=None):
    if args is None:
        args = parse_args()
    print("=" * 65)
    print(f" 🏥 물리치료 전문 뉴스 미디어 자동 렌더링 시스템 가동")
    print(f" 📅 대상 주차: {CURRENT_WEEK} | 생성 목표: 매주 3세트 (쇼츠 3개, 카드뉴스 3개)")
    if not GEMINI_API_KEY:
        raise ValueError("❌ GEMINI_API_KEY가 설정되지 않았습니다. .env 파일이나 GitHub Secrets에 API 키를 등록해야 합니다.")
    print(f" 🔑 Gemini API 연동 모드: 활성화됨 (모델: {DEFAULT_MODEL})")
    if args.skip_video:
        print(" ⚡ 옵션: 비디오 렌더링 건너뛰기 (--skip-video) 활성화")
    print("=" * 65)

    # 1. 에이전트 1 실행: 3개 세트 뉴스 리서치 및 큐레이션
    print("\n[Step 1/4] 🔍 Agent 1 (뉴스 큐레이터) 작업 시작...")
    batches = run_agent1()
    print(f"  -> {len(batches)}개 분야별 뉴스 세트 선별 완료!")

    # 카테고리 필터 옵션 처리
    if args.category:
        cat_filter = args.category.lower().strip()
        filtered = [
            b for b in batches
            if cat_filter in b.get("batch_id", "").lower()
            or cat_filter in b.get("batch_title", "").lower()
        ]
        if filtered:
            batches = filtered
            print(f"  🎯 카테고리 필터 적용: {len(batches)}개 세트만 생성 진행 ({args.category})")
        else:
            print(f"  ⚠️ 입력된 카테고리('{args.category}')와 일치하는 세트가 없어 전체 세트를 생성합니다.")

    for b in batches:
        print(f"     • [{b.get('batch_id')}] {b.get('batch_title')} ({len(b.get('news_items', []))}건)")

    week_output_dir = OUTPUT_DIR / CURRENT_WEEK
    week_output_dir.mkdir(parents=True, exist_ok=True)
    CONTENTS_DIR.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # 2~4. 각 세트별로 에이전트 2, 3, 4 및 렌더링 실행
    for idx, batch in enumerate(batches, start=1):
        batch_id = batch.get("batch_id", f"set{idx}")
        batch_folder = week_output_dir / batch_id
        batch_folder.mkdir(parents=True, exist_ok=True)

        print("\n" + "-" * 60)
        print(f"📦 [{idx}/{len(batches)}] 세트 처리 중: {batch.get('batch_title')}")
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

        # 콘텐츠 초안 JSON 저장 (Team_The_PT_Automation_Package 차용)
        draft_filename = f"draft_{timestamp}_{batch_id}.json"
        draft_path = CONTENTS_DIR / draft_filename
        draft_payload = {
            "timestamp": timestamp,
            "week": CURRENT_WEEK,
            "batch_id": batch_id,
            "batch_title": batch.get("batch_title"),
            "target_audience": batch.get("target_audience"),
            "news_items": batch.get("news_items", []),
            "card_news": final_card,
            "shorts": final_shorts
        }
        with open(draft_path, "w", encoding="utf-8") as df:
            json.dump(draft_payload, df, ensure_ascii=False, indent=2)
        print(f"  💾 기획 및 대본 데이터 보관: contents/{draft_filename}")

        # 배경 에셋 준비
        bg_dir = batch_folder / "backgrounds"
        bg_files = prepare_set_backgrounds(final_card, bg_dir)
        print(f"  🖼️ 배경 에셋: {bg_dir.name}/ 에 슬라이드 맞춤 배경 {len(bg_files)}장 배치 완료")

        # 미디어 렌더링 1: 고화질 카드뉴스 PNG 이미지 생성 (1080x1350 및 1080x1920)
        cards_dir = batch_folder / "cards"
        print(f"  🎨 카드뉴스 렌더러: 1080x1350 및 1080x1920 초고화질 이미지 렌더링 중...")
        render_res = render_cards(final_card, cards_dir, bg_files=bg_files)

        # 미디어 렌더링 2: 쇼츠 음성(TTS mp3) 및 스토리보드 생성
        shorts_dir = batch_folder / "shorts"
        print(f"  🎙️ 쇼츠 렌더러: 한국어 AI 보이스(MP3) 및 스토리보드 생성 중...")
        shorts_assets = save_shorts_assets(final_shorts, shorts_dir)

        # 미디어 렌더링 3: 배경만 시네마틱 모션으로 움직이고 텍스트는 고정된 쇼츠 동영상(MP4) 생성
        fg_images = render_res.get("fg_images_9x16", [])
        if not args.skip_video and bg_files and fg_images and shorts_assets["audio_path"].exists():
            shorts_video_path = shorts_dir / "shorts_video.mp4"
            print(f"  🎬 레이어드 비디오 렌더러: 배경 독립 모션 쇼츠 동영상(MP4) 생성 중...")
            render_shorts_video(bg_files, fg_images, shorts_assets["audio_path"], shorts_video_path)
        elif args.skip_video:
            print("  ⏭️ 비디오 렌더링을 건너뜁니다 (--skip-video).")

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
        f.write(f"> **생성 세트**: 총 {len(batches)}개 세트  \n")
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

    # history.json에 processed_weeks 업데이트
    if HISTORY_FILE.exists():
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                history_data = json.load(f)
        except Exception:
            history_data = {"processed_weeks": [], "history": []}
    else:
        history_data = {"processed_weeks": [], "history": []}

    if CURRENT_WEEK not in history_data.get("processed_weeks", []):
        history_data.setdefault("processed_weeks", []).append(CURRENT_WEEK)
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(history_data, f, ensure_ascii=False, indent=2)

    print("\n" + "=" * 65)
    print(f"🎉 축하합니다! {len(batches)}개 세트 미디어 생성이 완료되었습니다!")
    print(f"📁 결과물 저장 경로: {week_output_dir.resolve()}")
    print("=" * 65)
    print("생성된 결과물 요약:")
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

def parse_args():
    parser = argparse.ArgumentParser(description="물리치료 전문 뉴스 미디어 자동 생성 파이프라인")
    parser.add_argument("--skip-video", action="store_true", help="비디오 렌더링을 건너뛰고 카드뉴스 및 대본만 신속 생성")
    parser.add_argument("--category", type=str, default="", help="특정 카테고리/세트만 필터링하여 생성 (예: set1, set2, set3)")
    return parser.parse_args()

if __name__ == "__main__":
    args = parse_args()
    main(args)

