import json
import urllib.parse
from datetime import datetime
import feedparser
from config import CATEGORIES, HISTORY_FILE, GEMINI_API_KEY

def load_history():
    if HISTORY_FILE.exists():
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"processed_weeks": [], "history": []}

def save_history(history_data):
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history_data, f, ensure_ascii=False, indent=2)

def fetch_rss_news(query, is_korean=True, max_items=10):
    # 최근 7일(전주) 이내 기사 엄격 검색 (when:7d)
    query_7d = f"{query} when:7d"
    encoded_query = urllib.parse.quote(query_7d)
    if is_korean:
        url = f"https://news.google.com/rss/search?q={encoded_query}&hl=ko&gl=KR&ceid=KR:ko"
    else:
        url = f"https://news.google.com/rss/search?q={encoded_query}&hl=en-US&gl=US&ceid=US:en"
    
    feed = feedparser.parse(url)
    items = []
    for entry in feed.entries[:max_items]:
        items.append({
            "title": entry.title,
            "link": entry.link,
            "published": getattr(entry, "published", ""),
            "summary": getattr(entry, "summary", "")
        })

    # 만약 최근 7일 내 기사가 부족한 경우에만 일반 검색으로 보완
    if len(items) < 2:
        encoded_query_fallback = urllib.parse.quote(query)
        if is_korean:
            url_fallback = f"https://news.google.com/rss/search?q={encoded_query_fallback}&hl=ko&gl=KR&ceid=KR:ko"
        else:
            url_fallback = f"https://news.google.com/rss/search?q={encoded_query_fallback}&hl=en-US&gl=US&ceid=US:en"
        feed_fallback = feedparser.parse(url_fallback)
        for entry in feed_fallback.entries[:max_items]:
            if not any(it["link"] == entry.link for it in items):
                items.append({
                    "title": entry.title,
                    "link": entry.link,
                    "published": getattr(entry, "published", ""),
                    "summary": getattr(entry, "summary", "")
                })
            if len(items) >= max_items:
                break

    return items

from agents.llm_helper import generate_json_response

