# 이 모듈은 주간 6일 콘텐츠의 요일별 SNS 발행 일시 및 인스타그램용 공개 GitHub Raw URL을 계산합니다.
# YouTube 및 Meta Graph API 규격에 맞는 RFC 3339 및 UNIX Timestamp 스케줄 정보를 자동 생성합니다.

import sys
from pathlib import Path
from datetime import datetime, timedelta, timezone
from typing import Optional

sys.path.append(str(Path(__file__).resolve().parent.parent))
from config import BASE_DIR, GITHUB_REPO, GITHUB_BRANCH, PUBLISH_HOUR_KST

# 한국 표준시 (KST = UTC+9)
KST = timezone(timedelta(hours=9))

# 요일 인덱스 매핑 (월=0, 화=1, 수=2, 목=3, 금=4, 토=5, 일=6)
DAY_MAP = {
    "월요일": 0, "01_Mon_Policy": 0,
    "화요일": 1, "02_Tue_Creator": 1,
    "수요일": 2, "03_Wed_Sports": 2,
    "목요일": 3, "04_Thu_Tech": 3,
    "금요일": 4, "05_Fri_Celeb": 4,
    "토요일": 5, "06_Sat_Global": 5,
}


def get_schedule_for_day(
    day_name_or_folder: str,
    base_date: Optional[datetime] = None,
    target_hour: int = PUBLISH_HOUR_KST
) -> dict:
    """
    지정된 요일 또는 폴더명의 예약 발행 일시를 계산합니다.
    - base_date 기준으로 해당 주차의 해당 요일 오전 target_hour 시(KST)를 산출합니다.
    - YouTube용 RFC 3339 및 Instagram용 UNIX Timestamp를 함께 반환합니다.
    """
    now_kst = datetime.now(KST)
    base = base_date if base_date else now_kst

    target_weekday = DAY_MAP.get(day_name_or_folder, 0)
    current_weekday = base.weekday()

    # 이번 주 해당 요일 날짜 산출 (월요일 기준)
    days_diff = target_weekday - current_weekday
    target_date = (base + timedelta(days=days_diff)).replace(
        hour=target_hour, minute=0, second=0, microsecond=0
    )

    # 만약 목표 예약 시각이 현재보다 과거라면 (이미 지난 요일),
    # 안전하게 다음 주 동일 요일로 배정하거나 현재 시각 기준 최소 지연 시각을 고려합니다.
    if target_date <= now_kst:
        # 이미 오늘 오전 8시가 지난 경우 다음 주 해당 요일로 스케줄링
        target_date += timedelta(days=7)

    # 타임스탬프 및 형식 변환
    unix_timestamp = int(target_date.timestamp())
    # YouTube API: RFC 3339 형식 (예: 2026-09-08T08:00:00+09:00)
    rfc3339_str = target_date.isoformat()

    return {
        "target_datetime": target_date,
        "unix_timestamp": unix_timestamp,
        "rfc3339": rfc3339_str,
        "formatted_kst": target_date.strftime("%Y년 %m월 %d일 (%a) %H:%M KST")
    }


def get_github_raw_url(local_path: Path) -> str:
    """
    로컬 파일의 경로를 GitHub 저장소 공개 Raw URL로 변환합니다.
    (인스타그램 Graph API의 image_url / video_url 파라미터 요구조건 충족)
    """
    local_resolved = local_path.resolve()
    base_resolved = BASE_DIR.resolve()

    try:
        rel_path = local_resolved.relative_to(base_resolved).as_posix()
    except ValueError:
        rel_path = local_path.name

    return f"https://raw.githubusercontent.com/{GITHUB_REPO}/{GITHUB_BRANCH}/{rel_path}"


def get_all_weekly_schedules(base_date: Optional[datetime] = None) -> dict:
    """주간 6개 요일(월~토)의 전체 예약 스케줄 딕셔너리를 반환합니다."""
    schedules = {}
    for day_name in ["월요일", "화요일", "수요일", "목요일", "금요일", "토요일"]:
        schedules[day_name] = get_schedule_for_day(day_name, base_date=base_date)
    return schedules
