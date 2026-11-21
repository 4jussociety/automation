#!/usr/bin/env python3
"""자동화에이전트 Antigravity PreToolUse 안전 가드 훅.

- run_command:
  * curate.py build --render 및 4THEPT 카드뉴스·쇼츠 렌더링 스크립트 감지 시 명시적 렌더링 승인(force_ask)
  * curate.py upload (--dry-run 미포함) 및 sns_publisher.py --publish 감지 시 사용자 확인(force_ask)
  * git push --force / git reset --hard / git clean -fd 파괴적 명령 확인(force_ask)
- edit_file / write_file:
  * 소스·템플릿 내 API 키 및 액세스 토큰 하드코딩 차단(deny)
- 예외 발생 시 fail-open({"decision": "allow"})을 보장합니다.
"""

from __future__ import annotations

import json
import os
import re
import sys

DESTRUCTIVE_CMD_PATTERNS = [
    ("git 강제 푸시(push --force / -f)", re.compile(r"\bgit\s+push\b[^\n]*(?:--force(?!-with-lease)\b|\s-f\b)", re.IGNORECASE)),
    ("git 작업트리 초기화(reset --hard)", re.compile(r"\bgit\s+reset\s+--hard\b", re.IGNORECASE)),
    ("git 미추적 파일 강제 삭제(clean -fd)", re.compile(r"\bgit\s+clean\b[^\n]*\s-[a-z]*f", re.IGNORECASE)),
]

RENDER_CMD_PATTERN = re.compile(
    r"(?:curate\.py\b[^\n]*\bbuild\b[^\n]*--render\b|export_card_news_pngs\.py\b|build_real_promo_shorts\.py\b|build_cinematic_short_v2\.py\b)",
    re.IGNORECASE,
)
UPLOAD_CMD_PATTERN = re.compile(r"curate\.py\b[^\n]*\bupload\b", re.IGNORECASE)
PROMO_PUBLISH_PATTERN = re.compile(
    r"(?:sns_publisher\.py\b[^\n]*--publish\b|--publish\b[^\n]*sns_publisher\.py\b)",
    re.IGNORECASE,
)
DRY_RUN_PATTERN = re.compile(r"(?:^|\s)--dry-run(?:\s|$)", re.IGNORECASE)
FORCE_LOCAL_PATTERN = re.compile(r"(?:^|\s)--force-local(?:\s|$)", re.IGNORECASE)

SECRET_PATTERNS = [
    ("OpenAI API Key(sk-proj-)", re.compile(r"\bsk-proj-[A-Za-z0-9_-]{16,}")),
    ("Google API Key(AIzaSy)", re.compile(r"\bAIzaSy[A-Za-z0-9_-]{20,}")),
    ("Meta Access Token(EAA...)", re.compile(r"\bEAA[A-Za-z0-9]{24,}")),
]


def emit(decision: str, reason: str | None = None) -> int:
    payload: dict[str, str] = {"decision": decision}
    if reason:
        payload["reason"] = reason
    sys.stdout.write(json.dumps(payload, ensure_ascii=False))
    sys.stdout.flush()
    return 0


def check_run_command(args: dict) -> tuple[str, str | None]:
    cmd = str(args.get("CommandLine") or args.get("commandLine") or "")

    for label, pattern in DESTRUCTIVE_CMD_PATTERNS:
        if pattern.search(cmd):
            return (
                "force_ask",
                f"[Automation Guard] 파괴적 명령({label})이 감지되었습니다. 실행 전 사용자 확인이 필요합니다.",
            )

    for segment in re.split(r"[;&|\n]+", cmd):
        if UPLOAD_CMD_PATTERN.search(segment) and not DRY_RUN_PATTERN.search(segment):
            return (
                "force_ask",
                "[Automation Guard] 실제 SNS 발행(curate.py upload) 명령이 감지되었습니다. "
                "대상 날짜/플랫폼 확인 및 사용자 승인 후 진행하세요.",
            )

        if PROMO_PUBLISH_PATTERN.search(segment) and not DRY_RUN_PATTERN.search(segment):
            return (
                "force_ask",
                "[4THEPT Marketing Guard] 실제 SNS(YouTube/Instagram) 업로드(--publish) 명령이 감지되었습니다. "
                "DRY-RUN 검증 및 사용자 최종 승인 후 실행하세요.",
            )

        if RENDER_CMD_PATTERN.search(segment):
            return (
                "force_ask",
                "[Automation Rendering Guard] 카드뉴스·쇼츠 렌더링(--render) 명령이 감지되었습니다. "
                "사용자가 명시적으로 렌더링을 요청한 경우에만 승인하세요.",
            )

    return ("allow", None)


def check_file_write(tool_name: str, args: dict) -> tuple[str, str | None]:
    raw_path = str(args.get("Path") or args.get("path") or "")
    norm_path = raw_path.replace("\\", "/").lower()
    if norm_path.endswith(".env") or "/docs/devlogs/" in norm_path:
        return ("allow", None)

    if not norm_path.endswith((".py", ".html", ".yml", ".yaml", ".json", ".md")):
        return ("allow", None)

    text = str((args.get("Replacement") if tool_name == "edit_file" else args.get("Content")) or "")
    if not text:
        return ("allow", None)

    for idx, line in enumerate(text.splitlines(), 1):
        for label, pat in SECRET_PATTERNS:
            if pat.search(line):
                return (
                    "deny",
                    f"[Automation Guard] 파일({norm_path}, +{idx}행)에 시크릿 노출 의심({label})이 차단되었습니다.",
                )

    return ("allow", None)


def main() -> int:
    try:
        if hasattr(sys.stdin, "reconfigure"):
            sys.stdin.reconfigure(encoding="utf-8")
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8")

        raw = sys.stdin.read()
        if not raw.strip():
            return emit("allow")

        data = json.loads(raw)
        tool_call = data.get("toolCall") or {}
        tool_name = str(tool_call.get("name") or "")
        args = tool_call.get("args") or {}

        if tool_name == "run_command":
            decision, reason = check_run_command(args)
            return emit(decision, reason)
        if tool_name in ("edit_file", "write_file"):
            decision, reason = check_file_write(tool_name, args)
            return emit(decision, reason)

        return emit("allow")
    except Exception:
        return emit("allow")


if __name__ == "__main__":
    raise SystemExit(main())
