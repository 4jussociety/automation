# 이 모듈은 TTS 음성 합성 및 대본 검수를 위해 띄어쓰기, 쉼표, 온점 등 문장 부호를 정밀 정제합니다.
# 긴 문장의 호흡점(쉼표) 배치와 특수기호 및 영문 약어의 자연스러운 한국어 발음 변환을 전담합니다.

import sys
import re

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass


def refine_text_for_tts(text: str) -> str:
    """
    Edge-TTS가 또박또박 자연스러운 호흡(Pause)과 억양으로 발음할 수 있도록
    띄어쓰기, 쉼표(,), 온점(.), 특수기호 및 약어를 철저히 검수하고 정제합니다.
    """
    if not text:
        return ""

    t = text.strip()

    # 1. 특수기호 및 한자 음성 친화 변환
    symbol_map = [
        (r'\bAI\b', '에이아이'),
        (r'\bAPTA\b', '에이피티에이'),
        (r'\bEBP\b', '이비피'),
        (r'\bWHO\b', '더블유에이치오'),
        (r'\bROM\b', '알오엠'),
        (r'\bPT\b', '피티'),
        (r'4thept\.com', '포더피티 닷컴'),
        (r'teamthept@gmail\.com', '팀더피티 골뱅이 지메일 닷컴'),
        (r'teamthept', '팀더피티'),
        (r'4thept', '포더피티'),
        (r'thept\.co\.kr', '더피티 닷 시오 닷 케이알'),
        (r'(?<![a-zA-Z])thept(?![a-zA-Z])', '더피티'),
        (r'\bSt\.\s*', '세인트 '),
        (r'\bDr\.\s*', '닥터 '),
        (r'4:5', '4대 5'),
        (r'9:16', '9대 16'),
        (r'外\b', ' 외'),
        (r'&', ' 및 '),
        (r'·', ', '),  # 가운뎃점은 쉼표로 변환하여 자연스러운 끊어읽기 유도
        (r'/', ', '),  # 슬래시도 쉼표로 변환
        (r'(\d+)\s*%', r'\1 퍼센트'),
        (r'%', ' 퍼센트'),
        (r'\bvs\b\.?', ' 대 '),
        (r'~', ' 에서 '),
        (r'[▶▷💡📌✈️❤️✅•]', ''), # 이모지 및 특수 마크 제거
    ]
    for pattern, repl in symbol_map:
        t = re.sub(pattern, repl, t, flags=re.IGNORECASE)

    # 2. 붙어있는 단어 분리 및 오탈자/붙여쓰기 교정 (기사 제목 크롤링 시 공백 누락 복원)
    t = re.sub(r'숨통병[·,]?\s*의원은', '숨통이 트이고, 병의원은', t)
    t = re.sub(r'병[·,]?\s*의원', '병의원', t)

    # 3. 말줄임표 및 연속 문장부호 정돈
    t = re.sub(r'[\.]{2,}', '.', t)
    t = re.sub(r'[,]{2,}', ',', t)
    t = re.sub(r'[!]{2,}', '!', t)
    t = re.sub(r'[\?]{2,}', '?', t)
    t = t.replace('…', '.')

    # 4. 문장부호 앞뒤 공백 정규화
    # 부호 앞 공백 제거: "단어 , " -> "단어, " / "단어 . " -> "단어. "
    t = re.sub(r'\s+([,\.!\?])', r'\1', t)

    # 부호 뒤 공백 보장: 마침표, 쉼표, 느낌표, 물음표 뒤에 글자가 바로 붙어있으면 띄어쓰기 강제 삽입
    # 단, 소수점(예: 3.14, 1.5)은 제외
    t = re.sub(r'(?<=[가-힣a-zA-Z])([,\.!\?])(?=[가-힣a-zA-Z0-9])', r'\1 ', t)
    t = re.sub(r'(?<=\d)([,!\?])(?=[가-힣a-zA-Z])', r'\1 ', t)
    t = re.sub(r'(?<=\d)\.(?=[가-힣a-zA-Z])', '. ', t)

    # 5. 긴 구절 자연스러운 끊어읽기(호흡점 쉼표) 보강
    # Edge-TTS는 쉼표에서 약 150~200ms 쉬어가므로, 너무 길게 이어지는 구절에 쉼표 삽입
    pause_patterns = [
        (r'(\b이번 주 가장 뜨거운)\s+', r'\1, '),
        (r'(\b빠르게 변화하는 [^\s,]+ 속에서)\s+', r'\1, '),
        (r'(\b첫 번째 소식입니다\.)\s*', r'\1 '),
        (r'(\b두 번째 소식입니다\.)\s*', r'\1 '),
        (r'(\b세 번째 소식입니다\.)\s*', r'\1 '),
        (r'(\b이번 주 핵심 정리!)\s*', r'\1 '),
    ]
    for p, r in pause_patterns:
        t = re.sub(p, r, t)

    # 6. 다중 공백 제거 및 선후 공백 트림
    t = re.sub(r'\s+', ' ', t).strip()

    # 7. 문장 종결 부호(온점) 확실한 보장
    if t and not t.endswith(('.', '!', '?')):
        t += '.'

    return t


def verify_text_punctuation(text: str) -> dict:
    """
    텍스트의 띄어쓰기, 쉼표, 온점 배치 상태를 진단하고 리포트를 반환합니다.
    """
    issues = []
    if re.search(r'[가-힣a-zA-Z][,\.!\?][가-힣a-zA-Z]', text):
        issues.append("문장부호 뒤 띄어쓰기 누락")
    if re.search(r'\s+[,\.!\?]', text):
        issues.append("문장부호 앞 불필요한 공백 존재")
    if re.search(r'[\.]{2,}|[,]{2,}', text):
        issues.append("중복 문장부호 존재")
    if text and not text.endswith(('.', '!', '?')):
        issues.append("문장 끝 종결 온점 누락")
    
    refined = refine_text_for_tts(text)
    return {
        "original": text,
        "is_valid": len(issues) == 0,
        "issues": issues,
        "refined": refined
    }


if __name__ == "__main__":
    sample_texts = [
        "첫 번째 소식입니다.작업치료·물리치료 전문단체와 영유아 조기개입 지원 협력 外. 한국장애인개발원 울산센터,작업치료·물리치료 전문단체와 협약 체결",
        "도수치료 관리급여에 실손보험 숨통병·의원은 물리치료실 축소. 일선 병의원의 대비가 필요합니다",
        "물리치료사 필독!이번 주 가장 뜨거운 글로벌 재활 트렌드 3가지, 지금 바로 상세히 브리핑해 드립니다!",
        "새로운 가이드라인은 AI 및 APTA 기준에 맞춰 25.5% 향상된 재활 프로토콜을 제시합니다"
    ]

    print("=== [TTS 텍스트 검수 및 띄어쓰기/문장부호 정제 테스트] ===")
    for idx, sample in enumerate(sample_texts, 1):
        res = verify_text_punctuation(sample)
        print(f"\n[예시 {idx}]")
        print(f"  원본: {res['original']}")
        print(f"  진단 이슈: {res['issues'] if res['issues'] else '없음 (정상)'}")
        print(f"  정제: {res['refined']}")
