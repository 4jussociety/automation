# 배경 이미지에만 독립적인 시네마틱 모션을 적용하고 고정된 텍스트 카드를 오버레이하여 쇼츠 비디오(MP4)를 생성하는 모듈입니다.
# 글씨 흔들림 방지 레이어드 합성(Layered Composition) 및 오디오 0.01초 정밀 싱크 렌더링을 제공합니다.

import os
import sys
import subprocess
import shutil
from pathlib import Path
from typing import List

def get_audio_duration(audio_path: Path) -> float:
    """ffprobe를 사용하여 오디오 파일의 정확한 재생 시간(초)을 측정합니다."""
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(audio_path)
    ]
    try:
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True, encoding='utf-8', errors='replace')
        return float(result.stdout.strip())
    except Exception as e:
        print(f"  [경고] 오디오 길이 측정 실패 ({e}), 기본값 45.0초 사용")
        return 45.0

def calculate_slide_durations(total_duration: float, num_slides: int) -> List[float]:
    """오디오 전체 길이에 맞춰 6컷 슬라이드의 최적 재생 시간을 배분합니다."""
    if num_slides == 6:
        # 표지 10%, 뉴스1 24%, 뉴스2 24%, 뉴스3 22%, 인사이트 11%, 아웃트로 9%
        ratios = [0.10, 0.24, 0.24, 0.22, 0.11, 0.09]
    else:
        ratios = [1.0 / num_slides] * num_slides

    durations = [round(total_duration * r, 2) for r in ratios]
    durations[-1] = round(total_duration - sum(durations[:-1]), 2)
    return durations

def safe_ffmpeg_path(p: Path) -> str:
    """Windows 환경에서 FFmpeg 경로 인코딩 및 호환성을 보장하는 안전한 상대 경로 변환"""
    try:
        return os.path.relpath(p, start=Path.cwd())
    except Exception:
        return str(p.resolve()).replace("\\", "/")

def get_bg_motion_filter(idx: int, duration_frames: int) -> str:
    """순수 배경 이미지에만 적용할 역동적인 줌/팬 모션 필터를 생성합니다.
    2배 슈퍼샘플링(2160x3840) 및 Lanczos 다운스케일링으로 미세 떨림(지터)을 완전히 박멸하고,
    슬라이드별로 다채로운 시네마틱 카메라 워크와 시원한 속도감을 구현합니다."""
    df = max(duration_frames, 30)
    max_f = max(df - 1, 1)
    
    # 텍스트 가독성을 높이기 위한 다크 톤(어두움 14%, 대비 1.1) 보정
    darken = "eq=brightness=-0.14:contrast=1.1"

    # 슬라이드 인덱스 기반 6종 다채로운 모션 프리셋
    motion_type = (idx - 1) % 6

    if motion_type == 0:
        # 1. 다이내믹 센터 파워 줌인 (1.0 -> 1.30, 시선 집중)
        z_expr = f"1.0+0.30*(on/{max_f})"
        x_expr = "iw/2-(iw/zoom/2)"
        y_expr = "ih/2-(ih/zoom/2)"
    elif motion_type == 1:
        # 2. 좌측 -> 우측 시원한 가로 패닝 (줌 1.25 상태에서 좌에서 우로 스와이프)
        z_expr = "1.25"
        x_expr = f"(iw-iw/zoom)*(on/{max_f})"
        y_expr = "ih/2-(ih/zoom/2)"
    elif motion_type == 2:
        # 3. 다이내믹 줌아웃 (1.30 -> 1.05, 전체 구도를 시원하게 확장)
        z_expr = f"1.30-0.25*(on/{max_f})"
        x_expr = "iw/2-(iw/zoom/2)"
        y_expr = "ih/2-(ih/zoom/2)"
    elif motion_type == 3:
        # 4. 우측 -> 좌측 시원한 가로 패닝 (줌 1.25 상태에서 우에서 좌로 스와이프)
        z_expr = "1.25"
        x_expr = f"(iw-iw/zoom)*(1-on/{max_f})"
        y_expr = "ih/2-(ih/zoom/2)"
    elif motion_type == 4:
        # 5. 대각선 시네마틱 무브먼트 (줌 1.25, 좌하단 -> 우상단 이동)
        z_expr = "1.25"
        x_expr = f"(iw-iw/zoom)*(on/{max_f})"
        y_expr = f"(ih-ih/zoom)*(1-on/{max_f})"
    else:
        # 6. 수직 틸트 다운 (줌 1.22, 상단 -> 하단으로 부드러운 하향 틸트)
        z_expr = "1.22"
        x_expr = "iw/2-(iw/zoom/2)"
        y_expr = f"(ih-ih/zoom)*(on/{max_f})"

    # 2배 슈퍼샘플링 버퍼(2160x3840)에서 모션을 연산하고 Lanczos로 1080x1920으로 축소하여 정수 지터 완벽 제거
    return (
        f"scale=2160:3840:force_original_aspect_ratio=increase,crop=2160:3840,{darken},"
        f"zoompan=z='{z_expr}':d={df}:x='{x_expr}':y='{y_expr}':s=2160x3840:fps=30,"
        f"scale=1080:1920:flags=lanczos"
    )

