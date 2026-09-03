import sys
import os

# Windows cp949 콘솔 이모지 인코딩 지원
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from pathlib import Path
from datetime import datetime

from config import OUTPUT_DIR, CURRENT_WEEK, GEMINI_API_KEY
from agents.agent1_curator import run_agent1
from agents.agent2_card_writer import run_agent2
from agents.agent3_shorts_writer import run_agent3
from agents.agent4_reviewer import run_agent4
from generators.card_renderer import render_cards
from generators.shorts_renderer import save_shorts_assets

def main():
    print("=" * 65)
    print(f" 🏥 물리치료 전문 뉴스 4-에이전트 자동화 시스템 가동")
    print(f" 📅 대상 주차: {CURRENT_WEEK} | 생성 목표: 매주 3세트 (쇼츠 3개, 카드뉴스 3개)")
    if GEMINI_API_KEY:
        print(" 🔑 Gemini API 연동 모드: 활성화됨")
    else:
        print(" ℹ️ Gemini API 키 미등록: 표준 큐레이션 테스트 모드로 동작합니다.")
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

        # 미디어 렌더링 1: 고화질 카드뉴스 PNG 이미지 6장 생성
        cards_dir = batch_folder / "cards"
        print(f"  🎨 카드뉴스 렌더러: 1080x1350 초고화질 이미지 6장 생성 중...")
        render_cards(final_card, cards_dir)

        # 미디어 렌더링 2: 쇼츠 음성(TTS mp3) 및 스토리보드 생성
        shorts_dir = batch_folder / "shorts"
        print(f"  🎙️ 쇼츠 렌더러: 한국어 AI 보이스(MP3) 및 스토리보드 생성 중...")
        save_shorts_assets(final_shorts, shorts_dir)

        # 인스타그램 캡션 텍스트 저장
        caption_path = batch_folder / "instagram_caption.txt"
        with open(caption_path, "w", encoding="utf-8") as f:
            f.write(final_card.get("caption", ""))
        print(f"  📝 인스타그램 캡션 저장: {caption_path.name}")

    print("\n" + "=" * 65)
    print(f"🎉 축하합니다! 이번 주 3세트 전체 자동 생성 완료!")
    print(f"📁 결과물 저장 경로: {week_output_dir.resolve()}")
    print("=" * 65)
    print("생성된 결과물:")
    for b in batches:
        b_id = b.get("batch_id")
        print(f"  ▶ {week_output_dir / b_id}")
        print(f"     ├── cards/ (card_01.png ~ card_06.png)")
        print(f"     ├── shorts/ (narration.mp3, shorts_storyboard_guide.txt)")
        print(f"     └── instagram_caption.txt")

if __name__ == "__main__":
    main()
