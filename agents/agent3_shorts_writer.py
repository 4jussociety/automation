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

def run_agent3(batch_data):
    """Agent 3 실행: 배치 데이터 -> 40초 쇼츠 영상 대본 및 연출안 생성"""
    if not GEMINI_API_KEY:
        raise ValueError("[Agent 3] GEMINI_API_KEY가 설정되지 않았습니다. .env 파일을 확인하세요.")

    return generate_shorts_script_with_gemini(batch_data)
