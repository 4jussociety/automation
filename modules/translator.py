# 이 모듈은 영문 외신 기사의 제목 및 본문 텍스트를 자연스러운 한국어로 번역합니다.
# 글로벌 물리치료 트렌드 기사를 100% 한국어 카드뉴스 및 쇼츠 콘텐츠로 변환합니다.

import re
import time
from deep_translator import GoogleTranslator, MyMemoryTranslator


def is_english_text(text: str) -> bool:
    """텍스트가 주로 영문으로 구성되어 있는지 판별합니다."""
    if not text:
        return False
    # 한글 글자 수와 알파벳 글자 수 비교
    ko_count = len(re.findall(r'[가-힣]', text))
    en_count = len(re.findall(r'[a-zA-Z]', text))
    # 영문 글자가 6개 이상이고 한글보다 영문이 많으면 영어 텍스트로 판정
    return en_count >= 6 and en_count > ko_count


def translate_to_korean(text: str) -> str:
    """영문 텍스트를 고품질 한국어로 번역합니다. 이미 한국어면 그대로 반환합니다."""
    if not text:
        return ""
    if not is_english_text(text):
        return text

    clean_input = text.strip()
    if len(clean_input) > 4000:
        clean_input = clean_input[:4000]

    # 1차 시도: GoogleTranslator (최대 3회 재시도 및 지연 완충)
    for attempt in range(3):
        try:
            gt = GoogleTranslator(source='auto', target='ko')
            res = gt.translate(clean_input)
            if res and not res.startswith("Error") and not any(err in res.lower() for err in ["error 500", "too many requests"]):
                return res.strip()
        except Exception as e:
            if attempt < 2:
                time.sleep(0.5 * (attempt + 1))
            else:
                print(f"  [번역 1차 Google 재시도 소진]: {e}")

    # 2차 시도: MyMemoryTranslator fallback
    try:
        translator = MyMemoryTranslator(source='en-US', target='ko-KR')
        if len(clean_input) > 250:
            sentences = re.split(r'(?<=[\.\?\!])\s+', clean_input)
            translated_parts = []
            for s in sentences:
                s_strip = s.strip()
                if not s_strip:
                    continue
                if is_english_text(s_strip):
                    tr = translator.translate(s_strip[:250])
                    if tr and "MYMEMORY WARNING" not in tr and not tr.startswith("Error"):
                        translated_parts.append(tr)
                    else:
                        translated_parts.append(s_strip)
                else:
                    translated_parts.append(s_strip)
            if translated_parts:
                return " ".join(translated_parts)

        translated = translator.translate(clean_input[:300])
        if translated and "MYMEMORY WARNING" not in translated and not translated.startswith("Error"):
            return translated.strip()
    except Exception as e:
        print(f"  [번역 2차 MyMemory 경고]: {e}")

    return clean_input

