from datetime import datetime
from typing import List, Dict, Optional

class Video:
    def __init__(self, id: str, filename: str, filepath: str, title: str, description: str, target_accounts: List[str], status: str = "pending", results: Optional[Dict] = None, created_at: Optional[str] = None):
        self.id = id
        self.filename = filename
        self.filepath = filepath
        self.title = title
        self.description = description
        self.target_accounts = target_accounts
        self.status = status
        self.results = results or {}
        self.created_at = created_at or datetime.now().isoformat()

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "filename": self.filename,
            "filepath": self.filepath,
            "title": self.title,
            "description": self.description,
            "target_accounts": self.target_accounts,
            "status": self.status,
            "results": self.results,
            "created_at": self.created_at
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Video":
        return cls(
            id=data.get("id"),
            filename=data.get("filename"),
            filepath=data.get("filepath"),
            title=data.get("title"),
            description=data.get("description"),
            target_accounts=data.get("target_accounts", []),
            status=data.get("status", "pending"),
            results=data.get("results"),
            created_at=data.get("created_at")
        )
