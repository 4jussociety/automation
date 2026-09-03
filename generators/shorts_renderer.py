import asyncio
from pathlib import Path
import edge_tts
from config import TTS_VOICE

async def generate_narration_audio(text: str, output_path: Path):
    communicate = edge_tts.Communicate(text, TTS_VOICE)
    await communicate.save(str(output_path))
    print(f"  [쇼츠 음성 합성 완료] {output_path.name}")

def save_shorts_assets(shorts_data, output_dir: Path):
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # 1. Edge-TTS 오디오 파일 (.mp3) 생성
    audio_path = output_dir / "narration.mp3"
    narration_text = shorts_data.get("full_narration", "")
    if narration_text:
        try:
            asyncio.run(generate_narration_audio(narration_text, audio_path))
        except Exception as e:
            print(f"  [경고] Edge-TTS 오디오 생성 실패 ({e})")

    # 2. 영상 편집 및 업로드용 가이드 문서 (.txt) 저장
    guide_path = output_dir / "shorts_storyboard_guide.txt"
    scenes = shorts_data.get("scenes", [])
    
    storyboard_lines = []
    for s in scenes:
        storyboard_lines.append(f"""
[타임스탬프] {s.get('time_range')} | {s.get('section')}
- 자막 강조: {s.get('caption_highlight')}
- 시각 연출: {s.get('screen_visual_cue')}
- 음성 대본: {s.get('narration_snippet')}
------------------------------------------------------------""")

    guide_content = f"""============================================================
🎬 쇼츠 제목: {shorts_data.get('shorts_title')}
⏱ 예상 재생시간: 약 {shorts_data.get('estimated_seconds', 42)}초
🚨 3초 훅 카피: {shorts_data.get('hook_headline')}
============================================================

[스토리보드 및 화면 연출 가이드]
{''.join(storyboard_lines)}

============================================================
[전체 나레이션 대본]
{narration_text}

============================================================
[유튜브 쇼츠 설명란 & 해시태그 (복사해서 사용)]
{shorts_data.get('youtube_description', '')}
"""
    with open(guide_path, "w", encoding="utf-8") as f:
        f.write(guide_content)
    print(f"  [쇼츠 가이드 문서 저장] {guide_path.name}")

    return {
        "audio_path": audio_path,
        "guide_path": guide_path
    }
