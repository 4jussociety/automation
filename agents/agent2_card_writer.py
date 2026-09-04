import json
from config import GEMINI_API_KEY, CURRENT_WEEK

from agents.llm_helper import generate_json_response

def generate_card_news_with_gemini(batch_data):
    prompt = f"""
당신은 인스타그램 물리치료/헬스케어 매거진 수석 카피라이터 에이전트(Agent 2)입니다.
아래 제공된 [주간 뉴스 브리핑 데이터]를 바탕으로, 인스타그램 캐러셀(6장 슬라이드) 카드뉴스 텍스트와 본문 캡션을 작성하세요.

[입력 브리핑 데이터]
{json.dumps(batch_data, ensure_ascii=False, indent=2)}

[🎯 타겟 독자]
- 오직 물리치료사(PT), 도수치료사, 재활전문가, 작업치료사(OT) 등 임상 실무자입니다.
- 일반인을 위한 쉬운 건강 상식이 아니라, 전문가의 눈높이에 맞춘 전문 용어와 임상 실무적 가치(차팅 삭감 방지, 법적 리스크 대비, 최신 치료 프로토콜)를 깊이 있게 다루세요.

[작성 규칙]
1. 슬라이드 1 (표지):
   - 임상 치료사의 시선을 사로잡는 강력한 전문 타이틀 (예: "도수치료 실손 심사 기준 개편, 치료사가 챙길 3가지")
   - 부제목: "물리치료사 & 재활전문가를 위한 이번 주 핵심 실무 브리핑"
   - bullet_points: 3개 기사의 핵심 헤드라인을 말줄임표(...) 없이 온전한 문장/구문으로 전체 작성 (절대 말줄임 금지)
2. 슬라이드 2~4 (뉴스 1, 2, 3 상세):
   - 각 슬라이드마다 1개의 뉴스를 다룸.
   - 구성: 넘버링(01, 02, 03), 뉴스 헤드라인, 출처 뱃지, 핵심 요약 2~3줄, "💡 임상 실무 포인트" 한 줄
3. 슬라이드 5 (전문가 총평 및 실천 팁):
   - 슬라이드 제목: "임상 물리치료사를 위한 실무 종합 인사이트"
   - 이번 주 이슈들이 병원/클리닉 치료사에게 주는 시사점 종합 및 동료 치료사를 위한 실무 체크리스트 2개
4. 슬라이드 6 (아웃트로):
   - "임상 스터디를 위해 [저장]하고, 함께 일하는 동료 치료사에게 [공유]해보세요!"
5. 본문 캡션(caption) 및 해시태그(hashtags) 15개 작성 (일반인 태그 배제, 전문가 태그 위주).

[반드시 아래 JSON 형식만 반환하세요]
{{
  "batch_id": "{batch_data.get('batch_id')}",
  "week_tag": "{CURRENT_WEEK}",
  "cover_badge": "{batch_data.get('target_type', '물리치료 주간 브리핑')}",
  "slides": [
    {{
      "slide_number": 1,
      "type": "cover",
      "tag": "WEEKLY BRIEFING",
      "title": "표지 메인 타이틀",
      "subtitle": "물리치료사 & 재활전문가를 위한 핵심 실무 브리핑",
      "bullet_points": ["핵심 이슈 1 헤드라인 전문", "핵심 이슈 2", "핵심 이슈 3"]
    }},
    {{
      "slide_number": 2,
      "type": "news",
      "item_index": "01",
      "category_badge": "분류",
      "source_badge": "출처",
      "headline": "뉴스 1 헤드라인",
      "body_lines": ["요약 설명 1행", "요약 설명 2행"],
      "key_point": "💡 임상 실무 포인트 1문장"
    }},
    {{
      "slide_number": 3,
      "type": "news",
      "item_index": "02",
      "category_badge": "분류",
      "source_badge": "출처",
      "headline": "뉴스 2 헤드라인",
      "body_lines": ["요약 설명 1행", "요약 설명 2행"],
      "key_point": "💡 임상 실무 포인트 1문장"
    }},
    {{
      "slide_number": 4,
      "type": "news",
      "item_index": "03",
      "category_badge": "분류",
      "source_badge": "출처",
      "headline": "뉴스 3 헤드라인",
      "body_lines": ["요약 설명 1행", "요약 설명 2행"],
      "key_point": "💡 임상 실무 포인트 1문장"
    }},
    {{
      "slide_number": 5,
      "type": "insight",
      "tag": "EXPERT INSIGHT",
      "title": "임상 물리치료사를 위한 실무 종합 인사이트",
      "summary": "이번 주 동향 종합 분석 2~3줄",
      "action_checklist": ["체크 포인트 1", "체크 포인트 2"]
    }},
    {{
      "slide_number": 6,
      "type": "outro",
      "tag": "THEPT CLINICAL BRIEF",
      "title": "매주 업데이트되는\\n물리치료사 전문 브리핑",
      "cta_text": "임상 스터디를 위해 [저장]하고\\n동료 치료사에게 [공유]해보세요!",
      "footer_text": "@thept_official"
    }}
  ],
  "caption": "물리치료사 선생님들을 위한 인스타그램 본문 글 전문",
  "hashtags": ["#물리치료사", "#도수치료", "#재활치료사", "#임상물리치료", "#대한물리치료사협회", "#물리치료학과", "#도수치료교육", "#실손보험도수치료", "#재활의학"]
}}
"""
    return generate_json_response(prompt, temperature=0.4)

def run_agent2(batch_data):
    """Agent 2 실행: 배치 데이터 -> 인스타 카드뉴스 6장 텍스트 구조로 변환"""
    if not GEMINI_API_KEY:
        raise ValueError("[Agent 2] GEMINI_API_KEY가 설정되지 않았습니다. .env 파일을 확인하세요.")

    card_data = generate_card_news_with_gemini(batch_data)

    # 기사별 원문 링크 및 스크랩 기사 목록 보존
    card_data["news_items"] = batch_data.get("news_items", [])
    card_data["source_articles"] = batch_data.get("source_articles", [])
    return card_data
