"""Build V2 Cinema-Grade 9:16 (1080x1920, 30fps) Shorts & Reels Promo — AI Charting Edition.

Architecture (Zero Extra API Cost):
- Layer 0 Audio:
  * Gemini 3.8 Flash TTS (`gemini-3.8-flash-tts`, v1beta Free Tier, cached on disk by content hash;
    graceful 429 fallback to Edge TTS if daily Free Tier RPD is exhausted)
  * Commercial-free Mixkit BGM (`bgm_tech_upbeat.mp3`) sidechain-ducked beneath narration
  * Real Mixkit + Kenney CC0 SFX (`sfx_whoosh`, `sfx_typing`, `sfx_pop`, `sfx_click`, `sfx_confirm`)
  * Broadcast EQ + compressor + EBU R128 loudness normalization (`-14 LUFS`)
- Layer A Video Base (FFmpeg):
  * Full-bleed Google Flow Veo 3.1 Fast 9:16 B-roll clips (Cuts 1, 2, 6)
  * Blurred clinical dark B-roll + 2.2x zoomed live 4THEPT AI charting UI (1000x840) (Cuts 3, 4, 5)
  * Silky FFmpeg `xfade` cut transitions
- Layer B Transparent Motion Graphics Overlay (Playwright HTML5/CSS3/SVG + Pretendard):
  * Enlarged top hook banner (74px / 82px) focused strictly on post-treatment AI Charting
  * Enlarged 1000x840 device bezel + moving specular light sheen + SVG red callout overlays
  * Enlarged 84px kinetic pop subtitles cleanly above Shorts/Reels UI overlays
  * Refined one-line bottom review notice tucked cleanly at the very bottom
"""

from __future__ import annotations

import asyncio
import base64
import functools
import hashlib
import http.server
import json
import os
import re
import shutil
import socketserver
import subprocess
import tempfile
import threading
from dataclasses import dataclass
from pathlib import Path

import edge_tts
from google import genai
from PIL import Image, ImageDraw
from playwright.sync_api import sync_playwright

PROMO_DIR = Path(__file__).resolve().parents[1]
AUTO_ROOT = PROMO_DIR.parent
VIDEOS_DIR = AUTO_ROOT / "결과물" / "4THEPT마케팅" / "videos"
VIDEOS_DIR.mkdir(parents=True, exist_ok=True)
MEDIA_LIB = PROMO_DIR / "media_library"
BROLL_DIR = MEDIA_LIB / "broll"
BRAND_DIR = MEDIA_LIB / "brand"
UI_REC_DIR = MEDIA_LIB / "ui_recordings"
AUDIO_DIR = MEDIA_LIB / "audio"
TTS_DIR = MEDIA_LIB / "tts"
TTS_DIR.mkdir(parents=True, exist_ok=True)

OUT_MP4 = VIDEOS_DIR / "shorts_cinematic_v2_18s.mp4"

WIDTH = 1080
HEIGHT = 1920
FPS = 30
XFADE_SEC = 0.22

DEV_X = 40
DEV_Y = 340
DEV_W = 1000
DEV_H = 840
DEV_R = 30


@dataclass(frozen=True)
class CutSpec:
    kind: str  # "broll" | "ui_device" | "cta_broll"
    primary_asset: str
    backdrop_asset: str | None
    xfade_next: str | None
    hook_banner: bool
    step_tag: str
    callout_label: str
    callout_rect: tuple[int, int, int, int] | None  # abs px inside 1080x1920
    cta_card: bool
    voice_style: str
    narration: str
    subtitle_chunks: tuple[tuple[str, str, str], ...]  # (full_text, highlight_token, color_key)


V2_CUTS: list[CutSpec] = [
    CutSpec(
        kind="broll",
        primary_asset="broll_01_overtime.mp4",
        backdrop_asset=None,
        xfade_next="smoothleft",
        hook_banner=True,
        step_tag="",
        callout_label="",
        callout_rect=None,
        cta_card=False,
        voice_style="empathetic, urgent, relatable Korean physical therapist speaking briskly for Shorts hook",
        narration="치료 끝나고 밀린 차팅, 자세히 쓰자니 야근이고 대충 쓰자니 막막하셨죠?",
        subtitle_chunks=(
            ("자세히 쓰자니 야근", "야근", "yellow"),
            ("대충 쓰자니 막막한 차팅", "막막한 차팅", "yellow"),
        ),
    ),
    CutSpec(
        kind="broll",
        primary_asset="broll_02_typing.mp4",
        backdrop_asset=None,
        xfade_next="smoothup",
        hook_banner=True,
        step_tag="",
        callout_label="",
        callout_rect=None,
        cta_card=False,
        voice_style="crisp, energetic, trustworthy Korean narrator, brisk Shorts tempo",
        narration="이제 시행한 치료 테크닉과 환자 상태만 나만의 방식으로 간단히 적으세요.",
        subtitle_chunks=(
            ("치료 테크닉 · 환자 상태만", "치료 테크닉", "yellow"),
            ("나만의 방식으로 간단히!", "나만의 방식", "yellow"),
        ),
    ),
    CutSpec(
        kind="ui_device",
        primary_asset="ui_01_bodychart_typing.mp4",
        backdrop_asset="broll_02_typing.mp4",
        xfade_next="fadewhite",
        hook_banner=True,
        step_tag="STEP 01",
        callout_label="나만의 메모 · 약어 그대로 입력",
        callout_rect=(96, 468, 888, 200),
        cta_card=False,
        voice_style="clear, upbeat Korean explainer voice, crisp pacing",
        narration="평소 쓰던 약어나 짧은 메모 그대로 적어도 충분합니다.",
        subtitle_chunks=(
            ("평소 쓰던 메모 그대로", "메모 그대로", "yellow"),
            ("간단하게 한 줄 입력!", "한 줄 입력!", "yellow"),
        ),
    ),
    CutSpec(
        kind="ui_device",
        primary_asset="ui_02_soap_generate.mp4",
        backdrop_asset="broll_02_typing.mp4",
        xfade_next="smoothleft",
        hook_banner=True,
        step_tag="STEP 02",
        callout_label="EMR용 자세한 차팅 자동 변환",
        callout_rect=(82, 575, 860, 215),
        cta_card=False,
        voice_style="energetic, amazed, crisp Korean narrator, fast Shorts tempo",
        narration="AI가 병원 EMR에 바로 쓸 수 있는 자세한 차팅으로 깔끔하게 변환해 줍니다.",
        subtitle_chunks=(
            ("EMR에 바로 쓸 수 있는", "EMR", "emerald"),
            ("자세한 차팅으로 변환!", "자세한 차팅", "yellow"),
        ),
    ),
    CutSpec(
        kind="ui_device",
        primary_asset="ui_03_emr_copy_benefit.mp4",
        backdrop_asset="broll_02_typing.mp4",
        xfade_next="fadeblack",
        hook_banner=True,
        step_tag="STEP 03",
        callout_label="내용 검토 후 원클릭 복사",
        callout_rect=(746, 366, 266, 52),
        cta_card=False,
        voice_style="satisfying, crisp, upbeat Korean voice, decisive tempo",
        narration="변환된 내용을 가볍게 검토한 뒤 복사 버튼만 누르면 오늘 차팅 끝.",
        subtitle_chunks=(
            ("가볍게 검토한 뒤", "검토한 뒤", "emerald"),
            ("[복사] 누르면 차팅 끝!", "[복사]", "emerald"),
        ),
    ),
    CutSpec(
        kind="cta_broll",
        primary_asset="broll_03_leave_ontime.mp4",
        backdrop_asset=None,
        xfade_next=None,
        hook_banner=False,
        step_tag="",
        callout_label="",
        callout_rect=None,
        cta_card=True,
        voice_style="warm, decisive, encouraging Korean voice, energetic close",
        narration="더피티 회원은 매월 삼백 분까지 무료. 지금 포더피티닷컴에서 바로 써보세요.",
        subtitle_chunks=(
            ("THEPT 회원 300분 무료!", "300분 무료!", "yellow"),
            ("지금 4thept.com 시작!", "4thept.com", "emerald"),
        ),
    ),
]


