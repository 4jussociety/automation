# 이 파일은 주간 6대 카테고리 2단계 마크다운 큐레이션 및 파이프라인 구동 CLI 도구입니다.
# 1단계 수집(fetch) -> 2단계 검토(review) -> 최종 제작 및 히스토리 아카이빙(build)을 지원합니다.

import sys
import os
import argparse
import asyncio
import json
import re
from pathlib import Path
from datetime import datetime, timedelta

# 윈도우 UTF-8 출력 보장
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

sys.path.append(str(Path(__file__).resolve().parent))

from config import BASE_DIR, OUTPUT_DIR, build_4thept_promo_footer, build_first_comment
from modules.news_collector import collect_6categories_candidates, SIX_CATEGORIES
from modules.curation_manager import (
    save_candidates_cache,
    load_candidates_cache,
    generate_candidates_titles_markdown,
    generate_candidates_fulltext_markdown,
    parse_candidates_titles_markdown,
    generate_candidates_detail_markdown,
    parse_candidates_detail_markdown,
    build_curation_history_records,
    append_to_curation_history,
    rebalance_selected_articles,
    CACHE_FILE,
    HISTORY_FILE
)
from modules.article_image_fetcher import fetch_article_images


def get_weekly_dir(date_str: str = None, create: bool = True) -> Path:
    """
    주간 큐레이션 통합 작업 디렉토리(결과물/THEPT뉴스/{YYYY-MM-DD}_curated_weekly) 경로를 반환합니다.
    주간 기준 날짜가 전달되지 않으면, 일요일 실행 시에는 내일(월요일), 평일에는 해당 주의 월요일을 기본 날짜로 통일합니다.
    """
    if not date_str:
        now_dt = datetime.now()
        if now_dt.weekday() == 6:
            # 일요일 실행 시: 내일부터 시작하는 다가오는 주간(월~토) 기준
            monday_dt = now_dt + timedelta(days=1)
        else:
            monday_dt = now_dt - timedelta(days=now_dt.weekday())
        date_str = monday_dt.strftime("%Y-%m-%d")
    weekly_dir = OUTPUT_DIR / f"{date_str}_curated_weekly"
    if create:
        weekly_dir.mkdir(parents=True, exist_ok=True)
    return weekly_dir


def find_active_weekly_dir(date_str: str = None) -> Path:
    """
    작업할 주간 디렉토리를 결정합니다.
    - 날짜(YYYY-MM-DD)가 지정되면 해당 주간 디렉토리 반환
    - 4자리 MMDD 등 단축 날짜는 주간 디렉토리가 아닌 개별 날짜 필터이므로 최신 주간 디렉토리 자동 탐색
    - 이번 주(월요일 기준) 디렉토리가 있으면 반환
    - 없으면 가장 최근 생성된 *_curated_weekly 디렉토리 반환
    """
    if date_str and len(date_str) > 7:
        return get_weekly_dir(date_str, create=True)

    this_week_dir = get_weekly_dir(create=False)
    if this_week_dir.exists():
        return this_week_dir

    if OUTPUT_DIR.exists():
        weekly_dirs = sorted(
            [d for d in OUTPUT_DIR.iterdir() if d.is_dir() and d.name.endswith("_curated_weekly")],
            key=lambda x: x.name,
            reverse=True
        )
        if weekly_dirs:
            return weekly_dirs[0]

    return get_weekly_dir(create=True)


def cmd_fetch(args):
    """1단계: 6대 카테고리 요일별 15~30건 후보 수집 및 candidates_titles.md 생성"""
    target_count = args.count if getattr(args, "count", None) else 25
    weekly_dir = get_weekly_dir(getattr(args, "date", None), create=True)
    titles_md = weekly_dir / "candidates_titles.md"

    print("\n🚀 [1단계] 주 6일 6대 카테고리 후보 기사 대량 수집을 시작합니다...")
    candidates = collect_6categories_candidates(target_per_category=target_count)

    # 캐시 저장
    save_candidates_cache(candidates, CACHE_FILE)

    # 마크다운 생성 (output 주차별 폴더 내)
    generate_candidates_titles_markdown(candidates, titles_md)
    fulltext_md = weekly_dir / "candidates_fulltext.md"
    generate_candidates_fulltext_markdown(candidates, fulltext_md)

    print("\n" + "=" * 70)
    print("✅ [완료] 1단계 제목 스크리닝 및 본문 전문 열람 파일이 생성되었습니다!")
    print(f"👉 1. 제목 스크리닝 파일: {titles_md.resolve()}")
    print(f"👉 2. 본문 전문 열람 파일: {fulltext_md.resolve()}")
    print("=" * 70)
    print("📋 [다음 작업 안내]:")
    print(f" 1. 에디터에서 [candidates_titles.md]를 열어 관심 기사에 [x]를 체크하세요.")
    print(f"    (기사 전문이 궁금할 땐 [candidates_fulltext.md]에서 Ctrl+F로 바로 확인 가능!)")
    print(" 2. 추가하고 싶은 기사가 있다면 맨 아래 [✍️ 직접 기사 추가]에 URL을 적어주세요.")
    print(" 3. 저장이 끝나면 아래 명령어를 실행해 바로 콘텐츠를 제작하세요:")
    print("    👉 python curate.py build")
    print("    (※ 별도 상세 검토 파일이 필요할 때만 'python curate.py review' 실행)")
    print("=" * 70)


