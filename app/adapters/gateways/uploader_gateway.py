from abc import ABC, abstractmethod

class UploaderGateway(ABC):
    @abstractmethod
    async def upload(self, video_path: str, title: str, description: str, publish_type: str = "default") -> str:
        """
        Uploads a video to the platform.
        Returns the video URL or confirmation URL.
        """
        pass
