# 이 파일은 주간 물리치료 콘텐츠 자동 생성 시스템의 메인 CLI 진입점입니다.
# 월수금 쇼츠 & 화목토 카드뉴스 주간 6일 연계 콘텐츠를 주 1회 일괄 자동 생성합니다.

import sys
from pathlib import Path
import asyncio
import argparse

# 윈도우 콘솔 UTF-8 출력 보장
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from pipeline import run_weekly_pipeline


def main():
    parser = argparse.ArgumentParser(
        description="THEPT 주간 물리치료 뉴스 자동화 콘텐츠 생성기 (월수금 쇼츠 & 화목토 카드뉴스)"
    )
    parser.add_argument(
        "--policy-keywords",
        nargs="+",
        default=None,
        help="배치 1 (국내 정책·제도) 검색 키워드 목록"
    )
    parser.add_argument(
        "--clinical-keywords",
        nargs="+",
        default=None,
        help="배치 2 (임상 연구·첨단 기술) 검색 키워드 목록"
    )
    parser.add_argument(
        "--global-keywords",
        nargs="+",
        default=None,
        help="배치 3 (해외 글로벌 트렌드) 검색 키워드 목록"
    )
    args = parser.parse_args()

    try:
        results = asyncio.run(run_weekly_pipeline(
            domestic_keywords_a=args.policy_keywords,
            domestic_keywords_b=args.clinical_keywords,
            global_keywords=args.global_keywords
        ))
        print("\n🎉 [성공] 주간 6일 연계 콘텐츠가 성공적으로 생성되었습니다!")
        print(f"👉 마스터 저장 폴더: {results['weekly_dir']}")
        print(f"👉 주간 출처/스케줄: {results['sources_file']}")

    except Exception as e:
        print(f"\n❌ [오류 발생] 파이프라인 실행 중 문제가 발생했습니다: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