async def cmd_review_async(args):
    """2단계: 1차 선택된 기사의 상세 본문/사진을 파싱하여 candidates_detail.md 생성"""
    weekly_dir = find_active_weekly_dir(getattr(args, "date", None))
    titles_md = weekly_dir / "candidates_titles.md"
    detail_md = weekly_dir / "candidates_detail.md"

    if not titles_md.exists():
        print(f"❌ [오류] 1단계 파일이 존재하지 않습니다: {titles_md.resolve()}")
        print(f"   먼저 1단계 수집을 실행하세요: python curate.py fetch")
        sys.exit(1)

    print(f"\n🔍 [2단계] 1단계 체크박스 파싱 중: {titles_md.name} ({weekly_dir.name})")
    selected_by_cat = parse_candidates_titles_markdown(titles_md, CACHE_FILE)
    total_selected = sum(len(v) for v in selected_by_cat.values())

    if total_selected == 0:
        print("⚠️ [주의] 1단계에서 [x]로 체크된 기사가 하나도 없습니다!")
        print(f"   파일({titles_md.resolve()})에서 관심 기사에 [x]를 표시한 뒤 다시 실행해주세요.")
        sys.exit(1)

    print(f"  -> 총 {total_selected}건의 기사가 1차 선택되었습니다.")
    for k, meta in SIX_CATEGORIES.items():
        print(f"     - [{meta['day']}] {meta['title']}: {len(selected_by_cat.get(k, []))}건")

    # 보도 사진 및 원문 본문 크롤링 (통합된 backgrounds 폴더)
    bg_dir = weekly_dir / "backgrounds"
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

    # 2단계 상세 마크다운 생성 (output 주차별 폴더 내)
    generate_candidates_detail_markdown(selected_by_cat, detail_md)

    print("\n" + "=" * 70)
    print("✅ [완료] 2단계 상세 검토 파일이 생성되었습니다!")
    print(f"👉 파일 경로: {detail_md.resolve()}")
    print("=" * 70)
    print("📋 [다음 작업 안내]:")
    print(f" 1. 에디터에서 아래 파일을 엽니다:\n    👉 {detail_md.resolve()}")
    print(" 2. 요일별로 최종 발행할 기사를 [x] 로 체크하세요. (선택 이유 작성 불필요)")
    print(" 3. 저장이 끝나면 아래 명령어를 실행하여 주간 6일 콘텐츠를 일괄 제작하세요:")
    print("    👉 python curate.py build")
    print("=" * 70)


def cmd_build(args):
    """최종 선택 기사 확정(기본: candidates_titles.md 직통 파싱), 히스토리 저장 및 주 6일 콘텐츠 일괄 제작"""
    weekly_dir = find_active_weekly_dir(getattr(args, "date", None))
    use_detail = getattr(args, "from_detail", False)

    if use_detail:
        detail_md = weekly_dir / "candidates_detail.md"
        if not detail_md.exists():
            print(f"❌ [오류] 상세 검토 파일이 존재하지 않습니다: {detail_md.resolve()}")
            print(f"   먼저 검토 파일을 생성하거나(--from-detail 제외), 기본 모드로 실행하세요: python curate.py build")
            sys.exit(1)

        print(f"\n⚙️ [빌드] 상세 검토 결과 파싱 중: {detail_md.name} ({weekly_dir.name})")
        final_by_cat, history_records = parse_candidates_detail_markdown(detail_md, CACHE_FILE)
        source_md = detail_md
    else:
        titles_md = weekly_dir / "candidates_titles.md"
        if not titles_md.exists():
            print(f"❌ [오류] 1단계 제목 스크리닝 파일이 존재하지 않습니다: {titles_md.resolve()}")
            print(f"   먼저 1단계 수집을 실행하세요: python curate.py fetch")
            sys.exit(1)

        print(f"\n⚙️ [빌드] 제목 스크리닝 체크박스 직통 파싱 중: {titles_md.name} ({weekly_dir.name})")
        final_by_cat = parse_candidates_titles_markdown(titles_md, CACHE_FILE)
        history_records = build_curation_history_records(final_by_cat)
        source_md = titles_md

    total_final = sum(len(v) for v in final_by_cat.values())
    if total_final == 0:
        print(f"⚠️ [주의] {source_md.name}에서 [x]로 채택된 기사가 없습니다!")
        print(f"   파일({source_md.resolve()})에서 각 요일별 기사에 [x]를 체크해주세요.")
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
    do_render = getattr(args, "render", False)
    target_date_arg = getattr(args, "day", None)
    raw_date = getattr(args, "date", None)
    if raw_date and (len(raw_date) <= 5 or re.match(r"^\d{1,2}[/.-]\d{1,2}$", raw_date)):
        target_date_arg = raw_date

    if target_date_arg:
        mode_prefix = f"[{target_date_arg} 단독 모드]"
    else:
        mode_prefix = "주 6일 통합 콘텐츠"

    if do_render:
        print(f"\n🎬 {mode_prefix} (쇼츠 비디오 + 4:5 카드뉴스 + 4THEPT 광고 + SNS 캡션) 일괄 렌더링을 시작합니다...")
    else:
        print(f"\n📝 {mode_prefix} 패키지(OpenAI LLM 요약 + 쇼츠 대본 + 4THEPT 광고 + SNS 캡션) 생성을 시작합니다...")
        print("   (※ 카드뉴스 이미지/비디오 렌더링은 --render 옵션 사용 시 수행됩니다.)")

    from pipeline import run_curated_6days_pipeline
    results = asyncio.run(run_curated_6days_pipeline(
        rebalanced_by_cat,
        render_media=do_render,
        target_dir=weekly_dir,
        day_filter=target_date_arg
    ))

    print("\n" + "=" * 70)
    print("🎉 [제작 성공] 콘텐츠 생성이 모두 완료되었습니다!")
    print(f"👉 마스터 저장 폴더: {results.get('weekly_dir', weekly_dir)}")
    print("=" * 70)

    # GitHub 원격 저장소 자동 동기화 연동 (--sync 옵션 시)
    if getattr(args, "sync", False):
        print("\n" + "=" * 70)
        print("🚀 [--sync 옵션 감지] 주간 콘텐츠를 GitHub 원격 저장소에 즉시 동기화합니다...")
        cmd_sync(args)
    else:
        print("📋 [다음 작업 안내]:")
        print("   주간 콘텐츠 생성이 완료되었습니다. GitHub 원격 저장소에 동기화하여")
        print("   매일 아침 KST 08:00 GitHub Actions 무인 발행 준비를 완료하세요:")
        print("   👉 python curate.py sync")
        print("=" * 70)


