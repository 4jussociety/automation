# 이 모듈은 2단계 마크다운 큐레이션 워크플로우(제목 스크리닝 -> 본문 검토 및 선택 이유 작성)를 총괄합니다.
# 후보 마크다운 생성, 체크박스 파싱, 직접 기사 추가 처리 및 선택 이유 데이터셋 누적을 담당합니다.

import os
import re
import json
from pathlib import Path
from datetime import datetime
import urllib.parse

from modules.news_collector import SIX_CATEGORIES, parse_custom_url

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
CACHE_FILE = DATA_DIR / "candidates_cache.json"
HISTORY_FILE = DATA_DIR / "curation_history.jsonl"


def save_candidates_cache(candidates: dict, cache_file: Path = CACHE_FILE):
    """수집된 후보군 원본 데이터를 로컬 JSON 캐시에 저장합니다."""
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    with open(cache_file, "w", encoding="utf-8") as f:
        json.dump(candidates, f, ensure_ascii=False, indent=2)


def load_candidates_cache(cache_file: Path = CACHE_FILE) -> dict:
    """로컬 JSON 캐시에서 후보군 데이터를 로드합니다."""
    if not cache_file.exists():
        return {}
    with open(cache_file, "r", encoding="utf-8") as f:
        return json.load(f)


def generate_candidates_titles_markdown(candidates: dict, output_path: Path) -> Path:
    """
    1단계: 수집된 6대 카테고리 기사(최대 100건)의 제목 목록과 직접 기사 추가 섹션이 포함된 마크다운을 생성합니다.
    """
    now = datetime.now()
    created_at_str = f"{now.year}년 {now.month:02d}월 {now.day:02d}일 {now.hour:02d}:{now.minute:02d} (한국 기준시)"
    lines = [
        "# 📋 주간 6대 카테고리 후보 기사 목록 (1단계: 제목 스크리닝)",
        "",
        "> **안내사항**:",
        "> 1. 관심 가는 기사 앞의 `[ ]`를 `[x]`로 변경하세요. (요일당 3~5개 정도 넉넉히 체크 권장)",
        "> 2. 저장이 끝나면 터미널에서 `python curate.py review` 명령을 실행하세요.",
        "> 3. 후보 기사가 부족하거나 따로 다룰 기사가 있다면 맨 아래 **[✍️ 직접 기사 추가]** 섹션에 URL을 적어주세요.",
        "",
        f"- 생성 일시: {created_at_str}",
        f"- 수집된 총 후보 수: {candidates.get('total_count', 0)}건",
        ""
    ]

    for cat_key, meta in SIX_CATEGORIES.items():
        day_name = meta["day"]
        cat_title = meta["title"]
        cat_desc = meta["description"]
        articles = candidates.get(cat_key, [])

        lines.append(f"## 📅 {day_name}: {cat_title} ({len(articles)}건)")
        lines.append(f"> *{cat_desc}*")
        lines.append("")

        if not articles:
            lines.append("- (수집된 기사가 없습니다. 직접 기사 추가 란에 URL을 등록해주세요.)")
            lines.append("")
            continue

        for art in articles:
            art_id = art.get("id", "")
            title = art.get("title", "").replace("[", "(").replace("]", ")")
            link = art.get("link", "#")
            source = art.get("source", "뉴스")
            pub_date = art.get("pub_date", "")

            lines.append(f"- [ ] [{art_id}] [{title}]({link}) - {source} ({pub_date})")

        lines.append("")

    # 사용자 직접 기사 추가 섹션
    lines.extend([
        "---",
        "",
        "## ✍️ 직접 기사 추가 (User Manual Input)",
        "> 수집된 기사 외에 추가로 다루고 싶은 기사 URL이나 메모가 있다면 아래에 `- [x] [요일] URL` 형식으로 추가하세요.",
        "> (예시: `- [x] [월] https://n.news.naver.com/...`)",
        "",
        "- [ ] [월] ",
        "- [ ] [화] ",
        "- [ ] [수] ",
        "- [ ] [목] ",
        "- [ ] [금] ",
        "- [ ] [토] ",
        ""
    ])

    output_path.write_text("\n".join(lines), encoding="utf-8")
    return output_path


