import os
import json
from typing import List, Optional
from app.adapters.repositories.base_repository import BaseRepository
from app.domain.account import Account
from app.domain.video import Video

class JsonRepository(BaseRepository):
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._ensure_db_exists()

    def _ensure_db_exists(self):
        if not os.path.exists(self.db_path):
            initial_data = {
                "accounts": [],
                "videos": [],
                "settings": {
                    "chrome_path": "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
                    "headless": False
                }
            }
            self._write_file(initial_data)

    def _read_file(self) -> dict:
        try:
            with open(self.db_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {"accounts": [], "videos": [], "settings": {"chrome_path": "", "headless": False}}

    def _write_file(self, data: dict):
        with open(self.db_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def get_accounts(self) -> List[Account]:
        data = self._read_file()
        return [Account.from_dict(acc) for acc in data.get("accounts", [])]

    def save_accounts(self, accounts: List[Account]) -> None:
        data = self._read_file()
        data["accounts"] = [acc.to_dict() for acc in accounts]
        self._write_file(data)

    def add_account(self, account: Account) -> None:
        accounts = self.get_accounts()
        accounts.append(account)
        self.save_accounts(accounts)

    def delete_account(self, account_id: str) -> None:
        accounts = self.get_accounts()
        accounts = [acc for acc in accounts if acc.id != account_id]
        self.save_accounts(accounts)

    def get_videos(self) -> List[Video]:
        data = self._read_file()
        return [Video.from_dict(vid) for vid in data.get("videos", [])]

    def save_videos(self, videos: List[Video]) -> None:
        data = self._read_file()
        data["videos"] = [vid.to_dict() for vid in videos]
        self._write_file(data)

    def add_video(self, video: Video) -> None:
        videos = self.get_videos()
        videos.append(video)
        self.save_videos(videos)

    def get_settings(self) -> dict:
        data = self._read_file()
        return data.get("settings", {"chrome_path": "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe", "headless": False})

    def save_settings(self, settings: dict) -> None:
        data = self._read_file()
        data["settings"] = settings
        self._write_file(data)