def cmd_upload(args):
    """
    주간 콘텐츠(유튜브 쇼츠, 인스타그램 카드뉴스 캐러셀, 릴스)를 자동 예약 업로드합니다.
    --dry-run 옵션 지정 시 실제 API 호출 없이 스케줄 및 메타데이터, GitHub Raw URL을 시뮬레이션합니다.
    """
    weekly_dir = find_active_weekly_dir(getattr(args, "date", None))
    dry_run = getattr(args, "dry_run", False)
    platform = getattr(args, "platform", "all").lower()
    content_type = getattr(args, "type", "all").lower()

    # GitHub Actions 정기 발행뿐 아니라 로컬 PC에서의 즉시 업로드도 허용합니다.
    # (에이전트 실행 시 scripts/hooks/pre_tool_guard.py가 force_ask 사용자 확인 게이트를 적용합니다.)

    print("\n" + "=" * 70)
    mode_str = "🧪 [시뮬레이션 모드 (DRY-RUN)]" if dry_run else "🚀 [실제 API 업로드 모드]"
    print(f"{mode_str} 주간 SNS 자동 예약 발행 파이프라인을 시작합니다.")
    print(f"👉 대상 디렉토리: {weekly_dir.resolve()}")
    print(f"👉 대상 플랫폼: {platform.upper()} | 대상 콘텐츠: {content_type.upper()}")
    print("=" * 70)

    # 요일 폴더 탐색 (0907_Mon_Policy, 01_Mon_Policy 등 MMDD 또는 순번 프리픽스 지원)
    day_folders = sorted(
        [d for d in weekly_dir.iterdir() if d.is_dir() and re.match(r"^\d{2,4}_", d.name)],
        key=lambda x: x.name
    )

    if not day_folders:
        print(f"❌ [오류] 요일별 콘텐츠 폴더를 찾을 수 없습니다: {weekly_dir}")
        print("   먼저 콘텐츠를 제작하세요: python curate.py build --render")
        return

    # 날짜 필터링 (--today-only 또는 --day/--date, 미지정 시 안전하게 오늘 날짜 기본값 적용)
    today_only = getattr(args, "today_only", False)
    target_date_arg = getattr(args, "day", None)
    raw_date = getattr(args, "date", None)
    if raw_date and (len(raw_date) <= 5 or re.match(r"^\d{1,2}[/.-]\d{1,2}$", raw_date)):
        target_date_arg = raw_date

    if not target_date_arg and not today_only:
        # 미래 콘텐츠가 불필요하게 사전 예약되는 것을 방지하고 매일 GitHub Actions 무인 발행과 일치시킴
        today_only = True

    from modules.sns_scheduler import KST
    now_kst = datetime.now(KST)
    today_mmdd = now_kst.strftime("%m%d")

    if today_only:
        if now_kst.weekday() == 6:
            print("ℹ️ [스킵] 오늘은 일요일입니다. 주 6일(월~토) 정기 발행 대상 요일이 아니므로 안전하게 종료합니다.")
            return

        # 오늘 날짜(MMDD) 접두어(예: 0917_)로 폴더 1건 정확 매칭
        matched_today = [d for d in day_folders if d.name.startswith(f"{today_mmdd}_")]
        if not matched_today:
            print(f"⚠️ [주의] 오늘 날짜({today_mmdd})에 해당하는 콘텐츠 폴더를 찾을 수 없습니다: {weekly_dir}")
            return
        day_folders = matched_today
        print(f"🎯 [당일 발행 모드] 오늘 날짜({today_mmdd}) 콘텐츠를 즉시 공개 발행합니다: {[d.name for d in day_folders]}")

    elif target_date_arg:
        from modules.day_filter import match_day_filter
        matched_folders = [d for d in day_folders if match_day_filter(target_date_arg, folder_name=d.name)]
        if not matched_folders:
            print(f"⚠️ [주의] 지정하신 날짜('{target_date_arg}')와 일치하는 폴더를 찾을 수 없습니다: {weekly_dir}")
            return
        day_folders = matched_folders
        print(f"🎯 [지정 날짜 모드] 대상 폴더: {[d.name for d in day_folders]}")

    from modules.sns_scheduler import get_github_raw_url
    from modules.youtube_uploader import upload_youtube_short
    from modules.instagram_uploader import (
        InstagramGraphUploader,
        upload_instagram_carousel,
        upload_instagram_reel,
    )
    from config import get_youtube_category_id, YOUTUBE_CATEGORY_NAMES

    allow_duplicate = getattr(args, "allow_duplicate", False)
    ig_dup_checker = None if (dry_run or allow_duplicate) else InstagramGraphUploader()
    today_date_kst = now_kst.strftime("%Y-%m-%d")

    total_tasks = 0
    success_tasks = 0

    for folder in day_folders:
        folder_name = folder.name
        pkg_file = folder / "package_data.json"
        caption_file = folder / "instagram_caption.txt"
        card_dir = folder / "card_images_4x5"
        shorts_files = list(folder.glob("shorts_*.mp4")) or list(folder.glob("*.mp4"))

        # 메타데이터 로드
        pkg_data = {}
        if pkg_file.exists():
            try:
                with open(pkg_file, "r", encoding="utf-8") as f:
                    pkg_data = json.load(f)
            except Exception as e:
                print(f"⚠️ [{folder_name}] package_data.json 로드 실패: {e}")

        # 캡션 로드
        caption = ""
        if caption_file.exists():
            caption = caption_file.read_text(encoding="utf-8").strip()
        elif "caption" in pkg_data:
            caption = pkg_data["caption"].strip()

        day_label = pkg_data.get("day_name", folder_name)
        cat_title = pkg_data.get("category_title", folder_name)

        # 모든 발행은 [즉시 공개 업로드]로 일원화 (매일 08:00 GitHub Actions가 당일 정시 즉시 공개 및 첫 댓글 자동 등록)
        sched = {
            "unix_timestamp": None,
            "rfc3339": None,
            "is_immediate": True,
            "formatted_kst": "[즉시 공개 업로드] (실시간 발행 및 첫 댓글 자동 등록)"
        }

        print(f"\n📅 [{day_label}] {cat_title} ({folder_name})")
        print(f"   ⏰ 발행 모드: {sched['formatted_kst']}")

        # 사족 없는 공식 첫 댓글 로드 (config 단일 헬퍼 기반)
        comment_file = folder / "first_comment.txt"
        if comment_file.exists():
            first_comment = comment_file.read_text(encoding="utf-8").strip()
        else:
            first_comment = build_first_comment(
                utm_source="ig",
                utm_medium="carousel",
                utm_campaign=f"weekly_briefing_{folder_name.lower()}",
            )

        yt_first_comment = first_comment.replace("utm_source=ig", "utm_source=yt").replace(
            "utm_medium=carousel", "utm_medium=shorts"
        )

        # 1. YouTube Shorts 업로드
        if platform in ("all", "youtube") and content_type in ("all", "shorts", "video"):
            if not shorts_files:
                print("   ⚠️ [YouTube Shorts] 비디오 파일(.mp4)이 없어 건너뜁니다.")
            else:
                total_tasks += 1
                video_path = shorts_files[0]
                # 제목 규칙: '{요일} THEPT 물리치료 1분 브리핑 #Shorts'
                yt_title = f"{day_label} THEPT 물리치료 1분 브리핑 #Shorts"

                # 생성된 전용 유튜브 설명란 파일이 있으면 우선 사용
                yt_caption_file = folder / "youtube_shorts_caption.txt"
                if yt_caption_file.exists():
                    yt_desc = yt_caption_file.read_text(encoding="utf-8").strip()
                else:
                    yt_footer = build_4thept_promo_footer(
                        utm_source="yt",
                        utm_medium="shorts",
                        utm_campaign=f"weekly_briefing_{folder_name.lower()}",
                        include_disclaimer=True,
                    )
                    yt_desc = (
                        f"📢 {day_label} THEPT 물리치료 1분 브리핑 #Shorts\n\n"
                        f"{caption}\n\n"
                        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                        f"{yt_footer}\n"
                        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                        f"#물리치료 #물리치료사 #쇼츠 #Shorts #THEPT #더피티 #재활 #도수치료\n"
                    )

                custom_cat_arg = getattr(args, "category", None)
                yt_category_id = (
                    custom_cat_arg
                    or pkg_data.get("youtube_category_id")
                    or get_youtube_category_id(folder_name)
                    or get_youtube_category_id(day_label)
                )
                cat_name = YOUTUBE_CATEGORY_NAMES.get(str(yt_category_id), f"카테고리 {yt_category_id}")

                print(f"   ▶️ [YouTube Shorts] 즉시 공개 업로드 요청 중... (제목: '{yt_title}', 카테고리: {cat_name})")
                res_yt = upload_youtube_short(
                    video_path=video_path,
                    title=yt_title,
                    description=yt_desc,
                    tags=["물리치료", "물리치료사", "Shorts", "쇼츠", "THEPT", "더피티", "재활", "도수치료"],
                    category_id=yt_category_id,
                    publish_at_rfc3339=None,
                    first_comment=yt_first_comment,
                    dry_run=dry_run
                )
                if res_yt.get("success"):
                    success_tasks += 1
                    print(f"     ✅ YouTube 성공: {res_yt.get('video_id', 'DRY-RUN')} (상태: {res_yt.get('status')})")
                else:
                    print(f"     ❌ YouTube 실패: {res_yt.get('error')}")

        ig_dup_marker = f"주간 브리핑 - {day_label}]"

        # 2. Instagram Carousel 업로드
        if platform in ("all", "instagram") and content_type in ("all", "carousel"):
            card_images = sorted(list(card_dir.glob("*.png"))) if card_dir.exists() else []
            if not card_images:
                print("   ⚠️ [Instagram 캐러셀] 카드뉴스 이미지(*.png)가 없어 건너뜁니다.")
            else:
                total_tasks += 1
                dup_carousel = (
                    ig_dup_checker.has_recent_duplicate("carousel", ig_dup_marker, today_date_kst)
                    if ig_dup_checker
                    else None
                )
                if dup_carousel:
                    success_tasks += 1
                    print(
                        f"   ⏭️ [Instagram 캐러셀 중복 방지] 오늘({today_date_kst}) 이미 동일 브리핑이 발행되어 건너뜁니다. "
                        f"(기존 ID: {dup_carousel.get('id')})"
                    )
                else:
                    image_urls = [get_github_raw_url(p) for p in card_images]
                    print(f"   📸 [Instagram 캐러셀] 즉시 공개 업로드 요청 중... (총 {len(card_images)}장)")
                    res_ig = upload_instagram_carousel(
                        image_urls=image_urls,
                        caption=caption,
                        scheduled_timestamp=None,
                        first_comment=first_comment,
                        dry_run=dry_run
                    )
                    if res_ig.get("success"):
                        success_tasks += 1
                        print(f"     ✅ Instagram 캐러셀 성공: ID {res_ig.get('container_id', 'DRY-RUN')}")
                    else:
                        print(f"     ❌ Instagram 캐러셀 실패: {res_ig.get('error')}")

        # 3. Instagram Reels 업로드
        skip_reels = getattr(args, "skip_reels", False)
        if skip_reels:
            print("   ⏩ [Instagram 릴스] --skip-reels 옵션이 활성화되어 릴스 발행을 건너뜁니다.")
        elif platform in ("all", "instagram") and content_type in ("all", "shorts", "video", "reel", "reels"):
            if not shorts_files:
                print("   ⚠️ [Instagram 릴스] 비디오 파일(.mp4)이 없어 건너뜁니다.")
            else:
                total_tasks += 1
                dup_reels = (
                    ig_dup_checker.has_recent_duplicate("reels", ig_dup_marker, today_date_kst)
                    if ig_dup_checker
                    else None
                )
                if dup_reels:
                    success_tasks += 1
                    print(
                        f"   ⏭️ [Instagram 릴스 중복 방지] 오늘({today_date_kst}) 이미 동일 브리핑이 발행되어 건너뜁니다. "
                        f"(기존 ID: {dup_reels.get('id')})"
                    )
                else:
                    video_url = get_github_raw_url(shorts_files[0])
                    ig_reels_comment = first_comment.replace("utm_medium=carousel", "utm_medium=reels")
                    print(f"   🎥 [Instagram 릴스] 즉시 공개 업로드 요청 중...")
                    res_reel = upload_instagram_reel(
                        video_url=video_url,
                        caption=caption,
                        scheduled_timestamp=None,
                        first_comment=ig_reels_comment,
                        dry_run=dry_run
                    )
                    if res_reel.get("success"):
                        success_tasks += 1
                        print(f"     ✅ Instagram 릴스 성공: ID {res_reel.get('container_id', 'DRY-RUN')}")
                    else:
                        print(f"     ❌ Instagram 릴스 실패: {res_reel.get('error')}")

    print("\n" + "=" * 70)
    failed_tasks = total_tasks - success_tasks
    print(f"🏁 [발행 파이프라인 결과] 총 {total_tasks}개 대상 작업 중 {success_tasks}건 완료!")
    if failed_tasks > 0:
        print(f"⚠️ [경고] {failed_tasks}건의 업로드 작업이 실패했습니다!")
    if dry_run:
        print("💡 [DRY-RUN 모드 안내] 실제 업로드는 수행되지 않았으며 스케줄과 메타데이터가 정상 검증되었습니다.")
        print("   실제 업로드를 진행하려면 --dry-run 플래그를 제외하고 실행해주세요.")
    print("=" * 70)

    # 실패 건이 있으면 비정상 종료 (GitHub Actions에서 Job 실패로 감지)
    if not dry_run and failed_tasks > 0:
        sys.exit(1)


