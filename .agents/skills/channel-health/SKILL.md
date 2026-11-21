---
name: channel-health
description: >-
  THEPT YouTube 채널(UCbwC2jK9J-179R2Un3T0xPA / PLTEYR_IZibwI) 및 Instagram(@teamthept) OAuth/Graph API
  토큰 유효성 진단, 재인증(auth-yt), GitHub Secrets 내보내기(export-yt-secrets), 시뮬레이션(--dry-run)을 수행하는 스킬.
  사용자가 "토큰 확인해줘", "채널 연결 확인", "유튜브 인증해줘", "업로드 테스트해줘" 등을 요청할 때 활성화한다.
---

# THEPT 채널 & 토큰 헬스체크 스킬 (`channel-health`)

## 목표 채널 기준
- **YouTube 목표 채널**: `THEPT` (`UCbwC2jK9J-179R2Un3T0xPA`), 기본 재생목록 `PLTEYR_IZibwI`
- **Instagram 목표 계정**: `@teamthept` (`17841477942436147`, Facebook Graph API `EAA...` 토큰)

## Steps
1. **YouTube 채널 일치 및 토큰 진단**:
   ```powershell
   python curate.py test-yt
   ```
   - 목표 채널(`THEPT`)과 불일치할 경우 `python curate.py auth-yt --reauth` 실행 시 **`THEPT` 브랜드 채널**을 선택한 뒤 `python curate.py export-yt-secrets`로 GitHub Secret(`YOUTUBE_TOKEN_BASE64`) 갱신을 안내합니다.
2. **Instagram 계정 및 토큰 진단**:
   ```powershell
   python curate.py test-insta
   ```
3. **안전 시뮬레이션 검증**:
   ```powershell
   python curate.py upload --today-only --dry-run
   ```
   - 실제 업로드 API를 호출하지 않고 메타데이터, GitHub Raw URL, UTM 첫 댓글 매핑을 검증합니다.
