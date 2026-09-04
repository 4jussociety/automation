# Playwright 기반 인스타그램 브라우저 캐러셀(6장 4:5) 자동 예약 업로드 및 첫댓글 모듈
import os
import sys
import time
import argparse
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Optional

from playwright.sync_api import sync_playwright, Page, BrowserContext

from config import (
    BASE_DIR,
    ASSETS_DIR,
    INSTAGRAM_SESSION_FILE,
    INSTAGRAM_SCHEDULE_DEFAULT_HOUR,
    INSTAGRAM_HEADLESS,
)

INSTAGRAM_URL = "https://www.instagram.com/"

def generate_first_comment_text(batch_data: dict = None) -> str:
    """
    치료사 참여 유도 및 출처 확인을 위한 고품질 첫댓글 템플릿을 생성합니다.
    """
    return (
        "📌 [물리치료사 커뮤니티 한마디]\n"
        "선생님 병원에서는 이번 개편 기준이나 신기술 프로토콜에 어떻게 대비하고 계신가요?\n\n"
        "· 본 브리핑의 상세 원문 링크 및 해외 저널 출처는 프로필 링크의 [주간 브리핑 출처 모음]에서 확인하실 수 있습니다.\n"
        "· 원내 동료 치료사 선생님들께도 공유해 함께 스터디해 보세요! 🩺"
    )

