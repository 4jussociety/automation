# 이 파일은 THEPT 물리치료 콘텐츠 자동 생성 시스템의 진입점입니다.
# 2단계 마크다운 큐레이션 및 주 6일 콘텐츠 발행 CLI(curate.py)로 일원화되었습니다.

import sys
from pathlib import Path

# 윈도우 콘솔 UTF-8 출력 보장
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from curate import main

if __name__ == "__main__":
    main()


