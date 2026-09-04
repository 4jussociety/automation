# Google Gemini 최신 Flash 모델(gemini-flash-latest)을 호출하여 JSON 응답을 생성하는 헬퍼 모듈입니다.
# 에이전트 파이프라인의 콘텐츠 생성 및 자동 최신 모델 연동을 담당합니다.

import json
import time
from config import GEMINI_API_KEY, DEFAULT_MODEL

def generate_json_response(prompt: str, temperature: float = 0.3, max_retries: int = 3) -> dict:
    """Google 공식 최신 별칭 모델을 단독으로 호출하며, 일시적 503 발생 시 재시도합니다."""
    from google import genai
    from google.genai import types

    if not GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY가 설정되지 않았습니다. .env 파일을 확인하세요.")

    client = genai.Client(api_key=GEMINI_API_KEY)
    config = types.GenerateContentConfig(
        response_mime_type="application/json",
        temperature=temperature
    )

    last_error = None
    for attempt in range(1, max_retries + 1):
        try:
            response = client.models.generate_content(
                model=DEFAULT_MODEL,
                contents=prompt,
                config=config
            )
            return json.loads(response.text)
        except Exception as e:
            last_error = e
            err_msg = str(e)
            # 503 등 주요 에러 요약 추출
            err_summary = "503 서버 과부하" if "503" in err_msg else err_msg[:100]
            if attempt < max_retries:
                wait_sec = 8 * attempt
                print(f"[{DEFAULT_MODEL}] API 오류 ({err_summary}) -> 재시도 {attempt}/{max_retries} ({wait_sec}초 후)...")
                time.sleep(wait_sec)

    print(f"\n❌ [{DEFAULT_MODEL}] {max_retries}회 재시도 모두 실패! 최종 오류: {last_error}")
    raise RuntimeError(f"[{DEFAULT_MODEL}] Gemini API 호출이 {max_retries}회 재시도 후 최종 실패했습니다: {last_error}") from last_error
