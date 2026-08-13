from abc import ABC, abstractmethod
from typing import List, Optional
from app.domain.account import Account
from app.domain.video import Video

class BaseRepository(ABC):
    @abstractmethod
    def get_accounts(self) -> List[Account]:
        pass

    @abstractmethod
    def save_accounts(self, accounts: List[Account]) -> None:
        pass

    @abstractmethod
    def add_account(self, account: Account) -> None:
        pass

    @abstractmethod
    def delete_account(self, account_id: str) -> None:
        pass

    @abstractmethod
    def get_videos(self) -> List[Video]:
        pass

    @abstractmethod
    def save_videos(self, videos: List[Video]) -> None:
        pass

    @abstractmethod
    def add_video(self, video: Video) -> None:
        pass

    @abstractmethod
    def get_settings(self) -> dict:
        pass

    @abstractmethod
    def save_settings(self, settings: dict) -> None:
        pass