class InstagramBrowserUploader:
    def __init__(self, session_path: Path = INSTAGRAM_SESSION_FILE, headless: bool = INSTAGRAM_HEADLESS):
        self.session_path = session_path
        self.headless = headless
        self.session_path.parent.mkdir(parents=True, exist_ok=True)

    def is_session_available(self) -> bool:
        """저장된 로그인 세션 파일이 존재하는지 확인합니다."""
        return self.session_path.exists() and self.session_path.stat().st_size > 100

    def interactive_login(self):
        """
        사용자가 직접 브라우저에서 인스타그램에 로그인하고,
        로그인이 완료되면 세션(Cookie, LocalStorage)을 파일로 영구 저장합니다.
        """
        print("\n" + "=" * 60)
        print(" 🔑 인스타그램 1회 로그인 세션 생성기")
        print(" 브라우저 창이 열리면 인스타그램 계정으로 로그인해 주세요.")
        print(" (2단계 인증이 있으시면 인증 번호까지 완료해 주세요.)")
        print(" 로그인 완료 후 홈 피드가 로드되면 세션이 자동으로 저장됩니다.")
        print("=" * 60)

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False)
            context = browser.new_context(
                viewport={"width": 1280, "height": 900},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            )
            page = context.new_page()
            page.goto(INSTAGRAM_URL)

            print(" 👉 브라우저에서 로그인을 진행해 주세요... (최대 3분 대기)")
            logged_in = False
            for _ in range(180):
                time.sleep(1)
                try:
                    if (
                        page.locator("svg[aria-label='홈']").count() > 0
                        or page.locator("svg[aria-label='Home']").count() > 0
                        or page.locator("svg[aria-label='만들기']").count() > 0
                        or page.locator("svg[aria-label='New post']").count() > 0
                        or "accounts/login" not in page.url
                    ):
                        if page.locator("input[name='password']").count() == 0 and page.url != INSTAGRAM_URL + "accounts/login/":
                            time.sleep(2)
                            logged_in = True
                            break
                except Exception:
                    pass

            if logged_in:
                context.storage_state(path=str(self.session_path))
                print(f" ✅ 로그인 성공! 세션이 안전하게 저장되었습니다: {self.session_path}")
            else:
                print(" ❌ 로그인 시간 초과 또는 미완료. 다시 시도해 주세요.")

            browser.close()

    def upload_carousel_post(
        self,
        image_paths: List[Path],
        caption: str,
        first_comment: Optional[str] = None,
        schedule_datetime: Optional[datetime] = None,
        is_scheduled: bool = True
    ) -> bool:
        """
        4:5 비율 카드뉴스 이미지 6장을 캐러셀로 묶어 인스타그램에 예약 업로드합니다.
        예약 발행 모드에서는 캡션 하단에 첫댓글(소통 질문 및 출처 안내)을 일체형으로 자동 결합합니다.
        """
        if not self.is_session_available():
            print(f" ⚠️ 인스타그램 세션 파일이 없습니다: {self.session_path}")
            print(f"    먼저 'python -m generators.insta_browser_uploader --login' 명령어로 1회 로그인을 완료해 주세요.")
            return False

        valid_images = [p.resolve() for p in image_paths if p.exists()]
        if not valid_images:
            print(" ❌ 업로드할 이미지 파일이 존재하지 않습니다.")
            return False

        print(f"\n🚀 인스타그램 캐러셀 업로드 시작 (이미지 {len(valid_images)}장, 예약={is_scheduled})")

        # 첫댓글 내용을 캡션 하단에 통합 구성
        merged_caption = caption
        if first_comment:
            merged_caption = (
                f"{caption.strip()}\n\n"
                f"────────────────────\n"
                f"💬 [치료사 한마디 & 출처 안내]\n"
                f"{first_comment.strip()}"
            )

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=self.headless)
            context = browser.new_context(
                storage_state=str(self.session_path),
                viewport={"width": 1280, "height": 900},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            )
            page = context.new_page()

            try:
                print("  🌐 인스타그램 접속 중...")
                page.goto(INSTAGRAM_URL, wait_until="networkidle", timeout=30000)
                time.sleep(2)

                if "accounts/login" in page.url or page.locator("input[name='password']").count() > 0:
                    print("  ⚠️ 세션이 만료되었습니다. 다시 로그인 세션을 갱신해 주세요.")
                    browser.close()
                    return False

                # 팝업 닫기 (알림 설정 등)
                for btn_text in ["나중에 하기", "Not Now", "닫기", "Close"]:
                    try:
                        btn = page.locator(f"button:has-text('{btn_text}')")
                        if btn.count() > 0:
                            btn.first.click()
                            time.sleep(1)
                    except Exception:
                        pass

                # 1. '만들기' 버튼 클릭
                print("  ➕ [만들기] 버튼 탐색 중...")
                create_btn = page.locator("svg[aria-label='만들기'], svg[aria-label='New post'], svg[aria-label='Create']").locator("..")
                if create_btn.count() == 0:
                    create_btn = page.locator("a[href='#']:has-text('만들기'), a[href='#']:has-text('Create')")
                
                if create_btn.count() > 0:
                    create_btn.first.click()
                else:
                    page.locator("span:has-text('만들기'), span:has-text('Create')").first.click()
                time.sleep(2)

                # 2. 파일 업로드 input에 이미지 6장 주입
                print(f"  📁 4:5 카드뉴스 이미지 {len(valid_images)}장 첨부 중...")
                file_input = page.locator("input[type='file']")
                file_input.set_input_files([str(img) for img in valid_images])
                time.sleep(3)

                # 3. 크롭(비율) 설정 -> 4:5 선택
                print("  📐 4:5 세로 비율 조정 중...")
                try:
                    crop_btn = page.locator("button:has(svg[aria-label='자르기 선택']), button:has(svg[aria-label='Select crop'])")
                    if crop_btn.count() > 0:
                        crop_btn.first.click()
                        time.sleep(1)
                        ratio_4_5 = page.locator("button:has-text('4:5'), span:has-text('4:5')")
                        if ratio_4_5.count() > 0:
                            ratio_4_5.first.click()
                            time.sleep(1)
                except Exception as e:
                    print(f"    (비율 자동 조정 건너뜀: {e})")

                # 4. [다음] 클릭 (크롭 완료)
                print("  ➡️ [다음] 단계로 이동 (1/2)...")
                next_btn = page.locator("div[role='button']:has-text('다음'), button:has-text('다음'), div[role='button']:has-text('Next'), button:has-text('Next')")
                next_btn.first.click()
                time.sleep(2)

                # 5. [다음] 클릭 (필터 화면 통과)
                print("  ➡️ [다음] 단계로 이동 (2/2)...")
                next_btn = page.locator("div[role='button']:has-text('다음'), button:has-text('다음'), div[role='button']:has-text('Next'), button:has-text('Next')")
                next_btn.first.click()
                time.sleep(2)

                # 6. 캡션 입력
                print("  ✍️ 본문 캡션 및 첫댓글 내용 작성 중...")
                caption_box = page.locator("div[aria-label='문구 입력...'], div[aria-label='Write a caption...'], div[role='textbox']")
                if caption_box.count() > 0:
                    caption_box.first.click()
                    caption_box.first.fill(merged_caption)
                    time.sleep(1)
                else:
                    print("  ⚠️ 캡션 입력창을 찾지 못했습니다.")

                # 7. 예약 공개 (Schedule) 설정
                if is_scheduled:
                    target_time_display = schedule_datetime.strftime("%Y-%m-%d %I:%M %p") if schedule_datetime else f"오전 08:00"
                    print(f"  ⏰ 예약 공개(Schedule) 옵션 설정 중... (목표: {target_time_display})")
                    try:
                        # 고급 설정(Advanced settings) 클릭
                        adv_btn = page.locator("span:has-text('고급 설정'), span:has-text('Advanced settings'), div:has-text('고급 설정')")
                        if adv_btn.count() > 0:
                            adv_btn.first.click()
                            time.sleep(1)

                        # '이 게시물 예약' 토글 활성화
                        schedule_toggle = page.locator("input[type='checkbox'], button[role='switch']")
                        if schedule_toggle.count() > 0:
                            schedule_toggle.first.click()
                            time.sleep(1)
                            print(f"  ✅ 게시물 예약 모드 활성화됨 ({target_time_display})")

                            # 날짜/시간 입력란이 열린 경우 입력 시도
                            if schedule_datetime:
                                date_str = schedule_datetime.strftime("%Y-%m-%d")
                                date_inputs = page.locator("input[type='date'], input[placeholder*='YYYY'], input[placeholder*='날짜']")
                                if date_inputs.count() > 0:
                                    date_inputs.first.fill(date_str)
                    except Exception as e:
                        print(f"  ⚠️ 예약 토글 조작 중 참고 사항: {e}")

                # 8. 최종 '공유하기' 또는 '예약' 버튼 클릭
                print("  🚀 최종 [공유하기 / 예약] 버튼 클릭...")
                submit_btn = page.locator(
                    "div[role='button']:has-text('예약'), button:has-text('예약'), "
                    "div[role='button']:has-text('Schedule'), button:has-text('Schedule'), "
                    "div[role='button']:has-text('공유하기'), button:has-text('공유하기'), "
                    "div[role='button']:has-text('Share'), button:has-text('Share')"
                )

                if submit_btn.count() > 0:
                    submit_btn.first.click()
                    print("  ⏳ 업로드 및 예약 처리 완료 대기 중 (약 10~20초 소요)...")
                    
                    for _ in range(30):
                        time.sleep(1)
                        success_indicator = page.locator(
                            "span:has-text('게시물이 공유되었습니다'), "
                            "span:has-text('게시물이 예약되었습니다'), "
                            "span:has-text('Your post has been shared'), "
                            "span:has-text('Your post has been scheduled')"
                        )
                        if success_indicator.count() > 0:
                            print(f"  🎉 축하합니다! 인스타그램 캐러셀 예약이 완료되었습니다! ({target_time_display})")
                            break
                    time.sleep(3)
                    context.storage_state(path=str(self.session_path))
                    browser.close()
                    return True
                else:
                    print("  ❌ [공유하기/예약] 버튼을 찾을 수 없습니다.")

            except Exception as e:
                print(f"  ❌ 인스타그램 업로드 중 예외 발생: {e}")
            finally:
                browser.close()

        return False

    def upload_reels_video(
        self,
        video_path: Path,
        caption: str,
        first_comment: Optional[str] = None,
        schedule_datetime: Optional[datetime] = None,
        is_scheduled: bool = True
    ) -> bool:
        """
        1080x1920 세로형 쇼츠 영상을 인스타그램 릴스(Reels)로 예약 업로드합니다.
        (월/수/금 오전 08:00 스케줄 지원)
        """
        if not self.is_session_available():
            print(f" ⚠️ 인스타그램 세션 파일이 없습니다: {self.session_path}")
            return False

        if not video_path.exists():
            print(f" ❌ 업로드할 비디오 파일이 없습니다: {video_path}")
            return False

        target_time_display = schedule_datetime.strftime("%Y-%m-%d %I:%M %p") if schedule_datetime else "오전 08:00"
        print(f"\n🎬 인스타그램 릴스(Reels) 업로드 시작: {video_path.name} (예약: {target_time_display})")

        merged_caption = caption
        if first_comment:
            merged_caption = (
                f"{caption.strip()}\n\n"
                f"────────────────────\n"
                f"💬 [치료사 토론 질문 & 타임라인]\n"
                f"{first_comment.strip()}"
            )

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=self.headless)
            context = browser.new_context(
                storage_state=str(self.session_path),
                viewport={"width": 1280, "height": 900},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            )
            page = context.new_page()

            try:
                print("  🌐 인스타그램 접속 중...")
                page.goto(INSTAGRAM_URL, wait_until="networkidle", timeout=30000)
                time.sleep(2)

                # 1. '만들기' 버튼 클릭
                create_btn = page.locator("svg[aria-label='만들기'], svg[aria-label='New post'], svg[aria-label='Create']").locator("..")
                if create_btn.count() == 0:
                    create_btn = page.locator("span:has-text('만들기'), span:has-text('Create')")
                create_btn.first.click()
                time.sleep(2)

                # 2. 비디오 파일 첨부
                print(f"  📹 9:16 비디오 첨부 중: {video_path.name}")
                file_input = page.locator("input[type='file']")
                file_input.set_input_files(str(video_path.resolve()))
                time.sleep(4)

                # 3. 비디오 팝업(릴스로 공유됩니다 안내 등) 확인 및 [확인/다음]
                for _ in range(3):
                    next_btn = page.locator("div[role='button']:has-text('다음'), button:has-text('다음'), div[role='button']:has-text('Next'), button:has-text('Next'), button:has-text('확인'), button:has-text('OK')")
                    if next_btn.count() > 0:
                        next_btn.first.click()
                        time.sleep(2)

                # 4. 캡션 입력
                caption_box = page.locator("div[aria-label='문구 입력...'], div[aria-label='Write a caption...'], div[role='textbox']")
                if caption_box.count() > 0:
                    caption_box.first.click()
                    caption_box.first.fill(merged_caption)
                    time.sleep(1)

                # 5. 예약 공개 설정
                if is_scheduled:
                    try:
                        adv_btn = page.locator("span:has-text('고급 설정'), span:has-text('Advanced settings'), div:has-text('고급 설정')")
                        if adv_btn.count() > 0:
                            adv_btn.first.click()
                            time.sleep(1)

                        schedule_toggle = page.locator("input[type='checkbox'], button[role='switch']")
                        if schedule_toggle.count() > 0:
                            schedule_toggle.first.click()
                            time.sleep(1)
                            print(f"  ✅ 릴스 예약 모드 활성화됨 ({target_time_display})")
                    except Exception as e:
                        print(f"  ⚠️ 릴스 예약 토글 참고: {e}")

                # 6. 최종 예약 클릭
                submit_btn = page.locator(
                    "div[role='button']:has-text('예약'), button:has-text('예약'), "
                    "div[role='button']:has-text('Schedule'), button:has-text('Schedule'), "
                    "div[role='button']:has-text('공유하기'), button:has-text('공유하기'), "
                    "div[role='button']:has-text('Share'), button:has-text('Share')"
                )
                if submit_btn.count() > 0:
                    submit_btn.first.click()
                    print("  ⏳ 릴스 비디오 인코딩 및 예약 업로드 처리 중 (약 20~30초 소요)...")
                    for _ in range(40):
                        time.sleep(1)
                        success_indicator = page.locator(
                            "span:has-text('릴스가 공유되었습니다'), "
                            "span:has-text('릴스가 예약되었습니다'), "
                            "span:has-text('게시물이 예약되었습니다'), "
                            "span:has-text('Your reel has been shared'), "
                            "span:has-text('Your post has been scheduled')"
                        )
                        if success_indicator.count() > 0:
                            print(f"  🎉 축하합니다! 릴스 예약 업로드가 완료되었습니다! ({target_time_display})")
                            break
                    time.sleep(3)
                    context.storage_state(path=str(self.session_path))
                    browser.close()
                    return True
            except Exception as e:
                print(f"  ❌ 릴스 업로드 중 예외 발생: {e}")
            finally:
                browser.close()

        return False

