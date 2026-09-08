# 이 모듈은 주간 큐레이션 결과물을 GitHub 원격 저장소와 안전하게 동기화하고,
# 최근 4주치(1달치) 미디어만 활성 유지하여 저장소 용량을 150MB 이하로 슬림하게 관리합니다.

import sys
import subprocess
import re
from pathlib import Path
from typing import List, Optional

sys.path.append(str(Path(__file__).resolve().parent.parent))
from config import BASE_DIR, GITHUB_BRANCH


def find_all_weekly_dirs(output_dir: Optional[Path] = None) -> List[Path]:
    """output/ 디렉토리 내의 모든 주간 디렉토리를 날짜 내림차순(최신순)으로 반환합니다."""
    out_dir = output_dir or (BASE_DIR / "output")
    if not out_dir.exists():
        return []

    weekly_dirs = [
        d for d in out_dir.iterdir()
        if d.is_dir() and re.match(r"^\d{4}-\d{2}-\d{2}_curated_weekly$", d.name)
    ]
    # 날짜 내림차순 정렬 (최신 주차가 인덱스 0)
    weekly_dirs.sort(key=lambda x: x.name, reverse=True)
    return weekly_dirs


def apply_4week_retention(output_dir: Optional[Path] = None, retain_weeks: int = 4, dry_run: bool = False) -> List[str]:
    """
    최근 retain_weeks(기본 4주)를 초과한 과거 주간 폴더의 대용량 미디어 파일(*.mp4, *.png, *.mp3)을
    Git 추적에서만 해제(git rm --cached)하여 GitHub 저장소 용량을 150MB 이하로 유지합니다.
    (※ 사용자의 로컬 PC 원본 파일은 절대 삭제되지 않고 온전히 보존됩니다.)
    """
    weekly_dirs = find_all_weekly_dirs(output_dir)
    cleaned_items = []

    if len(weekly_dirs) <= retain_weeks:
        print(f"ℹ️ [보관 정책] 현재 주간 폴더 총 {len(weekly_dirs)}개 (기준 {retain_weeks}주 이내) -> 정리 대상 없음")
        return cleaned_items

    # 4주를 초과한 오래된 폴더들
    old_dirs = weekly_dirs[retain_weeks:]
    print(f"\n📦 [4주 롤링 보관] 4주가 경과한 과거 {len(old_dirs)}개 주간 폴더의 Git 미디어 슬림화를 점검합니다...")

    for old_dir in old_dirs:
        rel_dir = old_dir.relative_to(BASE_DIR)
        print(f"   • 과거 주차 점검: {old_dir.name}")
        
        # Git에서 추적 중인 미디어 파일만 해제
        media_patterns = [
            f"{rel_dir}/**/*.mp4",
            f"{rel_dir}/**/*.png",
            f"{rel_dir}/**/*.mp3"
        ]
        for pat in media_patterns:
            cmd = ["git", "rm", "-r", "--cached", "--ignore-unmatch", pat]
            if dry_run:
                print(f"     [DRY-RUN] 실행 예정: {' '.join(cmd)}")
                cleaned_items.append(pat)
            else:
                try:
                    res = subprocess.run(cmd, cwd=str(BASE_DIR), capture_output=True, text=True, check=False)
                    if res.stdout.strip():
                        cleaned_items.append(pat)
                        print(f"     ✅ Git 인덱스 정리 완료: {pat}")
                except Exception as e:
                    print(f"     ⚠️ Git 인덱스 정리 실패 ({pat}): {e}")

    return cleaned_items


def sync_weekly_output_to_github(
    weekly_dir: Optional[Path] = None,
    commit_msg: Optional[str] = None,
    retain_weeks: int = 4,
    dry_run: bool = False
) -> bool:
    """
    지정된 주간 폴더를 Git에 추가(git add)하고, 4주 롤링 보관을 적용한 뒤 커밋 및 푸시합니다.
    """
    target_dir = weekly_dir or (BASE_DIR / "output")
    rel_path = target_dir.relative_to(BASE_DIR) if target_dir.is_relative_to(BASE_DIR) else target_dir

    print("\n" + "=" * 70)
    mode_str = "🧪 [시뮬레이션 모드 (DRY-RUN)]" if dry_run else "🚀 [실제 GitHub 동기화]"
    print(f"{mode_str} 주간 콘텐츠 GitHub 동기화 및 스마트 보관을 시작합니다.")
    print(f"👉 대상 폴더: {rel_path}")
    print("=" * 70)

    # 1. 4주 롤링 보관 정책 적용
    apply_4week_retention(retain_weeks=retain_weeks, dry_run=dry_run)

    # 2. git add
    add_cmd = ["git", "add", str(rel_path)]
    print(f"\n📂 [Git Add] '{rel_path}' 스테이징 영역에 추가 중...")
    if dry_run:
        print(f"   [DRY-RUN] 실행 예정: {' '.join(add_cmd)}")
    else:
        try:
            subprocess.run(add_cmd, cwd=str(BASE_DIR), check=True)
            print("   ✅ 스테이징 추가 완료")
        except Exception as e:
            print(f"   ❌ Git add 실패: {e}")
            return False

    # 3. 변경 사항 확인
    status_cmd = ["git", "status", "--porcelain"]
    status_res = subprocess.run(status_cmd, cwd=str(BASE_DIR), capture_output=True, text=True)
    if not status_res.stdout.strip():
        print("ℹ️ [알림] GitHub에 반영할 새로운 변경 사항이 없습니다. (이미 최신 상태)")
        return True

    # 4. git commit
    default_msg = f"feat: 주간 콘텐츠 패키지 동기화 및 4주 롤링 슬림화 ({target_dir.name})"
    msg = commit_msg or default_msg
    commit_cmd = ["git", "commit", "-m", msg]
    print(f"\n📝 [Git Commit] 커밋 생성: \"{msg}\"")
    if dry_run:
        print(f"   [DRY-RUN] 실행 예정: {' '.join(commit_cmd)}")
    else:
        try:
            res_c = subprocess.run(commit_cmd, cwd=str(BASE_DIR), capture_output=True, text=True, check=True)
            print("   ✅ 커밋 완료")
        except Exception as e:
            print(f"   ❌ Git commit 실패: {e}")
            return False

    # 5. git push
    push_cmd = ["git", "push", "origin", GITHUB_BRANCH]
    print(f"\n🚀 [Git Push] GitHub 원격 저장소({GITHUB_BRANCH})로 전송 중...")
    if dry_run:
        print(f"   [DRY-RUN] 실행 예정: {' '.join(push_cmd)}")
        return True
    else:
        try:
            subprocess.run(push_cmd, cwd=str(BASE_DIR), check=True)
            print("   🎉 [성공] GitHub 원격 저장소에 완벽하게 반영되었습니다!")
            return True
        except Exception as e:
            print(f"   ❌ Git push 실패: {e}")
            print("   (네트워크 상태나 GitHub 접근 권한을 확인해주세요.)")
            return False
