# 이 모듈은 Meta Instagram Graph API를 활용하여 4:5 카드뉴스 캐러셀 및 9:16 릴스 비디오 예약 업로드를 수행합니다.
# 미디어 컨테이너 생성, 비디오 인코딩 상태 폴링, 최종 발행(media_publish) 파이프라인을 전담합니다.

import sys
import time
from pathlib import Path
from typing import List, Optional
import requests

sys.path.append(str(Path(__file__).resolve().parent.parent))
from config import INSTAGRAM_ACCOUNT_ID, INSTAGRAM_ACCESS_TOKEN

GRAPH_API_VERSION = "v20.0"
GRAPH_API_BASE = f"https://graph.facebook.com/{GRAPH_API_VERSION}"


class InstagramGraphUploader:
    """Meta Instagram Graph API 기반 자동 예약 업로더"""

    def __init__(
        self,
        account_id: Optional[str] = None,
        access_token: Optional[str] = None
    ):
        self.account_id = account_id or INSTAGRAM_ACCOUNT_ID
        self.access_token = access_token or INSTAGRAM_ACCESS_TOKEN
        # Instagram Login 토큰(IG...) 또는 Facebook Login 토큰(EAA...)에 따라 엔드포인트 호스트 자동 선택
        if self.access_token and self.access_token.startswith("IG"):
            self.api_base = f"https://graph.instagram.com/{GRAPH_API_VERSION}"
        else:
            self.api_base = f"https://graph.facebook.com/{GRAPH_API_VERSION}"

    def is_configured(self) -> bool:
        """인증 정보가 .env에 설정되어 있는지 확인합니다."""
        return bool(self.account_id and self.access_token)

    def verify_connection(self) -> dict:
        """인스타그램 비즈니스 계정 연결 상태 및 토큰 유효성을 진단합니다."""
        if not self.is_configured():
            return {
                "success": False,
                "error": "INSTAGRAM_ACCOUNT_ID 또는 INSTAGRAM_ACCESS_TOKEN이 .env에 설정되지 않았습니다."
            }

        url = f"{self.api_base}/{self.account_id}"
        params = {
            "fields": "id,username,name",
            "access_token": self.access_token
        }
        try:
            res = requests.get(url, params=params, timeout=10)
            data = res.json()
            if "error" in data:
                return {
                    "success": False,
                    "error": data["error"].get("message", "알 수 없는 API 오류"),
                    "details": data["error"]
                }
            return {
                "success": True,
                "account_id": data.get("id"),
                "username": data.get("username"),
                "name": data.get("name")
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def add_comment(self, media_id: str, comment_text: str) -> dict:
        """
        발행된 인스타그램 미디어(게시물/릴스)에 댓글을 작성합니다.
        POST {api_base}/{media_id}/comments
        """
        if not self.is_configured():
            raise ValueError("인스타그램 인증 정보(ACCOUNT_ID / ACCESS_TOKEN)가 설정되지 않았습니다.")

        url = f"{self.api_base}/{media_id}/comments"
        payload = {
            "message": comment_text,
            "access_token": self.access_token
        }
        try:
            res = requests.post(url, data=payload, timeout=15)
            data = res.json()
            if "id" not in data:
                print(f"⚠️ [Instagram] 첫 댓글 등록 실패: {data.get('error', data)}")
                return {"success": False, "error": data.get("error")}
            print(f"💬 [Instagram] 첫 댓글 등록 성공 (Comment ID: {data['id']})")
            return {"success": True, "comment_id": data["id"]}
        except Exception as e:
            print(f"⚠️ [Instagram] 첫 댓글 작성 중 예외 발생: {e}")
            return {"success": False, "error": str(e)}

    def upload_carousel_feed(
        self,
        image_urls: List[str],
        caption: str,
        schedule_timestamp: Optional[int] = None,
        first_comment: Optional[str] = None
    ) -> dict:
        """
        4:5 카드뉴스 캐러셀(최대 10장)을 생성하고 예약 발행합니다.
        - image_urls: 공개적으로 접근 가능한 고화질 이미지 URL 목록
        - schedule_timestamp: UNIX 타임스탬프 (현재 기준 20분 후 ~ 75일 이내)
        - first_comment: 즉시 발행 시 함께 등록할 첫 댓글 문구
        """
        if not self.is_configured():
            raise ValueError("인스타그램 인증 정보(ACCOUNT_ID / ACCESS_TOKEN)가 설정되지 않았습니다.")

        if not image_urls or len(image_urls) < 2:
            raise ValueError("캐러셀 피드는 최소 2장 이상의 이미지 URL이 필요합니다.")

        # 1. 각 슬라이드별 캐러셀 아이템 컨테이너 생성
        print(f"\n📸 [Instagram] 캐러셀 슬라이드 {len(image_urls)}장 컨테이너 생성 중...")
        item_ids = []
        for idx, img_url in enumerate(image_urls, 1):
            item_url = f"{self.api_base}/{self.account_id}/media"
            payload = {
                "image_url": img_url,
                "is_carousel_item": "true",
                "access_token": self.access_token
            }
            res = requests.post(item_url, data=payload, timeout=20)
            data = res.json()
            if "id" not in data:
                raise RuntimeError(f"슬라이드 {idx} 컨테이너 생성 실패: {data.get('error', data)}")
            item_ids.append(data["id"])
            print(f"   • 슬라이드 {idx}/{len(image_urls)} 컨테이너 준비 완료 (ID: {data['id']})")

        # 2. 캐러셀 부모 컨테이너 생성 및 예약 설정
        print("📦 [Instagram] 캐러셀 통합 컨테이너 생성 중...")
        carousel_payload = {
            "media_type": "CAROUSEL",
            "children": ",".join(item_ids),
            "caption": caption,
            "access_token": self.access_token
        }

        # 예약 발행 조건 점검 (현재 시각 + 20분 이상 미래)
        now_ts = int(time.time())
        is_scheduled = False
        if schedule_timestamp and (schedule_timestamp - now_ts >= 1200):
            carousel_payload["published"] = "false"
            carousel_payload["scheduled_publish_time"] = str(schedule_timestamp)
            is_scheduled = True
            print(f"   ⏰ 예약 발행 설정: 타임스탬프 {schedule_timestamp}")
        else:
            print("   ⚡ 즉시 발행 모드로 진행합니다.")

        res = requests.post(f"{self.api_base}/{self.account_id}/media", data=carousel_payload, timeout=20)
        c_data = res.json()
        if "id" not in c_data:
            raise RuntimeError(f"캐러셀 부모 컨테이너 생성 실패: {c_data.get('error', c_data)}")

        container_id = c_data["id"]

        # 3. 최종 발행 (publish)
        print("🚀 [Instagram] 캐러셀 최종 등록(publish) 실행 중...")
        pub_res = requests.post(
            f"{self.api_base}/{self.account_id}/media_publish",
            data={"creation_id": container_id, "access_token": self.access_token},
            timeout=20
        )
        pub_data = pub_res.json()
        if "id" not in pub_data:
            raise RuntimeError(f"캐러셀 최종 발행 실패: {pub_data.get('error', pub_data)}")

        post_id = pub_data["id"]
        print(f"✅ [Instagram] 카드뉴스 캐러셀 {'예약 ' if is_scheduled else ''}발행 완료! (게시물 ID: {post_id})")

        # 4. 첫 댓글 등록 (즉시 발행 시 지원)
        comment_res = None
        if first_comment:
            if not is_scheduled:
                comment_res = self.add_comment(post_id, first_comment)
            else:
                print("   ℹ️ [Instagram] 예약 발행 게시물은 스케줄 시점에 활성화되므로 첫 댓글은 본문 캡션 안내로 연동됩니다.")

        return {
            "post_id": post_id,
            "container_id": container_id,
            "is_scheduled": is_scheduled,
            "schedule_timestamp": schedule_timestamp,
            "comment": comment_res
        }

    # 메서드 별칭 지원
    upload_carousel = upload_carousel_feed

    def upload_reels_video(
        self,
        video_url: str,
        caption: str,
        schedule_timestamp: Optional[int] = None,
        first_comment: Optional[str] = None
    ) -> dict:
        """
        9:16 쇼츠 영상을 인스타그램 릴스(Reels)로 예약 업로드합니다.
        - video_url: 공개적으로 접근 가능한 MP4 영상 URL
        - first_comment: 즉시 발행 시 함께 등록할 첫 댓글 문구
        """
        if not self.is_configured():
            raise ValueError("인스타그램 인증 정보(ACCOUNT_ID / ACCESS_TOKEN)가 설정되지 않았습니다.")

        # 1. 릴스 비디오 컨테이너 생성
        print(f"\n🎬 [Instagram] 릴스 비디오 컨테이너 생성 중...")
        reels_payload = {
            "media_type": "REELS",
            "video_url": video_url,
            "caption": caption,
            "share_to_feed": "true",
            "access_token": self.access_token
        }

        now_ts = int(time.time())
        is_scheduled = False
        if schedule_timestamp and (schedule_timestamp - now_ts >= 1200):
            reels_payload["published"] = "false"
            reels_payload["scheduled_publish_time"] = str(schedule_timestamp)
            is_scheduled = True
            print(f"   ⏰ 릴스 예약 발행 설정: 타임스탬프 {schedule_timestamp}")

        res = requests.post(f"{self.api_base}/{self.account_id}/media", data=reels_payload, timeout=25)
        r_data = res.json()
        if "id" not in r_data:
            raise RuntimeError(f"릴스 컨테이너 생성 실패: {r_data.get('error', r_data)}")

        container_id = r_data["id"]

        # 2. 메타 서버의 비디오 인코딩 상태 폴링 (최대 3분)
        print("⏳ [Instagram] 메타 서버에서 릴스 비디오 인코딩 처리 중...")
        for _ in range(36):
            time.sleep(5)
            status_res = requests.get(
                f"{self.api_base}/{container_id}",
                params={"fields": "status_code", "access_token": self.access_token},
                timeout=10
            )
            s_data = status_res.json()
            code = s_data.get("status_code")
            if code == "FINISHED":
                print("   ✅ 비디오 인코딩 완료!")
                break
            elif code == "ERROR":
                raise RuntimeError(f"릴스 비디오 인코딩 오류: {s_data}")
            print(f"   ...처리 중 (status: {code})")
        else:
            raise TimeoutError("릴스 비디오 인코딩 대기 시간 초과")

        # 3. 최종 발행
        print("🚀 [Instagram] 릴스 최종 등록(publish) 실행 중...")
        pub_res = requests.post(
            f"{self.api_base}/{self.account_id}/media_publish",
            data={"creation_id": container_id, "access_token": self.access_token},
            timeout=20
        )
        pub_data = pub_res.json()
        if "id" not in pub_data:
            raise RuntimeError(f"릴스 최종 발행 실패: {pub_data.get('error', pub_data)}")

        reels_id = pub_data["id"]
        print(f"✅ [Instagram] 릴스 영상 {'예약 ' if is_scheduled else ''}발행 완료! (게시물 ID: {reels_id})")

        # 4. 첫 댓글 등록 (즉시 발행 시 지원)
        comment_res = None
        if first_comment:
            if not is_scheduled:
                comment_res = self.add_comment(reels_id, first_comment)
            else:
                print("   ℹ️ [Instagram] 예약 발행 릴스는 스케줄 시점에 활성화되므로 첫 댓글은 본문 캡션 안내로 연동됩니다.")

        return {
            "reels_id": reels_id,
            "container_id": container_id,
            "is_scheduled": is_scheduled,
            "schedule_timestamp": schedule_timestamp,
            "comment": comment_res
        }

    # 메서드 별칭 지원
    upload_reels = upload_reels_video


def upload_instagram_carousel(
    image_urls: List[str],
    caption: str,
    scheduled_timestamp: Optional[int] = None,
    first_comment: Optional[str] = None,
    dry_run: bool = False
) -> dict:
    """
    4:5 카드뉴스 이미지들을 인스타그램 캐러셀 피드로 예약 업로드합니다.
    dry_run=True 시 실제 API 호출 없이 파라미터 시뮬레이션만 수행합니다.
    """
    if dry_run:
        mode = "예약 업로드" if scheduled_timestamp else "즉시 업로드"
        print(f"     🧪 [DRY-RUN 시뮬레이션 - {mode}]")
        print(f"        • 이미지 수: {len(image_urls)}장")
        print(f"        • 대표 이미지 URL: {image_urls[0] if image_urls else 'N/A'}")
        print(f"        • 발행 설정: {f'타임스탬프 {scheduled_timestamp}' if scheduled_timestamp else '즉시 발행(Immediate)'}")
        if first_comment:
            print(f"        • 첫 댓글: {first_comment.splitlines()[0]}...")
        return {
            "success": True,
            "container_id": "DRY-RUN-IG-CAROUSEL",
            "is_scheduled": bool(scheduled_timestamp),
            "status": "scheduled (dry-run)" if scheduled_timestamp else "published (dry-run)"
        }

    try:
        uploader = InstagramGraphUploader()
        res = uploader.upload_carousel(
            image_urls=image_urls,
            caption=caption,
            schedule_timestamp=scheduled_timestamp,
            first_comment=first_comment
        )
        return {"success": True, **res}
    except Exception as e:
        return {"success": False, "error": str(e)}


def upload_instagram_reel(
    video_url: str,
    caption: str,
    scheduled_timestamp: Optional[int] = None,
    first_comment: Optional[str] = None,
    dry_run: bool = False
) -> dict:
    """
    9:16 쇼츠 비디오를 인스타그램 릴스로 예약 업로드합니다.
    dry_run=True 시 실제 API 호출 없이 파라미터 시뮬레이션만 수행합니다.
    """
    if dry_run:
        mode = "예약 업로드" if scheduled_timestamp else "즉시 업로드"
        print(f"     🧪 [DRY-RUN 시뮬레이션 - {mode}]")
        print(f"        • 비디오 URL: {video_url}")
        print(f"        • 발행 설정: {f'타임스탬프 {scheduled_timestamp}' if scheduled_timestamp else '즉시 발행(Immediate)'}")
        if first_comment:
            print(f"        • 첫 댓글: {first_comment.splitlines()[0]}...")
        return {
            "success": True,
            "container_id": "DRY-RUN-IG-REELS",
            "is_scheduled": bool(scheduled_timestamp),
            "status": "scheduled (dry-run)" if scheduled_timestamp else "published (dry-run)"
        }

    try:
        uploader = InstagramGraphUploader()
        res = uploader.upload_reels(
            video_url=video_url,
            caption=caption,
            schedule_timestamp=scheduled_timestamp,
            first_comment=first_comment
        )
        return {"success": True, **res}
    except Exception as e:
        return {"success": False, "error": str(e)}


def test_instagram_connection() -> bool:
    """
    Instagram Graph API 비즈니스 계정 연결 상태를 테스트합니다.
    """
    uploader = InstagramGraphUploader()
    res = uploader.verify_connection()
    if res.get("success"):
        print(f"✅ 계정 연결 정상: @{res.get('username')} (ID: {res.get('account_id')}, 이름: {res.get('name')})")
        return True
    else:
        print(f"❌ 연결 실패: {res.get('error')}")
        return False