def curate_news_with_gemini(category_key, category_info, candidate_items, past_titles):
    prompt = f"""
당신은 물리치료 및 재활의학 산업 전문 큐레이터 에이전트(Agent 1)입니다.
아래 제공된 최근 뉴스/연구 후보군 중에서, 쇼츠 및 카드뉴스로 제작하기에 가장 적합한 3~4개의 뉴스를 선별하고 브리핑용 데이터로 정제하세요.

[🎯 핵심 타겟 오디언스]
- 타겟 독자: 오직 물리치료사(PT), 도수치료사, 재활의학 임상가, 재활운동 전문가, 작업치료사(OT)입니다.
- 🚫 엄격한 제외 기준: 일반인을 위한 단순 건강상식(예: 집에서 하는 스트레칭, 목 디스크 초기증상 등)은 절대 선별하지 마세요!
- ✅ 필수 선별 기준: 임상 현장 실무에 직접적으로 영향을 주는 정책(실손보험 도수치료 인정기준, 심평원 물리치료 급여/비급여 고시), 제도 및 법안(의료기사법, 전문물리치료사), 최신 학술 임상 프로토콜(RCT 논문, JOSPT 등 해외 저널 가이드라인), 재활 신기술(로봇 치료, 정량적 평가 장비)만 엄선하세요.

[카테고리 정보]
- ID: {category_key}
- 대상 분야: {category_info['title']}

[이전 주에 다룬 기사 목록 (중복 절대 배제)]
{json.dumps(past_titles[-20:], ensure_ascii=False)}

[수집된 뉴스 후보 목록]
{json.dumps(candidate_items, ensure_ascii=False, indent=2)}

[요구사항]
1. 위 후보 중 물리치료사 및 재활전문가 실무에 가장 유익하고 시의성 높은 3~4개를 엄선하세요.
2. 이전 주에 다룬 내용과 겹치는 주제는 제외하세요.
3. 쇼츠(40초 영상)에서 10초 내외로 빠르게 소개하고, 카드뉴스(슬라이드)로 넘겨볼 수 있도록 요약하세요.
5. 각 기사의 link 필드에는 제공된 [수집된 뉴스 후보 목록]에서 해당 기사의 link URL을 그대로 정확하게 기입하세요.

[반드시 아래 JSON 형식만 반환하세요]
{{
  "batch_id": "{category_info['id']}",
  "batch_title": "이번 주 {category_info['title']} 브리핑",
  "target_audience": "물리치료사, 도수치료사, 재활전문가",
  "news_items": [
    {{
      "headline": "임상 치료사의 시선을 사로잡는 명확한 전문 헤드라인 (말줄임 없이 온전한 문장)",
      "category": "세부 분류 (예: 실손보험, 임상연구, 정책/수가, 재활신기술)",
      "source": "언론사 또는 학술 저널명",
      "link": "해당 후보 기사의 원문 링크 URL",
      "summary": "임상 전문가 관점에서의 핵심 내용 2문장 요약",
      "why_it_matters": "치료사의 임상 중재, 평가 기록, 청구 삭감 방지 관점에서 왜 중요한지 1문장",
      "action_tip": "치료사가 내일 임상 차팅이나 환자 중재 시 즉각 적용할 수 있는 구체적인 실무 팁 1문장"
    }}
  ]
}}
"""
    result = generate_json_response(prompt, temperature=0.3)
    # URL 누락 시 후보 기사에서 자동 매칭
    for item in result.get("news_items", []):
        if not item.get("link"):
            best_link = ""
            for c in candidate_items:
                if any(word in c.get("title", "") for word in item.get("headline", "").split()[:3]):
                    best_link = c.get("link", "")
                    break
            item["link"] = best_link or (candidate_items[0]["link"] if candidate_items else "")
    return result

def run_agent1():
    """Agent 1 실행: 3개 세트(국내 정책, 국내 임상, 해외 논문) 뉴스 수집 및 큐레이션"""
    if not GEMINI_API_KEY:
        raise ValueError("[Agent 1] GEMINI_API_KEY가 설정되지 않았습니다. .env 파일을 확인하세요.")

    history_data = load_history()
    past_titles = [item["headline"] for item in history_data.get("history", [])]

    results = []
    for cat_key, cat_info in CATEGORIES.items():
        is_korean = (cat_key != "SET_3_GLOBAL")
        
        # 1. RSS 검색
        candidate_items = []
        for q in cat_info["rss_queries"]:
            candidates = fetch_rss_news(q, is_korean=is_korean, max_items=5)
            for c in candidates:
                if not any(c["title"] == prev for prev in past_titles):
                    candidate_items.append(c)
        
        if len(candidate_items) < 2:
            raise RuntimeError(
                f"[Agent 1 - {cat_key}] '{cat_info['title']}' 후보 기사가 {len(candidate_items)}건으로 부족하여 큐레이션을 진행할 수 없습니다. 검색 쿼리를 점검하세요."
            )

        # 2. Gemini 큐레이션 (실패 시 즉시 예외 발생)
        batch_data = curate_news_with_gemini(cat_key, cat_info, candidate_items, past_titles)
        batch_data["source_articles"] = candidate_items
        results.append(batch_data)

        # 히스토리에 추가
        for item in batch_data.get("news_items", []):
            history_data["history"].append({
                "headline": item["headline"],
                "category": item.get("category", ""),
                "date": datetime.now().strftime("%Y-%m-%d")
            })

    save_history(history_data)
    return results

if __name__ == "__main__":
    batches = run_agent1()
    print(f"총 {len(batches)}개 배치 수집 완료:")
    for b in batches:
        print(f"- {b['batch_title']} (뉴스 {len(b['news_items'])}건)")
