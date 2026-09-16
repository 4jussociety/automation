# 이 모듈은 요일 검색어(영문/한글/날짜/번호 등)와 콘텐츠 폴더 간의 유연한 일치 여부를 판정합니다.
# 빌드, 렌더링, SNS 업로드 파이프라인에서 특정 요일 선별 필터링 기능에 사용됩니다.

import re


def match_day_filter(query: str, cat_key: str, day_name: str, folder_name: str) -> bool:
    """
    요일 검색어(query)가 특정 요일과 일치하는지 유연하게 판정합니다.
    - 날짜: '0910', '9/10', '9-10', '10', '10일' 등
    - 영문: 'mon', 'tue', 'wed', 'thu', 'fri', 'sat'
    - 한글: '월', '화', '수', '목', '금', '토', '월요일', '목요일' 등
    - 번호: '1', '2', '3', '4', '5', '6', '01', '02', '03', '04', '05', '06'
    - 폴더/카테고리명: '0910_Thu_Tech', '04_Thu_Tech', 'thu_tech', 'sports' 등
    """
    if not query:
        return True
    raw_q = query.strip().lower()

    # 쉼표(,) 구분자로 복수 요일 지정 지원 (예: 'thu,fri,sat', '목,금,토', '10,11,12')
    if "," in raw_q:
        return any(
            match_day_filter(part.strip(), cat_key, day_name, folder_name)
            for part in raw_q.split(",")
            if part.strip()
        )

    # 날짜 정규화 ('9/10', '09-10' -> '0910', '10일' -> '10')
    q = raw_q.replace("일", "").strip()
    m_date = re.match(r"^(\d{1,2})[/.-](\d{1,2})$", q)
    if m_date:
        q = f"{int(m_date.group(1)):02d}{int(m_date.group(2)):02d}"

    # 1. 4자리 MMDD 날짜 매칭 (예: '0910')
    if len(q) == 4 and q.isdigit():
        if q in folder_name.lower():
            return True

    # 2. 1~2자리 일(Day) 매칭 (예: '10' -> '0910_Thu_Tech'의 10일)
    if q.isdigit() and len(q) <= 2:
        m_folder_day = re.match(r"^\d{2}(\d{2})_", folder_name)
        if m_folder_day and int(m_folder_day.group(1)) == int(q):
            return True

    # 3. 요일별 키워드 매핑 테이블
    alias_map = {
        "mon_policy": ["mon", "월", "월요일", "1", "01", "policy", "정책", "수가"],
        "tue_clinical": ["tue", "화", "화요일", "2", "02", "clinical", "임상", "도수", "creator"],
        "wed_sports": ["wed", "수", "수요일", "3", "03", "sports", "스포츠", "운동"],
        "thu_tech": ["thu", "목", "목요일", "4", "04", "tech", "기술", "ai", "로봇"],
        "fri_celeb": ["fri", "금", "금요일", "5", "05", "celeb", "셀럽", "스타", "youtube", "유튜브"],
        "sat_global": ["sat", "토", "토요일", "6", "06", "global", "글로벌", "해외"],
    }

    # cat_key 기준 별칭 검사
    for key, aliases in alias_map.items():
        if key in cat_key or cat_key in key:
            if q in aliases or any(q == a for a in aliases):
                return True

    # 폴더명(0910_Thu_Tech) 등 문자열 포함 검사
    folder_low = folder_name.lower()
    day_low = day_name.lower()
    cat_low = cat_key.lower()

    if q in folder_low or q in day_low or q in cat_low:
        return True

    # 한글 요일 축약 매칭 (예: '목' in '목요일')
    for d_char in ["월", "화", "수", "목", "금", "토"]:
        if q == d_char and d_char in day_name:
            return True

    return False