def cmd_auth_yt(args):
    """YouTube Data API OAuth 인증 도우미"""
    from modules.youtube_uploader import authenticate_youtube
    reauth = getattr(args, "reauth", False)
    print("\n🔑 [YouTube Data API] OAuth 2.0 사용자 인증을 시작합니다...")
    service = authenticate_youtube(force_reauth=reauth)
    if service:
        print("\n🎉 [인증 완료] YouTube API 인증이 성공적으로 완료되었습니다!")
        print("   이제 'python curate.py upload --platform youtube'로 예약 업로드할 수 있습니다.")
    else:
        print("\n❌ [인증 실패] YouTube 인증에 실패했습니다. docs/api_setup_guide.md 를 참고해주세요.")


def cmd_test_insta(args):
    """Instagram Graph API 연결 진단 도우미"""
    from modules.instagram_uploader import test_instagram_connection
    print("\n🔍 [Instagram Graph API] 비즈니스 계정 및 토큰 연동 상태를 진단합니다...")
    ok = test_instagram_connection()
    if ok:
        print("\n🎉 [진단 통과] Instagram Graph API가 정상적으로 연동되어 있습니다!")
        print("   이제 'python curate.py upload --platform instagram'로 예약 업로드할 수 있습니다.")
    else:
        print("\n❌ [진단 실패] Instagram API 연결에 문제가 있습니다. docs/api_setup_guide.md 를 확인해주세요.")


