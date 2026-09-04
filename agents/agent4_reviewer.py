import json
from config import GEMINI_API_KEY

SAFETY_DISCLAIMER = "※ 본 브리핑은 물리치료사 및 재활전문가를 위한 학술·정책 실무 정보이며, 임상 적용 시 개별 환자의 상태와 최신 법적 기준을 재확인하시기 바랍니다."

from agents.llm_helper import generate_json_response

def review_content_with_gemini(card_data, shorts_data):
    prompt = f"""
당신은 물리치료 임상 감수 및 의료법/표현 규제 검수 에이전트(Agent 4)입니다.
앞선 에이전트들이 작성한 [카드뉴스 데이터]와 [쇼츠 대본]을 감수하여, 신뢰할 수 있고 법적으로 안전한 최종 발행본으로 승인하세요.

[카드뉴스 초안]
{json.dumps(card_data, ensure_ascii=False, indent=2)}

[쇼츠 대본 초안]
{json.dumps(shorts_data, ensure_ascii=False, indent=2)}

[검수 가이드라인]
1. 🎯 타겟 적합성 검수: 일반인 환자 대상 어투(예: "치료받으실 때 주의하세요", "집에서 따라해보세요")가 포함되어 있다면, 철저하게 "물리치료사/재활전문가의 임상 실무 조언"으로 완벽히 교정하세요.
2. 과장/허위 표현 교정: "완치", "단번에 해결", "기적의", "100%" 등 단정적 어조는 "개선에 기여", "부담 완화" 등으로 수정.
3. 전문가 디스클레이머 삽입: 인스타그램 캡션 및 쇼츠 설명란 하단에 전문가용 디스클레이머 추가.
4. 원활한 흐름 확인: 오타 및 비문 교정.

[반드시 아래 JSON 형식만 반환하세요]
{{
  "review_status": "APPROVED",
  "review_notes": "감수 결과 메모 (예: 전문가 타겟 톤앤매너 정렬 및 디스클레이머 부착 완료)",
  "safety_disclaimer": "{SAFETY_DISCLAIMER}",
  "final_card_data": [수정된 카드뉴스 데이터 객체],
  "final_shorts_data": [수정된 쇼츠 대본 객체]
}}
"""
    return generate_json_response(prompt, temperature=0.2)

def run_agent4(card_data, shorts_data):
    """Agent 4 실행: 최종 감수 및 승인"""
    if not GEMINI_API_KEY:
        raise ValueError("[Agent 4] GEMINI_API_KEY가 설정되지 않았습니다. .env 파일을 확인하세요.")

    res = review_content_with_gemini(card_data, shorts_data)

    # 원본 기사 링크 및 메타데이터 필드 보존 강제
    if "final_card_data" in res and isinstance(res["final_card_data"], dict):
        if "news_items" not in res["final_card_data"] or not res["final_card_data"]["news_items"]:
            res["final_card_data"]["news_items"] = card_data.get("news_items", [])
        if "source_articles" not in res["final_card_data"]:
            res["final_card_data"]["source_articles"] = card_data.get("source_articles", [])

    return res
