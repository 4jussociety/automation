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

def get_fallback_batch(category_key, category_info):
    """API 키가 없거나 테스트용 기본 데이터 생성 (물리치료사 및 재활전문가 타겟)"""
    if category_key == "SET_1_KR_POLICY":
        return {
            "batch_id": category_info["id"],
            "batch_title": "물리치료 실손보험 및 정책 동향 브리핑",
            "target_audience": "물리치료사, 도수치료사, 재활전문가",
            "news_items": [
                {
                    "headline": "실손보험 도수치료 보장 심사 기준 강화 추세",
                    "category": "보험/정책",
                    "source": "메디컬투데이",
                    "summary": "금융당국과 보험업계가 도수치료 청구 급증에 따라 과잉진료 방지 심사 가이드라인을 엄격히 적용하고 있습니다.",
                    "why_it_matters": "치료 소견서와 객관적 기능 평가 기록이 미비할 경우 삭감 및 보험금 부지급 분쟁으로 직결됩니다.",
                    "action_tip": "임상 차트 작성 시 관절가동범위(ROM), VAS 통증척도, 특수이학적 검사 결과를 주기적으로 수치화해 기록하세요."
                },
                {
                    "headline": "의료기사법 개정 논의… 전문물리치료사 역할 확대 목소리",
                    "category": "법률/제도",
                    "source": "청년의사",
                    "summary": "고령화 사회에 발맞춰 재활 및 방문 물리치료 서비스 접근성을 높여야 한다는 법안 개정 논의가 이어지고 있습니다.",
                    "why_it_matters": "방문재활 및 지역사회 통합돌봄 체계에서 물리치료사의 독립적 평가 및 중재 범위가 크게 주목받고 있습니다.",
                    "action_tip": "지역사회 방문재활 수가 및 전문물리치료사 자격 세부 요건 추진 방향을 면밀히 모니터링하세요."
                },
                {
                    "headline": "심평원, 재활 및 물리치료 적정성 평가 지표 개편 예고",
                    "category": "심평원 수가",
                    "source": "의협신문",
                    "summary": "환자 기능 회복도와 정량적 치료 결과를 중심으로 새로운 물리치료 적정성 평가 지표가 단계적으로 도입될 전망입니다.",
                    "why_it_matters": "단순 시행 횟수가 아닌 환자의 기능적 가동성 향상(FIM, 밸런스 지표 등) 실질 데이터가 수가 연동의 핵심이 됩니다.",
                    "action_tip": "치료 전후 기능적 평가 도구를 표준화하고 데이터 기반 임상 경과 기록 체계를 병원 내에 구축하세요."
                }
            ]
        }
    elif category_key == "SET_2_KR_CLINICAL":
        return {
            "batch_id": category_info["id"],
            "batch_title": "국내 최신 재활 연구 및 도수치료 임상 소식",
            "target_audience": "물리치료사, 도수치료사, 재활전문가",
            "news_items": [
                {
                    "headline": "거북목 증후군, 목 신전 운동보다 '턱 당기기(Chin-in)'가 경추 전만 회복에 2배 효과",
                    "category": "임상 연구",
                    "source": "대한물리치료학회지",
                    "summary": "단순 신전보다 심부경추굴곡근(CCF)을 활성화하는 친인 운동이 경추 분절 안정성과 디스크 압력 완화에 통계적으로 유의미한 우위를 보였습니다.",
                    "why_it_matters": "보상작용 없는 심부 굴곡근의 정밀한 격리 활성화가 도수교정 후 재발 방지의 핵심임을 시사합니다.",
                    "action_tip": "임상 중재 시 압력 바이오피드백(PBU)을 활용하여 20~30mmHg 단계별 점진 수축 훈련을 루틴화하세요."
                },
                {
                    "headline": "국내 연구진, 뇌졸중 환자 보행 재활 돕는 웨어러블 외골격 로봇 임상 성공",
                    "category": "신기술/재활로봇",
                    "source": "헬스조선",
                    "summary": "착용형 로봇 보조 물리치료가 보행 대칭성과 지지기 근활성도를 일반 지상 보행 훈련 대비 35% 빠르게 개선시켰습니다.",
                    "why_it_matters": "치료사의 물리적 신체 부담을 줄이면서도 고반복 신경가소성 자극을 최적의 궤적으로 제공할 수 있습니다.",
                    "action_tip": "신경계 물리치료 프로토콜에 로봇 체중지지 보조와 도수 촉진을 결합한 하이브리드 중재를 적극 검토하세요."
                },
                {
                    "headline": "만성 요통 환자, 허리 스트레칭보다 '골반 안정화 호흡' 병행 시 통증 점수 50% 감소",
                    "category": "운동 치료",
                    "source": "코메디닷컴",
                    "summary": "복횡근과 횡격막의 호흡 협응을 통한 복강내압(IAP) 조절이 척추 기립근의 과도한 보상 긴장을 즉시 완화한다는 임상 결과입니다.",
                    "why_it_matters": "과도한 신전 스트레칭은 오히려 척추 불안정성을 악화시킬 수 있으므로 안정화 호흡이 선행되어야 합니다.",
                    "action_tip": "도수치료 직후 환자에게 호기 시 복횡근-골반기저근 동시 수축 시퀀스를 큐잉하여 치료 효과를 유지시키세요."
                }
            ]
        }
    else:
        return {
            "batch_id": category_info["id"],
            "batch_title": "해외 저널 & APTA 글로벌 물리치료 최신 연구",
            "target_audience": "물리치료사, 도수치료사, 재활전문가",
            "news_items": [
                {
                    "headline": "Physical Therapy Journal: 햄스트링 손상 후 편심성(Eccentric) 근력 재활 신규 가이드라인",
                    "category": "글로벌 논문",
                    "source": "Physical Therapy Journal (PTJ)",
                    "summary": "단순 정적 스트레칭보다 원심성 근력 강화 프로토콜이 근섬유 파열 재발률을 60% 이상 현저히 낮춘다는 다기관 RCT 연구입니다.",
                    "why_it_matters": "유연성 증진 중심의 구형 프로토콜에서 고부하 신장성 수축 및 기능적 파워 회복으로 재활 패러다임이 전환되었습니다.",
                    "action_tip": "재활 후기 단계에서 노르딕 햄스트링 프로토콜을 점진적 과부하 원칙에 따라 체계적으로 처방하세요."
                },
                {
                    "headline": "APTA(미국물리치료협회), 유착성 관절낭염(오십견) 임상 실무 지침 개정",
                    "category": "해외 가이드라인",
                    "source": "APTA Clinical Guidelines",
                    "summary": "급성 동통기에는 고강도 관절낭 신장을 전면 금지하고, 통증 한계 내 Grade I~II 진동 수기치료와 신경가동술을 최우선 권고했습니다.",
                    "why_it_matters": "통증기 무리한 도수치료가 활액막 염증을 악화시키는 부작용을 임상 가이드라인 차원에서 공식 명시했습니다.",
                    "action_tip": "Freezing 단계에서는 관절낭 통증 조절에 집중하고, 강력한 엔드필 스트레칭은 Thawing 단계로 엄격히 제한하세요."
                },
                {
                    "headline": "JOSPT: 전방십자인대(ACL) 재건술 후 조기 체중부하 및 대퇴사두근 활성화 프로토콜",
                    "category": "스포츠 물리치료",
                    "source": "Journal of Orthopaedic & Sports Physical Therapy",
                    "summary": "수술 직후 관절가동범위 제한보다 대퇴사두근 근력 결손(AMI) 방지를 위한 신경근 전기자극(NMES) 병행이 복귀 기간을 4주 단축시켰습니다.",
                    "why_it_matters": "수술 후 뇌의 관절성 근억제를 얼마나 빠르게 해소하느냐가 스포츠 복귀 성공률의 핵심 분기점이 됩니다.",
                    "action_tip": "수술 1주차부터 등장성 대퇴사두근 세팅 훈련 시 NMES를 병행하여 대퇴사두근 활성화를 조기 복원하세요."
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
