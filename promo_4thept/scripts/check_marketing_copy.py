#!/usr/bin/env python3
"""4THEPT · THEPT 통합 마케팅 카피 및 SNS 프리셋 컴플라이언스 검증 CLI.

실제 검증 엔진은 `modules/marketing_compliance.py`를 단일 진실 소스로 사용합니다.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

PROMO_DIR = Path(__file__).resolve().parents[1]
AUTO_ROOT = PROMO_DIR.parent
if str(AUTO_ROOT) not in sys.path:
    sys.path.insert(0, str(AUTO_ROOT))

from config import PROMO_OUTPUT_DIR  # noqa: E402
from modules.marketing_compliance import (  # noqa: E402
    ComplianceIssue,
    check_promo_compliance,
    collect_promo_targets,
)


def resolve_target_paths(raw_paths: list[str]) -> list[Path]:
    if not raw_paths:
        return collect_promo_targets(PROMO_DIR, PROMO_OUTPUT_DIR)
    resolved: list[Path] = []
    for raw in raw_paths:
        p = Path(raw)
        if not p.is_absolute():
            p = (Path.cwd() / p).resolve()
        if p.is_dir():
            resolved.extend(sorted(p.glob("*.md")))
        else:
            resolved.append(p)
    return resolved


def main() -> int:
    parser = argparse.ArgumentParser(description="4THEPT 마케팅 카피 및 SNS 프리셋 컴플라이언스 검증")
    parser.add_argument(
        "--track",
        choices=("all", "hospital", "center"),
        default="all",
        help="검증 트랙 (center 지정 시 의료 용어 혼입 추가 차단)",
    )
    parser.add_argument(
        "paths",
        nargs="*",
        help="검사할 파일 경로 (생략 시 sns_publisher.py, 플레이북, 캘린더, 결과물/4THEPT마케팅/drafts/*.md 자동 검사)",
    )
    args = parser.parse_args()

    targets = resolve_target_paths(args.paths)
    if not targets:
        print("[SKIP] 검사 대상 마케팅 파일이 없습니다.")
        return 0

    all_issues: list[ComplianceIssue] = []
    print(f"=== 4THEPT 마케팅 컴플라이언스 검증 (track={args.track}) ===")
    for path in targets:
        file_issues = check_promo_compliance([path], track=args.track, promo_dir=PROMO_DIR, promo_out_dir=PROMO_OUTPUT_DIR)
        if file_issues:
            all_issues.extend(file_issues)
            print(f"  [FAIL] {path.name} ({len(file_issues)}건)")
        else:
            print(f"  [OK]   {path.name}")

    if all_issues:
        print("\n[위반 내역]")
        for v in all_issues:
            print(f"  - {v.scope}:{v.line_no} [{v.rule}] -> {v.excerpt}")
        print(f"\n총 {len(all_issues)}건의 컴플라이언스 위반이 발견되었습니다.")
        return 1

    print("\n모든 마케팅 카피·프리셋 검증을 통과했습니다 (위반 0건).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
