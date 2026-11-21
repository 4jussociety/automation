# 이 모듈은 4:5 카드뉴스와 TTS 음성을 결합하여 9:16 세로형 쇼츠 MP4 비디오를 렌더링합니다.
# 블러 배경 레이어와 슬라이드별 정확한 오디오 싱크를 FFmpeg로 고속 합성합니다.

import sys
from pathlib import Path
import subprocess
import shutil

sys.path.append(str(Path(__file__).resolve().parent.parent))

from PIL import Image

from config import (
    BASE_DIR,
    VIDEO_WIDTH, VIDEO_HEIGHT, CARD_WIDTH, CARD_HEIGHT,
    DEFAULT_BGM_PATH, BGM_VOLUME
)

SFX_WHOOSH_PATH = BASE_DIR / "assets" / "sfx" / "sfx_whoosh.wav"
SFX_POP_PATH = BASE_DIR / "assets" / "sfx" / "sfx_pop.wav"
VOICE_PRESENCE_FILTER = (
    "highpass=f=80,equalizer=f=2800:t=q:w=1.2:g=2.6,"
    "acompressor=threshold=-17dB:ratio=3:attack=5:release=60,"
    "alimiter=limit=0.92"
)


def get_video_filter(img_path: Path) -> str:
    """
    입력 이미지가 이미 9:16 세로형(1080x1920)인 경우 상하 왜곡 및 축소 없이 1:1 풀화면으로 직통 인코딩하고,
    4:5 비율(1080x1350)인 경우에만 센터 오버레이 + 블러 배경 처리를 적용합니다.
    """
    try:
        with Image.open(img_path) as im:
            w, h = im.size
            if h >= w * 1.6:  # 9:16 방송형 풀스크린 이미지 (예: 1080x1920)
                return f"[0:v]scale={VIDEO_WIDTH}:{VIDEO_HEIGHT},setsar=1[v]"
    except Exception:
        pass

    return (
        f"[0:v]scale={VIDEO_WIDTH}:{VIDEO_HEIGHT}:force_original_aspect_ratio=increase,"
        f"crop={VIDEO_WIDTH}:{VIDEO_HEIGHT},boxblur=28:6,setsar=1[bg];"
        f"[0:v]scale={CARD_WIDTH}:{CARD_HEIGHT}[fg];"
        f"[bg][fg]overlay=(W-w)/2:(H-h)/2[v]"
    )


def render_slide_segment(image_path: Path, audio_path: Path, duration: float, output_segment: Path) -> Path:
    """단일 슬라이드 이미지와 오디오를 9:16 세그먼트 영상으로 렌더링합니다."""
    output_segment.parent.mkdir(parents=True, exist_ok=True)

    filter_complex = f"{get_video_filter(image_path)};[1:a]{VOICE_PRESENCE_FILTER}[a]"

    cmd = [
        "ffmpeg", "-y",
        "-loop", "1",
        "-t", f"{duration:.3f}",
        "-i", str(image_path),
        "-i", str(audio_path),
        "-filter_complex", filter_complex,
        "-map", "[v]",
        "-map", "[a]",
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-crf", "20",
        "-pix_fmt", "yuv420p",
        "-r", "30",
        "-c:a", "aac",
        "-b:a", "192k",
        "-shortest",
        str(output_segment)
    ]

    res = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace"
    )
    if res.returncode != 0 or not output_segment.exists() or output_segment.stat().st_size == 0:
        raise RuntimeError(f"슬라이드 비디오 세그먼트 렌더링 실패 ({output_segment}):\n{res.stderr}")

    return output_segment


