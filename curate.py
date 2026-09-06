# 이 파일은 주간 6대 카테고리 2단계 마크다운 큐레이션 및 파이프라인 구동 CLI 도구입니다.
# 1단계 수집(fetch) -> 2단계 검토(review) -> 최종 제작 및 히스토리 아카이빙(build)을 지원합니다.

import sys
import os
import argparse
import asyncio
from pathlib import Path
from datetime import datetime

# 윈도우 UTF-8 출력 보장
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

sys.path.append(str(Path(__file__).resolve().parent))

from config import BASE_DIR, OUTPUT_DIR
from modules.news_collector import collect_6categories_candidates, SIX_CATEGORIES
from modules.curation_manager import (
    save_candidates_cache,
    load_candidates_cache,
    generate_candidates_titles_markdown,
    parse_candidates_titles_markdown,
    generate_candidates_detail_markdown,
    parse_candidates_detail_markdown,
    append_to_curation_history,
    rebalance_selected_articles,
    CACHE_FILE,
    HISTORY_FILE
)
from modules.article_image_fetcher import fetch_article_images


TITLES_MD = BASE_DIR / "candidates_titles.md"
DETAIL_MD = BASE_DIR / "candidates_detail.md"


def cmd_fetch(args):
    """1단계: 6대 카테고리 최대 100건 후보 수집 및 candidates_titles.md 생성"""
    target_count = args.count if args.count else 17
    print("\n🚀 [1단계] 주 6일 6대 카테고리 후보 기사 대량 수집을 시작합니다...")
    candidates = collect_6categories_candidates(target_per_category=target_count)

    # 캐시 저장
    save_candidates_cache(candidates, CACHE_FILE)

    # 마크다운 생성
    generate_candidates_titles_markdown(candidates, TITLES_MD)

    print("\n" + "=" * 70)
    print("✅ [완료] 1단계 제목 스크리닝 파일이 생성되었습니다!")
    print(f"👉 파일 경로: {TITLES_MD}")
    print("=" * 70)
    print("📋 [다음 작업 안내]:")
    print(" 1. 에디터에서 'candidates_titles.md' 파일을 엽니다.")
    print(" 2. 관심 있는 기사의 [ ] 를 [x] 로 체크하세요. (요일당 3~5개 권장)")
    print(" 3. 추가하고 싶은 기사가 있다면 맨 아래 [✍️ 직접 기사 추가]에 URL을 적어주세요.")
    print(" 4. 저장이 끝나면 아래 명령어를 실행하세요:")
    print("    👉 python curate.py review")
    print("=" * 70)


async def cmd_review_async(args):
    """2단계: 1차 선택된 기사의 상세 본문/사진을 파싱하여 candidates_detail.md 생성"""
    if not TITLES_MD.exists():
        print(f"❌ [오류] 먼저 1단계 수집을 실행하세요: python curate.py fetch")
        sys.exit(1)

    print("\n🔍 [2단계] 1단계 체크박스 파싱 및 상세 본문/보도 사진 크롤링 중...")
    selected_by_cat = parse_candidates_titles_markdown(TITLES_MD, CACHE_FILE)
    total_selected = sum(len(v) for v in selected_by_cat.values())

    if total_selected == 0:
        print("⚠️ [주의] 1단계에서 [x]로 체크된 기사가 하나도 없습니다!")
        print("   candidates_titles.md 파일에서 관심 기사에 [x]를 표시한 뒤 다시 실행해주세요.")
        sys.exit(1)

    print(f"  -> 총 {total_selected}건의 기사가 1차 선택되었습니다.")
    for k, meta in SIX_CATEGORIES.items():
        print(f"     - [{meta['day']}] {meta['title']}: {len(selected_by_cat.get(k, []))}건")

    # 보도 사진 및 원문 본문 크롤링
    today_str = datetime.now().strftime("%Y-%m-%d")
    bg_dir = OUTPUT_DIR / f"{today_str}_curation" / "backgrounds"
    bg_dir.mkdir(parents=True, exist_ok=True)

    print("\n🌐 각 기사의 원문 웹페이지에서 본문 및 보도 사진을 크롤링합니다...")
    for k, arts in selected_by_cat.items():
        if arts:
            prefix = k[:3]
            try:
                await fetch_article_images(arts, bg_dir, prefix=prefix)
            except Exception as e:
                print(f"  - [{prefix}] 크롤링 경고: {e}")

    # 캐시 업데이트
    cached = load_candidates_cache(CACHE_FILE)
    for k, arts in selected_by_cat.items():
        if k in cached:
            # 기존 캐시에 기사 본문 및 이미지 정보 병합
            for art in arts:
                for idx, c_art in enumerate(cached[k]):
                    if c_art.get("id") == art.get("id"):
                        cached[k][idx] = art
    save_candidates_cache(cached, CACHE_FILE)

    # 2단계 상세 마크다운 생성
    generate_candidates_detail_markdown(selected_by_cat, DETAIL_MD)

    print("\n" + "=" * 70)
    print("✅ [완료] 2단계 상세 검토 파일이 생성되었습니다!")
    print(f"👉 파일 경로: {DETAIL_MD}")
    print("=" * 70)
    print("📋 [다음 작업 안내]:")
    print(" 1. 에디터에서 'candidates_detail.md' 파일을 엽니다.")
    print(" 2. 요일별로 최종 발행할 기사를 [x] 로 체크하세요. (선택 이유 작성 불필요)")
    print(" 3. 저장이 끝나면 아래 명령어를 실행하여 주간 6일 콘텐츠를 일괄 제작하세요:")
    print("    👉 python curate.py build")
    print("=" * 70)


