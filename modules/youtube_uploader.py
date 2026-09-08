# 이 모듈은 YouTube Data API v3를 활용하여 9:16 쇼츠 비디오 예약 업로드 및 첫댓글 등록을 전담합니다.
# OAuth 2.0 1회 인증 후 토큰 자동 갱신과 분할 업로드(Resumable Upload)를 지원합니다.

import sys
import os
import pickle
from pathlib import Path
from typing import Optional, List

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

sys.path.append(str(Path(__file__).resolve().parent.parent))
from config import BASE_DIR, YOUTUBE_CLIENT_SECRET_FILE, YOUTUBE_TOKEN_FILE

# 유튜브 업로드 및 댓글 작성을 위한 OAuth 스코프
YOUTUBE_SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.force-ssl"
]


class YouTubeShortsUploader:
    """YouTube Data API v3 기반 쇼츠 비디오 예약 업로더"""

    def __init__(self, client_secret_file: Optional[Path] = None, token_file: Optional[Path] = None):
        self.client_secret = Path(client_secret_file) if client_secret_file else Path(YOUTUBE_CLIENT_SECRET_FILE)
        self.token_path = Path(token_file) if token_file else YOUTUBE_TOKEN_FILE
        self._service = None

    def get_service(self):
        """인증된 YouTube Data API 클라이언트 객체를 반환합니다."""
        if self._service:
            return self._service

        creds = None
        # 1. 저장된 토큰이 있으면 로드
        if self.token_path.exists():
            try:
                with open(self.token_path, "rb") as token:
                    creds = pickle.load(token)
            except Exception as e:
                print(f"⚠️ [YouTube] 기존 토큰 로드 실패 (재인증 필요): {e}")
                creds = None

        # 2. 토큰이 유효하지 않거나 없으면 갱신 또는 신규 인증
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    print("🔄 [YouTube] 만료된 OAuth 토큰을 자동으로 갱신합니다...")
                    creds.refresh(Request())
                except Exception as e:
                    print(f"⚠️ [YouTube] 토큰 자동 갱신 실패: {e}")
                    creds = None

            if not creds:
                if not self.client_secret.exists():
                    raise FileNotFoundError(
                        f"❌ [YouTube OAuth 오류] 클라이언트 시크릿 파일이 없습니다: {self.client_secret}\n"
                        f"👉 Google Cloud Console에서 OAuth 클라이언트 ID(client_secret.json)를 다운로드하여 "
                        f"프로젝트 루트에 저장해 주세요. (가이드: docs/api_setup_guide.md)"
                    )

                print("\n🌐 [YouTube 1회 인증] 웹 브라우저에서 Google 계정 로그인을 진행합니다...", flush=True)
                flow = InstalledAppFlow.from_client_secrets_file(
                    str(self.client_secret),
                    scopes=YOUTUBE_SCOPES
                )
                creds = self._run_auth_server(flow)

            # 새 토큰 저장
            with open(self.token_path, "wb") as token:
                pickle.dump(creds, token)
                print(f"✅ [YouTube] 인증 토큰이 성공적으로 저장되었습니다: {self.token_path.name}")

        self._service = build("youtube", "v3", credentials=creds)
        return self._service

    def _run_auth_server(self, flow):
        """인증 URL을 즉시 출력하고 Windows 브라우저를 안정적으로 오픈하는 로컬 인증 서버"""
        import wsgiref.simple_server
        import webbrowser
        from google_auth_oauthlib.flow import (
            _RedirectWSGIApp,
            _ExclusiveWSGIServer,
            _WSGIRequestHandler
        )

        wsgi_app = _RedirectWSGIApp("The authentication flow has completed. You may close this window.")
        local_server = wsgiref.simple_server.make_server(
            "localhost",
            0,
            wsgi_app,
            server_class=_ExclusiveWSGIServer,
            handler_class=_WSGIRequestHandler,
        )

        try:
            flow.redirect_uri = f"http://localhost:{local_server.server_port}/"
            auth_url, _ = flow.authorization_url(prompt="consent", access_type="offline")

            print("\n" + "=" * 70, flush=True)
            print("🔗 [인증 링크] 아래 URL을 클릭하거나 웹 브라우저에 붙여넣어 주세요:", flush=True)
            print(f"\n{auth_url}\n", flush=True)
            print("=" * 70 + "\n", flush=True)

            try:
                os.startfile(auth_url)
            except Exception:
                try:
                    webbrowser.open(auth_url, new=1, autoraise=True)
                except Exception:
                    pass

            print("⏳ 브라우저에서 Google 계정 승인을 완료해 주세요...", flush=True)
            local_server.handle_request()

            authorization_response = wsgi_app.last_request_uri.replace("http", "https")
            flow.fetch_token(authorization_response=authorization_response)
        finally:
            local_server.server_close()

        return flow.credentials

    def upload_shorts(
        self,
        video_path: Path,
        title: str,
        description: str,
        tags: Optional[List[str]] = None,
        publish_at: Optional[str] = None,
        first_comment: Optional[str] = None
    ) -> dict:
        """
        쇼츠 비디오를 업로드하고 예약 발행 일시를 설정합니다.
        - publish_at: RFC 3339 형식 문자열 (예: 2026-09-08T08:00:00+09:00)
        - 예약 설정 시 YouTube 규정에 따라 privacyStatus는 반드시 'private'여야 함
        """
        service = self.get_service()

        if not video_path.exists():
            raise FileNotFoundError(f"업로드할 비디오 파일이 없습니다: {video_path}")

        # 제목 및 태그 정제 (#Shorts 보장)
        clean_title = title.strip()
        if "#Shorts" not in clean_title and "#shorts" not in clean_title:
            clean_title = f"{clean_title[:85]} #Shorts"

        video_tags = tags or ["물리치료", "재활치료", "도수치료", "Shorts", "THEPT", "더피티"]

        # 예약 발행 여부에 따른 공개 설정
        status_body = {}
        if publish_at:
            status_body = {
                "privacyStatus": "private",
                "publishAt": publish_at,
                "selfDeclaredMadeForKids": False
            }
        else:
            status_body = {
                "privacyStatus": "public",
                "selfDeclaredMadeForKids": False
            }

        body = {
            "snippet": {
                "title": clean_title,
                "description": description,
                "tags": video_tags,
                "categoryId": "27"  # 27 = 교육 (Education) 또는 28 = 과학기술
            },
            "status": status_body
        }

        print(f"\n🚀 [YouTube] 쇼츠 비디오 업로드 시작: {video_path.name}")
        print(f"   • 제목: {clean_title}")
        if publish_at:
            print(f"   • 예약 발행 시각: {publish_at}")

        media = MediaFileUpload(
            str(video_path),
            mimetype="video/mp4",
            resumable=True,
            chunksize=1024 * 1024 * 5  # 5MB 단위 분할 업로드
        )

        request = service.videos().insert(
            part="snippet,status",
            body=body,
            media_body=media
        )

        response = None
        while response is None:
            status, response = request.next_chunk()
            if status:
                print(f"   ⏳ 업로드 진행률: {int(status.progress() * 100)}%")

        video_id = response.get("id")
        video_url = f"https://youtube.com/shorts/{video_id}"
        print(f"✅ [YouTube] 업로드 완료! 영상 ID: {video_id} ({video_url})")

        # 첫 댓글 등록 (출처 및 보충 링크)
        comment_id = None
        if first_comment and video_id:
            try:
                comment_id = self.add_comment(video_id, first_comment)
                print(f"💬 [YouTube] 첫 댓글 등록 성공 (Comment ID: {comment_id})")
            except Exception as e:
                print(f"⚠️ [YouTube] 첫 댓글 등록 중 경고: {e}")

        return {
            "video_id": video_id,
            "video_url": video_url,
            "publish_at": publish_at,
            "comment_id": comment_id
        }

    def add_comment(self, video_id: str, comment_text: str) -> str:
        """업로드된 비디오에 첫 댓글을 등록합니다."""
        service = self.get_service()
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
        res = service.commentThreads().insert(part="snippet", body=body).execute()
        return res.get("id")


