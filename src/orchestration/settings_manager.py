"""
Settings Manager - Manages user settings with SQLite storage
"""

import sqlite3
import os
import base64
from pathlib import Path
from typing import Optional, Dict, Any
from cryptography.fernet import Fernet
from pydantic import BaseModel


class LLMSettings(BaseModel):
    """LLM Settings model"""
    provider: str  # anthropic, openai, openrouter
    api_key: str
    model: str
    base_url: Optional[str] = None


class SettingsManager:
    """Manages application settings with SQLite storage and encryption"""

    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            # Default to project root/data directory
            project_root = Path(__file__).parent.parent.parent
            data_dir = project_root / "data"
            data_dir.mkdir(exist_ok=True)
            db_path = str(data_dir / "settings.db")

        self.db_path = db_path
        self.encryption_key = self._get_or_create_encryption_key()
        self.cipher = Fernet(self.encryption_key)
        self._initialize_database()

    def _get_or_create_encryption_key(self) -> bytes:
        """Get or create encryption key for API keys"""
        project_root = Path(__file__).parent.parent.parent
        key_file = project_root / "data" / ".encryption_key"

        if key_file.exists():
            with open(key_file, "rb") as f:
                return f.read()
        else:
            # Create new encryption key
            key = Fernet.generate_key()
            key_file.parent.mkdir(exist_ok=True)
            with open(key_file, "wb") as f:
                f.write(key)
            # Set file permissions to owner only
            os.chmod(key_file, 0o600)
            return key

    def _initialize_database(self):
        """Initialize SQLite database with settings table"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Create settings table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS llm_settings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    tenant TEXT NOT NULL,
                    provider TEXT NOT NULL,
                    api_key_encrypted TEXT NOT NULL,
                    model TEXT NOT NULL,
                    base_url TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(user_id, tenant)
                )
            """)

            # Create index for faster lookups
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_user_tenant
                ON llm_settings(user_id, tenant)
            """)

            conn.commit()

    def _encrypt_api_key(self, api_key: str) -> str:
        """Encrypt API key"""
        encrypted = self.cipher.encrypt(api_key.encode())
        return base64.b64encode(encrypted).decode()

    def _decrypt_api_key(self, encrypted_key: str) -> str:
        """Decrypt API key"""
        encrypted_bytes = base64.b64decode(encrypted_key.encode())
        decrypted = self.cipher.decrypt(encrypted_bytes)
        return decrypted.decode()

    def save_llm_settings(
        self,
        user_id: str,
        tenant: str,
        provider: str,
        api_key: str,
        model: str,
        base_url: Optional[str] = None
    ) -> bool:
        """Save LLM settings for a user"""
        encrypted_key = self._encrypt_api_key(api_key)

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Upsert (insert or update)
            cursor.execute("""
                INSERT INTO llm_settings (user_id, tenant, provider, api_key_encrypted, model, base_url)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id, tenant) DO UPDATE SET
                    provider = excluded.provider,
                    api_key_encrypted = excluded.api_key_encrypted,
                    model = excluded.model,
                    base_url = excluded.base_url,
                    updated_at = CURRENT_TIMESTAMP
            """, (user_id, tenant, provider, encrypted_key, model, base_url))

            conn.commit()

        return True

    def get_llm_settings(self, user_id: str, tenant: str) -> Optional[LLMSettings]:
        """Get LLM settings for a user"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            cursor.execute("""
                SELECT provider, api_key_encrypted, model, base_url
                FROM llm_settings
                WHERE user_id = ? AND tenant = ?
            """, (user_id, tenant))

            row = cursor.fetchone()

            if row:
                provider, encrypted_key, model, base_url = row
                api_key = self._decrypt_api_key(encrypted_key)

                return LLMSettings(
                    provider=provider,
                    api_key=api_key,
                    model=model,
                    base_url=base_url
                )

        return None

    def delete_llm_settings(self, user_id: str, tenant: str) -> bool:
        """Delete LLM settings for a user"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            cursor.execute("""
                DELETE FROM llm_settings
                WHERE user_id = ? AND tenant = ?
            """, (user_id, tenant))

            deleted = cursor.rowcount > 0
            conn.commit()

        return deleted

    def get_all_settings(self, user_id: str, tenant: str) -> Dict[str, Any]:
        """Get all settings for a user (for UI display, with masked API key)"""
        settings = self.get_llm_settings(user_id, tenant)

        if settings:
            # Mask API key for display (show only last 4 characters)
            masked_key = "*" * (len(settings.api_key) - 4) + settings.api_key[-4:]

            return {
                "provider": settings.provider,
                "api_key_masked": masked_key,
                "api_key_set": True,
                "model": settings.model,
                "base_url": settings.base_url,
                "has_settings": True
            }

        return {
            "provider": "anthropic",
            "api_key_masked": "",
            "api_key_set": False,
            "model": "claude-3-5-sonnet-20241022",
            "base_url": None,
            "has_settings": False
        }

    def test_connection(
        self,
        provider: str,
        api_key: str,
        model: str,
        base_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """Test LLM connection with provided credentials"""
        try:
            if provider == "anthropic":
                from anthropic import Anthropic
                kwargs = {"api_key": api_key}
                if base_url:
                    kwargs["base_url"] = base_url
                client = Anthropic(**kwargs)
                # Try a simple API call
                response = client.messages.create(
                    model=model,
                    max_tokens=10,
                    messages=[{"role": "user", "content": "Hello"}]
                )
                return {"success": True, "message": "Connection successful"}

            elif provider == "openai":
                import openai
                kwargs = {"api_key": api_key}
                if base_url:
                    kwargs["base_url"] = base_url
                client = openai.OpenAI(**kwargs)
                response = client.chat.completions.create(
                    model=model,
                    max_tokens=10,
                    messages=[{"role": "user", "content": "Hello"}]
                )
                return {"success": True, "message": "Connection successful"}

            elif provider == "openrouter":
                import openai
                client = openai.OpenAI(
                    base_url=base_url or "https://openrouter.ai/api/v1",
                    api_key=api_key
                )
                response = client.chat.completions.create(
                    model=model,
                    max_tokens=10,
                    messages=[{"role": "user", "content": "Hello"}]
                )
                return {"success": True, "message": "Connection successful"}

            else:
                return {"success": False, "message": f"Unknown provider: {provider}"}

        except Exception as e:
            return {"success": False, "message": f"Connection failed: {str(e)}"}