def cmd_test_yt(args):
    """YouTube Data API OAuth 토큰 및 목표 채널(THEPT) 일치 여부 진단 도우미"""
    from modules.youtube_uploader import test_youtube_connection
    print("\n🔍 [YouTube Data API] OAuth 토큰 및 목표 채널(THEPT) 연동 상태를 진단합니다...")
    ok = test_youtube_connection()
    if not ok:
        sys.exit(1)


def cmd_analytics(args):
    """YouTube · Instagram 통합 SNS 성과 및 중복 업로드 리포트 수집"""
    from modules.sns_analytics import run_analytics_report
    limit = getattr(args, "limit", 20)
    save_report = getattr(args, "save_report", False)
    sync_log = getattr(args, "sync_log", False)
    print(f"\n📊 [SNS 성과 분석] 최근 {limit}건 기준 YouTube 및 Instagram 데이터를 수집합니다...")
    run_analytics_report(limit=limit, save_report=save_report, sync_log=sync_log)


def cmd_check(args):
    """통합 마케팅 컴플라이언스(THEPT뉴스 + 4THEPT마케팅 프리셋/초안) 및 쇼츠 60초 규격 검증"""
    from modules.marketing_compliance import (
        check_config_compliance,
        check_package_compliance,
        check_promo_compliance,
    )
    print("\n🛡️ [통합 컴플라이언스 & 품질 게이트] 설정 · THEPT뉴스 · 4THEPT마케팅 검증을 시작합니다...")
    total_errors = 0

    cfg_issues = check_config_compliance()
    if cfg_issues:
        for iss in cfg_issues:
            print(f"  ❌ [{iss.scope}] {iss.rule} -> {iss.excerpt}")
        total_errors += len(cfg_issues)
    else:
        print("  ✅ [config.py] 기본 광고·푸터·첫 댓글 컴플라이언스 통과 (위반 0건)")

    weekly_dir = find_active_weekly_dir(getattr(args, "date", None))
    day_folders = sorted(
        [d for d in weekly_dir.iterdir() if d.is_dir() and re.match(r"^\d{2,4}_", d.name)],
        key=lambda x: x.name,
    )
    for folder in day_folders:
        pkg_file = folder / "package_data.json"
        if not pkg_file.exists():
            continue
        pkg = json.loads(pkg_file.read_text(encoding="utf-8"))
        ig_cap = (folder / "instagram_caption.txt").read_text(encoding="utf-8") if (folder / "instagram_caption.txt").exists() else ""
        yt_cap = (folder / "youtube_shorts_caption.txt").read_text(encoding="utf-8") if (folder / "youtube_shorts_caption.txt").exists() else ""
        fc = (folder / "first_comment.txt").read_text(encoding="utf-8") if (folder / "first_comment.txt").exists() else ""
        res = check_package_compliance(pkg, ig_caption=ig_cap, yt_caption=yt_cap, first_comment=fc)
        if res["errors"]:
            total_errors += len(res["errors"])
            for err in res["errors"]:
                print(f"  ❌ [{folder.name}/{err.scope}] {err.rule} -> {err.excerpt}")
        elif res["warnings"]:
            warn_txt = ", ".join(w.rule for w in res["warnings"])
            print(f"  ⚠️ [{folder.name}] 경고 {len(res['warnings'])}건: {warn_txt}")
        else:
            print(f"  ✅ [{folder.name}] 통과 (예상 {res['estimated_seconds']:.1f}초)")

    promo_issues = check_promo_compliance(track=getattr(args, "track", "all"))
    if promo_issues:
        for p_iss in promo_issues:
            print(f"  ❌ [4THEPT/{p_iss.scope}:{p_iss.line_no}] {p_iss.rule} -> {p_iss.excerpt}")
        total_errors += len(promo_issues)
    else:
        print("  ✅ [4THEPT마케팅] 프리셋 · 플레이북 · 결과물/4THEPT마케팅/drafts 통과 (위반 0건)")

    if total_errors > 0:
        print(f"\n❌ 총 {total_errors}건의 컴플라이언스 오류가 발견되었습니다.")
        sys.exit(1)
    print("\n🎉 모든 컴플라이언스 필수 검사를 통과했습니다 (오류 0건).")


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