def parse_candidates_titles_markdown(titles_path: Path, cache_file: Path = CACHE_FILE) -> dict[str, list[dict]]:
    """
    1단계 마크다운에서 `[x]`로 체크된 기사 및 직접 추가된 기사 URL을 파싱하여 반환합니다.
    """
    if not titles_path.exists():
        raise FileNotFoundError(f"제목 목록 파일이 존재하지 않습니다: {titles_path}")

    content = titles_path.read_text(encoding="utf-8")
    cached = load_candidates_cache(cache_file)

    # 1. 캐시된 기사 빠른 조회를 위한 ID 맵 생성
    id_map = {}
    for cat_key, arts in cached.items():
        if isinstance(arts, list):
            for a in arts:
                if isinstance(a, dict) and "id" in a:
                    id_map[a["id"]] = a

    selected_by_cat = {k: [] for k in SIX_CATEGORIES.keys()}
    selected_ids = set()

    # 요일 매핑
    day_to_key = {
        "월": "mon_policy", "월요일": "mon_policy", "mon": "mon_policy",
        "화": "tue_creator", "화요일": "tue_creator", "tue": "tue_creator",
        "수": "wed_sports", "수요일": "wed_sports", "wed": "wed_sports",
        "목": "thu_tech", "목요일": "thu_tech", "thu": "thu_tech",
        "금": "fri_celeb", "금요일": "fri_celeb", "fri": "fri_celeb",
        "토": "sat_global", "토요일": "sat_global", "sat": "sat_global",
    }

    # 라인별 정규식 검사
    # 패턴 1: - [x] [mon_01] ...
    # 패턴 2: - [x] [월] http...
    checkbox_regex = re.compile(r'^\s*-\s*\[([xX])\]\s*\[([^\]]+)\]\s*(.*)$')

    manual_counter = 1
    for line in content.splitlines():
        m = checkbox_regex.match(line)
        if not m:
            continue

        tag = m.group(2).strip()
        rest = m.group(3).strip()

        # 기존 캐시 기사 매칭 확인
        if tag in id_map:
            art = id_map[tag]
            cat_k = art.get("category_key", "mon_policy")
            if tag not in selected_ids:
                selected_ids.add(tag)
                art["stage_1_selected"] = True
                selected_by_cat[cat_k].append(art)

        # 직접 추가 URL 매칭 확인 (예: [월] https://...)
        elif tag in day_to_key or tag.lower() in day_to_key:
            cat_k = day_to_key.get(tag, day_to_key.get(tag.lower(), "mon_policy"))
            url_match = re.search(r'https?://[^\s\)]+', rest)
            if url_match:
                url = url_match.group(0)
                print(f"  [직접 기사 감지] {SIX_CATEGORIES[cat_k]['day']} 기사 파싱 중: {url}")
                try:
                    custom_art = parse_custom_url(url, category_key=cat_k)
                    custom_art["id"] = f"{cat_k[:3]}_manual_{manual_counter:02d}"
                    custom_art["stage_1_selected"] = True
                    manual_counter += 1
                    selected_by_cat[cat_k].append(custom_art)
                except Exception as e:
                    print(f"  [직접 기사 파싱 실패]: {url} ({e})")
            elif len(rest) > 5:
                # URL 없이 텍스트 메모만 입력한 경우
                prefix = cat_k[:3]
                memo_art = {
                    "id": f"{prefix}_manual_{manual_counter:02d}",
                    "title": rest,
                    "description": rest,
                    "link": "#",
                    "pub_date": datetime.now().strftime("%Y-%m-%d"),
                    "source": "사용자 메모",
                    "category": SIX_CATEGORIES[cat_k]["title"],
                    "category_key": cat_k,
                    "is_global": False,
                    "is_manual": True,
                    "stage_1_selected": True
                }
                manual_counter += 1
                selected_by_cat[cat_k].append(memo_art)

    return selected_by_cat