def upload_youtube_short(
    video_path: Path,
    title: str,
    description: str,
    tags: Optional[List[str]] = None,
    publish_at_rfc3339: Optional[str] = None,
    first_comment: Optional[str] = None,
    dry_run: bool = False
) -> dict:
    """
    YouTube Shorts 비디오를 업로드하고 예약 발행하는 편의 함수입니다.
    dry_run=True 시 실제 API 호출 없이 파라미터 시뮬레이션만 수행합니다.
    """
    if dry_run:
        mode = "예약 업로드" if publish_at_rfc3339 else "즉시 업로드"
        print(f"     🧪 [DRY-RUN 시뮬레이션 - {mode}]")
        print(f"        • 비디오: {Path(video_path).name}")
        print(f"        • 제목: {title}")
        print(f"        • 발행 설정: {publish_at_rfc3339 or '즉시 공개 (Public)'}")
        if first_comment:
            print(f"        • 첫 댓글: {first_comment.splitlines()[0]}...")
        return {
            "success": True,
            "video_id": "DRY-RUN-YT-SHORT",
            "video_url": "https://youtube.com/shorts/DRY-RUN-YT-SHORT",
            "status": "scheduled (dry-run)" if publish_at_rfc3339 else "published (dry-run)"
        }

    try:
        uploader = YouTubeShortsUploader()
        res = uploader.upload_shorts(
            video_path=Path(video_path),
            title=title,
            description=description,
            tags=tags,
            publish_at=publish_at_rfc3339,
            first_comment=first_comment
        )
        return {"success": True, **res, "status": "scheduled" if publish_at_rfc3339 else "published"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def authenticate_youtube():
    """
    YouTube Data API OAuth 최초 1회 브라우저 인증을 수행하고 서비스 객체를 반환합니다.
    """
    try:
        uploader = YouTubeShortsUploader()
        return uploader.get_service()
    except Exception as e:
        print(f"❌ YouTube 인증 실패: {e}")
        return None