def cmd_export_yt_secrets(args):
    """GitHub Actions Secrets 등록용 Base64 환경 변수 문자열을 출력합니다."""
    import base64
    from config import YOUTUBE_TOKEN_FILE, YOUTUBE_CLIENT_SECRET_FILE

    token_path = Path(YOUTUBE_TOKEN_FILE)
    cs_path = Path(YOUTUBE_CLIENT_SECRET_FILE)

    print("\n" + "=" * 70)
    print("🔐 [YouTube GitHub Secrets] 설정 도우미")
    print("GitHub 저장소 -> Settings -> Secrets and variables -> Actions 로 이동 후")
    print("아래 2개의 Secret을 새로 등록해 주세요:")
    print("=" * 70)

    if token_path.exists():
        t_b64 = base64.b64encode(token_path.read_bytes()).decode("utf-8")
        print("\n1️⃣ Secret Name: YOUTUBE_TOKEN_BASE64")
        print("   Value (아래 한 줄 전체 복사):")
        print(t_b64)
    else:
        print("\n❌ token.pickle 파일이 없습니다. 먼저 python curate.py auth-yt 를 실행하세요.")

    if cs_path.exists():
        c_b64 = base64.b64encode(cs_path.read_bytes()).decode("utf-8")
        print("\n2️⃣ Secret Name: YOUTUBE_CLIENT_SECRET_BASE64")
        print("   Value (아래 한 줄 전체 복사):")
        print(c_b64)
    else:
        print("\n⚠️ client_secret.json 파일이 없습니다.")

    print("\n" + "=" * 70)
    print("✅ 등록 후 매일 아침 08:00 KST에 GitHub Actions가 유튜브와 인스타그램을 자동 발행합니다.")
    print("=" * 70 + "\n")


