# 이 모듈은 OpenAI GPT 모델을 활용하여 물리치료 뉴스 기사를 고품질 카드뉴스 3줄 요약 및 쇼츠 대본으로 압축합니다.
# 기사 문맥, 핵심 수치, 물리치료 임상 및 제도 파급효과를 완결된 한국어 문장으로 생성합니다.

import json
import os
import re
import hashlib
from pathlib import Path
from config import BASE_DIR, OPENAI_API_KEY, OPENAI_MODEL

CACHE_FILE = BASE_DIR / "data" / "llm_summary_cache.json"


def _load_cache() -> dict:
    if CACHE_FILE.exists():
        try:
            return json.loads(CACHE_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _save_cache(cache_data: dict):
    try:
        CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        CACHE_FILE.write_text(json.dumps(cache_data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as e:
        print(f"  [LLM Cache] 캐시 저장 실패: {e}")


def _get_article_key(article: dict) -> str:
    """기사 고유 식별 키 생성 (ID 우선, 없으면 URL 또는 제목 해시)"""
    art_id = article.get("id")
    if art_id:
        return str(art_id)
    link = article.get("link", "")
    title = article.get("title", "")
    raw = f"{link}_{title}"
    return hashlib.md5(raw.encode("utf-8")).hexdigest()


def build_system_prompt(is_global: bool = False) -> str:
    global_rules = ""
    if is_global:
        global_rules = """
4. [글로벌 기사 전용] story_summary 작성 규칙:
   - 기사의 핵심 내용을 유튜브 설명란 및 인스타그램 캡션에 게시하기 위한 4~6문장 완결형 한국어 번역 스토리텔링 브리핑 단락입니다 (공백 포함 약 350~450자).
   - 서술 흐름: [연구 배경 및 이슈 ➔ 핵심 임상 연구 결과/통계 수치 ➔ 대한민국 물리치료사 임상 실무 관점의 파급효과와 시사점]이 하나의 자연스러운 단락으로 이어지도록 작성하십시오.
   - 모든 문장은 '~습니다, ~됩니다, ~권고됩니다' 등 신뢰감 있는 전문 기자 톤으로 완결하십시오.
"""
    json_format = """{
  "headline": "...",
  "bullets": [
    "첫 번째 불릿 문장...",
    "두 번째 불릿 문장...",
    "세 번째 불릿 문장..."
  ],
  "highlight": "💡 포인트: ...",
  "narration_body": "...\""""
    if is_global:
        json_format += ',\n  "story_summary": "4~6문장(350~450자)의 완성도 높은 번역 브리핑 단락..."\n}'
    else:
        json_format += "\n}"

    return f"""당신은 대한민국 1위 물리치료 전문 미디어 'THEPT'의 수석 전문기자이자 방송 앵커입니다.
제공되는 뉴스 기사(국내 정책, 임상 연구, 해외 APTA 동향, 디지털 재활 등)를 정밀 분석하여, 
인스타그램 4:5 카드뉴스와 9:16 유튜브 쇼츠에 최적화된 고품격 3줄 요약과 나레이션 대본을 작성해야 합니다.

[작성 지침 및 엄격한 규칙]
1. 완결된 문장: 모든 문장은 서술어가 명확히 종결된 완결형 문장이어야 합니다. 문장이 중간에 잘리거나 '~관련 최신 동향이 발표되었습니다' 같은 무성의한 땜질 어미를 절대 사용하지 마십시오.
2. 카드뉴스 레이아웃 규격 (글자 수 엄수):
   - headline: 카드뉴스 1080x1350 상단용. 공백 포함 18~34자 이내 (최대 2줄). 강렬하고 직관적인 헤드라인.
   - bullets (정확히 3개):
     * 불릿 1 [핵심 팩트]: 주체와 핵심 사건, 공식 발표/시행 골자를 명확히 제시 (공백 포함 42~54자).
     * 불릿 2 [구체적 배경/수치]: 제도적 변경점, 구체적 통계 수치(비율/금액/대상), 임상적 근거 명시 (공백 포함 42~54자).
     * 불릿 3 [현장 파급효과/시사점]: 물리치료사 임상 실무, 병의원 운영, 수가/급여, 환자 치료 접근성에 미치는 영향 (공백 포함 42~54자).
     * 3개 불릿의 총 글자 수 합계는 반드시 130자~162자 이내여야 합니다.
   - highlight: "💡 포인트: "로 시작하며, 해당 기사 내용에 직접 기반한 치료사를 위한 원포인트 실무 대응 조언 (공백 포함 40~55자).
   - narration_body: 유튜브 쇼츠용 본문 대본. 신뢰감 있고 정중한 아나운서 방송 브리핑 구어체(~습니다, ~됩니다, ~대비가 필요합니다 등)로 100~135자 내외 작성.

3. 전문 용어 및 글로벌 기사:
   - 영문 기사(APTA, PubMed, Medscape 등)인 경우 자연스러운 대한민국 물리치료 임상 표준 용어로 완벽히 번역하여 요약하십시오.
   - 허위 정보나 과장을 지양하고, 기사 본문과 요약의 사실(Fact)에 엄격히 입각하십시오.
{global_rules}
[반환 형식]
반드시 다음 키를 가진 순수 JSON 객체만 반환하십시오:
{json_format}"""


def summarize_article_with_llm(article: dict, is_global: bool = False) -> dict:
    """
    OpenAI GPT 모델을 호출하여 기사를 구조화된 3줄 불릿, 헤드라인, 하이라이트, 쇼츠 나레이션 및 글로벌 스토리 번역 브리핑으로 요약합니다.
    캐시가 존재하면 API 호출 없이 캐시를 반환합니다.
    """
    cache_key = _get_article_key(article)
    cache = _load_cache()

    if cache_key in cache:
        cached_result = cache[cache_key]
        if (
            isinstance(cached_result, dict)
            and "headline" in cached_result
            and "bullets" in cached_result
            and len(cached_result["bullets"]) == 3
            and (not is_global or cached_result.get("story_summary"))
        ):
            return cached_result

    if not OPENAI_API_KEY:
        raise ValueError("OPENAI_API_KEY가 설정되지 않았습니다.")

    title = article.get("title", "")
    desc = article.get("description", "")
    raw_body = article.get("article_body_raw", "")
    body = raw_body or article.get("article_body", "") or article.get("body_text", "")
    category = article.get("category", "") or article.get("category_title", "")
    source = article.get("source", "")
    pub_date = article.get("pub_date", "")

    user_prompt = f"""[기사 정보]
- 카테고리: {category}
- 출처/발행일: {source} ({pub_date})
- 제목: {title}
- 핵심 요약: {desc}
- 본문 발췌: {body[:2500]}
- 글로벌 기사 여부: {'예 (영문 - 상세 번역 브리핑 필수)' if is_global else '아니오'}

위 기사를 분석하여 카드뉴스 디자인 규격에 맞춘 JSON 요약을 작성해 주세요."""

    # 1. OpenAI SDK 호출 시도
    result_data = None
    try:
        from openai import OpenAI
        client = OpenAI(api_key=OPENAI_API_KEY)
        response = client.chat.completions.create(
            model=OPENAI_MODEL or "gpt-4o-mini",
            messages=[
                {"role": "system", "content": build_system_prompt(is_global=is_global)},
                {"role": "user", "content": user_prompt}
            ],
            response_format={"type": "json_object"},
            temperature=0.3,
        )
        content_text = response.choices[0].message.content
        result_data = json.loads(content_text)

    except ImportError:
        # SDK가 없을 경우 requests로 직접 REST API 호출
        import requests
        headers = {
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": OPENAI_MODEL or "gpt-4o-mini",
            "messages": [
                {"role": "system", "content": build_system_prompt(is_global=is_global)},
                {"role": "user", "content": user_prompt}
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.3
        }
        resp = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        content_text = data["choices"][0]["message"]["content"]
        result_data = json.loads(content_text)

    if not result_data:
        raise RuntimeError("LLM 요약 응답을 파싱하지 못했습니다.")

    # 반환 데이터 정제 및 규격 확인
    headline = result_data.get("headline", "").strip()
    bullets = result_data.get("bullets", [])
    highlight = result_data.get("highlight", "").strip()
    narration_body = result_data.get("narration_body", "").strip()
    story_summary = result_data.get("story_summary", "").strip()

    # 불릿 개수 3개 보장
    if len(bullets) < 3:
        while len(bullets) < 3:
            bullets.append("현장 물리치료사의 체계적인 임상 대응과 지속적인 관심이 필요합니다.")
    bullets = bullets[:3]

    # 각 불릿 끝 종결 부호 점검
    refined_bullets = []
    for b in bullets:
        b_clean = b.strip()
        if not b_clean.endswith(('.', '!', '?')):
            b_clean += '.'
        refined_bullets.append(b_clean)

    if not highlight.startswith("💡 포인트:"):
        highlight = f"💡 포인트: {highlight.lstrip('💡').lstrip('포인트:').strip()}"
    if not highlight.endswith(('.', '!', '?')):
        highlight += '.'

    if not narration_body.endswith(('.', '!', '?')):
        narration_body += '.'

    if is_global and not story_summary:
        # 글로벌 기사인데 story_summary가 누락되었을 경우 3대 불릿과 포인트를 결합하여 완성형 단락 구축
        story_summary = f"{refined_bullets[0]} {refined_bullets[1]} {refined_bullets[2]} {highlight.replace('💡 포인트: ', '').strip()}"

    final_result = {
        "headline": headline,
        "bullets": refined_bullets,
        "highlight": highlight,
        "narration_body": narration_body,
        "story_summary": story_summary
    }

    # 캐시 저장
    cache[cache_key] = final_result
    _save_cache(cache)

    return final_result
