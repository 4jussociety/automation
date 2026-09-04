# YouTube Data API v3 기반 쇼츠(1080x1920 MP4) 자동 업로드 및 첫댓글 모듈
import os
import sys
import time
import argparse
from pathlib import Path
from typing import Optional, List

from config import (
    BASE_DIR,
    ASSETS_DIR,
    YOUTUBE_CLIENT_SECRETS_FILE,
    YOUTUBE_TOKEN_FILE,
    YOUTUBE_DEFAULT_PRIVACY,
)

# 필요한 OAuth 스코프: 비디오 업로드 및 댓글 작성
SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.force-ssl"
]

def generate_shorts_first_comment(batch_title: str = "") -> str:
    """
    유튜브 쇼츠 알고리즘 참여도 극대화를 위한 맞춤 첫댓글 템플릿을 생성합니다.
    """
    return (
        f"🩺 [물리치료사 필독 브리핑: {batch_title}]\n\n"
        f"⏱ 타임라인 요약\n"
        f"00:05 핵심 이슈 헤드라인\n"
        f"00:15 심평원 심사 기준 및 변경점\n"
        f"00:28 임상 실무 대응 가이드\n\n"
        f"💬 이번 정책 및 임상 가이드에 대해 선생님 병원에서는 어떻게 생각하시나요?\n"
        f"댓글로 자유롭게 의견을 나눠주세요! (상세 원문 출처는 고정 댓글과 더보기란을 참고하세요)"
    )