def cmd_sync(args):
    """GitHub 저장소와 주간 큐레이션 미디어를 동기화하고, Google Drive에 자동 백업합니다."""
    from modules.git_sync_manager import sync_weekly_output_to_github
    weekly_dir = find_active_weekly_dir(getattr(args, "date", None))
    dry_run = getattr(args, "dry_run", False)
    commit_msg = getattr(args, "message", None)
    retain_weeks = getattr(args, "retain", 4)
    sync_weekly_output_to_github(weekly_dir=weekly_dir, commit_msg=commit_msg, retain_weeks=retain_weeks, dry_run=dry_run)

    # Google Drive 자동 백업 업로드
    skip_gdrive = getattr(args, "skip_gdrive", False)
    if not skip_gdrive:
        from modules.gdrive_uploader import sync_weekly_to_gdrive
        sync_weekly_to_gdrive(weekly_dir=weekly_dir, dry_run=dry_run)


def cmd_auth_gdrive(args):
    """Google Drive API OAuth 최초 1회 브라우저 인증 도우미"""
    from modules.gdrive_uploader import authenticate_gdrive
    print("\n🔑 [Google Drive API] OAuth 2.0 사용자 인증을 시작합니다...")
    service = authenticate_gdrive()
    if service:
        print("\n🎉 [인증 완료] Google Drive API 인증이 성공적으로 완료되었습니다!")
        print("   이제 'python curate.py sync' 실행 시 구글 드라이브로 자동 백업됩니다.")
    else:
        print("\n❌ [인증 실패] Google Drive 인증에 실패했습니다. client_secret.json 파일 및 API 활성화 상태를 확인해주세요.")


