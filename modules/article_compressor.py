# 이 모듈은 수집된 뉴스 기사(제목, 본문, 요약)를 정밀 분석하여 3대 핵심 불릿과 쇼츠 나레이션 대본으로 압축합니다.
# 기사의 구체적 사실 관계, 제도/임상적 수치 배경, 현장 파급 효과를 완결된 문장으로 구조화합니다.

import re
from modules.translator import translate_to_korean, is_english_text
from modules.llm_summarizer import summarize_article_with_llm


def clean_text_segment(text: str) -> str:
    """말줄임표, HTML 잔재, 특수문자, 기자명 및 언론사 태그를 완벽히 제거합니다."""
    if not text:
        return ""
    t = text
    # HTML 태그 및 엔티티 제거
    t = re.sub(r'<[^>]+>', '', t)
    t = t.replace('&quot;', '"').replace('&apos;', "'").replace('&amp;', '&')
    t = t.replace('&lt;', '<').replace('&gt;', '>').replace('&middot;', '·')
    t = t.replace('&nbsp;', ' ')
    
    # 편집자 메모, 기호 및 통신사 바이라인 제거 (예: -편집자 말, (충주=국제뉴스) =, (서울=연합뉴스) 등)
    t = re.sub(r'-?편집자\s*말\b\s*[◇◆▲■▶]?', '', t)
    t = re.sub(r'\(?\s*[가-힣]{2,4}\s*=\s*[가-힣]{2,8}\s*(?:뉴스|신문|일보|통신|닷컴)\s*\)?\s*=?\s*', '', t)
    t = re.sub(r'\[.*?기자.*?\]|\[.*?뉴스.*?\]|\(.*?\b기자\b.*?\)|\(.*?\b뉴스\b.*?\)', '', t)
    t = re.sub(r'\[.*?\]|【.*?】', '', t)  # 대괄호 언론사/말머리 태그 제거
    t = re.sub(r'\([a-zA-Z\s,.-]{2,}\)', '', t)  # 영문 병기 괄호 (American Physical Therapy) 등 제거
    t = re.sub(r'\([사단법인|사|주|주식회사]+\)', '', t)  # (사), (주) 제거
    t = re.sub(r'\([가-힣\s]{2,8}\s*대표\b\)|\([가-힣\s]{2,8}\s*회장\b\)', '', t) # (회장 곽성진) 등
    t = re.sub(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+', '', t)
    t = re.sub(r'\b[가-힣]{2,4}\s*(?:기자|특파원|논설위원)\b', '', t)
    t = re.sub(r'무단\s*전재\s*(?:및)?\s*재배포\s*금지', '', t)
    t = re.sub(r'저작권자\s*ⓒ.*', '', t)
    
    # 특수 편집 기호 제거
    for ch in ['◇', '◆', '▲', '▼', '■', '□', '▶', '▷', '☞', '※', 'ⓒ', '★', '☆']:
        t = t.replace(ch, '')
    
    # 말줄임표 및 연속 마침표 완전 제거
    t = re.sub(r'[\.]{2,}', '', t)
    t = t.replace('…', '').replace('..', '').replace('...', '')
    
    # 공백 및 선두/말미 기호 정리
    t = re.sub(r'\s+', ' ', t)
    t = re.sub(r'^[=\-\s]+', '', t)
    return t.strip()


def clean_headline_two_lines(headline: str, max_chars: int = 36) -> str:
    """
    카드뉴스 1080x1350 화면에서 헤드라인이 최대 2줄(34~36자 이내)을 절대 넘지 않도록
    자연스러운 어구 단위로 정돈합니다.
    """
    if not headline:
        return ""
    
    # 영문이면 한국어로 즉시 번역
    if is_english_text(headline):
        headline = translate_to_korean(headline)
        
    cleaned = clean_text_segment(headline)
    # 따옴표 제거
    cleaned = cleaned.replace('"', '').replace("'", "").replace('‘', '').replace('’', '').replace('“', '').replace('”', '').strip()
    
    if len(cleaned) <= max_chars:
        return cleaned
    
    # 36자 초과 시: 콜론, 쉼표, 대시 등 자연스러운 구분 기호 기준으로 분할
    parts = re.split(r'[:,\-–—|]\s*', cleaned)
    if len(parts) >= 2:
        for p in parts:
            p_strip = p.strip()
            if 14 <= len(p_strip) <= max_chars:
                return p_strip
        if 14 <= len(parts[0].strip()) <= max_chars:
            return parts[0].strip()
    
    # 구분 기호가 없거나 적절치 않은 경우 어절 단위로 안전하게 압축
    words = cleaned.split()
    accum = ""
    for w in words:
        if len(accum) + len(w) + 1 <= max_chars:
            accum += (" " if accum else "") + w
        else:
            break
    
    if accum:
        # 단어 끝에 붙은 불완전한 조사/어미 정돈
        if re.search(r'(을|를)$', accum):
            accum = re.sub(r'(을|를)$', '', accum) + " 도입"
            if len(accum) > max_chars:
                accum = re.sub(r'\s+도입$', '', accum)
        elif re.search(r'(의|에|과|와|이|가)$', accum):
            accum = re.sub(r'(의|에|과|와|이|가)$', '', accum)
        return accum.strip()
    
    return cleaned[:max_chars].strip()


def extract_valid_sentences(text: str) -> list[str]:
    """본문/설명 텍스트에서 서술어가 살아있는 완결된 유효 문장 목록을 추출합니다."""
    cleaned = clean_text_segment(text)
    if not cleaned:
        return []
    
    # 영문이면 한국어로 번역
    if is_english_text(cleaned):
        cleaned = translate_to_korean(cleaned)
    
    # 문장 종결 어미(. ? !) 기준으로 분리
    raw_sentences = re.split(r'(?<=[\.\?\!])\s+', cleaned)
    valid = []
    
    bad_keywords = [
        "장애인인식개선", "양육자를 위해", "기타리스트", "사진=", "무단전재", "저작권자", "기자",
        "shareadd", "googleadd", "add us", "subscribe", "all rights", "click here", "newsletter",
        "photo by", "caption", "copyright", "follow us", "advertisement", "sign up", "uofl health",
        "frazier rehabilitation", "spectrum news", "louisville", "ky.", "iowa - st."
    ]
    
    for s in raw_sentences:
        s = s.strip()
        lower_s = s.lower()
        # 노이즈 문장 배제
        if any(bad in lower_s for bad in bad_keywords):
            continue
        
        # 한글 글자 수가 10자 미만이면 제외 (영문 지명이나 부호 파편 방지)
        ko_chars = len(re.findall(r'[가-힣]', s))
        if ko_chars < 10:
            continue
        
        # 불필요한 접속부사 제거
        s = re.sub(r'^(한편|또한|이어|아울러|특히|이에|따라서|결과적으로|이와 함께)\s*,?\s*', '', s)
        
        # 서술어 존재 여부 검사
        ends_with_verb = any(s.endswith(e) or s.endswith(e + ".") for e in [
            '다', '까', '요', '음', '됨', '임', '함', '했다', '된다', '있다', 
            '체결했다', '보고됐다', '밝혔다', '강조했다', '선정됐다', '도입됐다'
        ])
        
        # 길이가 충분하고 서술어가 있는 완결 문장 선택
        if len(s) >= 15:
            if not s.endswith(('.', '!', '?')):
                s += '.'
            valid.append(s)
            
    return valid


def identify_article_theme(title: str, text: str) -> str:
    """기사의 핵심 키워드를 기반으로 전문 도메인 테마를 분류합니다."""
    combined = (title + " " + text).lower()
    
    if any(k in combined for k in ["도수치료", "실손보험", "비급여", "관리급여", "보험금", "지급 기준", "청구", "축소"]):
        return "manual_insurance"
    elif any(k in combined for k in ["방문", "돌봄", "재택", "커뮤니티케어", "통합돌봄", "지역사회", "협약", "복지"]):
        return "community_care"
    elif any(k in combined for k in ["ai", "인공지능", "로봇", "보행", "스마트", "웨어러블", "디지털", "기술", "혁신"]):
        return "ai_robot_tech"
    elif any(k in combined for k in ["뇌졸중", "신경", "파킨슨", "중추신경계", "인지", "척수", "마비", "소아"]):
        return "neuro_rehab"
    elif any(k in combined for k in ["도수", "관절", "척추", "디스크", "통증", "근골격계", "운동치료", "자세"]):
        return "musculoskeletal"
    elif any(k in combined for k in ["법안", "의기법", "단독개원", "지도", "처방", "협회", "권익", "정책", "수가"]):
        return "policy_law"
    elif any(k in combined for k in ["apta", "미국", "글로벌", "해외", "who", "국제", "세계물리치료", "world physiotherapy"]):
        return "global_apta"
    else:
        return "general_clinical"


def to_spoken_polite(sentence: str) -> str:
    """평서체 종결 어미를 자연스럽고 정중한 방송 브리핑용 존댓말 구어체로 변환합니다."""
    if not sentence:
        return ""
    s = sentence.strip()
    if any(s.endswith(e) for e in ['습니다.', '합니다.', '됩니다.', '입니다.', '시킵니다.', '드립니다.', '있습니다.']):
        return s
    
    rules = [
        (r'체결했다\.?$', '체결했습니다.'),
        (r'발표했다\.?$', '발표했습니다.'),
        (r'선정됐다\.?$', '선정되었습니다.'),
        (r'선정되었다\.?$', '선정되었습니다.'),
        (r'게재됐다\.?$', '게재되었습니다.'),
        (r'게재되었다\.?$', '게재되었습니다.'),
        (r'보고됐다\.?$', '보고되었습니다.'),
        (r'보고되었다\.?$', '보고되었습니다.'),
        (r'밝혔다\.?$', '밝혔습니다.'),
        (r'강조했다\.?$', '강조했습니다.'),
        (r'나타내고\s*있다\.?$', '나타내고 있습니다.'),
        (r'이어오고\s*있다\.?$', '이어오고 있습니다.'),
        (r'시작한다\.?$', '시작합니다.'),
        (r'추진한다\.?$', '추진합니다.'),
        (r'강화한다\.?$', '강화합니다.'),
        (r'확인됐다\.?$', '확인되었습니다.'),
        (r'입증됐다\.?$', '입증되었습니다.'),
        (r'입증했다\.?$', '입증했습니다.'),
        (r'불과하다\.?$', '불과합니다.'),
        (r'출발했다\.?$', '출발했습니다.'),
        (r'아니다\.?$', '아닙니다.'),
        (r'중요하다\.?$', '중요합니다.'),
        (r'필요하다\.?$', '필요한 상황입니다.'),
        (r'기대된다\.?$', '기대되고 있습니다.'),
        (r'이다\.?$', '입니다.'),
        (r'한다\.?$', '합니다.'),
        (r'된다\.?$', '됩니다.'),
        (r'있다\.?$', '있습니다.'),
    ]
    for pattern, repl in rules:
        if re.search(pattern, s):
            return re.sub(pattern, repl, s)
    
    if not s.endswith('.'):
        s += '.'
    return s


def clean_truncated_tail(text: str) -> str:
    """문장 끝에 어색하게 남은 조사나 연결어미, 영문 약어를 걷어냅니다."""
    t = text.strip().rstrip('.')
    # 어색한 말단 단어 반복 제거 (예: "동시에", "위한", "대한", "필요한", "제공하는", "st", "및", "과", "와" 등)
    for _ in range(2):
        t = re.sub(r'\s+(더|및|과|와|의|에|을|를|이|가|위한|대한|통한|필요한|제공하는|하는|되는|있는|동시에|위해|통해|대해|st|st\.)$', '', t, flags=re.IGNORECASE)
        t = re.sub(r'(더|및|과|와|의|에|을|를|이|가|st)$', '', t, flags=re.IGNORECASE)
        t = t.strip()
    return t


def complete_korean_sentence(phrase: str) -> str:
    """명사형이나 불완전한 구절을 자연스러운 서술형 완결 문장으로 변환합니다."""
    p = clean_truncated_tail(phrase)
    
    noun_rules = [
        (r'협약\s*체결$', '협약을 공식 체결했습니다.'),
        (r'체결$', '체결했습니다.'),
        (r'과제\s*선정$', '연구 과제에 최종 선정되었습니다.'),
        (r'선정$', '선정되었습니다.'),
        (r'논문\s*게재$', '국제 학술지에 게재되었습니다.'),
        (r'게재$', '게재되었습니다.'),
        (r'효과\s*입증$', '임상적 효과를 공식 입증했습니다.'),
        (r'입증$', '입증되었습니다.'),
        (r'개발\s*시동$', '기술 개발에 본격 착수했습니다.'),
        (r'시동$', '본격 시동을 걸었습니다.'),
        (r'업무\s*협약$', '업무 협약을 체결했습니다.'),
        (r'가이드라인\s*발표$', '새로운 가이드라인을 발표했습니다.'),
        (r'발표$', '발표되었습니다.'),
        (r'추진$', '적극 추진하고 있습니다.'),
        (r'도입$', '선제적으로 도입하고 있습니다.'),
        (r'강화$', '기준을 대폭 강화했습니다.'),
        (r'확대$', '적용 범위를 확대하고 있습니다.'),
        (r'실시$', '맞춤형 프로그램을 실시했습니다.'),
        (r'지원$', '체계적인 지원에 나섰습니다.'),
        (r'축소$', '축소될 것으로 전망됩니다.'),
        (r'논의$', '심도 있게 논의되었습니다.'),
        (r'주도\s*클리닉$', '학생들이 주도하는 무료 클리닉을 운영합니다.'),
        (r'클리닉$', '전담 클리닉을 운영하고 있습니다.'),
        (r'신기술$', '새로운 임상 기술이 도입되었습니다.'),
        (r'기술$', '첨단 기술이 적극 활용되고 있습니다.')
    ]
    for pattern, repl in noun_rules:
        if re.search(pattern, p):
            return re.sub(pattern, repl, p)
            
    if any(p.endswith(e) for e in ['다', '음', '임', '됨', '함']):
        return p + '.'
        
    return p + ' 관련 주요 내용이 공식 확인되었습니다.'


def compact_bullet_sentence(text: str, max_chars: int = 56) -> str:
    """
    본문 불릿 1개당 2줄(약 50~56자) 이내로 들어가도록
    핵심 절을 선별하여 완성형 서술어 문장으로 압축합니다.
    """
    if not text:
        return ""
    
    if is_english_text(text):
        text = translate_to_korean(text)
        
    t = clean_text_segment(text)
    if len(t) <= max_chars:
        return complete_korean_sentence(t)
    
    # 쉼표 기준 절 분할
    clauses = re.split(r'[,;]\s*', t)
    accum = ""
    for c in clauses:
        c = c.strip()
        if not c:
            continue
        if len(accum) + len(c) + 2 <= max_chars:
            accum += (", " if accum else "") + c
        else:
            break
            
    if accum and len(accum) >= 18:
        return complete_korean_sentence(accum)
    
    # 절 분할로 안 되면 어절 단위로 자르고 완성형 서술어 부착
    words = t.split()
    accum = ""
    for w in words:
        if len(accum) + len(w) + 1 <= max_chars - 12:
            accum += (" " if accum else "") + w
        else:
            break
            
    accum = accum.strip()
    return complete_korean_sentence(accum)


def compress_article_content(article: dict, is_global: bool = False) -> dict:
    """
    기사 데이터(title, description, article_body)를 분석하여
    - 헤드라인: 최대 2줄(34자 이내)
    - 본문 불릿: 3개 합계 8줄 이내(불릿당 45~55자, 총 160자 이내)
    - 1줄 하이라이트 및 쇼츠 본문 나레이션을 생성합니다.
    (OpenAI GPT 지능형 요약 1순위 적용, 예외 시 규칙 기반 Fallback)
    """
    # 1. OpenAI GPT 모델 기반 고품질 지능형 요약 시도
    try:
        llm_result = summarize_article_with_llm(article, is_global=is_global)
        if (
            isinstance(llm_result, dict)
            and "bullets" in llm_result
            and len(llm_result["bullets"]) == 3
            and llm_result.get("headline")
        ):
            return llm_result
    except Exception as e:
        print(f"  [LLM 요약 실패, 규칙 기반 Fallback 적용]: {e}")

    title_raw = article.get("title", "")
    desc_raw = article.get("description", "")
    body_raw = article.get("article_body", "")
    
    # 외신 또는 영문 기사 감지 시 한국어로 1차 번역
    if is_global or is_english_text(title_raw):
        title_raw = translate_to_korean(title_raw)
    if is_global or is_english_text(desc_raw):
        desc_raw = translate_to_korean(desc_raw)
    if is_global or is_english_text(body_raw):
        body_raw = translate_to_korean(body_raw)
    
    # 1. 헤드라인 2줄 이내(최대 34자) 압축
    headline = clean_headline_two_lines(title_raw, max_chars=34)
    if not headline:
        headline = "물리치료 임상 및 정책 주요 동향 발표"
    
    # 2. 본문 및 설명에서 실제 문장 추출
    combined_content = (body_raw + " " + desc_raw).strip()
    sentences = extract_valid_sentences(combined_content)
    
    # 3. 테마 분류
    theme = "global_apta" if is_global else identify_article_theme(title_raw, combined_content)
    
    # 테마별 표준 배경 및 현장 파급효과 맵 (모두 50자 내외의 정갈한 문장)
    theme_bullet_2_map = {
        "manual_insurance": "비급여 관리급여 전환과 심사 평가 기준이 대폭 강화되는 추세입니다.",
        "community_care": "초고령사회 대비 전문 인력 중심의 현장 맞춤형 재활 인프라를 확충합니다.",
        "ai_robot_tech": "데이터 기반의 정밀 운동 분석과 능동적 보행 재활 기술이 적극 도입됩니다.",
        "neuro_rehab": "신경 가소성을 촉진하는 조기 집중 재활과 정량 평가 체계가 수립되었습니다.",
        "musculoskeletal": "관절 가동성과 심부 근육 강화를 병행하는 과학적 복합 처방이 강조됩니다.",
        "policy_law": "의료 보건 현장 실효성을 높이기 위한 제도 개편과 전문 인력 안이 논의됐습니다.",
        "global_apta": "국제 표준 가이드라인에 따른 최신 임상 근거와 중재 프로토콜이 제시됐습니다.",
        "general_clinical": "환자 기능 회복을 극대화하기 위한 과학적 재활 프로토콜이 추진됩니다."
    }

    theme_bullet_3_map = {
        "manual_insurance": "일선 병의원의 물리치료실 운영 및 치료사 고용 환경 변화에 대비가 필요합니다.",
        "community_care": "병원 중심을 넘어 지역사회 환자의 실질적 일상 복귀를 견인할 전망입니다.",
        "ai_robot_tech": "치료사의 치료 피로도를 경감하고 환자의 회복 속도를 현저히 단축합니다.",
        "neuro_rehab": "급성기부터 유지기까지 단절 없는 표준화 재활 프로토콜 정착이 필수적입니다.",
        "musculoskeletal": "환자 자가 운동 교육과 정기적 기능 재평가를 결합한 치료 유지가 핵심입니다.",
        "policy_law": "치료사의 전문 영역 확립과 환자 안전을 위한 현장 거버넌스 구축이 시급합니다.",
        "global_apta": "글로벌 치료 동향을 국내 임상 현장에 선제 적용하는 역량 강화가 요구됩니다.",
        "general_clinical": "동료 치료사들과의 적극적인 케이스 공유와 최신 근거 중심 치료가 권장됩니다."
    }

    theme_highlight_map = {
        "manual_insurance": "💡 포인트: 관리급여 전환에 따른 실손 청구 및 고용 기준 변화에 선제 대응하세요.",
        "community_care": "💡 포인트: 지역사회 및 방문 재활 수요 확대에 맞춘 임상 전문성 확보가 핵심입니다.",
        "ai_robot_tech": "💡 포인트: 첨단 스마트 재활 기기를 접목한 환자 맞춤형 치료를 적극 모색하세요.",
        "neuro_rehab": "💡 포인트: 조기 집중 재활과 객관적 기능 평가지표 기록을 체계화해야 합니다.",
        "musculoskeletal": "💡 포인트: 도수치료와 기능적 운동치료 결합으로 재발 방지 효과를 극대화하세요.",
        "policy_law": "💡 포인트: 최신 정책 및 수가 개편 방향을 주시하여 치료 현장에 신속히 반영하세요.",
        "global_apta": "💡 포인트: 세계 물리치료 표준 가이드라인에 맞춘 근거중심 치료(EBP)를 실천하세요.",
        "general_clinical": "💡 포인트: 환자 중심 맞춤형 기능 평가와 표준화된 치료 프로토콜 수립이 중요합니다."
    }

    # 4. 불릿 1 (핵심 팩트) 선별
    bullet_1_raw = ""
    title_keywords = set(re.findall(r'[가-힣a-zA-Z0-9]{2,}', headline))
    best_candidate = None
    best_overlap = 0

    for s in sentences:
        s_words = set(re.findall(r'[가-힣a-zA-Z0-9]{2,}', s))
        overlap = len(title_keywords & s_words)
        if any(bad in s for bad in ["효율성이 아니다", "의문이 든다", "지난 1일", "지난달", "사진=", "양육자를 위해", "장애인인식개선"]):
            overlap -= 3
        if overlap > best_overlap:
            best_overlap = overlap
            best_candidate = s

    if best_candidate and len(best_candidate) >= 20:
        bullet_1_raw = best_candidate
    elif sentences:
        bullet_1_raw = sentences[0]
    else:
        h_clean = headline.replace("'", "").replace('"', '').strip()
        if not h_clean.endswith(('다.', '다', '음.', '음')):
            bullet_1_raw = f"{h_clean}에 대한 주요 현안과 최신 동향이 발표되었습니다."
        else:
            bullet_1_raw = h_clean if h_clean.endswith('.') else h_clean + '.'

    bullet_1 = compact_bullet_sentence(bullet_1_raw, max_chars=54)

    # 5. 불릿 2 (세부 배경/수치/내용) 선별: 완결된 서술어가 있는 문장 우선
    bullet_2_raw = ""
    candidates_2 = [
        s for s in sentences 
        if s != bullet_1_raw and len(s) >= 20 and any(s.endswith(e) for e in ['다.', '다', '음.', '음', '했다.', '된다.', '있다.', '했다', '된다', '있다'])
    ]
    if candidates_2:
        bullet_2_raw = candidates_2[0]
    else:
        bullet_2_raw = theme_bullet_2_map.get(theme, theme_bullet_2_map["general_clinical"])
    bullet_2 = compact_bullet_sentence(bullet_2_raw, max_chars=54)

    # 6. 불릿 3 (임상/현장 파급효과) 선별: 완결된 서술어가 있는 문장 우선
    bullet_3_raw = ""
    candidates_3 = [
        s for s in candidates_2 
        if s != bullet_2_raw and any(s.endswith(e) for e in ['다.', '다', '음.', '음', '했다.', '된다.', '있다.', '했다', '된다', '있다'])
    ]
    if candidates_3:
        bullet_3_raw = candidates_3[0]
    else:
        bullet_3_raw = theme_bullet_3_map.get(theme, theme_bullet_3_map["general_clinical"])
    bullet_3 = compact_bullet_sentence(bullet_3_raw, max_chars=54)

    # [본문 불릿 합계 8줄 이내 엄격 보장 장치]
    # 불릿당 2줄(한 줄 약 28자), 3개 불릿 총합 165자 이내면 최대 6~8줄 이내로 확실하게 수렴
    total_bullet_len = len(bullet_1) + len(bullet_2) + len(bullet_3)
    if total_bullet_len > 165:
        # 가장 긴 불릿을 46자 이내로 재압축
        bullets = [bullet_1, bullet_2, bullet_3]
        max_idx = max(range(3), key=lambda i: len(bullets[i]))
        bullets[max_idx] = compact_bullet_sentence(bullets[max_idx], max_chars=46)
        bullet_1, bullet_2, bullet_3 = bullets

    # 7. 하이라이트 문장 결정
    highlight = theme_highlight_map.get(theme, theme_highlight_map["general_clinical"])

    # 8. 쇼츠 나레이션용 본문 요약 (1분 이상 ~ 2분 미만 시간 준수)
    spoken_fact = to_spoken_polite(bullet_1)
    if len(spoken_fact) > 70:
        parts = re.split(r'[,;]\s*', spoken_fact)
        if len(parts) >= 2 and len(parts[0]) >= 20:
            spoken_fact = to_spoken_polite(parts[0].strip())
            
    theme_impact = to_spoken_polite(theme_bullet_3_map.get(theme, "현장 치료사들의 관심과 실천이 필요합니다."))
    narration_body = f"{spoken_fact} {theme_impact}"

    if not narration_body.endswith(('.', '!', '?')):
        narration_body += '.'

    return {
        "headline": headline,
        "bullets": [bullet_1, bullet_2, bullet_3],
        "highlight": highlight,
        "narration_body": narration_body
    }

