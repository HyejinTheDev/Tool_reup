from abc import ABC, abstractmethod
from typing import Optional

class UploaderGateway(ABC):
    @abstractmethod
    async def upload(self, video_path: str, title: str, description: str, publish_type: str = "default") -> str:
        """
        Uploads a video to the platform.
        Returns the video URL or confirmation URL.
        """
        pass

    @abstractmethod
    async def delete_post(self, title: str, post_url: Optional[str] = None) -> bool:
        """
        Deletes a video from the platform based on title or URL.
        Returns True if successful, False otherwise.
        """
        pass
