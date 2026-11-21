"""4THEPT · THEPT 통합 마케팅 컴플라이언스 & 쇼츠 품질 게이트 검증 모듈.

- 퇴출 직군(작업치료/언어치료/필라테스/물리재활/도수재활) 및 구 호칭(매니저/센터장/병원/의원) 탐지
- 의료법/SaMD 과장 표현(AI 자동 진단, EMR 완벽 대체, 식약처/의료기기 인증 등) 탐지
- 비의료 센터(center) 트랙 전용 의료 용어(환자/치료사/진단/처방 등) 격리 검증
- promo_4thept/scripts/sns_publisher.py PRESETS AST 검사 및 결과물/4THEPT마케팅/drafts 검수
- 생성된 뉴스 캡션·첫 댓글의 [초안] 보조 도구 고지, UTM 파라미터, 쇼츠 60초 초과 경고 검증
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from pathlib import Path

from config import (
    BASE_DIR,
    DEFAULT_AD_CONFIG,
    PROMO_OUTPUT_DIR,
    build_4thept_promo_footer,
    build_first_comment,
)

GLOBAL_BANNED_TERMS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("퇴출 직군/표현(작업치료·언어치료·필라테스·물리재활)", re.compile(r"작업치료|작업재활|언어치료|언어재활|도수필라테스|필라테스|물리재활|도수재활")),
    ("금지 기관 표기(병원/의원)", re.compile(r"병원/의원")),
    ("금지 구 호칭(매니저·센터장)", re.compile(r"매니저|센터장")),
)

SAMD_OVERCLAIM_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("SaMD 과장 의심(AI 자동 진단)", re.compile(r"AI\s*(?:가|의)?\s*(?:자동\s*)?진단(?!.*(?:하지\s*않|금지|않으며|아닙니다|아니며))")),
    ("과장 표현 의심(EMR 대체)", re.compile(r"(?:법정\s*)?EMR\s*(?:을|를)?\s*(?:완벽\s*|완전\s*)?대체(?!하(?:지\s*않|는\s*것.*금지))")),
    ("허위 인증 의심(식약처 인증/승인/허가)", re.compile(r"식약처\s*(?:인증|승인|허가)")),
    ("허위 인증 의심(의료기기 인증/승인/허가)", re.compile(r"의료기기\s*(?:인증|승인|허가|등록|소프트웨어)")),
    ("금지 표현 의심(질병명 추론)", re.compile(r"질병명\s*(?:자동\s*)?추론")),
)

CENTER_FORBIDDEN_MEDICAL_PATTERN = re.compile(
    r"환자|치료사|치료기록지|도수치료|진단명|진단평가|운동\s*처방|처방|병원|내원"
)
SAFE_BRAND_TOKEN_PATTERN = re.compile(
    r"https?://\S+|[\w.+-]+@[\w.-]+|\b(?:4thept|thept)\b",
    re.IGNORECASE,
)


@dataclass
class ComplianceIssue:
    scope: str
    severity: str  # "error" | "warning"
    rule: str
    excerpt: str
    line_no: int = 1


def check_text_lines(
    scope: str,
    text: str,
    track: str = "all",
    start_line: int = 1,
) -> list[ComplianceIssue]:
    """텍스트 문자열에 대해 금지 용어, SaMD 과장 표현 및 트랙별 용어 규칙을 검사합니다."""
    issues: list[ComplianceIssue] = []
    if not text:
        return issues

    for offset, raw_line in enumerate(text.splitlines()):
        line_no = start_line + offset
        clean = raw_line.strip()
        if not clean:
            continue

        for label, pat in GLOBAL_BANNED_TERMS:
            if pat.search(clean):
                issues.append(ComplianceIssue(scope, "error", label, clean[:100], line_no=line_no))

        for label, pat in SAMD_OVERCLAIM_PATTERNS:
            if pat.search(clean):
                issues.append(ComplianceIssue(scope, "error", label, clean[:100], line_no=line_no))

        if track == "center":
            scrubbed = SAFE_BRAND_TOKEN_PATTERN.sub("", clean)
            match = CENTER_FORBIDDEN_MEDICAL_PATTERN.search(scrubbed)
            if match:
                issues.append(
                    ComplianceIssue(
                        scope,
                        "error",
                        f"센터 트랙 의료 용어 금지({match.group(0)})",
                        clean[:100],
                        line_no=line_no,
                    )
                )

    return issues


def check_text_compliance(scope: str, text: str) -> list[ComplianceIssue]:
    """기존 뉴스 모듈 호환 래퍼 (track='all')."""
    return check_text_lines(scope, text, track="all", start_line=1)


def _extract_string_literals(node: ast.AST) -> list[tuple[int, str]]:
    found: list[tuple[int, str]] = []
    for child in ast.walk(node):
        if isinstance(child, ast.Constant) and isinstance(child.value, str):
            found.append((getattr(child, "lineno", 1), child.value))
    return found


def _node_references_name(node: ast.AST, target_name: str) -> bool:
    return any(isinstance(child, ast.Name) and child.id == target_name for child in ast.walk(node))


def check_sns_publisher_presets(publisher_path: Path, track: str = "all") -> list[ComplianceIssue]:
    """promo_4thept/scripts/sns_publisher.py 내 PRESETS 및 공유 고지문 상수를 AST로 검증합니다."""
    if not publisher_path.exists():
        return []
    try:
        rel_label = str(publisher_path.resolve().relative_to(BASE_DIR)).replace("\\", "/")
    except ValueError:
        rel_label = publisher_path.name

    source = publisher_path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(publisher_path))
    issues: list[ComplianceIssue] = []

    shared_footer_text = ""
    presets_dict_node: ast.Dict | None = None

    for stmt in tree.body:
        target_name: str | None = None
        value_node: ast.AST | None = None
        if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1 and isinstance(stmt.targets[0], ast.Name):
            target_name = stmt.targets[0].id
            value_node = stmt.value
        elif isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
            target_name = stmt.target.id
            value_node = stmt.value

        if target_name in (
            "SHARED_FOOTER_COMPLIANCE",
            "SHARED_CENTER_FOOTER_COMPLIANCE",
            "SHARED_FIRST_COMMENT",
            "SHARED_CENTER_FIRST_COMMENT",
        ) and value_node is not None:
            for lineno, text in _extract_string_literals(value_node):
                if target_name in ("SHARED_FOOTER_COMPLIANCE", "SHARED_CENTER_FOOTER_COMPLIANCE"):
                    shared_footer_text += text
                line_track = "center" if target_name.startswith("SHARED_CENTER_") else track
                issues.extend(check_text_lines(f"{rel_label}:{target_name}", text, line_track, start_line=lineno))

        if target_name == "PRESETS" and isinstance(value_node, ast.Dict):
            presets_dict_node = value_node

    if "초안" not in shared_footer_text or ("검수" not in shared_footer_text and "보조" not in shared_footer_text):
        issues.append(
            ComplianceIssue(
                rel_label,
                "error",
                "SHARED_FOOTER_COMPLIANCE에 '[초안]' 및 '검수/보조' 고지 누락",
                shared_footer_text[:100],
                line_no=1,
            )
        )

    if presets_dict_node is None:
        issues.append(ComplianceIssue(rel_label, "error", "PRESETS 딕셔너리를 찾을 수 없음", "PRESETS", line_no=1))
        return issues

    for key_node, val_node in zip(presets_dict_node.keys, presets_dict_node.values):
        preset_key = key_node.value if isinstance(key_node, ast.Constant) else "unknown"
        if not isinstance(val_node, ast.Call):
            continue

        caption_node: ast.AST | None = None
        for kw in val_node.keywords:
            if kw.arg == "caption":
                caption_node = kw.value
                break

        if caption_node is None:
            issues.append(
                ComplianceIssue(f"{rel_label}[{preset_key}]", "error", "caption 누락", str(preset_key), line_no=val_node.lineno)
            )
        else:
            caption_literals = "".join(t for _, t in _extract_string_literals(caption_node))
            has_shared = (
                _node_references_name(caption_node, "SHARED_FOOTER_COMPLIANCE")
                or _node_references_name(caption_node, "SHARED_CENTER_FOOTER_COMPLIANCE")
            )
            has_inline_disclaimer = "초안" in caption_literals and ("검수" in caption_literals or "보조" in caption_literals)
            if not (has_shared or has_inline_disclaimer):
                issues.append(
                    ComplianceIssue(
                        f"{rel_label}[{preset_key}]",
                        "error",
                        "캡션 내 보조 도구 [초안]/검수 고지 누락",
                        caption_literals[:80],
                        line_no=getattr(caption_node, "lineno", val_node.lineno),
                    )
                )

        preset_track = (
            "center"
            if ("center" in str(preset_key).lower() or _node_references_name(val_node, "SHARED_CENTER_FOOTER_COMPLIANCE"))
            else track
        )
        for lineno, text in _extract_string_literals(val_node):
            issues.extend(check_text_lines(f"{rel_label}[{preset_key}]", text, preset_track, start_line=lineno))

    return issues


def collect_promo_targets(promo_dir: Path | None = None, promo_out_dir: Path | None = None) -> list[Path]:
    """4THEPT 마케팅 검사 대상 기본 파일 목록을 수집합니다."""
    p_dir = promo_dir or (BASE_DIR / "promo_4thept")
    out_dir = promo_out_dir or PROMO_OUTPUT_DIR
    candidates = [
        p_dir / "scripts" / "sns_publisher.py",
        p_dir / "pt_marketing_playbook.md",
        p_dir / "campaigns" / "content_calendar.md",
    ]
    for d_dir in (out_dir / "drafts", p_dir / "campaigns" / "drafts"):
        if d_dir.exists():
            candidates.extend(sorted(d_dir.glob("*.md")))

    seen: set[Path] = set()
    targets: list[Path] = []
    for p in candidates:
        rp = p.resolve()
        if p.exists() and rp not in seen:
            seen.add(rp)
            targets.append(p)
    return targets


def check_promo_compliance(
    targets: list[Path] | None = None,
    track: str = "all",
    promo_dir: Path | None = None,
    promo_out_dir: Path | None = None,
) -> list[ComplianceIssue]:
    """4THEPT 홍보 프리셋, 플레이북, 캘린더, 결과물/4THEPT마케팅/drafts 초안을 통합 검사합니다."""
    p_dir = promo_dir or (BASE_DIR / "promo_4thept")
    publisher_file = (p_dir / "scripts" / "sns_publisher.py").resolve()
    files = targets if targets is not None else collect_promo_targets(p_dir, promo_out_dir)

    issues: list[ComplianceIssue] = []
    for path in files:
        if not path.exists():
            issues.append(ComplianceIssue(str(path), "error", "대상 파일 없음", str(path), line_no=1))
            continue
        rp = path.resolve()
        if rp == publisher_file:
            issues.extend(check_sns_publisher_presets(rp, track=track))
        else:
            try:
                rel_label = str(rp.relative_to(BASE_DIR)).replace("\\", "/")
            except ValueError:
                rel_label = str(rp).replace("\\", "/")
            file_track = track
            if track == "all" and "_center_" in path.name.lower():
                file_track = "center"
            issues.extend(check_text_lines(rel_label, rp.read_text(encoding="utf-8"), track=file_track))
    return issues


def check_config_compliance() -> list[ComplianceIssue]:
    """config.py 기본 광고 슬라이드·푸터·첫 댓글의 컴플라이언스를 검증합니다."""
    issues: list[ComplianceIssue] = []
    ad_blob = "\n".join([
        DEFAULT_AD_CONFIG.get("title", ""),
        DEFAULT_AD_CONFIG.get("sub_badge", ""),
        DEFAULT_AD_CONFIG.get("cta_text", ""),
        DEFAULT_AD_CONFIG.get("narration", ""),
        *[
            f"{c.get('name', '')} {' '.join(c.get('bullets', []))}"
            for c in DEFAULT_AD_CONFIG.get("categories", [])
        ],
    ])
    issues.extend(check_text_compliance("config.DEFAULT_AD_CONFIG", ad_blob))

    footer = build_4thept_promo_footer("ig", "carousel", "weekly_briefing")
    issues.extend(check_text_compliance("config.promo_footer", footer))
    if "초안" not in footer or ("검수" not in footer and "보조" not in footer):
        issues.append(ComplianceIssue("config.promo_footer", "error", "보조 도구 [초안]/검수 고지 누락", footer[:100]))
    if "utm_source=" not in footer:
        issues.append(ComplianceIssue("config.promo_footer", "error", "표준 UTM 파라미터 누락", footer[:100]))

    fc = build_first_comment("ig", "carousel", "weekly_briefing")
    issues.extend(check_text_compliance("config.first_comment", fc))
    if "초안" not in fc or ("검수" not in fc and "보조" not in fc):
        issues.append(ComplianceIssue("config.first_comment", "error", "첫 댓글 [초안]/검수 고지 누락", fc[:100]))
    if "utm_source=" not in fc:
        issues.append(ComplianceIssue("config.first_comment", "error", "첫 댓글 표준 UTM 누락", fc[:100]))

    return issues


def check_package_compliance(
    pkg: dict,
    ig_caption: str = "",
    yt_caption: str = "",
    first_comment: str = "",
) -> dict:
    """
    일별 생성 패키지(슬라이드 대본·광고·캡션·첫 댓글)에 대해
    컴플라이언스 위반 및 쇼츠 품질 게이트(60초 초과 경고, UTM, 고지문)를 점검합니다.
    """
    issues: list[ComplianceIssue] = []
    slides = pkg.get("slides", [])
    total_narration_chars = 0

    for idx, slide in enumerate(slides, 1):
        stype = slide.get("type", "unknown")
        narr = (slide.get("narration") or "").strip()
        total_narration_chars += len(re.sub(r"\s+", "", narr))
        if stype in ("cover", "ad", "outro"):
            issues.extend(check_text_compliance(f"slide_{idx}_{stype}.narration", narr))

        if stype == "ad":
            sdata = slide.get("data", {})
            ad_text = " ".join([
                str(sdata.get("title", "")),
                str(sdata.get("sub_badge", "")),
                str(sdata.get("cta_text", "")),
                *[
                    f"{c.get('name', '')} {' '.join(c.get('bullets', []))}"
                    for c in sdata.get("categories", [])
                ],
            ])
            issues.extend(check_text_compliance("slide_ad.data", ad_text))

    for scope, txt in (
        ("instagram_caption", ig_caption),
        ("youtube_shorts_caption", yt_caption),
        ("first_comment", first_comment),
    ):
        if not txt:
            continue
        footer_part = txt.split("━━━━━━━━━━━━━━━━━━━━━━━━━━━━")[-1] if "━━━━━━━━━━━━━━━━━━━━━━━━━━━━" in txt else txt
        issues.extend(check_text_compliance(scope, footer_part))
        if "초안" not in txt or ("검수" not in txt and "보조" not in txt):
            issues.append(ComplianceIssue(scope, "warning", "보조 도구 [초안]/직접 검수 고지 누락", txt[:80]))
        if "utm_source=" not in txt:
            issues.append(ComplianceIssue(scope, "warning", "표준 UTM 추적 링크 누락", txt[:80]))

    est_seconds = round(total_narration_chars / 6.3, 1) if total_narration_chars else 0.0
    if est_seconds > 60.0:
        issues.append(
            ComplianceIssue(
                "shorts_duration",
                "warning",
                f"쇼츠 예상 길이 60초 초과 ({est_seconds:.1f}초 / 공백제외 {total_narration_chars}자)",
                "나레이션 분량 축소 권장",
            )
        )

    errors = [i for i in issues if i.severity == "error"]
    warnings = [i for i in issues if i.severity == "warning"]
    return {
        "passed": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "estimated_seconds": est_seconds,
        "narration_chars": total_narration_chars,
    }
