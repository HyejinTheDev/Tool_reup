from datetime import datetime
from typing import Optional

class Account:
    def __init__(self, id: str, name: str, platform: str, profile_name: str, email: Optional[str] = None, created_at: Optional[str] = None):
        self.id = id
        self.name = name
        self.platform = platform
        self.profile_name = profile_name
        self.email = email
        self.created_at = created_at or datetime.now().isoformat()

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "platform": self.platform,
            "profile_name": self.profile_name,
            "email": self.email,
            "created_at": self.created_at
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Account":
        return cls(
            id=data.get("id"),
            name=data.get("name"),
            platform=data.get("platform"),
            profile_name=data.get("profile_name"),
            email=data.get("email"),
            created_at=data.get("created_at")
        )
