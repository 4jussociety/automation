import json
from config import GEMINI_API_KEY, DEFAULT_MODEL, CURRENT_WEEK

def generate_shorts_script_with_gemini(batch_data):
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=GEMINI_API_KEY)

    prompt = f"""
당신은 숏폼(유튜브 쇼츠, 인스타 릴스, 틱톡) 전문 비디오 디렉터 에이전트(Agent 3)입니다.
아래 제공된 [주간 뉴스 브리핑 데이터]를 바탕으로, 40~45초 동안 시청자를 꽉 붙잡아두는 빠른 템포의 뉴스 브리핑 쇼츠 대본을 작성하세요.

[입력 브리핑 데이터]
{json.dumps(batch_data, ensure_ascii=False, indent=2)}

[작성 규칙]
1. 길이: 정확히 40~45초 분량 (총 글자 수 공백 포함 280~320자 내외).
2. 0~4초 (Hook):
   - 첫 마디에서 시청자가 스크롤을 멈추게 하는 강력한 오프닝 (예: "물리치료사도 환자도 꼭 알아야 할 이번 주 3대 이슈, 40초 만에 정리해 드립니다!")
3. 뉴스 1, 2, 3 소개 (각 8~10초):
   - 군더더기 없이 핵심 팩트 + 왜 중요한지 2문장씩 빠르게 전달.
4. 40~45초 (Outro):
   - "도움이 되셨다면 좋아요와 구독 누르시고, 다음 주 물리치료 뉴스도 놓치지 마세요!"
5. 음성 합성(TTS)용 전체 나레이션 텍스트:
   - 괄호나 특수문자 없이 아나운서가 매끄럽게 읽을 수 있는 순수 한국어 문장으로 연결.

[반드시 아래 JSON 형식만 반환하세요]
{{
  "batch_id": "{batch_data.get('batch_id')}",
  "shorts_title": "쇼츠 업로드용 제목 (예: 이번 주 물리치료계 핫이슈 TOP 3 🚨)",
  "hook_headline": "화면에 크게 박힐 3초 훅 카피",
  "full_narration": "TTS 음성 합성용 전체 나레이션 줄글 (특수문자 제외)",
  "estimated_seconds": 42,
  "scenes": [
    {{
      "time_range": "00:00 - 00:04",
      "section": "오프닝 훅",
      "narration_snippet": "나레이션 문장",
      "screen_visual_cue": "[화면 연출] 화면 상단에 사이렌 아이콘과 함께 헤드라인 타이포그래피 등장",
      "caption_highlight": "이번 주 물리치료 핫이슈!"
    }},
    {{
      "time_range": "00:05 - 00:16",
      "section": "뉴스 01",
      "narration_snippet": "뉴스 1 나레이션",
      "screen_visual_cue": "[화면 연출] 병원 및 서류/진료 관련 스톡 영상 + 뉴스 타이틀 팝업",
      "caption_highlight": "뉴스 1 핵심 단어"
    }},
    {{
      "time_range": "00:17 - 00:28",
      "section": "뉴스 02",
      "narration_snippet": "뉴스 2 나레이션",
      "screen_visual_cue": "[화면 연출] 재활 운동 및 물리치료 클립 영상",
      "caption_highlight": "뉴스 2 핵심 단어"
    }},
    {{
      "time_range": "00:29 - 00:38",
      "section": "뉴스 03",
      "narration_snippet": "뉴스 3 나레이션",
      "screen_visual_cue": "[화면 연출] 연구 논문 그래프 또는 해부학 3D 모션 그래픽",
      "caption_highlight": "뉴스 3 핵심 단어"
    }},
    {{
      "time_range": "00:39 - 00:44",
      "section": "아웃트로",
      "narration_snippet": "마무리 나레이션",
      "screen_visual_cue": "[화면 연출] 구독/좋아요 및 댓글 유도 버튼 애니메이션",
      "caption_highlight": "구독하고 매주 받아보기!"
    }}
  ],
  "youtube_description": "유튜브 쇼츠 설명란 텍스트 (타임스탬프, 해시태그 포함)"
}}
"""
    response = client.models.generate_content(
        model=DEFAULT_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=0.3
        )
    )
    return json.loads(response.text)

def get_fallback_shorts_data(batch_data):
    """API 키 미등록 시 기본 데이터 기반 쇼츠 대본 생성"""
    news_items = batch_data.get("news_items", [])
    batch_title = batch_data.get("batch_title", "물리치료 주간 브리핑")

    hook = f"물리치료사와 환자 모두 알아야 할 이번 주 핫이슈, 40초 만에 정리해 드립니다!"
    
    body_parts = []
    scenes = [
        {
            "time_range": "00:00 - 00:04",
            "section": "오프닝 훅",
            "narration_snippet": hook,
            "screen_visual_cue": "[화면 연출] 사이렌 이모지와 함께 대형 텍스트 '이번 주 물리치료 핫이슈'",
            "caption_highlight": "이번 주 핫이슈 TOP 3"
        }
    ]

    time_ranges = ["00:05 - 00:16", "00:17 - 00:28", "00:29 - 00:38"]
    for idx, item in enumerate(news_items[:3]):
        snippet = f"첫 번째, {item['headline']}. {item.get('summary', '')}" if idx == 0 else \
                  f"두 번째, {item['headline']}. {item.get('summary', '')}" if idx == 1 else \
                  f"세 번째, {item['headline']}. {item.get('summary', '')}"
        body_parts.append(snippet)
        scenes.append({
            "time_range": time_ranges[idx],
            "section": f"뉴스 0{idx+1}",
            "narration_snippet": snippet,
            "screen_visual_cue": f"[화면 연출] {item.get('category', '물리치료')} 관련 스톡 영상 및 자막 강조",
            "caption_highlight": item["headline"][:15]
        })

    outro = "도움이 되셨다면 저장과 구독 누르시고 다음 주 물리치료 소식도 가장 빠르게 받아보세요!"
    scenes.append({
        "time_range": "00:39 - 00:44",
        "section": "아웃트로",
        "narration_snippet": outro,
        "screen_visual_cue": "[화면 연출] 구독 및 공유 아이콘 애니메이션",
        "caption_highlight": "구독하고 매주 소식받기!"
    })

    full_narration = f"{hook} {' '.join(body_parts)} {outro}"

    return {
        "batch_id": batch_data.get("batch_id"),
        "shorts_title": f"🚨 이번 주 {batch_title} TOP 3 요약! #shorts",
        "hook_headline": "이번 주 물리치료계 3대 뉴스!",
        "full_narration": full_narration,
        "estimated_seconds": 43,
        "scenes": scenes,
        "youtube_description": f"""이번 주 물리치료 주요 뉴스 브리핑입니다.

00:00 인트로
00:05 1. {news_items[0]['headline'] if len(news_items)>0 else ''}
00:17 2. {news_items[1]['headline'] if len(news_items)>1 else ''}
00:29 3. {news_items[2]['headline'] if len(news_items)>2 else ''}
00:39 마무리

#물리치료 #도수치료 #재활치료 #쇼츠 #물리치료사 #건강뉴스
"""
    }

def run_agent3(batch_data):
    """Agent 3 실행: 배치 데이터 -> 40초 쇼츠 영상 대본 및 연출안 생성"""
    if GEMINI_API_KEY:
        try:
            return generate_shorts_script_with_gemini(batch_data)
        except Exception as e:
            print(f"[Agent 3] Gemini 생성 실패 ({e}), 폴백 쇼츠 데이터 사용")
            return get_fallback_shorts_data(batch_data)
    else:
        return get_fallback_shorts_data(batch_data)
