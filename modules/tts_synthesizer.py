# 이 모듈은 4THEPT 최신 TTS 파이프라인(Gemini 3.8 Flash TTS + 해시 디스크 캐싱 + Edge TTS 자동 폴백)과
# 양방향 무음 트리밍·목표 발화 속도(CPS) 보정으로 고음질 한국어 나레이션을 합성합니다.

from __future__ import annotations

import asyncio
import base64
import hashlib
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

import edge_tts

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

sys.path.append(str(Path(__file__).resolve().parent.parent))

from config import (
    TTS_CACHE_DIR,
    TTS_RATE,
    TTS_VOICE,
    TTS_VOICE_FEMALE,
    TTS_VOICE_MALE,
    TTS_VOLUME,
)
from modules.text_verifier import refine_text_for_tts

try:
    from google import genai
except Exception:
    genai = None  # type: ignore[assignment]

TTS_ENGINE = os.getenv("TTS_ENGINE", "auto").strip().lower()  # auto | gemini | edge
TTS_GEMINI_MODEL = os.getenv("TTS_GEMINI_MODEL", "gemini-3.8-flash-tts").strip()
TTS_GEMINI_VOICE_FEMALE = os.getenv("TTS_GEMINI_VOICE_FEMALE", "Kore").strip()
TTS_GEMINI_VOICE_MALE = os.getenv("TTS_GEMINI_VOICE_MALE", "Puck").strip()
TTS_TARGET_CPS = float(os.getenv("TTS_TARGET_CPS", "6.5"))

SLIDE_VOICE_STYLES = {
    "cover": "energetic, crisp Korean broadcast news anchor opening hook, brisk tempo",
    "news": "clear, articulate Korean broadcast news anchor, steady brisk tempo",
    "ad": "upbeat, engaging, trustworthy Korean narrator, brisk promo tempo",
    "outro": "warm, decisive Korean closing news anchor, brisk tempo",
}

_GEMINI_CLIENT: Any = None
_GEMINI_QUOTA_EXHAUSTED = False


def count_spoken_chars(text: str) -> int:
    """음성 발화 속도(CPS) 계산용 실제 발화 문자(한글/영문/숫자) 수를 반환합니다."""
    return len(re.findall(r"[가-힣A-Za-z0-9]", text or ""))


def get_audio_duration(audio_path: Path) -> float:
    """ffprobe를 사용하여 오디오 파일의 정확한 재생 길이(초)를 반환합니다."""
    cmd = [
        "ffprobe",
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(audio_path),
    ]
    try:
        res = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=True,
        )
        return float(res.stdout.strip())
    except Exception as e:
        raise RuntimeError(f"오디오 길이 측정 실패 ({audio_path}): {e}")


def _get_gemini_client():
    global _GEMINI_CLIENT
    if TTS_ENGINE == "edge" or _GEMINI_QUOTA_EXHAUSTED or genai is None:
        return None
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        return None
    if _GEMINI_CLIENT is None:
        _GEMINI_CLIENT = genai.Client(api_key=api_key, http_options={"api_version": "v1beta"})
    return _GEMINI_CLIENT


def _synth_gemini_wav(
    text: str,
    voice_name: str,
    voice_style: str,
    raw_wav: Path,
) -> str:
    """Gemini 3.8 Flash TTS WAV를 디스크 캐시에서 로드하거나 API로 합성합니다."""
    global _GEMINI_QUOTA_EXHAUSTED
    TTS_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256(
        f"{TTS_GEMINI_MODEL}|{voice_name}|{voice_style}|{text}".encode("utf-8")
    ).hexdigest()[:14]
    cache_wav = TTS_CACHE_DIR / f"tts_{voice_name.lower()}_{digest}.wav"

    if cache_wav.exists() and cache_wav.stat().st_size > 2500:
        shutil.copy2(cache_wav, raw_wav)
        return f"cached:{TTS_GEMINI_MODEL}"

    client = _get_gemini_client()
    if client is None:
        raise RuntimeError("Gemini TTS client unavailable")

    try:
        inter = client.interactions.create(
            model=TTS_GEMINI_MODEL,
            input=[
                {
                    "type": "user_input",
                    "content": [
                        {
                            "type": "text",
                            "text": text,
                            "annotations": [{"type": "speech_metadata", "style": voice_style}],
                        }
                    ],
                }
            ],
            response_format={"type": "audio"},
            generation_config={"speech_config": [{"voice": voice_name}]},
        )
        audio_obj = getattr(inter, "output_audio", None)
        if not (audio_obj and getattr(audio_obj, "data", None)):
            raise RuntimeError("Empty audio returned from Gemini TTS")
        wav_bytes = base64.b64decode(audio_obj.data)
        cache_wav.write_bytes(wav_bytes)
        raw_wav.write_bytes(wav_bytes)
        return f"live:{TTS_GEMINI_MODEL}"
    except Exception as exc:
        msg = str(exc)
        if any(tok in msg for tok in ("429", "RESOURCE_EXHAUSTED", "quota", "Quota")):
            _GEMINI_QUOTA_EXHAUSTED = True
        raise


