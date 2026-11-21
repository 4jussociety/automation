---
name: sns-analytics
description: >-
  THEPT YouTube(THEPT 채널) 및 Instagram(@teamthept) 최근 성과 조회, 4THEPT 제품 홍보 슬롯과의 분리 현황 점검,
  당일 중복 업로드 탐지 및 마케팅 컴플라이언스 검증을 수행하는 스킬.
  사용자가 "성과 분석해줘", "조회수 확인해줘", "컴플라이언스 검사해줘", "중복 업로드 확인" 등을 요청할 때 활성화한다.
---

# THEPT SNS 성과 분석 & 컴플라이언스 스킬 (`sns-analytics`)

## 공유 계정 슬롯 분리 원칙 (`@teamthept`)
- **오전 정기 슬롯 (07:00~12:00 KST)**: `자동화에이전트` 주간 뉴스 브리핑 (`THEPT 주간 브리핑`)
- **저녁/비정기 슬롯 (18:00~22:00 KST)**: `4THEPT` 제품 홍보 (`4THEPT 제품 홍보`)
- 성과 수집 시 두 슬롯을 구분 집계하고, 동일 날짜/포맷/브리핑 중복 여부를 감시합니다.

## Steps
1. **실시간 성과 및 중복 리포트**:
   ```powershell
   python curate.py analytics --limit 20 --save-report --sync-log
   ```
   - `결과물/THEPT뉴스/analytics_report.md` 및 `결과물/4THEPT마케팅/analytics_snapshot.md` 생성, `publish_log.md` 동기화, 조회/도달/저장/평균시청시간·중복 경고 확인.
2. **통합 마케팅 컴플라이언스 & 쇼츠 60초 규격 검사**:
   ```powershell
   python curate.py check
   ```
   - `THEPT뉴스` 패키지 + `4THEPT마케팅` 프리셋·플레이북·초안의 금지 용어(`병원/의원`, `매니저`, `센터장`, 퇴출 직군), SaMD 과장 표현, `[초안]` 고지·UTM 링크·60초 초과 여부 일괄 점검.
3. **벤치마킹 공식 반영**:
   - 고성과 벤치마크 기준(0~3초 손실 회피/질문형 훅, 6.1~6.8자/초 고속 호흡, 60초 이내 완주율 최적화)을 참고해 대본/템플릿을 개선합니다.