def generate_candidates_detail_markdown(selected_by_cat: dict, output_path: Path) -> Path:
    """
    2단계: 1단계에서 체크된 기사의 본문, 요약, 출처 정보를 담아 최종 채택 체크박스 및 선택 이유 작성 마크다운을 생성합니다.
    """
    total_selected = sum(len(v) for v in selected_by_cat.values())
    lines = [
        "# 📝 주간 6대 카테고리 상세 검토 및 최종 선정 (2단계)",
        "",
        "> **안내사항**:",
        "> 1. 주 6일 매일 3건씩(총 18건 이상 권장) 관심 기사의 `[ ]`를 `[x]`로 체크하세요. (선택 이유 작성 불필요)",
        "> 2. **[자동 균등 재배치 및 자동 보충]**: 특정 요일 기사가 부족하더라도 사용자가 선택한 여유 기사 및 후보 풀에서 자동으로 균등 분배되어 주 6일 매일 정확히 3건(항상 6장 슬라이드: 표지+뉴스3건+4THEPT광고+아웃트로)의 콘텐츠가 완성됩니다.",
        "> 3. 작성이 완료되면 터미널에서 `python curate.py build` 명령을 실행하세요.",
        "",
        f"- 검토 대상 기사 수: {total_selected}건",
        ""
    ]

    for cat_key, meta in SIX_CATEGORIES.items():
        day_name = meta["day"]
        cat_title = meta["title"]
        articles = selected_by_cat.get(cat_key, [])

        lines.append(f"## 📅 {day_name}: {cat_title} (최종 2~3개 선택 권장)")
        lines.append("")

        if not articles:
            lines.append("> 1단계에서 선택된 기사가 없습니다.")
            lines.append("")
            continue

        for art in articles:
            art_id = art.get("id", "")
            title = art.get("title", "")
            source = art.get("source", "뉴스")
            link = art.get("link", "#")
            pub_date = art.get("pub_date", "")
            desc = art.get("description", "")
            body = art.get("article_body", "") or art.get("body_text", "") or desc

            lines.append(f"### [ ] [{art_id}] {title}")
            lines.append(f"- **출처/언론사**: {source} ({pub_date})")
            lines.append(f"- **원문 링크**: [기사 원문 보기]({link})")
            lines.append(f"- **핵심 요약**: {desc}")
            if body and body != desc:
                # 300자 내외 발췌
                preview = body[:300].strip() + ("..." if len(body) > 300 else "")
                lines.append(f"- **본문 발췌**: {preview}")
            lines.append("")

        lines.append("---")
        lines.append("")

    output_path.write_text("\n".join(lines), encoding="utf-8")
    return output_path


