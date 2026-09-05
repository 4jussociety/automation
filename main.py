import os
import sys
import json
import argparse
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

import config
from generators.tts_generator import generate_voice
from generators.card_renderer import render_cards
from generators.shorts_renderer import render_shorts_video


def get_latest_draft_file():
    content_dir = config.CONTENTS_DIR
    if not os.path.exists(content_dir):
        return None
    draft_files = sorted(
        Path(content_dir).glob("draft_*.json"),
        key=os.path.getmtime,
        reverse=True
    )
    return str(draft_files[0]) if draft_files else None


def render_from_draft_data(payload, draft_path=None, skip_video=False):
    issue_info = payload.get("issue") or payload.get("topic", {})
    card_data = payload.get("card_news", {})
    shorts_data = payload.get("shorts", {})
    timestamp = payload.get("timestamp", datetime.now().strftime("%Y%m%d_%H%M%S"))
    category = issue_info.get("category") or card_data.get("category") or "clinic"
    issue_title = issue_info.get("title") or card_data.get("title", "물리치료 주간 이슈 브리핑")

    job_output_dir = os.path.join(config.OUTPUT_DIR, f"{timestamp}_{category}")
    card_output_dir = os.path.join(job_output_dir, "cards")
    video_output_dir = os.path.join(job_output_dir, "video")
    os.makedirs(card_output_dir, exist_ok=True)
    os.makedirs(video_output_dir, exist_ok=True)

    print(f"\n==================================================")
    print(f"[주간 이슈 브리핑 렌더러] {issue_title}")
    if draft_path:
        print(f"* 대본 파일: {draft_path}")
    print(f"==================================================")

    print(f"\n[1/3] 4:5 인스타그램 피드 카드뉴스 렌더링 중...")
    card_files = render_cards(card_data, card_output_dir)

    video_file = None
    if not skip_video and shorts_data:
        print(f"\n[2/3] 무료 고음질 Edge-TTS 음성 합성 및 9:16 쇼츠 비디오 렌더링 중...")
        audio_path = os.path.join(video_output_dir, "narration.mp3")
        srt_path = os.path.join(video_output_dir, "subtitles.srt")

        narration = shorts_data.get("full_narration", "")
        if narration:
            generate_voice(narration, audio_path, srt_path)
            output_mp4 = os.path.join(video_output_dir, "shorts.mp4")
            video_file = render_shorts_video(shorts_data, audio_path, srt_path, output_mp4)
        else:
            print("  -> 안내: full_narration 텍스트가 없어 영상 생성을 건너뜁니다.")
    else:
        print("\n[2/3] 비디오 렌더링을 건너뜁니다.")

    print(f"\n[3/3] 콘텐츠 히스토리 기록 중...")
    history_file = os.path.join(BASE_DIR, "history.json")
    history_entry = {
        "timestamp": timestamp,
        "issue_title": issue_title,
        "category": category,
        "json_path": str(draft_path) if draft_path else payload.get("json_path", ""),
        "card_files": [str(c) for c in card_files],
        "video_file": str(video_file) if video_file else None,
        "status": "READY_FOR_PUBLISH"
    }

    history_data = []
    if os.path.exists(history_file):
        try:
            with open(history_file, "r", encoding="utf-8") as f:
                history_data = json.load(f)
        except Exception:
            history_data = []

    if isinstance(history_data, dict):
        history_data.setdefault("history", []).append(history_entry)
    elif isinstance(history_data, list):
        history_data.append(history_entry)
    else:
        history_data = [history_entry]

    with open(history_file, "w", encoding="utf-8") as f:
        json.dump(history_data, f, ensure_ascii=False, indent=2)

    print("\n[완료] 주간 이슈 미디어 렌더링이 성공적으로 끝났습니다.")
    print("==================================================")
    print(f"* 산출물 디렉토리: {job_output_dir}")
    print(f"* 카드뉴스 슬라이드: {len(card_files)}장 ({card_output_dir})")
    if video_file:
        print(f"* 숏폼 비디오: {video_file}")
    print("==================================================\n")
    return job_output_dir


def run_from_draft_file(draft_path, skip_video=False):
    if not os.path.exists(draft_path):
        print(f"오류: 대본 파일을 찾을 수 없습니다: {draft_path}")
        sys.exit(1)

    with open(draft_path, "r", encoding="utf-8") as f:
        payload = json.load(f)

    return render_from_draft_data(payload, draft_path=draft_path, skip_video=skip_video)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Team The PT - Weekly Physical Therapy Issue Media Engine')
    parser.add_argument(
        '--draft', '-d', type=str,
        help='렌더링할 주간 이슈 대본 JSON 파일 경로 (미지정 시 최신 대본 자동 렌더링)'
    )
    parser.add_argument('--skip-video', action='store_true', help='비디오 렌더링 건너뛰기')
    args = parser.parse_args()

    target_draft = args.draft or get_latest_draft_file()
    if not target_draft:
        print("오류: contents/ 디렉터리에 렌더링할 대본(JSON) 파일이 없습니다.")
        sys.exit(1)

    run_from_draft_file(target_draft, skip_video=args.skip_video)
