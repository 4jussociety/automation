# 이 모듈은 Google Drive API v3를 활용하여 주간 큐레이션 결과물을 구글 드라이브에 자동 업로드합니다.
# OAuth 2.0 1회 인증 후 토큰 자동 갱신 및 대용량 파일 분할 업로드(Resumable Upload)를 지원합니다.

import sys
import os
import pickle
import mimetypes
from pathlib import Path
from typing import Optional, Dict, Any, List

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
from config import (
    BASE_DIR,
    GDRIVE_CLIENT_SECRET_FILE,
    GDRIVE_TOKEN_FILE,
    GDRIVE_ROOT_FOLDER_NAME
)

# 구글 드라이브 업로드를 위한 권한 범위 (앱이 생성한 파일/폴더에 대한 안전한 전체 접근)
GDRIVE_SCOPES = [
    "https://www.googleapis.com/auth/drive.file"
]


def authenticate_gdrive(
    client_secret_file: Optional[Path] = None, 
    token_file: Optional[Path] = None
) -> Optional[Any]:
    """
    Google Drive API OAuth 2.0 사용자 인증을 수행하고 인증된 서비스를 반환합니다.
    최초 1회 브라우저 로그인을 통해 gdrive_token.pickle을 생성하며, 이후에는 자동 갱신됩니다.
    """
    cs_path = Path(client_secret_file) if client_secret_file else Path(GDRIVE_CLIENT_SECRET_FILE)
    t_path = Path(token_file) if token_file else Path(GDRIVE_TOKEN_FILE)

    if not cs_path.exists():
        print(f"❌ [Google Drive] 클라이언트 자격증명 파일이 없습니다: {cs_path.resolve()}")
        return None

    creds = None
    if t_path.exists():
        try:
            with open(t_path, "rb") as token:
                creds = pickle.load(token)
        except Exception as e:
            print(f"⚠️ [Google Drive] 기존 토큰 로드 실패: {e}")

    # 유효한 자격 증명이 없는 경우 새로 로그인/갱신
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                print("🔄 [Google Drive] 만료된 토큰을 자동으로 갱신합니다...")
                creds.refresh(Request())
            except Exception as e:
                print(f"⚠️ [Google Drive] 토큰 자동 갱신 실패 (재인증 필요): {e}")
                creds = None

        if not creds:
            print("\n🌐 [Google Drive] 최초 1회 브라우저 인증을 시작합니다.")
            print("   웹 브라우저가 열리면 Google 계정으로 로그인 후 드라이브 파일 접근 권한을 허용해주세요...")
            flow = InstalledAppFlow.from_client_secrets_file(
                str(cs_path),
                scopes=GDRIVE_SCOPES
            )
            creds = flow.run_local_server(port=0)

        # 갱신되거나 새로 생성된 토큰 저장
        try:
            with open(t_path, "wb") as token:
                pickle.dump(creds, token)
            print(f"💾 [Google Drive] 인증 토큰이 안전하게 저장되었습니다: {t_path.name}")
        except Exception as e:
            print(f"⚠️ [Google Drive] 토큰 저장 실패: {e}")

    try:
        service = build("drive", "v3", credentials=creds)
        return service
    except Exception as e:
        print(f"❌ [Google Drive] API 클라이언트 빌드 실패: {e}")
        return None


