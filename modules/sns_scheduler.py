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
    "화요일": 1, "02_Tue_Clinical": 1, "02_Tue_Creator": 1,
    "수요일": 2, "03_Wed_Sports": 2,
    "목요일": 3, "04_Thu_Tech": 3,
    "금요일": 4, "05_Fri_YouTube": 4, "05_Fri_Celeb": 4,
    "토요일": 5, "06_Sat_Global": 5,
}


def get_schedule_for_day(
    day_name_or_folder: str,
    base_date: Optional[datetime] = None,
    target_hour: int = PUBLISH_HOUR_KST
) -> dict:
    """
    지정된 요일 또는 폴더명의 예약 발행 일시를 계산합니다.
    - [일요일 실행 시]: 다가오는 주간(월~토) 6일 전체를 순차적으로 오전 target_hour 시(KST)에 예약 발행합니다.
    - [평일 실행 시 (월~토)]:
        * 오늘 및 이미 지난 요일(target_weekday <= current_weekday): 즉시 업로드 (is_immediate=True)
          (예: 월요일 시작 시 월요일 즉시, 화요일 시작 시 월/화 즉시, 수요일 시작 시 월/화/수 즉시 등)
        * 오늘 이후의 미래 요일(target_weekday > current_weekday): 이번 주 해당 요일 오전 target_hour 시 예약 발행
    """
    now_kst = datetime.now(KST)
    base = base_date if base_date else now_kst

    target_weekday = DAY_MAP.get(day_name_or_folder)
    if target_weekday is None:
        low = day_name_or_folder.lower()
        if "mon" in low or "월" in low:
            target_weekday = 0
        elif "tue" in low or "화" in low:
            target_weekday = 1
        elif "wed" in low or "수" in low:
            target_weekday = 2
        elif "thu" in low or "목" in low:
            target_weekday = 3
        elif "fri" in low or "금" in low:
            target_weekday = 4
        elif "sat" in low or "토" in low:
            target_weekday = 5
        else:
            target_weekday = 0
    current_weekday = base.weekday()

    if current_weekday == 6:
        # [일요일 실행]: 내일(월요일)부터 시작하는 다가오는 주간 6일 순차 예약
        days_to_monday = 1
        monday_date = (base + timedelta(days=days_to_monday)).replace(
            hour=target_hour, minute=0, second=0, microsecond=0
        )
        target_date = monday_date + timedelta(days=target_weekday)
        is_immediate = False
    else:
        # [평일 실행 (월~토)]:
        if target_weekday <= current_weekday:
            # 월요일 시작 시 월요일 즉시, 화요일 시작 시 월/화 즉시 등
            is_immediate = True
            target_date = now_kst
        else:
            # 이번 주 남은 요일: 이번 주 해당 요일 오전 target_hour 시 예약
            is_immediate = False
            days_diff = target_weekday - current_weekday
            target_date = (base + timedelta(days=days_diff)).replace(
                hour=target_hour, minute=0, second=0, microsecond=0
            )

    if is_immediate:
        day_korean = ["월", "화", "수", "목", "금", "토", "일"][target_weekday]
        return {
            "target_datetime": target_date,
            "unix_timestamp": None,
            "rfc3339": None,
            "is_immediate": True,
            "formatted_kst": f"[즉시 업로드] ({day_korean}요일 콘텐츠 즉시 공개)"
        }
    else:
        unix_timestamp = int(target_date.timestamp())
        rfc3339_str = target_date.isoformat()
        return {
            "target_datetime": target_date,
            "unix_timestamp": unix_timestamp,
            "rfc3339": rfc3339_str,
            "is_immediate": False,
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
