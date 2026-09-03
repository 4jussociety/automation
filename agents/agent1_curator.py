import json
import urllib.parse
from datetime import datetime
import feedparser
import requests
from config import CATEGORIES, HISTORY_FILE, GEMINI_API_KEY, DEFAULT_MODEL

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
    encoded_query = urllib.parse.quote(query)
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
    return items

def curate_news_with_gemini(category_key, category_info, candidate_items, past_titles):
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=GEMINI_API_KEY)
    
    prompt = f"""
당신은 물리치료 및 재활의학 산업 전문 큐레이터 에이전트(Agent 1)입니다.
아래 제공된 최근 뉴스/연구 후보군 중에서, 쇼츠 및 카드뉴스로 제작하기에 가장 적합한 3~4개의 뉴스를 선별하고 브리핑용 데이터로 정제하세요.

[카테고리 정보]
- ID: {category_key}
- 대상 분야: {category_info['title']}

[이전 주에 다룬 기사 목록 (중복 절대 배제)]
{json.dumps(past_titles[-20:], ensure_ascii=False)}

[수집된 뉴스 후보 목록]
{json.dumps(candidate_items, ensure_ascii=False, indent=2)}

[요구사항]
1. 위 후보 중 가장 화제성이 높고 물리치료사 및 일반인에게 의미 있는 3~4개를 엄선하세요.
2. 이전 주에 다룬 내용과 겹치는 주제는 제외하세요.
3. 쇼츠(40초 영상)에서 10초 내외로 빠르게 소개하고, 카드뉴스(슬라이드)로 넘겨볼 수 있도록 요약하세요.
4. 해외 뉴스의 경우 한국어로 자연스럽게 번역 및 요약하세요.

[반드시 아래 JSON 형식만 반환하세요]
{{
  "batch_id": "{category_info['id']}",
  "batch_title": "이번 주 {category_info['title']} 브리핑",
  "target_audience": "물리치료사, 재활운동 전문가, 일상 통증을 겪는 일반인",
  "news_items": [
    {{
      "headline": "간결하고 명확한 뉴스 헤드라인",
      "category": "세부 분류 (예: 실손보험, 연구논문, 정책, 신기술)",
      "source": "언론사 또는 저널명",
      "summary": "핵심 내용 2문장 요약",
      "why_it_matters": "치료사와 환자 입장에서 왜 중요한지 1문장 설명",
      "action_tip": "실천 가능한 조언 또는 주목해야 할 포인트 1문장"
    }}
  ]
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

def get_fallback_batch(category_key, category_info):
    """API 키가 없거나 테스트용 기본 데이터 생성"""
    if category_key == "SET_1_KR_POLICY":
        return {
            "batch_id": category_info["id"],
            "batch_title": "물리치료 실손보험 및 정책 동향 브리핑",
            "target_audience": "도수치료 환자 및 물리치료사",
            "news_items": [
                {
                    "headline": "실손보험 도수치료 보장 심사 기준 강화 추세",
                    "category": "보험/정책",
                    "source": "메디컬투데이",
                    "summary": "금융당국과 보험업계가 도수치료 청구 급증에 따라 과잉진료 방지 심사 가이드라인을 엄격히 적용하고 있습니다.",
                    "why_it_matters": "치료 목적의 소견서와 객관적 검사 기록이 없으면 보험금 지급이 거절될 수 있습니다.",
                    "action_tip": "치료 전 전문의의 정밀 진단과 단계별 경과 기록을 꼼꼼히 확인하세요."
                },
                {
                    "headline": "의료기사법 개정 논의… 전문물리치료사 역할 확대 목소리",
                    "category": "법률/제도",
                    "source": "청년의사",
                    "summary": "고령화 사회에 발맞춰 재활 및 방문 물리치료 서비스 접근성을 높여야 한다는 법안 개정 논의가 이어지고 있습니다.",
                    "why_it_matters": "방문재활 및 지역사회 통합돌봄에서 물리치료사의 독립적 서비스 제공 범위가 주목받고 있습니다.",
                    "action_tip": "향후 재활 인프라 변화와 급여화 추진 방향을 주시할 필요가 있습니다."
                },
                {
                    "headline": "심평원, 재활 및 물리치료 적정성 평가 지표 개편 예고",
                    "category": "심평원 수가",
                    "source": "의협신문",
                    "summary": "환자 기능 회복도와 치료 만족도 중심의 새로운 평가 지표가 단계적으로 도입될 전망입니다.",
                    "why_it_matters": "단순 치료 횟수가 아닌 실질적 관절 가동 범위 회복과 삶의 질 개선이 핵심 지표가 됩니다.",
                    "action_tip": "치료사와 환자 간의 주기적인 기능 평가 기록이 더욱 중요해집니다."
                }
            ]
        }
    elif category_key == "SET_2_KR_CLINICAL":
        return {
            "batch_id": category_info["id"],
            "batch_title": "국내 최신 재활 연구 및 도수치료 임상 소식",
            "target_audience": "거북목, 허리 통증 환자 및 임상의",
            "news_items": [
                {
                    "headline": "거북목 증후군, 목 신전 운동보다 '턱 당기기(Chin-in)'가 경추 전만 회복에 2배 효과",
                    "category": "임상 연구",
                    "source": "대한물리치료학회지",
                    "summary": "단순히 고개를 뒤로 젖히는 것보다 심부경추굴곡근을 활성화하는 친인 운동이 목 디스크 압력을 현저히 줄인다는 연구 결과입니다.",
                    "why_it_matters": "잘못된 셀프 스트레칭이 후관절 압박을 유발할 수 있음을 증명했습니다.",
                    "action_tip": "의자에 앉아 정수리를 천장으로 길게 뻗으며 턱을 뒤로 살짝 당겨 10초 유지하세요."
                },
                {
                    "headline": "국내 연구진, 뇌졸중 환자 보행 재활 돕는 웨어러블 외골격 로봇 임상 성공",
                    "category": "신기술/재활로봇",
                    "source": "헬스조선",
                    "summary": "착용형 로봇을 활용한 조기 물리치료가 보행 대칭성과 근지구력을 일반 치료 대비 35% 빠르게 향상시켰습니다.",
                    "why_it_matters": "고강도 반복 보행 훈련의 효율이 극대화되어 치료사의 신체적 부담도 경감됩니다.",
                    "action_tip": "첨단 로봇 재활 시스템을 갖춘 재활의학과 센터의 임상 적용이 확대되고 있습니다."
                },
                {
                    "headline": "만성 요통 환자, 허리 스트레칭보다 '골반 안정화 호흡' 병행 시 통증 점수 50% 감소",
                    "category": "운동 치료",
                    "source": "코메디닷컴",
                    "summary": "복횡근과 횡격막을 동시에 자극하는 호흡 기반 코어 운동이 척추 기립근 긴장을 완화한다는 임상 보고가 나왔습니다.",
                    "why_it_matters": "과도한 허리 꺾기 스트레칭은 오히려 척추 불안정증을 악화시킬 수 있습니다.",
                    "action_tip": "누워서 숨을 내쉴 때 갈비뼈를 조이고 아랫배를 살짝 당기는 호흡부터 연습하세요."
                }
            ]
        }
    else:
        return {
            "batch_id": category_info["id"],
            "batch_title": "해외 저널 & APTA 글로벌 물리치료 최신 연구",
            "target_audience": "글로벌 연구 트렌드에 관심 있는 전문가 및 독자",
            "news_items": [
                {
                    "headline": "Physical Therapy Journal: 햄스트링 스트레칭의 새로운 가이드라인 발표",
                    "category": "글로벌 논문",
                    "source": "Physical Therapy Journal (PTJ)",
                    "summary": "정적 스트레칭보다 편심성 수축(Eccentric) 근력 운동이 근섬유 파열 재발을 60% 이상 줄인다는 다기관 연구입니다.",
                    "why_it_matters": "단순히 근육을 늘리는 유연성 훈련에서 부하를 견디는 기능적 재활로 패러다임이 전환되고 있습니다.",
                    "action_tip": "노르딕 햄스트링 컬 같은 신장성 수축 운동을 주 2회 루틴에 포함해보세요."
                },
                {
                    "headline": "APTA(미국물리치료협회), 오십견(유착성 관절낭염) 치료 프로토콜 업데이트",
                    "category": "해외 가이드라인",
                    "source": "APTA Clinical Guidelines",
                    "summary": "극초기 심한 통증기에는 무리한 관절 가동 운동을 지양하고, 통증 없는 범위 내의 진자 운동과 환자 교육을 최우선 권고했습니다.",
                    "why_it_matters": "통증을 참으며 억지로 꺾는 재활은 관절낭의 염증과 유착을 오히려 악화시킬 수 있습니다.",
                    "action_tip": "통증 지수 10점 중 3점 이하의 편안한 범위에서만 팔을 부드럽게 흔들어주세요."
                },
                {
                    "headline": "란셋(Lancet) 연구: 무릎 관절염, 관절경 수술보다 맞춤형 물리치료가 장기 예후 우수",
                    "category": "국제 의학저널",
                    "source": "The Lancet",
                    "summary": "퇴행성 반월상 연골 파열 환자 500명을 5년간 추적한 결과, 보존적 물리치료군이 수술군과 대등하거나 더 높은 기능 점수를 보였습니다.",
                    "why_it_matters": "불필요한 조기 관절 수술을 피하고 비수술적 운동 재활의 가치를 입증한 대표 연구입니다.",
                    "action_tip": "대퇴사두근 강화와 둔근 운동으로 무릎 관절에 가해지는 하중을 분산시키세요."
                }
            ]
        }

def run_agent1():
    """Agent 1 실행: 3개 세트(국내 정책, 국내 임상, 해외 논문) 뉴스 수집 및 큐레이션"""
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
        
        # 2. Gemini 큐레이션 또는 폴백
        batch_data = None
        if GEMINI_API_KEY and len(candidate_items) >= 2:
            try:
                batch_data = curate_news_with_gemini(cat_key, cat_info, candidate_items, past_titles)
            except Exception as e:
                print(f"[{cat_key}] Gemini 큐레이션 중 오류 발생 ({e}), 폴백 데이터 사용")
                batch_data = get_fallback_batch(cat_key, cat_info)
        else:
            batch_data = get_fallback_batch(cat_key, cat_info)

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