def cmd_build(args):
    """3단계: 최종 선택 기사 확정, 큐레이션 히스토리 저장 및 주 6일 콘텐츠 일괄 제작"""
    if not DETAIL_MD.exists():
        print(f"❌ [오류] 먼저 2단계 검토 파일을 생성하세요: python curate.py review")
        sys.exit(1)

    print("\n⚙️ [3단계] 최종 큐레이션 검토 결과 파싱 및 데이터셋 저장 중...")
    final_by_cat, history_records = parse_candidates_detail_markdown(DETAIL_MD, CACHE_FILE)

    total_final = sum(len(v) for v in final_by_cat.values())
    if total_final == 0:
        print("⚠️ [주의] 2단계에서 [x]로 최종 채택된 기사가 없습니다!")
        print("   candidates_detail.md 파일에서 각 요일별 기사에 [x]를 체크해주세요.")
        sys.exit(1)

    print(f"  -> 총 {total_final}건의 기사가 최종 채택되었습니다.")
    for k, meta in SIX_CATEGORIES.items():
        arts = final_by_cat.get(k, [])
        print(f"     - [{meta['day']}] {meta['title']}: {len(arts)}건 채택")
        for a in arts:
            print(f"       * {a['title'][:40]}")

    # 큐레이션 히스토리 영구 누적 저장 (향후 에이전트 학습용)
    append_to_curation_history(history_records, HISTORY_FILE)
    print(f"\n📁 [데이터셋 저장] {len(history_records)}건의 큐레이션 기록이 '{HISTORY_FILE}'에 안전하게 누적되었습니다.")

    # 사용자 선택 기사 기반 요일별 균등 재배치 및 자동 보충 (요일별 3건, 총 18건 보장)
    rebalanced_by_cat, rebalance_logs = rebalance_selected_articles(final_by_cat, min_per_day=3, max_per_day=3)
    if rebalance_logs:
        print("\n" + "=" * 70)
        print("🔄 [기사 3건 균등 재배치 및 자동 보충 실행]")
        print("   주 6일 매일 정확히 3건(총 18건)을 맞추기 위해 기사를 재배치/보충했습니다:")
        for log in rebalance_logs:
            print(f"   {log}")
        print("=" * 70)

    # 렌더링 파이프라인 구동
    print("\n🎬 주 6일 통합 콘텐츠(쇼츠 비디오 + 4:5 카드뉴스 + 4THEPT 광고 + SNS 캡션) 일괄 렌더링을 시작합니다...")
    from pipeline import run_curated_6days_pipeline
    results = asyncio.run(run_curated_6days_pipeline(rebalanced_by_cat))

    print("\n" + "=" * 70)
    print("🎉 [제작 성공] 주간 6일 연계 콘텐츠 생성이 모두 완료되었습니다!")
    print(f"👉 마스터 저장 폴더: {results.get('weekly_dir', OUTPUT_DIR)}")
    print("=" * 70)


def cmd_stats(args):
    """누적된 큐레이션 히스토리 데이터셋 통계 확인"""
    if not HISTORY_FILE.exists():
        print("📊 아직 누적된 큐레이션 히스토리가 없습니다.")
        return

    total = 0
    selected = 0
    reasons_count = 0
    with open(HISTORY_FILE, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            total += 1
            data = json.loads(line)
            if data.get("final_selected"):
                selected += 1
                if data.get("selection_reason"):
                    reasons_count += 1

    print("\n" + "=" * 50)
    print("📊 [THEPT] 큐레이션 데이터셋 누적 현황")
    print("=" * 50)
    print(f"• 총 검토 기사 수: {total}건")
    print(f"• 최종 채택 기사 수: {selected}건")
    print(f"• 선택 이유 작성 건수: {reasons_count}건")
    print(f"• 히스토리 파일: {HISTORY_FILE}")
    print("=" * 50)


def main():
    parser = argparse.ArgumentParser(
        description="THEPT 주 6일 6대 카테고리 2단계 마크다운 큐레이션 도구"
    )
    subparsers = parser.add_subparsers(dest="command", help="실행할 작업 선택")

    # 1. fetch
    p_fetch = subparsers.add_parser("fetch", help="1단계: 6대 카테고리 최대 100건 후보 수집 및 제목 마크다운 생성")
    p_fetch.add_argument("--count", type=int, default=17, help="카테고리당 수집 건수 (기본 17건, 총 약 100건)")

    # 2. review
    p_review = subparsers.add_parser("review", help="2단계: 1차 선택 기사 상세 본문/사진 크롤링 및 검토 마크다운 생성")

    # 3. build
    p_build = subparsers.add_parser("build", help="3단계: 최종 선택 기사 확정, 이유 저장 및 주 6일 콘텐츠 일괄 제작")

    # 4. stats
    p_stats = subparsers.add_parser("stats", help="누적된 큐레이션 데이터셋 통계 확인")

    args = parser.parse_args()

    if args.command == "fetch":
        cmd_fetch(args)
    elif args.command == "review":
        asyncio.run(cmd_review_async(args))
    elif args.command == "build":
        cmd_build(args)
    elif args.command == "stats":
        cmd_stats(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
