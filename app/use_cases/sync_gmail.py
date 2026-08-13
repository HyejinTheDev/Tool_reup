import os
import json
import uuid
from datetime import datetime
from app.adapters.repositories.base_repository import BaseRepository
from app.domain.account import Account

class SyncGmailUseCase:
    def __init__(self, repository: BaseRepository):
        self.repository = repository

    def execute(self) -> int:
        gmail_db_path = r"C:\Chuongtrinh\tools\gmail\database.json"
        gmail_profiles_dir = r"C:\Chuongtrinh\tools\gmail\chrome_profiles"
        
        if not os.path.exists(gmail_db_path):
            raise FileNotFoundError("Không tìm thấy tệp tin database của Gmail Manager.")
            
        try:
            with open(gmail_db_path, "r", encoding="utf-8") as f:
                gmail_accounts = json.load(f)
        except Exception as e:
            raise Exception(f"Lỗi đọc dữ liệu Gmail: {str(e)}")
            
        accounts = self.repository.get_accounts()
        existing_emails = {acc.email for acc in accounts if acc.platform == "youtube" and acc.email}
        
        added_count = 0
        for g_acc in gmail_accounts:
            email = g_acc.get("email")
            if not email or email in existing_emails:
                continue
                
            email_name = "".join(c for c in email.split('@')[0] if c.isalnum() or c in ("_", "-")).lower()
            profile_name = f"profile_{email_name}"
            absolute_profile_path = os.path.join(gmail_profiles_dir, profile_name)
            
            new_account = Account(
                id=f"acc_gmail_{uuid.uuid4().hex[:8]}",
                name=g_acc.get("notes") or email,
                email=email,
                platform="youtube",
                profile_name=absolute_profile_path,
                created_at=datetime.now().isoformat()
            )
            self.repository.add_account(new_account)
            added_count += 1
            
        return added_count