def load_env_key(name: str = "GEMINI_API_KEY") -> str:
    val = os.environ.get(name, "").strip()
    if val:
        return val
    for env_path in (AUTO_ROOT / ".env", PROMO_DIR / ".env"):
        if env_path.exists():
            for line in env_path.read_text(encoding="utf-8").splitlines():
                s = line.strip()
                if not s or s.startswith("#") or "=" not in s:
                    continue
                k, v = s.split("=", 1)
                if k.strip() == name:
                    return v.strip().strip('"').strip("'")
    return ""


def probe_duration(path: Path) -> float:
    out = subprocess.check_output(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(path),
        ],
        text=True,
    ).strip()
    return float(out)


def count_spoken_chars(text: str) -> int:
    return len(re.findall(r"[가-힣A-Za-z0-9]", text))


async def _synth_edge_fallback(text: str, mp3_path: Path, voice: str = "ko-KR-SunHiNeural") -> None:
    comm = edge_tts.Communicate(text, voice=voice, rate="+24%")
    await comm.save(str(mp3_path))


def synth_gemini_tts_all(cuts: list[CutSpec], work_dir: Path) -> list[tuple[Path, float, str]]:
    """Synthesize or load cached Gemini 3.8 Flash TTS WAVs, with graceful 429 Edge TTS fallback."""
    api_key = load_env_key("GEMINI_API_KEY")
    client = genai.Client(api_key=api_key, http_options={"api_version": "v1beta"}) if api_key else None
    voice_name = "Kore"
    outputs: list[tuple[Path, float, str]] = []

    for idx, cut in enumerate(cuts, 1):
        digest = hashlib.sha256(f"{cut.narration}|{cut.voice_style}|{voice_name}".encode("utf-8")).hexdigest()[:12]
        raw_wav = TTS_DIR / f"v2_cut_{idx:02d}_{digest}_raw.wav"
        engine_used = "cached:gemini-3.8-flash-tts"

        if not (raw_wav.exists() and raw_wav.stat().st_size > 2500):
            quota_hit = False
            if client is not None:
                try:
                    inter = client.interactions.create(
                        model="gemini-3.8-flash-tts",
                        input=[
                            {
                                "type": "user_input",
                                "content": [
                                    {
                                        "type": "text",
                                        "text": cut.narration,
                                        "annotations": [{"type": "speech_metadata", "style": cut.voice_style}],
                                    }
                                ],
                            }
                        ],
                        response_format={"type": "audio"},
                        generation_config={"speech_config": [{"voice": voice_name}]},
                    )
                    audio_obj = getattr(inter, "output_audio", None)
                    if not (audio_obj and getattr(audio_obj, "data", None)):
                        raise RuntimeError(f"Empty audio from gemini-3.8-flash-tts on cut {idx}")
                    raw_wav.write_bytes(base64.b64decode(audio_obj.data))
                    engine_used = "live:gemini-3.8-flash-tts"
                except Exception as exc:
                    safe_msg = str(exc).replace(api_key, "[REDACTED]") if api_key else str(exc)
                    if any(tok in safe_msg for tok in ("429", "RESOURCE_EXHAUSTED", "quota", "Quota")):
                        cached_cut6 = TTS_DIR / "v2_cut_06_b313dffbc740_raw.wav"
                        if idx == 6 and cached_cut6.exists() and cached_cut6.stat().st_size > 2500:
                            shutil.copy2(cached_cut6, raw_wav)
                            engine_used = "cached-compat:gemini-3.8-flash-tts"
                            print(f"[TTS-WARN] cut {idx:02d} Gemini quota (429); reusing consistent Kore Gemini cache")
                        else:
                            quota_hit = True
                            print(f"[TTS-WARN] cut {idx:02d} Gemini free quota (429) hit; falling back to Edge TTS")
                    else:
                        raise RuntimeError(
                            f"Gemini 3.8 TTS failed on cut {idx}: {type(exc).__name__}: {safe_msg[:300]}"
                        ) from None
            else:
                quota_hit = True

            if quota_hit:
                fb_mp3 = work_dir / f"edge_fb_{idx:02d}.mp3"
                asyncio.run(_synth_edge_fallback(cut.narration, fb_mp3))
                subprocess.run(
                    [
                        "ffmpeg",
                        "-y",
                        "-i",
                        str(fb_mp3),
                        "-ar",
                        "24000",
                        "-ac",
                        "1",
                        "-c:a",
                        "pcm_s16le",
                        str(raw_wav),
                    ],
                    check=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                engine_used = "fallback:edge-tts"

        trimmed_wav = work_dir / f"tts_trim_{idx:02d}.wav"
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-i",
                str(raw_wav),
                "-af",
                (
                    "silenceremove=start_periods=1:start_silence=0.02:start_threshold=-42dB,"
                    "areverse,"
                    "silenceremove=start_periods=1:start_silence=0.04:start_threshold=-42dB,"
                    "areverse,"
                    "aresample=44100"
                ),
                "-ar",
                "44100",
                "-ac",
                "2",
                "-c:a",
                "pcm_s16le",
                str(trimmed_wav),
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        raw_dur = probe_duration(trimmed_wav)
        n_chars = max(1, count_spoken_chars(cut.narration))
        cps = n_chars / max(0.4, raw_dur)
        target_cps = 6.6
        tempo = 1.0 if cps >= target_cps else min(1.22, max(1.0, target_cps / cps))
        final_wav = work_dir / f"tts_final_{idx:02d}.wav"
        af_chain = "afade=t=in:st=0:d=0.015"
        if tempo > 1.01:
            af_chain = f"atempo={tempo:.4f}," + af_chain
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-i",
                str(trimmed_wav),
                "-af",
                af_chain,
                "-ar",
                "44100",
                "-ac",
                "2",
                "-c:a",
                "pcm_s16le",
                str(final_wav),
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        final_dur = probe_duration(final_wav)
        print(
            f"[TTS] cut {idx:02d} ({engine_used}) raw={raw_dur:.2f}s tempo={tempo:.2f} final={final_dur:.2f}s ({n_chars/final_dur:.2f} c/s)"
        )
        outputs.append((final_wav, final_dur, engine_used))
    return outputs


def compute_timeline(cuts: list[CutSpec], speech_durs: list[float]) -> tuple[list[dict], float]:
    """Compute exact lock-step visual xfade offsets and narration start times."""
    seg_durs: list[float] = []
    for i, sdur in enumerate(speech_durs):
        pad = 0.44 if i < len(cuts) - 1 else 0.62
        if i == 0:
            pad = 0.42
        seg_durs.append(max(3.55, min(5.15, sdur + pad)))

    n = len(cuts)
    timeline: list[dict] = []
    vis_cursor = 0.0
    for i in range(n):
        vis_start = vis_cursor
        seg_dur = seg_durs[i]
        has_next = i < n - 1
        vis_end = vis_start + seg_dur - (XFADE_SEC if has_next else 0.0)
        v_start = vis_start + (0.06 if i == 0 else 0.16)
        timeline.append(
            {
                "idx": i,
                "kind": cuts[i].kind,
                "segDur": seg_dur,
                "visStart": vis_start,
                "visEnd": vis_end,
                "voiceStart": v_start,
                "speechDur": speech_durs[i],
                "hookBanner": cuts[i].hook_banner,
                "stepTag": cuts[i].step_tag,
                "calloutLabel": cuts[i].callout_label,
                "calloutRect": list(cuts[i].callout_rect) if cuts[i].callout_rect else None,
                "ctaCard": cuts[i].cta_card,
                "subtitleChunks": [list(c) for c in cuts[i].subtitle_chunks],
            }
        )
        vis_cursor = vis_end

    total_dur = vis_cursor
    print(f"[TIMELINE] total={total_dur:.2f}s | cuts={[round(t['segDur'], 2) for t in timeline]}")
    return timeline, total_dur


def mix_studio_audio(
    tts_files: list[Path], timeline: list[dict], total_dur: float, work_dir: Path
) -> Path:
    """Build voice bus, sidechain-ducked real BGM, real Mixkit+Kenney SFX bus, and loudness-normalized master."""
    voice_bus = work_dir / "voice_bus.wav"
    bgm_bus = work_dir / "bgm_ducked.wav"
    master_wav = work_dir / "master_audio.wav"

    v_inputs: list[str] = []
    v_filter: list[str] = []
    v_labels: list[str] = []
    for i, (wav_path, tl) in enumerate(zip(tts_files, timeline)):
        v_inputs.extend(["-i", str(wav_path)])
        delay_ms = max(0, int(tl["voiceStart"] * 1000))
        lbl = f"[v{i}]"
        v_filter.append(f"[{i}:a]adelay={delay_ms}|{delay_ms}{lbl}")
        v_labels.append(lbl)
    v_filter.append(
        f"{''.join(v_labels)}amix=inputs={len(tts_files)}:duration=longest:normalize=0,"
        f"apad=whole_dur={total_dur:.3f},"
        "highpass=f=80,equalizer=f=2800:t=q:w=1.2:g=2.6,"
        "acompressor=threshold=-17dB:ratio=3:attack=5:release=60,"
        "alimiter=limit=0.92[vout]"
    )
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            *v_inputs,
            "-filter_complex",
            ";".join(v_filter),
            "-map",
            "[vout]",
            "-t",
            f"{total_dur:.3f}",
            "-ar",
            "44100",
            "-ac",
            "2",
            "-c:a",
            "pcm_s16le",
            str(voice_bus),
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    bgm_src = AUDIO_DIR / "bgm_tech_upbeat.mp3"
    fade_out_st = max(0.5, total_dur - 1.1)
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-stream_loop",
            "-1",
            "-i",
            str(bgm_src),
            "-i",
            str(voice_bus),
            "-filter_complex",
            (
                f"[0:a]atrim=0:{total_dur:.3f},asetpts=PTS-STARTPTS,"
                f"volume=0.34,afade=t=in:st=0:d=0.30,afade=t=out:st={fade_out_st:.3f}:d=1.10[bgm];"
                "[bgm][1:a]sidechaincompress=threshold=0.025:ratio=6:attack=25:release=260:makeup=1[bgmout]"
            ),
            "-map",
            "[bgmout]",
            "-t",
            f"{total_dur:.3f}",
            "-ar",
            "44100",
            "-ac",
            "2",
            "-c:a",
            "pcm_s16le",
            str(bgm_bus),
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    sfx_events: list[tuple[Path, float, float]] = []
    for tl in timeline[1:]:
        sfx_events.append((AUDIO_DIR / "sfx_whoosh.wav", max(0.0, tl["visStart"] - 0.14), 0.34))
    sfx_events.append((AUDIO_DIR / "sfx_typing.wav", timeline[2]["visStart"] + 0.55, 0.28))
    sfx_events.append((AUDIO_DIR / "sfx_pop.wav", timeline[3]["visStart"] + 0.24, 0.46))
    # Align Copy click + confirm SFX cleanly to live ui_03 click at ~1.32s into Cut 5
    sfx_events.append((AUDIO_DIR / "sfx_click.wav", timeline[4]["visStart"] + 1.32, 0.58))
    sfx_events.append((AUDIO_DIR / "sfx_confirm.wav", timeline[4]["visStart"] + 1.48, 0.50))

    m_inputs = ["-i", str(voice_bus), "-i", str(bgm_bus)]
    m_filter: list[str] = []
    s_labels: list[str] = []
    for k, (s_path, t_sec, vol) in enumerate(sfx_events):
        m_inputs.extend(["-i", str(s_path)])
        in_idx = k + 2
        d_ms = max(0, int(t_sec * 1000))
        lbl = f"[sx{k}]"
        m_filter.append(f"[{in_idx}:a]volume={vol:.2f},adelay={d_ms}|{d_ms}{lbl}")
        s_labels.append(lbl)
    m_filter.append(
        f"[0:a][1:a]{''.join(s_labels)}amix=inputs={2 + len(sfx_events)}:duration=first:normalize=0,"
        "loudnorm=I=-14:TP=-1.5:LRA=9[master]"
    )
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            *m_inputs,
            "-filter_complex",
            ";".join(m_filter),
            "-map",
            "[master]",
            "-t",
            f"{total_dur:.3f}",
            "-ar",
            "48000",
            "-ac",
            "2",
            "-c:a",
            "pcm_s16le",
            str(master_wav),
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    print(f"[AUDIO] Master studio audio ready ({master_wav.stat().st_size} bytes)")
    return master_wav


def make_rounded_mask(out_path: Path, w: int, h: int, radius: int) -> None:
    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, w - 1, h - 1], radius=radius, fill=255)
    mask.save(str(out_path), "PNG")


