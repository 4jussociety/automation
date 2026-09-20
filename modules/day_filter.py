# 이 모듈은 날짜 검색어(4자리 MMDD 또는 M/D 등)와 콘텐츠 폴더(예: 0917_Thu_Tech) 간의 일치 여부를 판정합니다.
# 빌드, 렌더링, SNS 업로드 파이프라인에서 특정 날짜 선별 필터링 기능에 사용됩니다.

import re


def match_day_filter(query: str, cat_key: str = "", day_name: str = "", folder_name: str = "") -> bool:
    """
    날짜 검색어(query: '0917', '9/17', '9-17' 등)가 폴더명(예: '0917_Thu_Tech')과 일치하는지 판정합니다.
    폴더명 맨 앞 4자리 MMDD 접두어 일치(f"{mmdd}_")를 기준으로 명확하고 간결하게 동작합니다.
    """
    if not query:
        return True
    raw_q = query.strip()

    # 쉼표(,) 구분자로 복수 날짜 지정 지원 (예: '0917,0918')
    if "," in raw_q:
        return any(
            match_day_filter(part.strip(), cat_key, day_name, folder_name)
            for part in raw_q.split(",")
            if part.strip()
        )

    # 날짜 정규화 ('9/17', '9-17', '09.17' -> '0917')
    m_date = re.match(r"^(\d{1,2})[/.-](\d{1,2})$", raw_q)
    if m_date:
        q = f"{int(m_date.group(1)):02d}{int(m_date.group(2)):02d}"
    else:
        q = raw_q

    # 폴더명 접두어(예: '0917_') 또는 폴더명 내 MMDD 포함 판정
    folder_low = folder_name.lower()
    return folder_low.startswith(f"{q}_") or q in folder_low

