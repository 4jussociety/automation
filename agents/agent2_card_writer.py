import json
from config import GEMINI_API_KEY, DEFAULT_MODEL, CURRENT_WEEK

def generate_card_news_with_gemini(batch_data):
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=GEMINI_API_KEY)

    prompt = f"""
당신은 인스타그램 물리치료/헬스케어 매거진 수석 카피라이터 에이전트(Agent 2)입니다.
아래 제공된 [주간 뉴스 브리핑 데이터]를 바탕으로, 인스타그램 캐러셀(6장 슬라이드) 카드뉴스 텍스트와 본문 캡션을 작성하세요.

[입력 브리핑 데이터]
{json.dumps(batch_data, ensure_ascii=False, indent=2)}

[작성 규칙]
1. 슬라이드 1 (표지):
   - 시선을 강탈하는 짧고 강력한 메인 타이틀 (예: "도수치료 실손보험, 이번 달부터 바뀝니다")
   - 부제목: 이번 주 핵심 쟁점 3가지 요약
2. 슬라이드 2~4 (뉴스 1, 2, 3 상세):
   - 각 슬라이드마다 1개의 뉴스를 다룸.
   - 구성: 넘버링(01, 02, 03), 뉴스 헤드라인, 출처 뱃지, 핵심 요약 2~3줄, "💡 핵심 포인트" 한 줄
3. 슬라이드 5 (전문가 총평 및 실천 팁):
   - 이번 주 뉴스들이 치료사와 환자에게 주는 시사점 종합 및 권장 행동 요령
4. 슬라이드 6 (아웃트로):
   - 저장 & 팔로우 유도 문구 ("나중에 다시 보려면 [저장], 동료/지인에게 [공유]!")
5. 본문 캡션(caption) 및 해시태그(hashtags) 15개 작성.

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
      "subtitle": "부제목 설명",
      "bullet_points": ["핵심 이슈 1", "핵심 이슈 2", "핵심 이슈 3"]
    }},
    {{
      "slide_number": 2,
      "type": "news",
      "item_index": "01",
      "category_badge": "분류 (예: 실손보험)",
      "source_badge": "출처",
      "headline": "뉴스 1 헤드라인",
      "body_lines": ["요약 설명 1행", "요약 설명 2행"],
      "key_point": "💡 기억할 점 1문장"
    }},
    {{
      "slide_number": 3,
      "type": "news",
      "item_index": "02",
      "category_badge": "분류",
      "source_badge": "출처",
      "headline": "뉴스 2 헤드라인",
      "body_lines": ["요약 설명 1행", "요약 설명 2행"],
      "key_point": "💡 기억할 점 1문장"
    }},
    {{
      "slide_number": 4,
      "type": "news",
      "item_index": "03",
      "category_badge": "분류",
      "source_badge": "출처",
      "headline": "뉴스 3 헤드라인",
      "body_lines": ["요약 설명 1행", "요약 설명 2행"],
      "key_point": "💡 기억할 점 1문장"
    }},
    {{
      "slide_number": 5,
      "type": "insight",
      "tag": "EXPERT INSIGHT",
      "title": "물리치료 전문가의 주간 총평",
      "summary": "이번 주 동향 종합 분석 2~3줄",
      "action_checklist": ["체크 포인트 1", "체크 포인트 2"]
    }},
    {{
      "slide_number": 6,
      "type": "outro",
      "tag": "PHYSICAL THERAPY TODAY",
      "title": "매주 업데이트되는\\n물리치료 최신 브리핑",
      "cta_text": "도움이 되셨다면 [저장]하고\\n필요한 동료에게 [공유]해보세요!",
      "footer_text": "@pt_weekly_brief"
    }}
  ],
  "caption": "인스타그램 본문 글 전문",
  "hashtags": ["#물리치료", "#도수치료", "..."]
}}
"""
    response = client.models.generate_content(
        model=DEFAULT_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=0.4
        )
    )
    return json.loads(response.text)

def get_fallback_card_data(batch_data):
    """API 키 미등록 시 기본 데이터 기반 카드뉴스 생성"""
    news_items = batch_data.get("news_items", [])
    batch_title = batch_data.get("batch_title", "물리치료 주간 브리핑")
    
    slides = [
        {
            "slide_number": 1,
            "type": "cover",
            "tag": f"WEEKLY BRIEFING • {CURRENT_WEEK}",
            "title": batch_title,
            "subtitle": "이번 주 물리치료계 꼭 알아야 할 3대 이슈 총정리",
            "bullet_points": [item["headline"][:28] + "..." for item in news_items[:3]]
        }
    ]

    for idx, item in enumerate(news_items[:3], start=1):
        slides.append({
            "slide_number": idx + 1,
            "type": "news",
            "item_index": f"0{idx}",
            "category_badge": item.get("category", "업계 이슈"),
            "source_badge": item.get("source", "보도자료"),
            "headline": item["headline"],
            "body_lines": [
                item.get("summary", ""),
                item.get("why_it_matters", "")
            ],
            "key_point": f"💡 {item.get('action_tip', '주목해야 할 핵심 포인트입니다.')}"
        })

    slides.append({
        "slide_number": 5,
        "type": "insight",
        "tag": "EXPERT INSIGHT",
        "title": "치료사와 환자가 꼭 챙겨야 할 포인트",
        "summary": "최신 제도 변화와 임상 근거를 바탕으로 보다 신뢰성 높은 재활 치료 환경이 구축되고 있습니다.",
        "action_checklist": [
            "진단서 및 치료 계획서의 객관적 수치(ROM, 통증 척도) 꼼꼼히 관리",
            "과도한 수동 치료보다 능동적 코어/신장성 수축 재활 병행 권장"
        ]
    })

    slides.append({
        "slide_number": 6,
        "type": "outro",
        "tag": "PHYSICAL THERAPY TODAY",
        "title": "매주 가장 빠른\\n물리치료 뉴스 브리핑",
        "cta_text": "도움이 되셨다면 [저장]하고\\n동료 치료사 및 지인에게 [공유]하세요!",
        "footer_text": "@pt_weekly_briefing"
    })

    caption = f"""📢 [{batch_title}] - {CURRENT_WEEK}

이번 주 물리치료계에서 가장 뜨거웠던 주요 소식들을 모아 전해드립니다!

📌 이번 주 핵심 요약:
{chr(10).join([f"• {item['headline']}" for item in news_items[:3]])}

자세한 내용은 슬라이드를 옆으로 넘겨 확인해보세요 👉

#물리치료 #도수치료 #재활운동 #물리치료사 #체형교정 #건강정보 #재활의학 #주간브리핑
"""

    return {
        "batch_id": batch_data.get("batch_id"),
        "week_tag": CURRENT_WEEK,
        "cover_badge": batch_data.get("batch_title", "물리치료 주간 브리핑"),
        "slides": slides,
        "caption": caption,
        "hashtags": ["#물리치료", "#도수치료", "#재활운동", "#체형교정", "#물리치료사", "#실손보험", "#건강상식"]
    }

def run_agent2(batch_data):
    """Agent 2 실행: 배치 데이터 -> 인스타 카드뉴스 6장 텍스트 구조로 변환"""
    if GEMINI_API_KEY:
        try:
            return generate_card_news_with_gemini(batch_data)
        except Exception as e:
            print(f"[Agent 2] Gemini 생성 실패 ({e}), 폴백 카드 데이터 사용")
            return get_fallback_card_data(batch_data)
    else:
        return get_fallback_card_data(batch_data)
