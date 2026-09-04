# 주간 콘텐츠(월수금 쇼츠/릴스, 화목토 카드뉴스 오전 8시) 예약 발행 일정 계산 모듈
import sys
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from datetime import datetime, timedelta
from typing import Dict, Any

def get_next_weekly_schedule(base_date: datetime = None) -> Dict[str, Dict[str, Any]]:
    """
    기준 일자(기본: 현재 날짜)를 기준으로 차주 월요일부터 토요일까지의
    오전 8:00 예약 발행 일정을 계산합니다.

    [편성표]
    - 월요일 08:00: Set 1 쇼츠 / 릴스 (국내 정책·보험)
    - 화요일 08:00: Set 1 카드뉴스 캐러셀 (국내 정책·보험)
    - 수요일 08:00: Set 2 쇼츠 / 릴스 (국내 임상·연구)
    - 목요일 08:00: Set 2 카드뉴스 캐러셀 (국내 임상·연구)
    - 금요일 08:00: Set 3 쇼츠 / 릴스 (해외 동향·논문)
    - 토요일 08:00: Set 3 카드뉴스 캐러셀 (해외 동향·논문)
    """
    if base_date is None:
        base_date = datetime.now()

    # 기준일(보통 일요일) 이후 다가오는 첫 월요일(weekday = 0) 탐색
    days_ahead = 0 - base_date.weekday()
    if days_ahead <= 0:  # 오늘이 월요일이거나 그 이후면 다음 주 월요일로
        days_ahead += 7
    
    # 만약 일요일(weekday=6)에 실행하면 +1일이 다음 날 월요일
    if base_date.weekday() == 6:
        next_monday = base_date + timedelta(days=1)
    else:
        next_monday = base_date + timedelta(days=days_ahead)

    # 오전 8시 정각 기준 설정
    monday_8am = next_monday.replace(hour=8, minute=0, second=0, microsecond=0)

    schedule = {
        "set1": {
            "video": {
                "target_datetime": monday_8am,
                "day_name": "월요일",
                "label": "Set 1 [국내정책·보험] 쇼츠/릴스",
                "rfc3339": monday_8am.strftime("%Y-%m-%dT%H:%M:%S+09:00"),
                "date_str": monday_8am.strftime("%Y-%m-%d"),
                "time_str": "08:00 AM",
            },
            "carousel": {
                "target_datetime": monday_8am + timedelta(days=1),
                "day_name": "화요일",
                "label": "Set 1 [국내정책·보험] 카드뉴스",
                "rfc3339": (monday_8am + timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%S+09:00"),
                "date_str": (monday_8am + timedelta(days=1)).strftime("%Y-%m-%d"),
                "time_str": "08:00 AM",
            }
        },
        "set2": {
            "video": {
                "target_datetime": monday_8am + timedelta(days=2),
                "day_name": "수요일",
                "label": "Set 2 [국내임상·연구] 쇼츠/릴스",
                "rfc3339": (monday_8am + timedelta(days=2)).strftime("%Y-%m-%dT%H:%M:%S+09:00"),
                "date_str": (monday_8am + timedelta(days=2)).strftime("%Y-%m-%d"),
                "time_str": "08:00 AM",
            },
            "carousel": {
                "target_datetime": monday_8am + timedelta(days=3),
                "day_name": "목요일",
                "label": "Set 2 [국내임상·연구] 카드뉴스",
                "rfc3339": (monday_8am + timedelta(days=3)).strftime("%Y-%m-%dT%H:%M:%S+09:00"),
                "date_str": (monday_8am + timedelta(days=3)).strftime("%Y-%m-%d"),
                "time_str": "08:00 AM",
            }
        },
        "set3": {
            "video": {
                "target_datetime": monday_8am + timedelta(days=4),
                "day_name": "금요일",
                "label": "Set 3 [해외동향·논문] 쇼츠/릴스",
                "rfc3339": (monday_8am + timedelta(days=4)).strftime("%Y-%m-%dT%H:%M:%S+09:00"),
                "date_str": (monday_8am + timedelta(days=4)).strftime("%Y-%m-%d"),
                "time_str": "08:00 AM",
            },
            "carousel": {
                "target_datetime": monday_8am + timedelta(days=5),
                "day_name": "토요일",
                "label": "Set 3 [해외동향·논문] 카드뉴스",
                "rfc3339": (monday_8am + timedelta(days=5)).strftime("%Y-%m-%dT%H:%M:%S+09:00"),
                "date_str": (monday_8am + timedelta(days=5)).strftime("%Y-%m-%d"),
                "time_str": "08:00 AM",
            }
        }
    }

    return schedule

def print_weekly_schedule(schedule: Dict[str, Dict[str, Any]]):
    """주간 편성표를 콘솔에 보기 쉽게 출력합니다."""
    print("\n" + "─" * 65)
    print(" 📅 [주간 자동 예약 발행 편성표 (매일 오전 08:00)]")
    print("─" * 65)
    order = [
        ("set1", "video"),
        ("set1", "carousel"),
        ("set2", "video"),
        ("set2", "carousel"),
        ("set3", "video"),
        ("set3", "carousel"),
    ]
    for s_key, c_key in order:
        item = schedule[s_key][c_key]
        dt = item["target_datetime"]
        print(f" • {dt.strftime('%m/%d')}({item['day_name']}) 08:00 AM ➔ {item['label']}")
    print("─" * 65 + "\n")

if __name__ == "__main__":
    sch = get_next_weekly_schedule()
    print_weekly_schedule(sch)