class GoogleDriveUploader:
    """Google Drive API v3 기반 주간 콘텐츠 자동 업로더"""

    def __init__(self, service):
        self.service = service

    def get_or_create_folder(self, folder_name: str, parent_id: Optional[str] = None) -> str:
        """
        지정된 위치에 폴더가 이미 있으면 해당 folder_id를 반환하고,
        없으면 새로 생성하여 folder_id를 반환합니다.
        """
        parent_query = f"'{parent_id}' in parents" if parent_id else "'root' in parents"
        query = (
            f"mimeType = 'application/vnd.google-apps.folder' "
            f"and name = '{folder_name}' "
            f"and {parent_query} "
            f"and trashed = false"
        )

        try:
            results = self.service.files().list(
                q=query,
                spaces="drive",
                fields="files(id, name)"
            ).execute()
            files = results.get("files", [])
            if files:
                return files[0]["id"]

            # 폴더 생성
            file_metadata = {
                "name": folder_name,
                "mimeType": "application/vnd.google-apps.folder"
            }
            if parent_id:
                file_metadata["parents"] = [parent_id]

            folder = self.service.files().create(
                body=file_metadata,
                fields="id"
            ).execute()
            return folder.get("id")
        except Exception as e:
            raise RuntimeError(f"폴더 '{folder_name}' 생성/조회 실패: {e}")

    def upload_file(self, local_path: Path, parent_id: str) -> Optional[dict]:
        """
        로컬 파일을 지정된 부모 폴더에 업로드합니다.
        동일한 이름의 파일이 이미 있으면 내용을 갱신(Update)합니다.
        """
        if not local_path.exists():
            return None

        file_name = local_path.name
        mime_type, _ = mimetypes.guess_type(str(local_path))
        if not mime_type:
            if local_path.suffix.lower() == ".md":
                mime_type = "text/markdown"
            elif local_path.suffix.lower() == ".json":
                mime_type = "application/json"
            else:
                mime_type = "application/octet-stream"

        media = MediaFileUpload(str(local_path), mimetype=mime_type, resumable=True)

        # 기존 동일 파일 검색
        query = (
            f"name = '{file_name}' "
            f"and '{parent_id}' in parents "
            f"and trashed = false"
        )
        try:
            results = self.service.files().list(
                q=query,
                spaces="drive",
                fields="files(id, name)"
            ).execute()
            existing = results.get("files", [])

            if existing:
                # 파일 갱신 (Update)
                file_id = existing[0]["id"]
                updated = self.service.files().update(
                    fileId=file_id,
                    media_body=media,
                    fields="id, name"
                ).execute()
                return updated
            else:
                # 새 파일 생성 (Create)
                metadata = {
                    "name": file_name,
                    "parents": [parent_id]
                }
                created = self.service.files().create(
                    body=metadata,
                    media_body=media,
                    fields="id, name"
                ).execute()
                return created
        except Exception as e:
            print(f"     ⚠️ [{file_name}] 업로드 실패: {e}")
            return None

    def upload_weekly_package(self, weekly_dir: Path) -> Dict[str, Any]:
        """
        주간 큐레이션 폴더 전체(카드뉴스 36장 + 쇼츠 영상 6편 + 요약본 등)를
        구글 드라이브 'THEPT_주간콘텐츠' 폴더 아래에 구조 그대로 업로드합니다.
        """
        print("\n" + "=" * 70)
        print(f"☁️ [Google Drive] 주간 콘텐츠 자동 백업 업로드를 시작합니다.")
        print(f"👉 로컬 폴더: {weekly_dir.name}")
        print("=" * 70)

        # 1. 루트 폴더 'THEPT_주간콘텐츠' 확보
        root_id = self.get_or_create_folder(GDRIVE_ROOT_FOLDER_NAME, parent_id=None)

        # 2. 이번 주차 폴더(예: 2026-09-21_curated_weekly) 확보
        weekly_folder_id = self.get_or_create_folder(weekly_dir.name, parent_id=root_id)

        # 3. 주간 요약 파일 업로드
        summary_file = weekly_dir / "weekly_summary.md"
        if summary_file.exists():
            self.upload_file(summary_file, weekly_folder_id)

        uploaded_counts = {"images": 0, "videos": 0, "texts": 0}

        # 4. 요일별 폴더(0921_Mon_Policy 등) 순회 업로드
        day_folders = sorted([d for d in weekly_dir.iterdir() if d.is_dir() and not d.name.startswith(".")])
        total_days = len(day_folders)

        for idx, day_dir in enumerate(day_folders, start=1):
            if day_dir.name in ["backgrounds", "tmp", ".cache"]:
                continue

            print(f"\n📂 [{idx}/{total_days}] '{day_dir.name}' 업로드 중...")
            day_folder_id = self.get_or_create_folder(day_dir.name, parent_id=weekly_folder_id)

            # (1) 4:5 카드뉴스 이미지 업로드
            card_dir = day_dir / "card_images_4x5"
            if card_dir.exists():
                cards_folder_id = self.get_or_create_folder("card_images_4x5", parent_id=day_folder_id)
                png_files = sorted(list(card_dir.glob("*.png")))
                for png in png_files:
                    res = self.upload_file(png, cards_folder_id)
                    if res:
                        uploaded_counts["images"] += 1

            # (2) 9:16 쇼츠 비디오 업로드
            video_files = list(day_dir.glob("shorts_*.mp4")) or list(day_dir.glob("*.mp4"))
            for vf in video_files:
                res = self.upload_file(vf, day_folder_id)
                if res:
                    uploaded_counts["videos"] += 1

            # (3) 대본 및 캡션 텍스트 파일 업로드
            for txt_name in ["package_data.json", "instagram_caption.txt", "youtube_shorts_caption.txt", "first_comment.txt"]:
                tf = day_dir / txt_name
                if tf.exists():
                    res = self.upload_file(tf, day_folder_id)
                    if res:
                        uploaded_counts["texts"] += 1

            print(f"   ✅ '{day_dir.name}' 업로드 완료")

        print("\n" + "=" * 70)
        print(f"🎉 [업로드 완료] Google Drive '내 드라이브 > {GDRIVE_ROOT_FOLDER_NAME} > {weekly_dir.name}'에 저장을 완료했습니다!")
        print(f"   • 카드뉴스 이미지: {uploaded_counts['images']}장")
        print(f"   • 쇼츠 비디오: {uploaded_counts['videos']}편")
        print(f"   • 대본 및 메타데이터: {uploaded_counts['texts']}개")
        print("=" * 70)

        return {
            "success": True,
            "weekly_folder_id": weekly_folder_id,
            "counts": uploaded_counts
        }


def sync_weekly_to_gdrive(weekly_dir: Path, dry_run: bool = False) -> bool:
    """
    curate.py sync에서 호출되는 Google Drive 연동 메인 함수.
    인증 파일이 없으면 안내 후 안전하게 건너뛰며, dry_run 시 시뮬레이션만 수행합니다.
    """
    if dry_run:
        print("\n[DRY-RUN] Google Drive 업로드 시뮬레이션: 실제 업로드는 건너뜁니다.")
        return True

    token_path = Path(GDRIVE_TOKEN_FILE)
    if not token_path.exists():
        print("\nℹ️ [Google Drive 안내] Google Drive 연동 인증 파일(gdrive_token.pickle)이 없습니다.")
        print("   Google Drive 자동 저장을 원하시면 최초 1회 아래 명령어를 실행해주세요:")
        print("   👉 python curate.py auth-gdrive\n")
        return False

    try:
        service = authenticate_gdrive()
        if not service:
            print("⚠️ [Google Drive] 서비스 인증 실패로 구글 드라이브 업로드를 건너뜁니다.")
            return False

        uploader = GoogleDriveUploader(service)
        uploader.upload_weekly_package(weekly_dir)
        return True
    except Exception as e:
        print(f"⚠️ [Google Drive] 동기화 업로드 중 오류 발생: {e}")
        return False
