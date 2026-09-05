# 이 모듈은 Microsoft Edge-TTS를 활용하여 빠른 템포의 고음질 한국어 음성을 합성합니다.
# 슬라이드별 나레이션 MP3 파일 생성 및 정확한 재생 시간(duration)을 측정합니다.

import sys
from pathlib import Path
import asyncio
import subprocess
import edge_tts

sys.path.append(str(Path(__file__).resolve().parent.parent))

from config import TTS_VOICE, TTS_RATE, TTS_VOLUME


def get_audio_duration(audio_path: Path) -> float:
    """ffprobe를 사용하여 오디오 파일의 정확한 재생 길이(초)를 반환합니다."""
    cmd = [
        "ffprobe",
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(audio_path)
    ]
    try:
        res = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=True
        )
        return float(res.stdout.strip())
    except Exception as e:
        raise RuntimeError(f"오디오 길이 측정 실패 ({audio_path}): {e}")


async def synthesize_slide_audio(text: str, output_file: Path, voice: str = TTS_VOICE, rate: str = TTS_RATE) -> float:
    """단일 슬라이드의 텍스트를 음성으로 합성하고 재생 길이를 반환합니다."""
    if not text.strip():
        raise ValueError("합성할 음성 텍스트가 비어 있습니다.")

    output_file.parent.mkdir(parents=True, exist_ok=True)
    communicate = edge_tts.Communicate(text=text, voice=voice, rate=rate, volume=TTS_VOLUME)
    await communicate.save(str(output_file))

    if not output_file.exists() or output_file.stat().st_size == 0:
        raise RuntimeError(f"TTS 음성 합성 실패 (파일 생성 불가): {output_file}")

    duration = get_audio_duration(output_file)
    return duration


async def synthesize_all_narration(package: dict, output_dir: Path) -> list[dict]:
    """
    모든 슬라이드의 나레이션을 각각의 MP3로 합성하고, 각 슬라이드의 오디오 경로와 재생 길이를 반환합니다.
    """
    slides = package.get("slides", [])
    if not slides:
        raise ValueError("합성할 슬라이드 목록이 없습니다.")

    output_dir.mkdir(parents=True, exist_ok=True)
    audio_results = []
    total_duration = 0.0

    print(f"[TTS] 총 {len(slides)}개 슬라이드 음성 합성 시작 (음성: {TTS_VOICE}, 속도: {TTS_RATE})...")

    for idx, slide in enumerate(slides):
        slide_type = slide["type"]
        narration_text = slide.get("narration", "")
        if not narration_text:
            raise ValueError(f"슬라이드 {idx+1} ({slide_type})에 나레이션 텍스트가 없습니다.")

        audio_path = output_dir / f"audio_{idx+1:02d}_{slide_type}.mp3"
        duration = await synthesize_slide_audio(narration_text, audio_path)
        total_duration += duration

        audio_results.append({
            "slide_index": idx,
            "slide_type": slide_type,
            "audio_path": audio_path,
            "duration": duration,
            "narration": narration_text
        })
        print(f"[TTS 완료] 슬라이드 {idx+1}: {duration:.2f}초 - {audio_path.name}")

    print(f"[TTS 전체 완료] 총 나레이션 길이: {total_duration:.2f}초 (쇼츠 1분 규격 만족: {'YES' if total_duration <= 60 else 'NO - 길이 초과 주의'})")

    return audio_results


if __name__ == "__main__":
    from modules.news_collector import collect_weekly_physical_therapy_news
    from modules.content_builder import build_content_package

    print("[테스트] TTS 음성 합성 시작...")
    test_news = collect_weekly_physical_therapy_news(min_news_count=3)
    test_pkg = build_content_package(test_news)
    test_out = Path(__file__).resolve().parent.parent / "output" / "test_audio"
    results = asyncio.run(synthesize_all_narration(test_pkg, test_out))
    total = sum(r["duration"] for r in results)
    print(f"[성공] 총 {len(results)}개 오디오 생성 완료, 총합: {total:.2f}초")