def _postprocess_tts_audio(
    src_audio: Path,
    out_mp3: Path,
    spoken_text: str,
    target_cps: float = TTS_TARGET_CPS,
) -> float:
    """
    4THEPT 스튜디오 방식의 양방향 무음 트리밍(areverse + silenceremove) 및
    목표 발화 속도(CPS) 자동 보정 후 44.1kHz 스테레오 MP3로 출력합니다.
    """
    out_mp3.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="thept_tts_") as td:
        tmp_trim = Path(td) / "trimmed.wav"
        trim_cmd = [
            "ffmpeg", "-y", "-i", str(src_audio),
            "-af", (
                "silenceremove=start_periods=1:start_silence=0.02:start_threshold=-42dB,"
                "areverse,"
                "silenceremove=start_periods=1:start_silence=0.04:start_threshold=-42dB,"
                "areverse,"
                "aresample=44100"
            ),
            "-ar", "44100", "-ac", "2", "-c:a", "pcm_s16le",
            str(tmp_trim),
        ]
        res = subprocess.run(trim_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
        working_src = tmp_trim if (res.returncode == 0 and tmp_trim.exists() and tmp_trim.stat().st_size > 2000) else src_audio

        raw_dur = get_audio_duration(working_src)
        n_chars = max(1, count_spoken_chars(spoken_text))
        cps = n_chars / max(0.4, raw_dur)
        tempo = 1.0 if cps >= target_cps else min(1.22, max(1.0, target_cps / cps))

        af_chain = "afade=t=in:st=0:d=0.015"
        if tempo > 1.01:
            af_chain = f"atempo={tempo:.4f},{af_chain}"

        final_cmd = [
            "ffmpeg", "-y", "-i", str(working_src),
            "-af", af_chain,
            "-ar", "44100", "-ac", "2",
            "-c:a", "libmp3lame", "-b:a", "192k",
            str(out_mp3),
        ]
        res_final = subprocess.run(final_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
        if res_final.returncode != 0 or not out_mp3.exists() or out_mp3.stat().st_size < 1500:
            if src_audio.resolve() != out_mp3.resolve():
                shutil.copy2(src_audio, out_mp3)

    return get_audio_duration(out_mp3)


def _trim_audio_silence(audio_path: Path, spoken_text: str = "") -> None:
    """기존 호출 호환용 양방향 무음 트리밍 래퍼."""
    tmp_out = audio_path.with_name(f"trim_{audio_path.name}")
    try:
        _postprocess_tts_audio(audio_path, tmp_out, spoken_text or "가" * 10, target_cps=0.0)
        if tmp_out.exists() and tmp_out.stat().st_size > 2000 and get_audio_duration(tmp_out) >= 0.45:
            shutil.move(str(tmp_out), str(audio_path))
            return
    except Exception:
        pass
    if tmp_out.exists():
        try:
            tmp_out.unlink()
        except Exception:
            pass


async def synthesize_slide_audio(
    text: str,
    output_file: Path,
    voice: str | None = None,
    rate: str = TTS_RATE,
    retries: int = 3,
    voice_style: str | None = None,
    gemini_voice: str | None = None,
    slide_type: str = "news",
) -> float:
    """단일 슬라이드 텍스트를 Gemini 3.8 Flash TTS(우선) 또는 Edge TTS(폴백)로 합성하고 길이를 반환합니다."""
    if not text.strip():
        raise ValueError("합성할 음성 텍스트가 비어 있습니다.")

    refined_text = refine_text_for_tts(text)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    style = voice_style or SLIDE_VOICE_STYLES.get(slide_type, SLIDE_VOICE_STYLES["news"])

    edge_voice = voice or TTS_VOICE
    if gemini_voice:
        g_voice = gemini_voice
    else:
        g_voice = TTS_GEMINI_VOICE_MALE if edge_voice == TTS_VOICE_MALE else TTS_GEMINI_VOICE_FEMALE

    # 1. Gemini 3.8 Flash TTS 우선 시도 (캐시 히트 또는 라이브 생성)
    if _get_gemini_client() is not None and TTS_ENGINE in ("auto", "gemini"):
        with tempfile.TemporaryDirectory(prefix="thept_gem_") as td:
            raw_wav = Path(td) / "gem_raw.wav"
            try:
                engine_used = _synth_gemini_wav(refined_text, g_voice, style, raw_wav)
                duration = _postprocess_tts_audio(raw_wav, output_file, refined_text)
                if duration >= 0.45:
                    print(f"   🎙️ [TTS:{engine_used}] voice={g_voice} ({duration:.2f}s)")
                    return duration
            except Exception as exc:
                safe_msg = str(exc)[:140]
                print(f"   ⚠️ [TTS 폴백] Gemini TTS -> Edge TTS 전환 ({safe_msg})")

    # 2. Edge TTS 폴백/기본 합성 (재시도 포함)
    last_err: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            with tempfile.TemporaryDirectory(prefix="thept_edge_") as td:
                raw_mp3 = Path(td) / "edge_raw.mp3"
                communicate = edge_tts.Communicate(
                    text=refined_text,
                    voice=edge_voice,
                    rate=rate,
                    volume=TTS_VOLUME,
                )
                await communicate.save(str(raw_mp3))

                if not raw_mp3.exists() or raw_mp3.stat().st_size < 3000:
                    if len(refined_text) > 15:
                        size_now = raw_mp3.stat().st_size if raw_mp3.exists() else 0
                        raise RuntimeError(f"TTS 음성 파일 크기 비정상 ({size_now} bytes)")

                duration = _postprocess_tts_audio(raw_mp3, output_file, refined_text)
                if duration < 0.8 and len(refined_text) > 15:
                    raise RuntimeError(f"TTS 오디오 재생 길이 비정상 ({duration:.2f}초)")
                return duration
        except Exception as e:
            last_err = e
            if attempt < retries:
                await asyncio.sleep(1.2 * attempt)

    raise RuntimeError(f"TTS 음성 합성 {retries}회 시도 실패 ({output_file}): {last_err}")


async def synthesize_all_narration(package: dict, output_dir: Path) -> list[dict]:
    """
    모든 슬라이드의 나레이션을 남녀 교차 듀오 앵커로 합성하고,
    각 슬라이드의 오디오 경로와 재생 길이를 반환합니다.
    """
    slides = package.get("slides", [])
    if not slides:
        raise ValueError("합성할 슬라이드 목록이 없습니다.")

    output_dir.mkdir(parents=True, exist_ok=True)
    audio_results = []
    total_duration = 0.0

    engine_label = "Gemini 3.8 TTS (+Edge 폴백)" if _get_gemini_client() is not None else f"Edge TTS ({TTS_RATE})"
    print(f"[TTS] 총 {len(slides)}개 슬라이드 남녀 듀오 교차 음성 합성 시작 (엔진: {engine_label})...")

    for idx, slide in enumerate(slides):
        slide_type = slide["type"]
        narration_text = slide.get("narration", "")
        if not narration_text:
            raise ValueError(f"슬라이드 {idx+1} ({slide_type})에 나레이션 텍스트가 없습니다.")

        is_female = (idx % 2 == 0)
        assigned_voice = slide.get("voice") or (TTS_VOICE_FEMALE if is_female else TTS_VOICE_MALE)
        g_voice = TTS_GEMINI_VOICE_FEMALE if assigned_voice == TTS_VOICE_FEMALE else TTS_GEMINI_VOICE_MALE
        anchor_name = "여성(Kore/SunHi)" if assigned_voice == TTS_VOICE_FEMALE else "남성(Puck/InJoon)"

        audio_path = output_dir / f"audio_{idx+1:02d}_{slide_type}.mp3"
        refined_narration = refine_text_for_tts(narration_text)
        duration = await synthesize_slide_audio(
            refined_narration,
            audio_path,
            voice=assigned_voice,
            rate=TTS_RATE,
            gemini_voice=g_voice,
            slide_type=slide_type,
        )
        total_duration += duration

        audio_results.append({
            "slide_index": idx,
            "slide_type": slide_type,
            "voice": assigned_voice,
            "gemini_voice": g_voice,
            "anchor": anchor_name,
            "audio_path": audio_path,
            "duration": duration,
            "narration": narration_text,
            "refined_narration": refined_narration,
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
    test_out = Path(__file__).resolve().parent.parent / "결과물" / "THEPT뉴스" / "test_audio"
    results = asyncio.run(synthesize_all_narration(test_pkg, test_out))
    total = sum(r["duration"] for r in results)
    print(f"[성공] 총 {len(results)}개 오디오 생성 완료, 총합: {total:.2f}초")