def render_shorts_video(bg_images: List[Path], fg_images: List[Path], audio_path: Path, output_video_path: Path, fps: int = 30) -> Path:
    """배경 이미지에만 모션을 적용하고 고정된 투명 텍스트 카드를 오버레이하여 글씨 흔들림 없는 쇼츠 비디오를 완성합니다."""
    output_video_path.parent.mkdir(parents=True, exist_ok=True)
    temp_dir = output_video_path.parent / "_temp_segments"
    temp_dir.mkdir(parents=True, exist_ok=True)

    total_duration = get_audio_duration(audio_path)
    durations = calculate_slide_durations(total_duration, len(bg_images))

    segment_files = []
    print(f"  [레이어드 비디오 렌더러] 총 {total_duration:.1f}초 분량의 무지터 다이내믹 모션 세그먼트 생성 중...")

    try:
        # 1. 컷별 레이어 합성 세그먼트 렌더링 (temp_dir 내부에서 안전한 파일명으로 격리 실행)
        for i, (bg_img, fg_img, dur) in enumerate(zip(bg_images, fg_images, durations), start=1):
            seg_out = temp_dir / f"seg_{i:02d}.mp4"
            duration_frames = int(dur * fps)
            bg_filter = get_bg_motion_filter(i, duration_frames)

            # 한글 경로 인코딩 문제 방지를 위해 temp_dir에 순수 파일명으로 복사
            temp_bg = temp_dir / f"in_bg_{i:02d}{bg_img.suffix}"
            temp_fg = temp_dir / f"in_fg_{i:02d}{fg_img.suffix}"
            shutil.copy2(bg_img, temp_bg)
            shutil.copy2(fg_img, temp_fg)

            # 복합 필터그래프: [0:v] 단일 배경 이미지 모션 렌더링 -> [bg]; [bg][1:v] 투명 텍스트 카드 오버레이
            filter_complex = f"[0:v]{bg_filter}[bg]; [1:v]scale=1080:1920[fg]; [bg][fg]overlay=0:0:format=auto[v]"

            cmd = [
                "ffmpeg", "-y",
                "-i", temp_bg.name,
                "-loop", "1", "-i", temp_fg.name,
                "-filter_complex", filter_complex,
                "-map", "[v]",
                "-c:v", "libx264",
                "-crf", "18",
                "-preset", "veryfast",
                "-t", str(dur),
                "-pix_fmt", "yuv420p",
                "-r", str(fps),
                seg_out.name
            ]
            subprocess.run(cmd, cwd=str(temp_dir), stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True, encoding='utf-8', errors='replace')
            segment_files.append(seg_out)

        # 2. 세그먼트 Concat 리스트 작성 (순수 파일명 기록)
        concat_list_path = temp_dir / "concat_list.txt"
        with open(concat_list_path, "w", encoding="utf-8") as f:
            for seg in segment_files:
                f.write(f"file '{seg.name}'\n")

        # 3. 비디오 합체 및 오디오 트랙 결합 (temp_dir 내부 실행)
        print(f"  [레이어드 비디오 렌더러] 오디오 트랙 싱크 합성 및 최종 MP4 인코딩 중...")
        temp_audio = temp_dir / audio_path.name
        shutil.copy2(audio_path, temp_audio)
        temp_final = temp_dir / "final_shorts.mp4"

        merge_cmd = [
            "ffmpeg", "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", "concat_list.txt",
            "-i", audio_path.name,
            "-c:v", "copy",
            "-c:a", "aac",
            "-b:a", "192k",
            "-shortest",
            "final_shorts.mp4"
        ]
        subprocess.run(merge_cmd, cwd=str(temp_dir), stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True, encoding='utf-8', errors='replace')

        # 생성된 최종 영상을 목표 위치로 이동
        if temp_final.exists():
            if output_video_path.exists():
                output_video_path.unlink()
            shutil.move(str(temp_final), str(output_video_path))

        print(f"  [완전 무결 쇼츠 완성] {output_video_path.name} ({total_duration:.1f}초, 1080x1920)")

    finally:
        # 임시 디렉터리 정리
        if temp_dir.exists():
            shutil.rmtree(temp_dir, ignore_errors=True)

    return output_video_path