def render_multi_photo_slide_segment(image_paths: list[Path], audio_path: Path, duration: float, output_segment: Path) -> Path:
    """복수의 보도사진(2~3장)을 슬라이드 재생 시간에 맞춰 순차 교체 컷으로 렌더링합니다."""
    valid_paths = [p for p in image_paths if p and p.exists()]
    if not valid_paths:
        raise ValueError("렌더링할 유효한 이미지 경로가 없습니다.")
    if len(valid_paths) == 1:
        return render_slide_segment(valid_paths[0], audio_path, duration, output_segment)

    output_segment.parent.mkdir(parents=True, exist_ok=True)
    temp_dir = output_segment.parent / "temp_sub_segments"
    temp_dir.mkdir(parents=True, exist_ok=True)

    n = len(valid_paths)
    sub_duration = duration / n
    sub_segments = []

    for i, img in enumerate(valid_paths):
        sub_seg = temp_dir / f"sub_{output_segment.stem}_{i:02d}.mp4"
        filter_complex = get_video_filter(img)
        cmd = [
            "ffmpeg", "-y",
            "-loop", "1",
            "-t", f"{sub_duration:.3f}",
            "-i", str(img),
            "-filter_complex", filter_complex,
            "-map", "[v]",
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-crf", "20",
            "-pix_fmt", "yuv420p",
            "-r", "30",
            str(sub_seg)
        ]
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace")
        if res.returncode == 0 and sub_seg.exists():
            sub_segments.append(sub_seg)

    # 비디오 서브 세그먼트 연결 후 오디오 합성
    concat_txt = temp_dir / f"concat_{output_segment.stem}.txt"
    concat_txt.write_text("\n".join([f"file '{p.resolve().as_posix()}'" for p in sub_segments]), encoding="utf-8")
    merged_v = temp_dir / f"merged_v_{output_segment.name}"

    subprocess.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_txt), "-c", "copy", str(merged_v)],
                   stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    # 최종 오디오 합성 (4THEPT 스튜디오 보이스 Presence EQ + 컴프레서 마스터링 적용)
    cmd_final = [
        "ffmpeg", "-y",
        "-i", str(merged_v),
        "-i", str(audio_path),
        "-c:v", "copy",
        "-af", VOICE_PRESENCE_FILTER,
        "-c:a", "aac",
        "-b:a", "192k",
        "-shortest",
        str(output_segment)
    ]
    subprocess.run(cmd_final, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    # 임시 폴더 정리
    shutil.rmtree(temp_dir, ignore_errors=True)
    return output_segment


def concatenate_segments(segment_paths: list[Path], final_output: Path) -> Path:
    """모든 슬라이드 비디오 세그먼트를 하나의 완성형 MP4로 병합합니다."""
    final_output.parent.mkdir(parents=True, exist_ok=True)
    concat_list_file = final_output.parent / "concat_list.txt"

    lines = [f"file '{p.resolve().as_posix()}'" for p in segment_paths]
    concat_list_file.write_text("\n".join(lines), encoding="utf-8")

    cmd = [
        "ffmpeg", "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", str(concat_list_file),
        "-c", "copy",
        str(final_output)
    ]

    res = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace"
    )
    if res.returncode != 0 or not final_output.exists() or final_output.stat().st_size == 0:
        raise RuntimeError(f"최종 쇼츠 비디오 병합 실패 ({final_output}):\n{res.stderr}")

    # 임시 목록 파일 정리
    if concat_list_file.exists():
        concat_list_file.unlink()

    return final_output


def _mix_transition_sfx(
    video_path: Path,
    durations: list[float],
    sfx_path: Path = SFX_WHOOSH_PATH,
    pop_delays_ms: list[int] | None = None,
) -> Path:
    """슬라이드 전환 효과음(sfx_whoosh) 및 핵심/광고 포인트 효과음(sfx_pop)을 믹싱합니다."""
    has_whoosh = bool(sfx_path and sfx_path.exists() and len(durations) > 1)
    has_pop = bool(pop_delays_ms and SFX_POP_PATH.exists())
    if not has_whoosh and not has_pop:
        return video_path

    out_file = video_path.parent / f"sfx_mixed_{video_path.name}"
    cum_ms = 0
    cut_delays_ms: list[int] = []
    if has_whoosh:
        for d in durations[:-1]:
            cum_ms += int(d * 1000)
            if cum_ms > 120:
                cut_delays_ms.append(max(0, cum_ms - 80))

    sfx_events: list[tuple[Path, int, float]] = [(sfx_path, d_ms, 0.18) for d_ms in cut_delays_ms]
    if has_pop and pop_delays_ms:
        sfx_events.extend((SFX_POP_PATH, d_ms, 0.22) for d_ms in pop_delays_ms)

    if not sfx_events:
        return video_path

    cmd = ["ffmpeg", "-y", "-i", str(video_path)]
    filter_parts = []
    mix_labels = ["[0:a]"]
    for idx, (ev_path, delay_ms, vol) in enumerate(sfx_events, start=1):
        cmd.extend(["-i", str(ev_path)])
        lbl = f"[s{idx}]"
        filter_parts.append(f"[{idx}:a]adelay={delay_ms}|{delay_ms},volume={vol:.2f}{lbl}")
        mix_labels.append(lbl)

    filter_parts.append(
        f"{''.join(mix_labels)}amix=inputs={len(mix_labels)}:duration=first:normalize=0[aout]"
    )
    cmd.extend([
        "-filter_complex", ";".join(filter_parts),
        "-map", "0:v", "-map", "[aout]",
        "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest",
        str(out_file),
    ])
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace")
    if res.returncode == 0 and out_file.exists() and out_file.stat().st_size > 0:
        video_path.unlink()
        shutil.move(str(out_file), str(video_path))
        return video_path
    if out_file.exists():
        out_file.unlink()
    return video_path