def parse_candidates_detail_markdown(
    detail_path: Path,
    cache_file: Path = CACHE_FILE
) -> tuple[dict[str, list[dict]], list[dict]]:
    """
    2단계 마크다운에서 최종 채택된 기사(`[x]`)와 작성된 선택 이유를 파싱합니다.
    - 반환값: (요일별_최종채택_기사맵, 히스토리_기록용_전체_항목리스트)
    """
    if not detail_path.exists():
        raise FileNotFoundError(f"상세 검토 파일이 존재하지 않습니다: {detail_path}")

    content = detail_path.read_text(encoding="utf-8")
    cached = load_candidates_cache(cache_file)

    id_map = {}
    for cat_key, arts in cached.items():
        if isinstance(arts, list):
            for a in arts:
                if isinstance(a, dict) and "id" in a:
                    id_map[a["id"]] = a

    # 정규식으로 기사 섹션 분리
    # 형식: ### [x] [mon_01] 제목
    art_block_regex = re.compile(
        r'###\s*\[([ xX])\]\s*\[([^\]]+)\]\s*([^\n]+)(.*?)(?=(?:###\s*\[|\Z))',
        re.DOTALL
    )

    final_by_cat = {k: [] for k in SIX_CATEGORIES.keys()}
    history_records = []
    now_iso = datetime.now().isoformat()

    for match in art_block_regex.finditer(content):
        is_checked = match.group(1).strip().lower() == "x"
        art_id = match.group(2).strip()
        title = match.group(3).strip()
        body_block = match.group(4)

        # 선택 이유 파싱
        reason_match = re.search(r'-\s*\*\*선택 이유\*\*:\s*([^\n]+)', body_block)
        if not reason_match:
            reason_match = re.search(r'-\s*선택 이유:\s*([^\n]+)', body_block)
        selection_reason = reason_match.group(1).strip() if reason_match else ""

        # 원문 링크 파싱
        link_match = re.search(r'-\s*\*\*원문 링크\*\*:\s*\[[^\]]+\]\(([^\)]+)\)', body_block)
        link = link_match.group(1).strip() if link_match else ""

        # 출처 파싱
        source_match = re.search(r'-\s*\*\*출처/언론사\*\*:\s*([^\n\(]+)', body_block)
        source = source_match.group(1).strip() if source_match else "뉴스"

        # 핵심 요약 파싱
        desc_match = re.search(r'-\s*\*\*핵심 요약\*\*:\s*([^\n]+)', body_block)
        desc = desc_match.group(1).strip() if desc_match else ""

        # 카테고리 결정
        prefix = art_id.split("_")[0]
        cat_key = "mon_policy"
        for k in SIX_CATEGORIES.keys():
            if k.startswith(prefix):
                cat_key = k
                break

        # 기본 기사 정보 구성
        base_art = id_map.get(art_id, {}).copy()
        base_art.update({
            "id": art_id,
            "title": title or base_art.get("title", ""),
            "link": link or base_art.get("link", ""),
            "source": source or base_art.get("source", ""),
            "description": desc or base_art.get("description", ""),
            "category_key": cat_key,
            "category": SIX_CATEGORIES[cat_key]["title"],
            "day": SIX_CATEGORIES[cat_key]["day"],
            "selection_reason": selection_reason,
            "final_selected": is_checked
        })

        # 최종 채택된 경우 요일별 맵에 추가
        if is_checked:
            final_by_cat[cat_key].append(base_art)

        # 향후 에이전트 분석용 히스토리 레코드 생성
        history_records.append({
            "id": art_id,
            "title": base_art["title"],
            "link": base_art["link"],
            "source": base_art["source"],
            "category_key": cat_key,
            "category": base_art["category"],
            "day": base_art["day"],
            "final_selected": is_checked,
            "selection_reason": selection_reason,
            "curated_at": now_iso
        })

    return final_by_cat, history_records


def append_to_curation_history(history_records: list[dict], history_file: Path = HISTORY_FILE):
    """선택 이유 및 기사 메타데이터를 curation_history.jsonl에 누적 저장합니다."""
    history_file.parent.mkdir(parents=True, exist_ok=True)
    with open(history_file, "a", encoding="utf-8") as f:
        for record in history_records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")


