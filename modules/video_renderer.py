# 이 모듈은 4:5 카드뉴스와 TTS 음성을 결합하여 9:16 세로형 쇼츠 MP4 비디오를 렌더링합니다.
# 블러 배경 레이어와 슬라이드별 정확한 오디오 싱크를 FFmpeg로 고속 합성합니다.

import sys
from pathlib import Path
import subprocess
import shutil

sys.path.append(str(Path(__file__).resolve().parent.parent))

from config import VIDEO_WIDTH, VIDEO_HEIGHT, CARD_WIDTH, CARD_HEIGHT


def render_slide_segment(image_path: Path, audio_path: Path, duration: float, output_segment: Path) -> Path:
    """단일 슬라이드 이미지와 오디오를 9:16 세그먼트 영상으로 렌더링합니다."""
    output_segment.parent.mkdir(parents=True, exist_ok=True)

    # 4:5 이미지를 중앙에 배치하고, 배경은 동일 이미지를 블러 처리하여 1080x1920으로 채우는 필터
    filter_complex = (
        f"[0:v]scale={VIDEO_WIDTH}:{VIDEO_HEIGHT}:force_original_aspect_ratio=increase,"
        f"crop={VIDEO_WIDTH}:{VIDEO_HEIGHT},boxblur=28:6,setsar=1[bg];"
        f"[0:v]scale={CARD_WIDTH}:{CARD_HEIGHT}[fg];"
        f"[bg][fg]overlay=(W-w)/2:(H-h)/2[v]"
    )

    cmd = [
        "ffmpeg", "-y",
        "-loop", "1",
        "-t", f"{duration:.3f}",
        "-i", str(image_path),
        "-i", str(audio_path),
        "-filter_complex", filter_complex,
        "-map", "[v]",
        "-map", "1:a",
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
        filter_complex = (
            f"[0:v]scale={VIDEO_WIDTH}:{VIDEO_HEIGHT}:force_original_aspect_ratio=increase,"
            f"crop={VIDEO_WIDTH}:{VIDEO_HEIGHT},boxblur=28:6,setsar=1[bg];"
            f"[0:v]scale={CARD_WIDTH}:{CARD_HEIGHT}[fg];"
            f"[bg][fg]overlay=(W-w)/2:(H-h)/2[v]"
        )
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

    # 최종 오디오 합성
    cmd_final = [
        "ffmpeg", "-y",
        "-i", str(merged_v),
        "-i", str(audio_path),
        "-c:v", "copy",
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


def render_shorts_video(card_image_paths: list[Path], audio_info_list: list[dict], output_video_path: Path) -> Path:
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

    print(f"[비디오 렌더] 총 {len(card_image_paths)}개 슬라이드 세그먼트 영상 렌더링 시작...")

    for i, (img_path, audio_info) in enumerate(zip(card_image_paths, audio_info_list)):
        dur = audio_info["duration"]
        aud_path = audio_info["audio_path"]
        seg_path = temp_segment_dir / f"seg_{i+1:02d}.mp4"

        render_slide_segment(img_path, aud_path, dur, seg_path)
        segment_paths.append(seg_path)
        print(f"[세그먼트 완료] 슬라이드 {i+1}/{len(card_image_paths)} ({dur:.2f}초): {seg_path.name}")

    # 모든 세그먼트 병합
    print(f"[비디오 병합] 완성형 쇼츠 비디오 병합 중: {output_video_path.name}...")
    concatenate_segments(segment_paths, output_video_path)

    # 임시 세그먼트 디렉토리 정리
    shutil.rmtree(temp_segment_dir, ignore_errors=True)

    print(f"[비디오 완성] 쇼츠 영상 생성 성공: {output_video_path} (크기: {output_video_path.stat().st_size / (1024*1024):.2f} MB)")
    return output_video_path


if __name__ == "__main__":
    from modules.news_collector import collect_weekly_physical_therapy_news
    from modules.content_builder import build_content_package
    from modules.card_renderer import render_cards_to_images
    from modules.tts_synthesizer import synthesize_all_narration
    import asyncio

    print("[테스트] 9:16 쇼츠 비디오 전체 렌더링 테스트 시작...")
    test_dir = Path(__file__).resolve().parent.parent / "output" / "test_full_run"
    news = collect_weekly_physical_therapy_news(min_news_count=3)
    pkg = build_content_package(news)

    cards = asyncio.run(render_cards_to_images(pkg, test_dir / "cards"))
    audios = asyncio.run(synthesize_all_narration(pkg, test_dir / "audio"))

    out_mp4 = test_dir / "shorts_test.mp4"
    res = render_shorts_video(cards, audios, out_mp4)
    print(f"[성공] 테스트 비디오 생성 완료: {res}")
