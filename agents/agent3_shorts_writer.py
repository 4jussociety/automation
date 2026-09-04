import json
from config import GEMINI_API_KEY

from agents.llm_helper import generate_json_response

def generate_shorts_script_with_gemini(batch_data):
    prompt = f"""
당신은 숏폼(유튜브 쇼츠, 인스타 릴스, 틱톡) 전문 비디오 디렉터 에이전트(Agent 3)입니다.
아래 제공된 [주간 뉴스 브리핑 데이터]를 바탕으로, 40~45초 동안 시청자를 꽉 붙잡아두는 빠른 템포의 뉴스 브리핑 쇼츠 대본을 작성하세요.

[입력 브리핑 데이터]
{json.dumps(batch_data, ensure_ascii=False, indent=2)}

[🎯 타겟 시청자]
- 오직 물리치료사(PT), 도수치료사, 재활전문가, 작업치료사(OT) 등 현업 임상가입니다.
- 일반인을 부르는 멘트("허리 아프신 분들", "치료받으실 때" 등)는 절대 금지합니다.
- 동료 치료사 선생님들에게 브리핑하는 전문적이고 빠르고 정확한 어조로 작성하세요.

[작성 규칙]
1. 길이: 정확히 40~45초 분량 (총 글자 수 공백 포함 280~320자 내외).
2. 0~4초 (Hook):
   - 물리치료사 선생님들을 직접 호명하며 스크롤을 멈추게 하는 강력한 전문 오프닝
   - (예: "물리치료사 선생님들 주목! 이번 주 임상 현장 핵심 3대 이슈, 40초 만에 빠르게 브리핑합니다.")
3. 뉴스 1, 2, 3 소개 (각 8~10초):
   - 군더더기 없이 임상 실무 핵심 팩트 + 치료사 입장에서의 주의점을 2문장씩 빠르게 전달.
4. 40~45초 (Outro):
   - "전국의 물리치료사, 재활전문가를 위한 THEPT 브리핑! 유익하셨다면 동료 치료사에게 공유하시고 팔로우해 주세요!"
5. 음성 합성(TTS)용 전체 나레이션 텍스트:
   - 괄호나 특수문자 없이 아나운서가 매끄럽게 읽을 수 있는 순수 한국어 문장으로 연결.

[반드시 아래 JSON 형식만 반환하세요]
{{
  "batch_id": "{batch_data.get('batch_id')}",
  "shorts_title": "쇼츠 업로드용 제목 (예: [물리치료사 필독] 이번 주 임상 핫이슈 TOP 3 🚨)",
  "hook_headline": "화면에 크게 박힐 3초 훅 카피",
  "full_narration": "TTS 음성 합성용 전체 나레이션 줄글 (특수문자 제외)",
  "estimated_seconds": 42,
  "scenes": [
    {{
      "time_range": "00:00 - 00:04",
      "section": "오프닝 훅",
      "narration_snippet": "나레이션 문장",
      "screen_visual_cue": "[화면 연출] 화면 상단에 사이렌 아이콘과 함께 헤드라인 타이포그래피 등장",
      "caption_highlight": "물리치료사 필독!"
    }},
    {{
      "time_range": "00:05 - 00:16",
      "section": "뉴스 01",
      "narration_snippet": "뉴스 1 나레이션",
      "screen_visual_cue": "[화면 연출] 병원 및 차트/심평원 관련 스톡 영상 + 뉴스 타이틀 팝업",
      "caption_highlight": "뉴스 1 핵심 단어"
    }},
    {{
      "time_range": "00:17 - 00:28",
      "section": "뉴스 02",
      "narration_snippet": "뉴스 2 나레이션",
      "screen_visual_cue": "[화면 연출] 도수치료 및 임상 중재 영상",
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
      "screen_visual_cue": "[화면 연출] 동료 공유 및 팔로우 유도 버튼 애니메이션",
      "caption_highlight": "동료 치료사에게 공유하기!"
    }}
  ],
  "youtube_description": "유튜브 쇼츠 설명란 텍스트 (타임스탬프, 해시태그 포함)"
}}
"""
    return generate_json_response(prompt, temperature=0.3)

def get_fallback_shorts_data(batch_data):
    """API 키 미등록 시 기본 데이터 기반 쇼츠 대본 생성 (물리치료사 타겟)"""
    news_items = batch_data.get("news_items", [])
    batch_title = batch_data.get("batch_title", "물리치료 주간 브리핑")

    hook = "물리치료사 선생님들 주목! 이번 주 임상 현장에서 꼭 알아야 할 핵심 3대 이슈, 40초 만에 빠르게 브리핑합니다."
    
    body_parts = []
    scenes = [
        {
            "time_range": "00:00 - 00:04",
            "section": "오프닝 훅",
            "narration_snippet": hook,
            "screen_visual_cue": "[화면 연출] 사이렌 이모지와 함께 대형 텍스트 '물리치료사 필독 3대 이슈'",
            "caption_highlight": "물리치료사 필독 TOP 3"
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
            "screen_visual_cue": f"[화면 연출] {item.get('category', '물리치료')} 관련 임상 현장 영상 및 자막 강조",
            "caption_highlight": item["headline"][:18]
        })

    outro = "전국의 물리치료사, 재활전문가를 위한 THEPT 주간 브리핑! 유익하셨다면 동료 치료사에게 공유하시고 팔로우해 주세요!"
    scenes.append({
        "time_range": "00:39 - 00:44",
        "section": "아웃트로",
        "narration_snippet": outro,
        "screen_visual_cue": "[화면 연출] 동료 공유 및 팔로우 아이콘 애니메이션",
        "caption_highlight": "동료 치료사에게 공유하기!"
    })

    full_narration = f"{hook} {' '.join(body_parts)} {outro}"

    return {
        "batch_id": batch_data.get("batch_id"),
        "shorts_title": f"🚨 [물리치료사 필독] 이번 주 {batch_title} TOP 3 요약! #shorts",
        "hook_headline": "물리치료사 필독 3대 이슈!",
        "full_narration": full_narration,
        "estimated_seconds": 43,
        "scenes": scenes,
        "youtube_description": f"""물리치료사 및 재활전문가를 위한 이번 주 핵심 실무 브리핑입니다.

00:00 물리치료사 필독 인트로
00:05 1. {news_items[0]['headline'] if len(news_items)>0 else ''}
00:17 2. {news_items[1]['headline'] if len(news_items)>1 else ''}
00:29 3. {news_items[2]['headline'] if len(news_items)>2 else ''}
00:39 마무리

#물리치료사 #도수치료 #재활치료사 #임상물리치료 #물리치료학과 #THEPT
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