def mix_bgm_to_video(
    video_path: Path,
    bgm_path: Path = None,
    bgm_volume: float = BGM_VOLUME,
    output_path: Path = None
) -> Path:
    """
    완성된 영상 비디오(TTS 음성 포함)에 BGM 배경음악을 sidechaincompress 자동 덕킹으로 믹싱하고,
    -14 LUFS 방송 음량 정규화(loudnorm) 및 종료 1.5초 페이드아웃을 적용합니다.
    """
    target_bgm = Path(bgm_path) if bgm_path else Path(DEFAULT_BGM_PATH)
    if not target_bgm or not target_bgm.exists():
        return video_path

    out_file = output_path or video_path.parent / f"bgm_mixed_{video_path.name}"

    try:
        cmd_dur = [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(video_path)
        ]
        res = subprocess.run(cmd_dur, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
        total_dur = float(res.stdout.strip())
    except Exception:
        total_dur = 60.0

    fade_st = max(0.0, total_dur - 1.5)

    # 1차 시도: sidechaincompress 자동 덕킹 + -14 LUFS loudnorm
    duck_filter = (
        f"[0:a]asplit=2[voice][sc];"
        f"[1:a]volume={bgm_volume * 1.4:.3f},afade=t=out:st={fade_st:.2f}:d=1.5[bgm_raw];"
        f"[bgm_raw][sc]sidechaincompress=threshold=0.02:ratio=6:attack=25:release=220[bgm_duck];"
        f"[voice][bgm_duck]amix=inputs=2:duration=first:normalize=0,loudnorm=I=-14:LRA=11:TP=-1.5[aout]"
    )
    fallback_filter = (
        f"[1:a]volume={bgm_volume:.3f},afade=t=out:st={fade_st:.2f}:d=1.5[bgm];"
        f"[0:a][bgm]amix=inputs=2:duration=first:dropout_transition=2[aout]"
    )

    for filter_expr in (duck_filter, fallback_filter):
        cmd = [
            "ffmpeg", "-y",
            "-i", str(video_path),
            "-stream_loop", "-1",
            "-i", str(target_bgm),
            "-filter_complex", filter_expr,
            "-map", "0:v",
            "-map", "[aout]",
            "-c:v", "copy",
            "-c:a", "aac",
            "-b:a", "192k",
            "-shortest",
            str(out_file)
        ]
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace")
        if res.returncode == 0 and out_file.exists() and out_file.stat().st_size > 0:
            if output_path is None:
                video_path.unlink()
                shutil.move(str(out_file), str(video_path))
                return video_path
            return out_file

    print(f"⚠️ [BGM 믹싱 경고] 배경음악 합성 실패, 원본 유지")
    return video_path


def render_shorts_video(
    card_image_paths: list[Path],
    audio_info_list: list[dict],
    output_video_path: Path,
    slide_image_lists: list[list[Path]] = None,
) -> Path:
    """
    모든 카드뉴스 이미지와 TTS 오디오를 매칭하여 9:16 완성형 쇼츠 비디오(shorts.mp4)를 렌더링합니다.
    """
    if len(card_image_paths) != len(audio_info_list):
        raise ValueError(
            f"이미지 개수({len(card_image_paths)})와 오디오 개수({len(audio_info_list)})가 일치하지 않습니다."
        )

    temp_segment_dir = output_video_path.parent / "temp_segments"
    temp_segment_dir.mkdir(parents=True, exist_ok=True)
    segment_paths = []
    durations = []

    print(f"[비디오 렌더] 총 {len(card_image_paths)}개 슬라이드 세그먼트 영상 렌더링 시작...")

    for i, (img_path, audio_info) in enumerate(zip(card_image_paths, audio_info_list)):
        dur = audio_info["duration"]
        durations.append(dur)
        aud_path = audio_info["audio_path"]
        seg_path = temp_segment_dir / f"seg_{i+1:02d}.mp4"

        multi_imgs = slide_image_lists[i] if slide_image_lists and i < len(slide_image_lists) else None
        if multi_imgs and len([p for p in multi_imgs if p and Path(p).exists()]) >= 2:
            render_multi_photo_slide_segment(multi_imgs, aud_path, dur, seg_path)
        else:
            render_slide_segment(img_path, aud_path, dur, seg_path)
        segment_paths.append(seg_path)
        print(f"[세그먼트 완료] 슬라이드 {i+1}/{len(card_image_paths)} ({dur:.2f}초): {seg_path.name}")

    # 모든 세그먼트 병합
    print(f"[비디오 병합] 완성형 쇼츠 비디오 병합 중: {output_video_path.name}...")
    concatenate_segments(segment_paths, output_video_path)

    # 임시 세그먼트 디렉토리 정리
    shutil.rmtree(temp_segment_dir, ignore_errors=True)

    # 전환 SFX + 광고 포인트 Pop SFX 믹싱
    pop_delays_ms: list[int] = []
    cum_ms = 0
    for d, a_info in zip(durations, audio_info_list):
        if a_info.get("slide_type") == "ad" and cum_ms > 0:
            pop_delays_ms.append(cum_ms + 120)
        cum_ms += int(d * 1000)

    if SFX_WHOOSH_PATH.exists() or (pop_delays_ms and SFX_POP_PATH.exists()):
        _mix_transition_sfx(output_video_path, durations, SFX_WHOOSH_PATH, pop_delays_ms=pop_delays_ms)

    # BGM 배경음악 자동 덕킹 + -14 LUFS 정규화 믹싱
    if DEFAULT_BGM_PATH and Path(DEFAULT_BGM_PATH).exists():
        print(f"🎵 [BGM 합성] 자동 덕킹 및 음량 정규화 믹싱 중: {Path(DEFAULT_BGM_PATH).name} (볼륨: {int(BGM_VOLUME * 100)}%)...")
        mix_bgm_to_video(output_video_path, DEFAULT_BGM_PATH, BGM_VOLUME)

    print(f"[비디오 완성] 쇼츠 영상 생성 성공: {output_video_path} (크기: {output_video_path.stat().st_size / (1024*1024):.2f} MB)")
    return output_video_path


if __name__ == "__main__":
    from modules.news_collector import collect_weekly_physical_therapy_news
    from modules.content_builder import build_content_package
    from modules.card_renderer import render_cards_to_images
    from modules.tts_synthesizer import synthesize_all_narration
    import asyncio

    print("[테스트] 9:16 쇼츠 비디오 전체 렌더링 테스트 시작...")
    test_dir = Path(__file__).resolve().parent.parent / "결과물" / "THEPT뉴스" / "test_full_run"
    news = collect_weekly_physical_therapy_news(min_news_count=3)
    pkg = build_content_package(news)

    cards = asyncio.run(render_cards_to_images(pkg, test_dir / "cards"))
    audios = asyncio.run(synthesize_all_narration(pkg, test_dir / "audio"))

    out_mp4 = test_dir / "shorts_test.mp4"
    res = render_shorts_video(cards, audios, out_mp4)
    print(f"[성공] 테스트 비디오 생성 완료: {res}")