def rebalance_selected_articles(
    final_by_cat: dict,
    min_per_day: int = 3,
    max_per_day: int = 3,
    cache_file: Path = CACHE_FILE
) -> tuple[dict, list[str]]:
    """
    주간 6일(월~토) 전 요일에 정확히 3건(총 18건)의 기사가 배치되도록 재배치 및 자동 보충합니다.
    1. 사용자가 직접 [x] 체크한 기사 중 여유 요일(>3건)의 기사를 부족 요일(<3건)로 우선 재배치합니다.
    2. 총 선택 건수가 18건 미만이라 여전히 3건에 미달하는 요일이 있다면,
       후보 캐시(candidates_cache.json)의 미선택 후보 중 최상위 기사를 자동 보충하여 무조건 요일당 3건을 완성합니다.
    3. 요일당 최대 3건으로 고정하여 반환합니다.
    - 반환값: (재배치된_기사맵, 재배치_로그_리스트)
    """
    rebalanced = {k: [a.copy() for a in arts] for k, arts in final_by_cat.items()}
    logs = []

    total_selected = sum(len(arts) for arts in rebalanced.values())
    if total_selected == 0:
        return rebalanced, logs

    # 1단계: 사용자 선택 기사 간의 균등 재배치 (surplus 요일 -> deficit 요일)
    while True:
        # min_per_day 미만인 요일 중 가장 기사가 적은 요일 찾기
        target_day = None
        min_count = min_per_day
        for cat_key in SIX_CATEGORIES.keys():
            count = len(rebalanced.get(cat_key, []))
            if count < min_count:
                min_count = count
                target_day = cat_key

        if not target_day:
            # 모든 요일이 3건 이상 확보됨
            break

        # min_per_day 초과인 요일 중 가장 기사가 많은 요일 찾기
        source_day = None
        max_count = min_per_day
        for cat_key in SIX_CATEGORIES.keys():
            count = len(rebalanced.get(cat_key, []))
            if count > max_count:
                max_count = count
                source_day = cat_key

        if not source_day:
            # 여유 기사를 가진 요일이 없어 더 이상 사용자 체크 기사 차출 불가
            break

        moved_art = rebalanced[source_day].pop()
        src_name = SIX_CATEGORIES[source_day]["day"]
        tgt_name = SIX_CATEGORIES[target_day]["day"]

        # 원래 카테고리 보존 및 새 요일 메타데이터 갱신
        moved_art["original_category"] = moved_art.get("category", "")
        moved_art["original_day"] = src_name
        moved_art["category_key"] = target_day
        moved_art["day"] = tgt_name

        rebalanced[target_day].append(moved_art)
        log_msg = f"[기사 이동: {src_name} -> {tgt_name}] '{moved_art.get('title', '')[:30]}...'"
        logs.append(log_msg)

    # 2단계: 18건 미달로 여전히 3건 미만인 요일이 있다면, 후보 캐시에서 자동 보충
    cached = load_candidates_cache(cache_file)
    existing_ids = {a.get("id") for arts in rebalanced.values() for a in arts}

    for cat_key in SIX_CATEGORIES.keys():
        while len(rebalanced.get(cat_key, [])) < min_per_day:
            day_name = SIX_CATEGORIES[cat_key]["day"]
            candidates = cached.get(cat_key, [])
            supplemented = False
            for cand in candidates:
                cand_id = cand.get("id")
                if cand_id and cand_id not in existing_ids:
                    cand_copy = cand.copy()
                    cand_copy["final_selected"] = True
                    cand_copy["is_supplemented"] = True
                    cand_copy["day"] = day_name
                    cand_copy["category_key"] = cat_key
                    cand_copy["category"] = SIX_CATEGORIES[cat_key]["title"]
                    rebalanced[cat_key].append(cand_copy)
                    existing_ids.add(cand_id)
                    supplemented = True
                    log_msg = f"[후보 기사 자동 보충: {day_name}] '{cand_copy.get('title', '')[:30]}...'"
                    logs.append(log_msg)
                    break

            if not supplemented:
                # 해당 카테고리 고갈 시 타 카테고리 후보에서라도 보충
                for any_cat, any_cands in cached.items():
                    for cand in any_cands:
                        cand_id = cand.get("id")
                        if cand_id and cand_id not in existing_ids:
                            cand_copy = cand.copy()
                            cand_copy["final_selected"] = True
                            cand_copy["is_supplemented"] = True
                            cand_copy["day"] = day_name
                            cand_copy["category_key"] = cat_key
                            cand_copy["category"] = SIX_CATEGORIES[cat_key]["title"]
                            rebalanced[cat_key].append(cand_copy)
                            existing_ids.add(cand_id)
                            supplemented = True
                            log_msg = f"[후보 기사 교차 보충: {day_name}] '{cand_copy.get('title', '')[:30]}...'"
                            logs.append(log_msg)
                            break
                    if supplemented:
                        break

            if not supplemented:
                break

    # 3단계: 요일당 정확히 3건(max_per_day)으로 슬라이싱
    for cat_key in SIX_CATEGORIES.keys():
        if len(rebalanced[cat_key]) > max_per_day:
            rebalanced[cat_key] = rebalanced[cat_key][:max_per_day]

    return rebalanced, logs