def main():
    parser = argparse.ArgumentParser(description="인스타그램 캐러셀 자동 예약 업로더")
    parser.add_argument("--login", action="store_true", help="브라우저를 열어 인스타그램 1회 로그인 세션을 저장합니다.")
    parser.add_argument("--test", action="store_true", help="최신 주차 1세트 카드뉴스로 예약 업로드 테스트를 수행합니다.")
    args = parser.parse_args()

    uploader = InstagramBrowserUploader()

    if args.login:
        uploader.interactive_login()
    elif args.test:
        from config import OUTPUT_DIR, CURRENT_WEEK
        sample_dir = OUTPUT_DIR / CURRENT_WEEK / "set1_국내정책_보험" / "cards" / "feed_4x5"
        images = sorted(list(sample_dir.glob("card_[0-9]*.png"))) or sorted(list(sample_dir.glob("card_slide_*.png")))
        caption_file = OUTPUT_DIR / CURRENT_WEEK / "set1_국내정책_보험" / "instagram_caption.txt"
        
        caption = "물리치료 전문 뉴스 브리핑"
        if caption_file.exists():
            with open(caption_file, "r", encoding="utf-8") as f:
                caption = f.read()

        first_comment = generate_first_comment_text()
        uploader.upload_carousel_post(
            image_paths=images,
            caption=caption,
            first_comment=first_comment,
            is_scheduled=True
        )
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
