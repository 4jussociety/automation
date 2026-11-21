# 4THEPT SNS 발행 이력 및 성과 로그 (Publish Log)

`sns-publish` 스킬을 통해 실제로 발행(`--publish`)된 Instagram(캐러셀·릴스) 및 YouTube Shorts 콘텐츠를 빠짐없이 기록합니다.
발행 후 48시간~7일 시점에 `py promo_4thept/promo_4thept/scripts/sns_analytics.py --save-report --sync-log`를 실행하면 [analytics_snapshot.md](file:///c:/개발/자동화에이전트/promo_4thept/campaigns/analytics_snapshot.md)가 최신화되고, 아래 테이블에 등록된 YouTube/Instagram ID 행의 조회·도달·저장·좋아요·댓글 수치가 자동으로 동기화됩니다. (`| 메모:` 뒤의 수동 평가 문구는 그대로 보존됩니다.)

---

## 발행 기록 테이블

| 발행일(KST) | 플랫폼 | 트랙 | 프리셋 / 슬롯 | 훅 버전 | 게시물 URL / ID | 성과 메모 (조회 · 저장 · 댓글 · 유입) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 2026-11-21 11:33 | YouTube Shorts (`THEPT (@더피티)`) | Track A (병원 PT) | `shorts_cinematic_v2` (V2 시네마틱 27.58s) | V2: 도수치료 끝나고 밀린 차팅 | [Shorts](https://youtube.com/shorts/6CFHetgqcAY) (`6CFHetgqcAY`) | 발행 완료 (첫 댓글 `Ugx7YP4kbeGkNZBlOsV4AaABAg` · `4thept.com` 단일 표기 · 공식 로고) |
| 2026-11-21 11:33 | Instagram Reels (`@teamthept`) | Track A (병원 PT) | `shorts_cinematic_v2` (V2 시네마틱 27.58s) | V2: 도수치료 끝나고 밀린 차팅 | Reels ID `18361135768216775` | 발행 완료 (첫 댓글 `18030541115921946` · Meta 200 OK · THEPT 월 300분 안내) |

---

## 주간 성과 회고 체크리스트
1. **훅 승률 비교**: 같은 주간 내 A안 vs B안(예: `shorts_female` vs `shorts_male`, 공감형 훅 vs 수치/속도형 훅)의 3초 이탈률 및 저장/공유 수 비교.
2. **트랙별 반응 비교**: Track A(병원 물리치료사) vs Track B(운동·트레이닝·PT 센터) 중 팔로우·댓글 질문 비율 확인 후 다음 주 비중(60:40 <-> 70:30) 조정.
3. **고정 댓글 CTA 점검**: 모든 발행물 첫 댓글에 `https://www.4thept.com/intro` 및 최신 무료 조건(120분/300분)이 정상 노출되었는지 확인.