def build_base_video_layer(cuts: list[CutSpec], timeline: list[dict], work_dir: Path) -> Path:
    """Render each cut segment and stitch via FFmpeg xfade into base_layer.mp4."""
    mask_path = work_dir / "device_mask.png"
    make_rounded_mask(mask_path, DEV_W, DEV_H, DEV_R)

    seg_paths: list[Path] = []
    for i, (cut, tl) in enumerate(zip(cuts, timeline)):
        seg_dur = tl["segDur"]
        seg_mp4 = work_dir / f"seg_{i:02d}.mp4"
        if cut.kind in ("broll", "cta_broll"):
            src_vid = BROLL_DIR / cut.primary_asset
            if not src_vid.exists():
                raise FileNotFoundError(f"Missing B-roll: {src_vid}")
            grade = (
                "eq=contrast=1.05:saturation=1.06:brightness=-0.04,"
                if cut.kind == "broll"
                else "eq=contrast=1.04:saturation=1.08:brightness=-0.02,"
            )
            subprocess.run(
                [
                    "ffmpeg",
                    "-y",
                    "-stream_loop",
                    "-1",
                    "-i",
                    str(src_vid),
                    "-t",
                    f"{seg_dur:.3f}",
                    "-vf",
                    f"fps={FPS},scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=increase,crop={WIDTH}:{HEIGHT},{grade}format=yuv420p",
                    "-an",
                    "-c:v",
                    "libx264",
                    "-preset",
                    "medium",
                    "-crf",
                    "18",
                    "-pix_fmt",
                    "yuv420p",
                    str(seg_mp4),
                ],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        else:
            bg_vid = BROLL_DIR / (cut.backdrop_asset or "broll_02_typing.mp4")
            ui_vid = UI_REC_DIR / cut.primary_asset
            ui_dur = probe_duration(ui_vid)
            pad_needed = max(0.0, seg_dur - ui_dur + 0.30)
            ui_chain = (
                f"fps={FPS},scale={DEV_W}:{DEV_H}:flags=lanczos,"
                + (f"tpad=stop_mode=clone:stop_duration={pad_needed:.3f}," if pad_needed > 0.01 else "")
                + f"trim=0:{seg_dur:.3f},setpts=PTS-STARTPTS,format=rgba"
            )
            subprocess.run(
                [
                    "ffmpeg",
                    "-y",
                    "-stream_loop",
                    "-1",
                    "-i",
                    str(bg_vid),
                    "-i",
                    str(ui_vid),
                    "-loop",
                    "1",
                    "-i",
                    str(mask_path),
                    "-filter_complex",
                    (
                        f"[0:v]trim=0:{seg_dur:.3f},setpts=PTS-STARTPTS,"
                        f"fps={FPS},scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=increase,crop={WIDTH}:{HEIGHT},"
                        "boxblur=26:2,eq=brightness=-0.32:saturation=0.72[bg];"
                        f"[1:v]{ui_chain}[ui];"
                        f"[2:v]trim=0:{seg_dur:.3f},setpts=PTS-STARTPTS,format=gray[msk];"
                        "[ui][msk]alphamerge[uialpha];"
                        f"[bg][uialpha]overlay=x={DEV_X}:y={DEV_Y}:shortest=1,format=yuv420p[out]"
                    ),
                    "-map",
                    "[out]",
                    "-t",
                    f"{seg_dur:.3f}",
                    "-an",
                    "-c:v",
                    "libx264",
                    "-preset",
                    "medium",
                    "-crf",
                    "18",
                    "-pix_fmt",
                    "yuv420p",
                    str(seg_mp4),
                ],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        seg_paths.append(seg_mp4)
        print(f"[VIDEO-BASE] Segment {i+1}/{len(cuts)} ready ({seg_dur:.2f}s)")

    base_mp4 = work_dir / "base_layer.mp4"
    xf_inputs: list[str] = []
    for sp in seg_paths:
        xf_inputs.extend(["-i", str(sp)])

    xf_chains: list[str] = []
    cur_lbl = "[0:v]"
    offset = 0.0
    for i in range(len(seg_paths) - 1):
        offset += timeline[i]["segDur"] - XFADE_SEC
        trans = cuts[i].xfade_next or "smoothleft"
        next_lbl = f"[xf{i}]" if i < len(seg_paths) - 2 else "[baseout]"
        xf_chains.append(
            f"{cur_lbl}[{i+1}:v]xfade=transition={trans}:duration={XFADE_SEC:.2f}:offset={offset:.3f}{next_lbl}"
        )
        cur_lbl = next_lbl

    subprocess.run(
        [
            "ffmpeg",
            "-y",
            *xf_inputs,
            "-filter_complex",
            ";".join(xf_chains) + ";[baseout]format=yuv420p[vfin]",
            "-map",
            "[vfin]",
            "-an",
            "-c:v",
            "libx264",
            "-preset",
            "medium",
            "-crf",
            "17",
            "-pix_fmt",
            "yuv420p",
            str(base_mp4),
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    print(f"[VIDEO-BASE] Stitched xfade base layer: {probe_duration(base_mp4):.2f}s")
    return base_mp4


def build_overlay_html(timeline: list[dict], total_dur: float, font_url_eb: str, font_url_b: str) -> str:
    payload = json.dumps(
        {"timeline": timeline, "totalDur": total_dur, "dev": [DEV_X, DEV_Y, DEV_W, DEV_H, DEV_R]},
        ensure_ascii=False,
    )
    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="utf-8">
<style>
@font-face {{
  font-family: 'PretendardV2';
  src: url('{font_url_b}') format('truetype');
  font-weight: 700;
}}
@font-face {{
  font-family: 'PretendardV2';
  src: url('{font_url_eb}') format('truetype');
  font-weight: 800 900;
}}
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
html, body {{
  width: 1080px;
  height: 1920px;
  overflow: hidden;
  background: transparent !important;
  font-family: 'PretendardV2', 'Malgun Gothic', sans-serif;
  -webkit-font-smoothing: antialiased;
}}
#top-scrim {{
  position: absolute;
  left: 0; top: 0; width: 1080px; height: 340px;
  background: linear-gradient(180deg, rgba(2,6,23,0.90) 0%, rgba(2,6,23,0.62) 66%, rgba(2,6,23,0) 100%);
}}
#bottom-scrim {{
  position: absolute;
  left: 0; top: 1120px; width: 1080px; height: 800px;
  background: linear-gradient(0deg, rgba(2,6,23,0.94) 0%, rgba(2,6,23,0.82) 55%, rgba(2,6,23,0.36) 84%, rgba(2,6,23,0) 100%);
}}
#progress-track {{
  position: absolute;
  left: 0; top: 0; width: 1080px; height: 9px;
  background: rgba(255,255,255,0.14);
}}
#progress-fill {{
  height: 100%; width: 0%;
  background: linear-gradient(90deg, #3B82F6 0%, #34D399 65%, #FACC15 100%);
  box-shadow: 0 0 12px rgba(59,130,246,0.85);
}}
#hook-banner {{
  position: absolute;
  left: 32px; top: 64px; width: 1016px;
  text-align: center;
  transform-origin: center top;
}}
.hook-line-1 {{
  font-size: 74px;
  font-weight: 900;
  line-height: 1.15;
  letter-spacing: -2px;
  color: #FFFFFF;
  text-shadow: 0 6px 20px rgba(0,0,0,0.85);
  -webkit-text-stroke: 2.5px rgba(2,6,23,0.58);
  paint-order: stroke fill;
}}
.hook-line-2 {{
  font-size: 82px;
  font-weight: 900;
  line-height: 1.15;
  letter-spacing: -2.2px;
  color: #FACC15;
  text-shadow: 0 7px 24px rgba(0,0,0,0.92);
  -webkit-text-stroke: 3px rgba(2,6,23,0.68);
  paint-order: stroke fill;
}}
#step-pill {{
  position: absolute;
  left: 44px; top: 260px;
  padding: 11px 22px;
  border-radius: 999px;
  background: rgba(15, 23, 42, 0.90);
  border: 2px solid rgba(96, 165, 250, 0.58);
  color: #E2E8F0;
  font-size: 27px;
  font-weight: 900;
  letter-spacing: -0.4px;
  box-shadow: 0 8px 24px rgba(0,0,0,0.45);
  display: none;
  align-items: center;
  gap: 12px;
}}
.step-logo-img {{
  height: 22px;
  width: auto;
  display: block;
}}
.step-sep {{
  width: 2px;
  height: 20px;
  background: rgba(148, 163, 184, 0.45);
}}
#callout-badge {{
  position: absolute;
  right: 44px; top: 256px;
  padding: 13px 26px;
  border-radius: 999px;
  background: #FACC15;
  color: #0F172A;
  font-size: 38px;
  font-weight: 900;
  letter-spacing: -0.8px;
  border: 3px solid #EF4444;
  box-shadow: 0 10px 26px rgba(0,0,0,0.55);
  white-space: nowrap;
  transform-origin: right center;
}}
#device-bezel {{
  position: absolute;
  left: {DEV_X - 3}px; top: {DEV_Y - 3}px;
  width: {DEV_W + 6}px; height: {DEV_H + 6}px;
  border-radius: {DEV_R + 3}px;
  border: 3px solid rgba(255, 255, 255, 0.36);
  box-shadow:
    0 30px 70px rgba(2, 6, 23, 0.78),
    0 0 0 1px rgba(59, 130, 246, 0.32),
    inset 0 1px 0 rgba(255, 255, 255, 0.42);
  overflow: hidden;
  pointer-events: none;
  background: transparent;
}}
#device-sheen {{
  position: absolute;
  top: -80px; left: -260px;
  width: 210px; height: 1080px;
  background: linear-gradient(90deg, rgba(255,255,255,0) 0%, rgba(255,255,255,0.22) 50%, rgba(255,255,255,0) 100%);
  transform: rotate(22deg);
}}
#callout-svg {{
  position: absolute;
  left: 0; top: 0; width: 1080px; height: 1920px;
  pointer-events: none;
}}
#cta-brand-pill {{
  position: absolute;
  left: 50%;
  top: 64px;
  transform: translateX(-50%);
  padding: 17px 40px;
  border-radius: 999px;
  background: #FFFFFF;
  border: 2.5px solid rgba(147, 197, 253, 0.85);
  box-shadow: 0 14px 34px rgba(2, 6, 23, 0.55);
  display: none;
  align-items: center;
  justify-content: center;
}}
.cta-brand-logo {{
  height: 46px;
  width: auto;
  display: block;
}}
#cta-card {{
  position: absolute;
  left: 44px; top: 840px; width: 992px;
  border-radius: 30px;
  padding: 28px 34px;
  background: rgba(15, 23, 42, 0.88);
  border: 2.5px solid rgba(96, 165, 250, 0.65);
  box-shadow: 0 24px 52px rgba(2, 6, 23, 0.76);
  color: #FFFFFF;
}}
.cta-top-row {{
  display: flex; align-items: center; gap: 14px; margin-bottom: 16px;
}}
.cta-card-logo {{
  height: 30px; width: auto; display: block;
}}
.cta-eyebrow {{
  font-size: 25px; font-weight: 800; color: #93C5FD;
}}
.cta-row {{
  display: flex; align-items: center; justify-content: space-between; gap: 18px;
}}
.cta-metric .m-lbl {{ font-size: 24px; font-weight: 800; color: #94A3B8; display: block; }}
.cta-metric .m-val {{ font-size: 46px; font-weight: 900; color: #FFFFFF; letter-spacing: -1.2px; }}
.cta-metric .m-val.blue {{ font-size: 50px; color: #60A5FA; }}
.cta-url-pill {{
  padding: 18px 30px;
  border-radius: 18px;
  background: #2563EB;
  color: #FFFFFF;
  font-size: 36px;
  font-weight: 900;
  white-space: nowrap;
  box-shadow: 0 10px 24px rgba(37, 99, 235, 0.50);
}}
#subtitle-wrap {{
  position: absolute;
  left: 34px; top: 1252px; width: 1012px; height: 150px;
  display: flex; align-items: center; justify-content: center;
}}
#subtitle-text {{
  font-size: 84px;
  font-weight: 900;
  letter-spacing: -1.8px;
  line-height: 1.12;
  text-align: center;
  color: #FFFFFF;
  -webkit-text-stroke: 14px #020617;
  paint-order: stroke fill;
  filter: drop-shadow(0 6px 16px rgba(0,0,0,0.88));
  white-space: nowrap;
}}
.hl-yellow {{ color: #FACC15; }}
.hl-emerald {{ color: #34D399; }}
#compliance-footer {{
  position: absolute;
  left: 0; width: 1080px; bottom: 26px;
  text-align: center;
  color: rgba(226, 232, 240, 0.88);
  font-size: 23px;
  font-weight: 700;
  letter-spacing: -0.3px;
  text-shadow: 0 2px 8px rgba(0,0,0,0.92);
  white-space: nowrap;
}}
</style>
</head>
<body>
  <div id="top-scrim"></div>
  <div id="bottom-scrim"></div>
  <div id="progress-track"><div id="progress-fill"></div></div>

  <div id="hook-banner">
    <div class="hook-line-1">도수치료 끝나고</div>
    <div class="hook-line-2">밀린 차팅, 언제 다 쓰죠?</div>
  </div>
  <div id="step-pill">
    <img class="step-logo-img" src="4thept_logo_white_transparent.png" alt="4THEPT" />
    <span class="step-sep"></span>
    <span id="step-pill-label"></span>
  </div>
  <div id="callout-badge"></div>

  <div id="device-bezel">
    <div id="device-sheen"></div>
  </div>

  <svg id="callout-svg" viewBox="0 0 1080 1920">
    <ellipse id="callout-ellipse" cx="0" cy="0" rx="10" ry="10"
      fill="none" stroke="#EF4444" stroke-width="6.5" stroke-linecap="round"
      stroke-dasharray="2000" stroke-dashoffset="2000" style="display:none; filter: drop-shadow(0 3px 6px rgba(0,0,0,0.65));"/>
  </svg>

  <div id="cta-brand-pill">
    <img class="cta-brand-logo" src="4thept_logo_navy_transparent.png" alt="4THEPT" />
  </div>
  <div id="cta-card">
    <div class="cta-top-row">
      <img class="cta-card-logo" src="4thept_logo_white_transparent.png" alt="4THEPT" />
      <span class="cta-eyebrow">THEPT 공식 AI 차팅 · 카드 등록 없음</span>
    </div>
    <div class="cta-row">
      <div class="cta-metric"><span class="m-lbl" style="color:#93C5FD;">THEPT 회원</span><span class="m-val blue">월 300분</span></div>
      <div class="cta-metric"><span class="m-lbl">기본 무료</span><span class="m-val">월 120분</span></div>
      <div class="cta-url-pill">4thept.com</div>
    </div>
  </div>

  <div id="subtitle-wrap"><div id="subtitle-text"></div></div>
  <div id="compliance-footer">AI 생성 차팅은 기록 작성을 돕는 초안이므로 담당 치료사 검토 후 사용해 주세요.</div>

<script>
const CFG = {payload};
function clamp(v, lo, hi) {{ return Math.max(lo, Math.min(hi, v)); }}
function easeOutCubic(x) {{ x = clamp(x, 0, 1); return 1 - Math.pow(1 - x, 3); }}
function easeOutBack(x) {{
  x = clamp(x, 0, 1);
  const c1 = 1.70158, c3 = c1 + 1;
  return 1 + c3 * Math.pow(x - 1, 3) + c1 * Math.pow(x - 1, 2);
}}
function escHtml(s) {{
  return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}}

window.__setTime = function(t) {{
  const total = CFG.totalDur;
  document.getElementById('progress-fill').style.width = (clamp(t / total, 0, 1) * 100).toFixed(2) + '%';

  let active = CFG.timeline[CFG.timeline.length - 1];
  for (let i = 0; i < CFG.timeline.length; i++) {{
    const c = CFG.timeline[i];
    if (t >= c.visStart && (t < c.visEnd || i === CFG.timeline.length - 1)) {{
      active = c;
      break;
    }}
  }}
  const dtVis = Math.max(0, t - active.visStart);

  document.getElementById('top-scrim').style.opacity = active.hookBanner ? '1' : '0.68';

  const hb = document.getElementById('hook-banner');
  if (active.hookBanner) {{
    hb.style.display = 'block';
    const pop = active.idx === 0 ? easeOutBack(dtVis / 0.30) : 1.0;
    const op = active.idx === 0 ? clamp(dtVis / 0.14, 0, 1) : 1.0;
    hb.style.opacity = op.toFixed(3);
    hb.style.transform = `scale(${{(0.88 + 0.12 * pop).toFixed(4)}})`;
  }} else {{
    hb.style.display = 'none';
  }}

  const sp = document.getElementById('step-pill');
  const spLbl = document.getElementById('step-pill-label');
  if (active.stepTag) {{
    sp.style.display = 'inline-flex';
    spLbl.textContent = active.stepTag;
    const e = easeOutCubic(dtVis / 0.22);
    sp.style.opacity = e.toFixed(3);
    sp.style.transform = `translateY(${{(12 * (1 - e)).toFixed(1)}}px)`;
  }} else {{
    sp.style.display = 'none';
  }}

  const bezel = document.getElementById('device-bezel');
  const sheen = document.getElementById('device-sheen');
  if (active.kind === 'ui_device') {{
    bezel.style.display = 'block';
    const op = easeOutCubic(dtVis / 0.18);
    bezel.style.opacity = op.toFixed(3);
    const sheenU = clamp((dtVis - 0.15) / 1.15, 0, 1);
    sheen.style.left = (-260 + sheenU * 1520).toFixed(1) + 'px';
  }} else {{
    bezel.style.display = 'none';
  }}

  const oval = document.getElementById('callout-ellipse');
  const cbadge = document.getElementById('callout-badge');
  if (active.calloutLabel) {{
    const bScale = easeOutBack((dtVis - 0.16) / 0.28);
    cbadge.style.display = 'block';
    cbadge.textContent = active.calloutLabel;
    cbadge.style.opacity = clamp((dtVis - 0.14) / 0.15, 0, 1).toFixed(3);
    cbadge.style.transform = `scale(${{(0.78 + 0.22 * bScale).toFixed(4)}})`;
  }} else {{
    cbadge.style.display = 'none';
  }}

  if (active.calloutRect) {{
    const [rx, ry, rw, rh] = active.calloutRect;
    const cx = rx + rw / 2, cy = ry + rh / 2;
    const a = rw / 2 + 14, b = rh / 2 + 12;
    const perim = 2 * Math.PI * Math.sqrt((a*a + b*b) / 2);
    let delayDraw = 0.35;
    if (active.idx === 2) delayDraw = 0.90;
    if (active.idx === 4) delayDraw = 1.15;
    const drawU = easeOutCubic((dtVis - delayDraw) / 0.42);
    let ovalOp = 1.0;
    if (active.idx === 3 && dtVis > 1.40) {{
      ovalOp = clamp(1.0 - (dtVis - 1.40) / 0.28, 0, 1);
    }}
    oval.style.display = (drawU > 0.02 && ovalOp > 0.02) ? 'block' : 'none';
    oval.style.opacity = ovalOp.toFixed(3);
    oval.setAttribute('cx', cx.toFixed(1));
    oval.setAttribute('cy', cy.toFixed(1));
    oval.setAttribute('rx', a.toFixed(1));
    oval.setAttribute('ry', b.toFixed(1));
    oval.setAttribute('stroke-dasharray', perim.toFixed(1));
    oval.setAttribute('stroke-dashoffset', (perim * (1 - drawU)).toFixed(1));
  }} else {{
    oval.style.display = 'none';
  }}

  const ctaCard = document.getElementById('cta-card');
  const brandPill = document.getElementById('cta-brand-pill');
  if (active.ctaCard) {{
    const u = easeOutCubic(dtVis / 0.34);
    brandPill.style.display = 'flex';
    brandPill.style.opacity = u.toFixed(3);
    ctaCard.style.display = 'block';
    ctaCard.style.opacity = u.toFixed(3);
    ctaCard.style.transform = `translateY(${{(28 * (1 - u)).toFixed(1)}}px)`;
  }} else {{
    brandPill.style.display = 'none';
    ctaCard.style.display = 'none';
  }}

  const subEl = document.getElementById('subtitle-text');
  const chunks = active.subtitleChunks;
  const vStart = active.voiceStart;
  const sDur = active.speechDur;
  const vt = t - vStart;
  if (vt < -0.05 || t > active.visEnd - 0.04) {{
    subEl.style.opacity = '0';
  }} else {{
    const split = sDur * 0.48;
    const chunkIdx = vt >= split && chunks.length > 1 ? 1 : 0;
    const chunkStart = chunkIdx === 0 ? 0.0 : split;
    const chunkAge = Math.max(0, vt - chunkStart);
    const [fullTxt, hlTok, colKey] = chunks[chunkIdx];
    const pop = easeOutBack(chunkAge / 0.18);
    subEl.style.fontSize = fullTxt.length > 11 ? '76px' : '84px';
    subEl.style.opacity = clamp(chunkAge / 0.06, 0, 1).toFixed(3);
    subEl.style.transform = `scale(${{(0.84 + 0.16 * pop).toFixed(4)}})`;
    const cls = colKey === 'emerald' ? 'hl-emerald' : 'hl-yellow';
    if (hlTok && fullTxt.includes(hlTok)) {{
      const pos = fullTxt.indexOf(hlTok);
      subEl.innerHTML =
        escHtml(fullTxt.slice(0, pos)) +
        `<span class="${{cls}}">${{escHtml(hlTok)}}</span>` +
        escHtml(fullTxt.slice(pos + hlTok.length));
    }} else {{
      subEl.textContent = fullTxt;
    }}
  }}
}};
</script>
</body>
</html>"""


class _QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args) -> None:
        return


def composite_with_overlay(
    base_mp4: Path, master_wav: Path, timeline: list[dict], total_dur: float, work_dir: Path
) -> None:
    """Render deterministic transparent Layer B PNG stream in Playwright and composite over Layer A + audio."""
    web_dir = work_dir / "overlay_web"
    web_dir.mkdir(parents=True, exist_ok=True)
    eb_font = Path("C:/Windows/Fonts/Pretendard-ExtraBold.ttf")
    b_font = Path("C:/Windows/Fonts/Pretendard-Bold.ttf")
    if not eb_font.exists():
        eb_font = Path("C:/Windows/Fonts/malgunbd.ttf")
    if not b_font.exists():
        b_font = Path("C:/Windows/Fonts/malgunbd.ttf")
    shutil.copy2(eb_font, web_dir / "font_eb.ttf")
    shutil.copy2(b_font, web_dir / "font_b.ttf")
    for logo_name in ("4thept_logo_original.png", "4thept_logo_navy_transparent.png", "4thept_logo_white_transparent.png"):
        shutil.copy2(BRAND_DIR / logo_name, web_dir / logo_name)

    handler = functools.partial(_QuietHandler, directory=str(web_dir))
    httpd = socketserver.TCPServer(("127.0.0.1", 0), handler)
    port = httpd.server_address[1]
    srv_thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    srv_thread.start()

    try:
        html_str = build_overlay_html(
            timeline,
            total_dur,
            f"http://127.0.0.1:{port}/font_eb.ttf",
            f"http://127.0.0.1:{port}/font_b.ttf",
        )
        (web_dir / "index.html").write_text(html_str, encoding="utf-8")

        total_frames = int(round(probe_duration(base_mp4) * FPS))
        cmd = [
            "ffmpeg",
            "-y",
            "-loglevel",
            "error",
            "-i",
            str(base_mp4),
            "-f",
            "image2pipe",
            "-vcodec",
            "png",
            "-r",
            str(FPS),
            "-i",
            "pipe:0",
            "-i",
            str(master_wav),
            "-filter_complex",
            "[0:v][1:v]overlay=0:0:shortest=1,format=yuv420p[vout]",
            "-map",
            "[vout]",
            "-map",
            "2:a",
            "-c:v",
            "libx264",
            "-preset",
            "medium",
            "-crf",
            "18",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-movflags",
            "+faststart",
            "-shortest",
            str(OUT_MP4),
        ]
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        assert proc.stdin is not None

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(viewport={"width": WIDTH, "height": HEIGHT}, device_scale_factor=1)
            page = context.new_page()
            cdp = context.new_cdp_session(page)
            cdp.send("Emulation.setDefaultBackgroundColorOverride", {"color": {"r": 0, "g": 0, "b": 0, "a": 0}})
            page.goto(f"http://127.0.0.1:{port}/index.html", wait_until="networkidle")
            page.evaluate("() => document.fonts.ready")

            for fi in range(total_frames):
                t = fi / FPS
                page.evaluate("(ts) => window.__setTime(ts)", t)
                res = cdp.send("Page.captureScreenshot", {"format": "png", "fromSurface": True})
                proc.stdin.write(base64.b64decode(res["data"]))

            proc.stdin.close()
            _, stderr_bytes = proc.communicate()
            context.close()
            browser.close()
            if proc.returncode != 0:
                raise RuntimeError(f"FFmpeg overlay composite failed: {stderr_bytes.decode('utf-8', 'replace')[:600]}")

        print(f"[FINAL] Rendered {OUT_MP4.name} | dur={probe_duration(OUT_MP4):.2f}s | bytes={OUT_MP4.stat().st_size}")
    finally:
        httpd.shutdown()
        httpd.server_close()


def main() -> None:
    global V2_CUTS
    with tempfile.TemporaryDirectory() as td:
        work_dir = Path(td)
        tts_results = synth_gemini_tts_all(V2_CUTS, work_dir)
        # If Cut 6 reused the earlier cached Kore WAV due to 429 quota, keep its subtitle phrasing matched
        if tts_results[5][2].startswith("cached-compat:"):
            c6 = V2_CUTS[5]
            V2_CUTS[5] = CutSpec(
                kind=c6.kind,
                primary_asset=c6.primary_asset,
                backdrop_asset=c6.backdrop_asset,
                xfade_next=c6.xfade_next,
                hook_banner=c6.hook_banner,
                step_tag=c6.step_tag,
                callout_label=c6.callout_label,
                callout_rect=c6.callout_rect,
                cta_card=c6.cta_card,
                voice_style=c6.voice_style,
                narration=c6.narration,
                subtitle_chunks=(("매월 120분 · 300분 무료", "300분 무료", "yellow"), ("지금 4thept.com 시작!", "4thept.com", "emerald")),
            )
        tts_files = [r[0] for r in tts_results]
        speech_durs = [r[1] for r in tts_results]
        timeline, total_dur = compute_timeline(V2_CUTS, speech_durs)
        master_wav = mix_studio_audio(tts_files, timeline, total_dur, work_dir)
        base_mp4 = build_base_video_layer(V2_CUTS, timeline, work_dir)
        composite_with_overlay(base_mp4, master_wav, timeline, total_dur, work_dir)


if __name__ == "__main__":
    main()