def main():
    parser = argparse.ArgumentParser(
        description="THEPT 주 6일 6대 카테고리 2단계 마크다운 큐레이션 및 자동 발행 도구"
    )
    subparsers = parser.add_subparsers(dest="command", help="실행할 작업 선택")

    # 1. fetch
    p_fetch = subparsers.add_parser("fetch", help="1단계: 6대 카테고리 요일별 15~30건 후보 수집 및 제목 마크다운 생성")
    p_fetch.add_argument("--count", type=int, default=25, help="카테고리당 수집 건수 (기본 25건, 15~30건 범위)")
    p_fetch.add_argument("--date", type=str, default=None, help="대상 주간 날짜 (기본값: 오늘 YYYY-MM-DD)")

    # 2. review (선택적 보조 단계)
    p_review = subparsers.add_parser("review", help="(선택) 1차 선택 기사 상세 본문/사진 크롤링 및 candidates_detail.md 생성")
    p_review.add_argument("--date", type=str, default=None, help="대상 주간 날짜 (기본값: 최신 주차)")

    # 3. build
    p_build = subparsers.add_parser("build", help="2단계(핵심): candidates_titles.md [x] 기반 주 6일 콘텐츠 일괄 제작")
    p_build.add_argument("--day", "--target-date", type=str, default=None, help="특정 날짜만 단독 빌드/렌더링 (4자리 MMDD 예: 0917, 9/17)")
    p_build.add_argument("--render", action="store_true", default=False, help="카드뉴스 PNG 및 쇼츠 MP4 미디어 렌더링까지 즉시 수행")
    p_build.add_argument("--sync", action="store_true", default=False, help="빌드 및 렌더링 완료 후 GitHub 원격 저장소 푸시까지 즉시 연계 실행")
    p_build.add_argument("--from-detail", action="store_true", default=False, help="(선택) candidates_titles.md 대신 candidates_detail.md 기준으로 빌드")
    p_build.add_argument("--date", type=str, default=None, help="대상 주간 날짜 (기본값: 최신 주차 YYYY-MM-DD 또는 단독 날짜 MMDD)")

    # 4. upload
    p_upload = subparsers.add_parser("upload", help="주간 콘텐츠(카드뉴스/쇼츠)를 유튜브 및 인스타그램에 자동 예약 업로드")
    p_upload.add_argument("--date", type=str, default=None, help="대상 주간 날짜 (YYYY-MM-DD) 또는 특정 날짜 (MMDD 예: 0917)")
    p_upload.add_argument("--platform", type=str, default="all", choices=["all", "youtube", "instagram"], help="대상 플랫폼 선택 (all, youtube, instagram)")
    p_upload.add_argument("--type", type=str, default="all", choices=["all", "carousel", "shorts", "video"], help="대상 콘텐츠 유형 (all, carousel, shorts)")
    p_upload.add_argument("--today-only", action="store_true", default=False, help="오늘 날짜(KST 기준 MMDD)에 해당하는 콘텐츠 1건만 즉시 발행")
    p_upload.add_argument("--day", "--target-date", type=str, default=None, help="특정 날짜 지정 발행 (4자리 MMDD 예: 0917, 9/17)")
    p_upload.add_argument("--category", "--yt-category", type=str, default=None, help="유튜브 업로드 카테고리 ID 수동 지정 (기본값: 요일별 테마 자동 할당)")
    p_upload.add_argument("--skip-reels", action="store_true", default=False, help="인스타그램 릴스 발행을 건너뛰고 캐러셀 피드 및 유튜브 쇼츠만 선별 발행")
    p_upload.add_argument("--allow-duplicate", action="store_true", default=False, help="당일 동일 Instagram 브리핑 중복 방지 가드를 해제하고 강제 재업로드")
    p_upload.add_argument("--force-local", action="store_true", default=False, help="로컬 개발 환경에서 실제 API 발행을 비상 허용")
    p_upload.add_argument("--dry-run", action="store_true", default=False, help="실제 API 호출 없이 예약 스케줄 및 업로드 매핑 시뮬레이션")

    # 5. sync
    p_sync = subparsers.add_parser("sync", help="GitHub 저장소와 주간 미디어 동기화, Google Drive 자동 백업 및 4주 롤링 슬림화")
    p_sync.add_argument("--date", type=str, default=None, help="대상 주간 날짜 (기본값: 최신 주차)")
    p_sync.add_argument("--message", "-m", type=str, default=None, help="커밋 메시지 직접 지정")
    p_sync.add_argument("--retain", type=int, default=4, help="활성 유지할 주간 폴더 수 (기본 4주)")
    p_sync.add_argument("--skip-gdrive", action="store_true", default=False, help="Google Drive 자동 업로드를 건너뜁니다.")
    p_sync.add_argument("--dry-run", action="store_true", default=False, help="실제 Git 커밋/푸시 및 업로드 없이 시뮬레이션만 수행")

    # 6. auth-yt
    p_auth_yt = subparsers.add_parser("auth-yt", help="YouTube Data API OAuth 최초 1회 브라우저 인증 도우미")
    p_auth_yt.add_argument("--reauth", action="store_true", default=False, help="기존 token.pickle을 백업하고 브라우저에서 채널을 새로 인증")

    # 7. auth-gdrive
    p_auth_gd = subparsers.add_parser("auth-gdrive", help="Google Drive API OAuth 최초 1회 브라우저 인증 도우미")

    # 8. test-insta & test-yt
    p_test_insta = subparsers.add_parser("test-insta", help="Instagram Graph API 토큰 및 비즈니스 계정 연결 진단 도우미")
    p_test_yt = subparsers.add_parser("test-yt", help="YouTube OAuth 토큰 및 목표 채널(THEPT) 일치 여부 진단")

    # 9. analytics & check
    p_analytics = subparsers.add_parser("analytics", help="YouTube · Instagram 최근 성과 및 중복 업로드 리포트 조회")
    p_analytics.add_argument("--limit", type=int, default=20, help="조회할 최근 게시물/영상 수 (기본 20건)")
    p_analytics.add_argument("--save-report", action="store_true", default=False, help="결과물/THEPT뉴스/analytics_report.md 및 4THEPT마케팅 스냅샷 저장")
    p_analytics.add_argument("--sync-log", action="store_true", default=False, help="promo_4thept/campaigns/publish_log.md 성과 수치 동기화")

    p_check = subparsers.add_parser("check", help="통합 마케팅 컴플라이언스(THEPT뉴스 + 4THEPT마케팅) 및 쇼츠 60초 규격 검증")
    p_check.add_argument("--date", type=str, default=None, help="대상 주간 날짜 (기본값: 최신 주차)")
    p_check.add_argument("--track", choices=("all", "hospital", "center"), default="all", help="4THEPT 검증 트랙")

    # 10. stats
    p_stats = subparsers.add_parser("stats", help="누적된 큐레이션 데이터셋 통계 확인")

    # 11. export-yt-secrets
    p_secrets = subparsers.add_parser("export-yt-secrets", help="GitHub Actions Secrets 등록용 YouTube 토큰 Base64 출력 도우미")

    args = parser.parse_args()

    if args.command == "fetch":
        cmd_fetch(args)
    elif args.command == "review":
        asyncio.run(cmd_review_async(args))
    elif args.command == "build":
        cmd_build(args)
    elif args.command == "upload":
        cmd_upload(args)
    elif args.command == "sync":
        cmd_sync(args)
    elif args.command == "auth-yt":
        cmd_auth_yt(args)
    elif args.command == "auth-gdrive":
        cmd_auth_gdrive(args)
    elif args.command == "test-insta":
        cmd_test_insta(args)
    elif args.command == "test-yt":
        cmd_test_yt(args)
    elif args.command == "analytics":
        cmd_analytics(args)
    elif args.command == "check":
        cmd_check(args)
    elif args.command == "stats":
        cmd_stats(args)
    elif args.command == "export-yt-secrets":
        cmd_export_yt_secrets(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
