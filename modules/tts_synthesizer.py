# 이 모듈은 Microsoft Edge-TTS를 활용하여 빠른 템포의 고음질 한국어 음성을 합성합니다.
# 슬라이드별 나레이션 MP3 파일 생성 및 정확한 재생 시간(duration)을 측정합니다.

import sys
from pathlib import Path
import asyncio
import subprocess
import edge_tts

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

sys.path.append(str(Path(__file__).resolve().parent.parent))

from config import TTS_VOICE, TTS_RATE, TTS_VOLUME, TTS_VOICE_FEMALE, TTS_VOICE_MALE
from modules.text_verifier import refine_text_for_tts


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


async def synthesize_slide_audio(text: str, output_file: Path, voice: str = None, rate: str = TTS_RATE, retries: int = 3) -> float:
    """단일 슬라이드의 텍스트를 음성으로 합성하고 재생 길이를 반환합니다. (일시적 네트워크 오류 시 최대 3회 재시도)"""
    if not text.strip():
        raise ValueError("합성할 음성 텍스트가 비어 있습니다.")

    voice_to_use = voice or TTS_VOICE
    # 띄어쓰기, 쉼표, 온점 및 약어 정밀 정제 (TTS 호흡/발음 최적화)
    refined_text = refine_text_for_tts(text)
    output_file.parent.mkdir(parents=True, exist_ok=True)

    last_err = None
    for attempt in range(1, retries + 1):
        try:
            communicate = edge_tts.Communicate(text=refined_text, voice=voice_to_use, rate=rate, volume=TTS_VOLUME)
            await communicate.save(str(output_file))

            if not output_file.exists() or output_file.stat().st_size < 3000:
                if len(refined_text) > 15:
                    size_now = output_file.stat().st_size if output_file.exists() else 0
                    raise RuntimeError(f"TTS 음성 파일 크기 비정상 ({size_now} bytes)")

            duration = get_audio_duration(output_file)
            if duration < 1.0 and len(refined_text) > 15:
                raise RuntimeError(f"TTS 오디오 재생 길이 비정상 ({duration:.2f}초)")

            return duration
        except Exception as e:
            last_err = e
            if attempt < retries:
                await asyncio.sleep(1.2 * attempt)

    raise RuntimeError(f"TTS 음성 합성 {retries}회 시도 실패 ({output_file}): {last_err}")


async def synthesize_all_narration(package: dict, output_dir: Path) -> list[dict]:
    """
    모든 슬라이드의 나레이션을 남녀 교차 듀오 앵커(여-남-여-남-여-남, 속도 +20%)로 각각의 MP3로 합성하고,
    각 슬라이드의 오디오 경로와 재생 길이를 반환합니다.
    """
    slides = package.get("slides", [])
    if not slides:
        raise ValueError("합성할 슬라이드 목록이 없습니다.")

    output_dir.mkdir(parents=True, exist_ok=True)
    audio_results = []
    total_duration = 0.0

    print(f"[TTS] 총 {len(slides)}개 슬라이드 남녀 듀오 교차 음성 합성 시작 (속도: {TTS_RATE})...")

    for idx, slide in enumerate(slides):
        slide_type = slide["type"]
        narration_text = slide.get("narration", "")
        if not narration_text:
            raise ValueError(f"슬라이드 {idx+1} ({slide_type})에 나레이션 텍스트가 없습니다.")

        # 남녀 교차 배정: 짝수 슬라이드(표지, 뉴스2, 광고) = 여성 / 홀수 슬라이드(뉴스1, 뉴스3, 아웃트로) = 남성
        assigned_voice = slide.get("voice")
        if not assigned_voice:
            assigned_voice = TTS_VOICE_FEMALE if (idx % 2 == 0) else TTS_VOICE_MALE
        
        anchor_name = "여성(SunHi)" if assigned_voice == TTS_VOICE_FEMALE else "남성(InJoon)"

        audio_path = output_dir / f"audio_{idx+1:02d}_{slide_type}.mp3"
        refined_narration = refine_text_for_tts(narration_text)
        duration = await synthesize_slide_audio(refined_narration, audio_path, voice=assigned_voice, rate=TTS_RATE)
        total_duration += duration

        audio_results.append({
            "slide_index": idx,
            "slide_type": slide_type,
            "voice": assigned_voice,
            "anchor": anchor_name,
            "audio_path": audio_path,
            "duration": duration,
            "narration": narration_text,
            "refined_narration": refined_narration
        })
        print(f"[TTS 완료] 슬라이드 {idx+1} ({anchor_name}): {duration:.2f}초 - {audio_path.name} (대본: '{refined_narration[:30]}...')")

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
