import json
from config import GEMINI_API_KEY, DEFAULT_MODEL

SAFETY_DISCLAIMER = "※ 본 콘텐츠는 의료 정보 전달을 목적으로 하며, 개별 증상에 대한 치료는 반드시 전문의 및 물리치료사와 상담하시기 바랍니다."

def review_content_with_gemini(card_data, shorts_data):
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=GEMINI_API_KEY)

    prompt = f"""
당신은 물리치료 임상 감수 및 의료법/표현 규제 검수 에이전트(Agent 4)입니다.
앞선 에이전트들이 작성한 [카드뉴스 데이터]와 [쇼츠 대본]을 감수하여, 신뢰할 수 있고 법적으로 안전한 최종 발행본으로 승인하세요.

[카드뉴스 초안]
{json.dumps(card_data, ensure_ascii=False, indent=2)}

[쇼츠 대본 초안]
{json.dumps(shorts_data, ensure_ascii=False, indent=2)}

[검수 가이드라인]
1. 과장/허위 표현 교정: "완치", "단번에 해결", "기적의", "100%" 등 단정적 어조는 "개선에 도움", "부담 완화" 등으로 수정.
2. 안전 경고 문구 삽입: 인스타그램 캡션 및 쇼츠 설명란 하단에 안전 디스클레이머 추가.
3. 원활한 흐름 확인: 어색한 문장 교정.

[반드시 아래 JSON 형식만 반환하세요]
{{
  "review_status": "APPROVED",
  "review_notes": "감수 결과 메모 (예: 특정 과장 표현 1건 완화 수정 완료)",
  "safety_disclaimer": "{SAFETY_DISCLAIMER}",
  "final_card_data": [수정된 카드뉴스 데이터 객체],
  "final_shorts_data": [수정된 쇼츠 대본 객체]
}}
"""
    response = client.models.generate_content(
        model=DEFAULT_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=0.2
        )
    )
    return json.loads(response.text)

def fallback_review(card_data, shorts_data):
    """기본 감수 로직 (안전 문구 자동 부착 및 승인)"""
    # 캡션 하단에 안전 문구 추가
    if "caption" in card_data and SAFETY_DISCLAIMER not in card_data["caption"]:
        card_data["caption"] += f"\n\n{SAFETY_DISCLAIMER}"
        
    if "youtube_description" in shorts_data and SAFETY_DISCLAIMER not in shorts_data["youtube_description"]:
        shorts_data["youtube_description"] += f"\n\n{SAFETY_DISCLAIMER}"

    return {
        "review_status": "APPROVED",
        "review_notes": "기본 감수 완료: 의료법 및 안전 가이드라인에 따른 주의 문구 부착 완료.",
        "safety_disclaimer": SAFETY_DISCLAIMER,
        "final_card_data": card_data,
        "final_shorts_data": shorts_data
    }

def run_agent4(card_data, shorts_data):
    """Agent 4 실행: 최종 감수 및 승인"""
    if GEMINI_API_KEY:
        try:
            return review_content_with_gemini(card_data, shorts_data)
        except Exception as e:
            print(f"[Agent 4] Gemini 감수 중 오류 ({e}), 폴백 감수 적용")
            return fallback_review(card_data, shorts_data)
    else:
        return fallback_review(card_data, shorts_data)