class YouTubeShortsUploader:
    def __init__(
        self,
        client_secrets_file: Path = YOUTUBE_CLIENT_SECRETS_FILE,
        token_file: Path = YOUTUBE_TOKEN_FILE,
        default_privacy: str = YOUTUBE_DEFAULT_PRIVACY
    ):
        self.client_secrets_file = client_secrets_file
        self.token_file = token_file
        self.default_privacy = default_privacy
        self.token_file.parent.mkdir(parents=True, exist_ok=True)

    def get_authenticated_service(self):
        """
        저장된 OAuth 토큰을 로드하거나 최초 브라우저 인증을 통해 YouTube 서비스 객체를 반환합니다.
        """
        try:
            from googleapiclient.discovery import build
            from google_auth_oauthlib.flow import InstalledAppFlow
            from google.auth.transport.requests import Request
            from google.oauth2.credentials import Credentials
        except ImportError:
            print(" ❌ Google API 클라이언트 라이브러리가 필요합니다: pip install google-api-python-client google-auth-oauthlib")
            return None

        creds = None
        if self.token_file.exists():
            try:
                creds = Credentials.from_authorized_user_file(str(self.token_file), SCOPES)
            except Exception:
                creds = None

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                    with open(self.token_file, "w", encoding="utf-8") as f:
                        f.write(creds.to_json())
                    print(" 🔄 YouTube API 토큰이 성공적으로 갱신되었습니다.")
                except Exception as e:
                    print(f" ⚠️ 토큰 갱신 실패: {e}")
                    creds = None

            if not creds:
                if not self.client_secrets_file.exists():
                    print("\n" + "!" * 65)
                    print(" ⚠️ YouTube API 클라이언트 시크릿 파일이 필요합니다.")
                    print(f"    위치: {self.client_secrets_file}")
                    print("    1. https://console.cloud.google.com/ 에 접속합니다.")
                    print("    2. 'YouTube Data API v3'를 사용 설정합니다.")
                    print("    3. [사용자 인증 정보] -> [OAuth 클라이언트 ID] (데스크톱 앱) 생성")
                    print(f"    4. 다운로드한 JSON 파일을 '{self.client_secrets_file.name}'로 변경 후")
                    print(f"       '{self.client_secrets_file.parent}' 폴더에 넣어주세요.")
                    print("!" * 65 + "\n")
                    return None

                print(" 🔑 브라우저에서 YouTube 채널 계정으로 로그인해 주세요...")
                flow = InstalledAppFlow.from_client_secrets_file(str(self.client_secrets_file), SCOPES)
                creds = flow.run_local_server(port=0)
                with open(self.token_file, "w", encoding="utf-8") as f:
                    f.write(creds.to_json())
                print(f" ✅ YouTube 인증 성공! 토큰 저장됨: {self.token_file}")

        return build("youtube", "v3", credentials=creds)

    def upload_shorts(
        self,
        video_path: Path,
        title: str,
        description: str,
        tags: Optional[List[str]] = None,
        privacy_status: Optional[str] = None,
        first_comment: Optional[str] = None,
        publish_at: Optional[str] = None,
    ) -> Optional[str]:
        """
        쇼츠 영상(MP4)을 유튜브에 업로드하고 완료 후 첫댓글을 자동으로 게시합니다.
        publish_at이 전달되면 지정된 일시(RFC 3339)에 예약 공개(Scheduled)됩니다.
        """
        if not video_path.exists():
            print(f" ❌ 비디오 파일을 찾을 수 없습니다: {video_path}")
            return None

        youtube = self.get_authenticated_service()
        if not youtube:
            print(" ⚠️ YouTube API 서비스 인증 실패로 업로드를 건너뜁니다.")
            return None

        from googleapiclient.http import MediaFileUpload

        if tags is None:
            tags = ["물리치료", "도수치료", "재활", "물리치료사", "Shorts", "의료뉴스"]

        # 쇼츠 알고리즘 필수 태그 '#Shorts' 타이틀에 보장
        if "#Shorts" not in title and "#shorts" not in title:
            title = f"{title.strip()} #Shorts"

        status_dict = {
            "selfDeclaredMadeForKids": False,
        }

        if publish_at:
            status_dict["privacyStatus"] = "private"
            status_dict["publishAt"] = publish_at
            privacy_display = f"예약 공개 ({publish_at})"
        else:
            status_dict["privacyStatus"] = privacy_status or self.default_privacy
            privacy_display = status_dict["privacyStatus"]

        body = {
            "snippet": {
                "title": title[:100],  # 유튜브 최대 100자
                "description": description,
                "tags": tags,
                "categoryId": "27",  # Education
            },
            "status": status_dict
        }

        print(f"\n🎬 YouTube Shorts 업로드 시작: {video_path.name}")
        print(f"   제목: {title}")
        print(f"   공개 설정: {privacy_display}")

        media = MediaFileUpload(str(video_path), mimetype="video/mp4", resumable=True, chunksize=1024*1024*2)
        request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)

        response = None
        while response is None:
            status, response = request.next_chunk()
            if status:
                print(f"   ⏳ 업로드 진행률: {int(status.progress() * 100)}%")

        video_id = response.get("id")
        video_url = f"https://youtube.com/shorts/{video_id}"
        print(f"  🎉 쇼츠 업로드 완료! 영상 ID: {video_id}")
        print(f"  🔗 영상 링크: {video_url}")

        # 첫댓글 자동 등록
        if first_comment and video_id:
            self.post_first_comment(youtube, video_id, first_comment)

        return video_id

    def post_first_comment(self, youtube, video_id: str, comment_text: str) -> bool:
        """
        업로드된 쇼츠 영상에 첫댓글을 작성합니다.
        """
        print(f"  💬 첫댓글 작성 중...")
        try:
            body = {
                "snippet": {
                    "videoId": video_id,
                    "topLevelComment": {
                        "snippet": {
                            "textOriginal": comment_text
                        }
                    }
                }
            }
            res = youtube.commentThreads().insert(part="snippet", body=body).execute()
            comment_id = res.get("id")
            print(f"  ✅ 첫댓글 등록 성공! (댓글 ID: {comment_id})")
            return True
        except Exception as e:
            print(f"  ⚠️ 첫댓글 등록 중 오류: {e}")
            return False

def main():
    parser = argparse.ArgumentParser(description="YouTube Shorts 자동 업로더 및 첫댓글 도구")
    parser.add_argument("--auth", action="store_true", help="최초 1회 구글 계정 브라우저 인증을 수행합니다.")
    parser.add_argument("--test", action="store_true", help="최신 주차 1세트 쇼츠 비디오 업로드 테스트를 수행합니다.")
    args = parser.parse_args()

    uploader = YouTubeShortsUploader()

    if args.auth:
        service = uploader.get_authenticated_service()
        if service:
            print(" ✅ YouTube API 인증이 완벽하게 완료되었습니다!")
    elif args.test:
        from config import OUTPUT_DIR, CURRENT_WEEK
        sample_video = OUTPUT_DIR / CURRENT_WEEK / "set1_국내정책_보험" / "shorts" / "shorts_video.mp4"
        if sample_video.exists():
            first_comment = generate_shorts_first_comment("국내 정책 / 보험 이슈")
            uploader.upload_shorts(
                video_path=sample_video,
                title="[물리치료사 필독] 도수치료 24회 제한 & 심사 지침 변경 총정리 #Shorts",
                description="물리치료사를 위한 주간 핵심 뉴스 브리핑입니다.",
                privacy_status="unlisted",  # 테스트이므로 unlisted
                first_comment=first_comment
            )
        else:
            print(f" ❌ 테스트 비디오를 찾을 수 없습니다: {sample_video}")
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
