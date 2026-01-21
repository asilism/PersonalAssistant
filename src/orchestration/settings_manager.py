"""
Settings Manager - Manages user settings with SQLite storage
"""

import sqlite3
import os
import json
import base64
from pathlib import Path
from typing import Optional, Dict, Any
from cryptography.fernet import Fernet
from pydantic import BaseModel


class LLMSettings(BaseModel):
    """LLM Settings model"""
    config_name: str  # Configuration name (e.g., "Claude Prod", "GPT Dev")
    provider: str  # anthropic, openai, openrouter
    api_key: str
    model: str
    base_url: Optional[str] = None
    max_retries: int = 3
    timeout: int = 30000  # milliseconds
    is_active: bool = False  # Whether this configuration is currently active


class MCPServerSettings(BaseModel):
    """MCP Server Settings model"""
    server_name: str
    enabled: bool = True
    transport: str = "http"  # "stdio", "http", "streamable-http", or "sse"
    url: Optional[str] = None  # URL for HTTP/SSE transport
    command: Optional[str] = None  # Command for STDIO transport
    args: Optional[list] = None  # Args for STDIO transport
    env_vars: Optional[Dict[str, str]] = None
    headers: Optional[Dict[str, str]] = None  # Custom headers for HTTP/SSE transport (e.g., API keys)


class ChatSession(BaseModel):
    """Chat session model"""
    session_id: str
    user_id: str
    tenant: str
    title: Optional[str] = None  # Auto-generated from first message
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class ChatMessage(BaseModel):
    """Chat message model"""
    id: Optional[int] = None
    session_id: str
    user_id: str
    tenant: str
    role: str  # "user" or "assistant"
    content: str
    created_at: Optional[str] = None


class ExecutionResult(BaseModel):
    """Execution result model for storing structured tool outputs"""
    id: Optional[int] = None
    session_id: str
    user_id: str
    tenant: str
    request_text: str
    results_json: str  # JSON string of structured results
    created_at: Optional[str] = None


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

            # Create LLM settings table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS llm_settings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    tenant TEXT NOT NULL,
                    config_name TEXT NOT NULL,
                    provider TEXT NOT NULL,
                    api_key_encrypted TEXT NOT NULL,
                    model TEXT NOT NULL,
                    base_url TEXT,
                    max_retries INTEGER DEFAULT 3,
                    timeout INTEGER DEFAULT 30000,
                    is_active INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(user_id, tenant, config_name)
                )
            """)

            # Check if base_url column exists and add if missing (migration for existing DBs)
            cursor.execute("PRAGMA table_info(llm_settings)")
            columns = [row[1] for row in cursor.fetchall()]

            migrations_performed = []

            if "base_url" not in columns:
                print("⚠️  Migrating database: Adding base_url column to llm_settings table")
                cursor.execute("ALTER TABLE llm_settings ADD COLUMN base_url TEXT")
                migrations_performed.append("base_url")

            if "max_retries" not in columns:
                print("⚠️  Migrating database: Adding max_retries column to llm_settings table")
                cursor.execute("ALTER TABLE llm_settings ADD COLUMN max_retries INTEGER DEFAULT 3")
                migrations_performed.append("max_retries")

            if "timeout" not in columns:
                print("⚠️  Migrating database: Adding timeout column to llm_settings table")
                cursor.execute("ALTER TABLE llm_settings ADD COLUMN timeout INTEGER DEFAULT 30000")
                migrations_performed.append("timeout")

            if "config_name" not in columns:
                print("⚠️  Migrating database: Adding config_name column to llm_settings table")
                cursor.execute("ALTER TABLE llm_settings ADD COLUMN config_name TEXT DEFAULT 'Default'")
                migrations_performed.append("config_name")

            if "is_active" not in columns:
                print("⚠️  Migrating database: Adding is_active column to llm_settings table")
                cursor.execute("ALTER TABLE llm_settings ADD COLUMN is_active INTEGER DEFAULT 0")
                migrations_performed.append("is_active")

                # Set first existing record as active for each user/tenant
                cursor.execute("""
                    UPDATE llm_settings
                    SET is_active = 1
                    WHERE id IN (
                        SELECT MIN(id)
                        FROM llm_settings
                        GROUP BY user_id, tenant
                    )
                """)

            if migrations_performed:
                conn.commit()
                print(f"✅ Database migration complete: Added columns {', '.join(migrations_performed)}")

                # Handle UNIQUE constraint migration
                if "config_name" in migrations_performed:
                    print("⚠️  Migrating UNIQUE constraint from (user_id, tenant) to (user_id, tenant, config_name)")
                    # SQLite doesn't support ALTER TABLE DROP CONSTRAINT, so we need to recreate the table
                    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='llm_settings_new'")
                    if not cursor.fetchone():
                        # Create new table with correct schema
                        cursor.execute("""
                            CREATE TABLE llm_settings_new (
                                id INTEGER PRIMARY KEY AUTOINCREMENT,
                                user_id TEXT NOT NULL,
                                tenant TEXT NOT NULL,
                                config_name TEXT NOT NULL,
                                provider TEXT NOT NULL,
                                api_key_encrypted TEXT NOT NULL,
                                model TEXT NOT NULL,
                                base_url TEXT,
                                max_retries INTEGER DEFAULT 3,
                                timeout INTEGER DEFAULT 30000,
                                is_active INTEGER DEFAULT 0,
                                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                                UNIQUE(user_id, tenant, config_name)
                            )
                        """)

                        # Copy data from old table
                        cursor.execute("""
                            INSERT INTO llm_settings_new
                            (id, user_id, tenant, config_name, provider, api_key_encrypted, model,
                             base_url, max_retries, timeout, is_active, created_at, updated_at)
                            SELECT id, user_id, tenant,
                                   COALESCE(config_name, 'Default'),
                                   provider, api_key_encrypted, model,
                                   base_url,
                                   COALESCE(max_retries, 3),
                                   COALESCE(timeout, 30000),
                                   COALESCE(is_active, 0),
                                   created_at, updated_at
                            FROM llm_settings
                        """)

                        # Drop old table and rename new one
                        cursor.execute("DROP TABLE llm_settings")
                        cursor.execute("ALTER TABLE llm_settings_new RENAME TO llm_settings")

                        conn.commit()
                        print("✅ UNIQUE constraint migration complete")

            # Create index for faster lookups
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_user_tenant
                ON llm_settings(user_id, tenant)
            """)

            # Create MCP server settings table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS mcp_server_settings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    tenant TEXT NOT NULL,
                    server_name TEXT NOT NULL,
                    enabled INTEGER DEFAULT 1,
                    transport TEXT DEFAULT 'http',
                    url TEXT,
                    command TEXT,
                    args TEXT,
                    env_vars TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(user_id, tenant, server_name)
                )
            """)

            # Check if transport, url, headers columns exist and add if missing
            cursor.execute("PRAGMA table_info(mcp_server_settings)")
            mcp_columns = [row[1] for row in cursor.fetchall()]

            if "transport" not in mcp_columns:
                print("⚠️  Migrating database: Adding transport column to mcp_server_settings table")
                cursor.execute("ALTER TABLE mcp_server_settings ADD COLUMN transport TEXT DEFAULT 'http'")
                migrations_performed.append("transport")

            if "url" not in mcp_columns:
                print("⚠️  Migrating database: Adding url column to mcp_server_settings table")
                cursor.execute("ALTER TABLE mcp_server_settings ADD COLUMN url TEXT")
                migrations_performed.append("url")

            if "headers" not in mcp_columns:
                print("⚠️  Migrating database: Adding headers column to mcp_server_settings table")
                cursor.execute("ALTER TABLE mcp_server_settings ADD COLUMN headers TEXT")
                migrations_performed.append("headers")

            # Create index for MCP server settings
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_mcp_user_tenant
                ON mcp_server_settings(user_id, tenant)
            """)

            # Create sessions table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    tenant TEXT NOT NULL,
                    title TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Create index for sessions (for fast user/tenant lookups)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_sessions_user_tenant
                ON sessions(user_id, tenant, updated_at DESC)
            """)

            # Create chat history table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS chat_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    tenant TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Create index for chat history (for fast session lookups)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_chat_session
                ON chat_history(session_id, created_at)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_chat_user_tenant
                ON chat_history(user_id, tenant, created_at)
            """)

            # Create execution results table for storing structured tool outputs
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS execution_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    tenant TEXT NOT NULL,
                    request_text TEXT NOT NULL,
                    results_json TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Create index for execution results (for fast session lookups)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_execution_session
                ON execution_results(session_id, created_at)
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
        config_name: str,
        provider: str,
        api_key: str,
        model: str,
        base_url: Optional[str] = None,
        max_retries: int = 3,
        timeout: int = 30000,
        is_active: bool = False
    ) -> bool:
        """Save LLM settings for a user"""
        encrypted_key = self._encrypt_api_key(api_key)

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # If setting this as active, deactivate all other configs for this user/tenant
            if is_active:
                cursor.execute("""
                    UPDATE llm_settings
                    SET is_active = 0
                    WHERE user_id = ? AND tenant = ? AND config_name != ?
                """, (user_id, tenant, config_name))

            # Upsert (insert or update)
            cursor.execute("""
                INSERT INTO llm_settings (user_id, tenant, config_name, provider, api_key_encrypted, model, base_url, max_retries, timeout, is_active)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id, tenant, config_name) DO UPDATE SET
                    provider = excluded.provider,
                    api_key_encrypted = excluded.api_key_encrypted,
                    model = excluded.model,
                    base_url = excluded.base_url,
                    max_retries = excluded.max_retries,
                    timeout = excluded.timeout,
                    is_active = excluded.is_active,
                    updated_at = CURRENT_TIMESTAMP
            """, (user_id, tenant, config_name, provider, encrypted_key, model, base_url, max_retries, timeout, int(is_active)))

            conn.commit()

        return True

    def get_llm_settings(self, user_id: str, tenant: str) -> Optional[LLMSettings]:
        """Get active LLM settings for a user (backward compatibility)"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            cursor.execute("""
                SELECT config_name, provider, api_key_encrypted, model, base_url, max_retries, timeout, is_active
                FROM llm_settings
                WHERE user_id = ? AND tenant = ? AND is_active = 1
            """, (user_id, tenant))

            row = cursor.fetchone()

            if row:
                config_name, provider, encrypted_key, model, base_url, max_retries, timeout, is_active = row
                api_key = self._decrypt_api_key(encrypted_key)

                return LLMSettings(
                    config_name=config_name,
                    provider=provider,
                    api_key=api_key,
                    model=model,
                    base_url=base_url,
                    max_retries=max_retries or 3,
                    timeout=timeout or 30000,
                    is_active=bool(is_active)
                )

        return None

    def get_all_llm_settings(self, user_id: str, tenant: str) -> list[LLMSettings]:
        """Get all LLM settings for a user"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            cursor.execute("""
                SELECT config_name, provider, api_key_encrypted, model, base_url, max_retries, timeout, is_active
                FROM llm_settings
                WHERE user_id = ? AND tenant = ?
                ORDER BY is_active DESC, created_at ASC
            """, (user_id, tenant))

            settings_list = []
            for row in cursor.fetchall():
                config_name, provider, encrypted_key, model, base_url, max_retries, timeout, is_active = row
                api_key = self._decrypt_api_key(encrypted_key)

                settings_list.append(LLMSettings(
                    config_name=config_name,
                    provider=provider,
                    api_key=api_key,
                    model=model,
                    base_url=base_url,
                    max_retries=max_retries or 3,
                    timeout=timeout or 30000,
                    is_active=bool(is_active)
                ))

            return settings_list

    def get_llm_settings_by_name(self, user_id: str, tenant: str, config_name: str) -> Optional[LLMSettings]:
        """Get specific LLM settings by configuration name"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            cursor.execute("""
                SELECT config_name, provider, api_key_encrypted, model, base_url, max_retries, timeout, is_active
                FROM llm_settings
                WHERE user_id = ? AND tenant = ? AND config_name = ?
            """, (user_id, tenant, config_name))

            row = cursor.fetchone()

            if row:
                config_name, provider, encrypted_key, model, base_url, max_retries, timeout, is_active = row
                api_key = self._decrypt_api_key(encrypted_key)

                return LLMSettings(
                    config_name=config_name,
                    provider=provider,
                    api_key=api_key,
                    model=model,
                    base_url=base_url,
                    max_retries=max_retries or 3,
                    timeout=timeout or 30000,
                    is_active=bool(is_active)
                )

        return None

    def set_active_llm_settings(self, user_id: str, tenant: str, config_name: str) -> bool:
        """Set a specific configuration as active (deactivates all others)"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # First, check if the config exists
            cursor.execute("""
                SELECT id FROM llm_settings
                WHERE user_id = ? AND tenant = ? AND config_name = ?
            """, (user_id, tenant, config_name))

            if not cursor.fetchone():
                return False

            # Deactivate all configs for this user/tenant
            cursor.execute("""
                UPDATE llm_settings
                SET is_active = 0
                WHERE user_id = ? AND tenant = ?
            """, (user_id, tenant))

            # Activate the specified config
            cursor.execute("""
                UPDATE llm_settings
                SET is_active = 1
                WHERE user_id = ? AND tenant = ? AND config_name = ?
            """, (user_id, tenant, config_name))

            conn.commit()

        return True

    def delete_llm_settings(self, user_id: str, tenant: str, config_name: str) -> bool:
        """Delete specific LLM settings by configuration name"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            cursor.execute("""
                DELETE FROM llm_settings
                WHERE user_id = ? AND tenant = ? AND config_name = ?
            """, (user_id, tenant, config_name))

            deleted = cursor.rowcount > 0
            conn.commit()

        return deleted

    def get_all_settings(self, user_id: str, tenant: str) -> Dict[str, Any]:
        """Get all LLM settings for a user (for UI display, with masked API keys)"""
        all_settings = self.get_all_llm_settings(user_id, tenant)

        if all_settings:
            configs = []
            for settings in all_settings:
                # Mask API key for display (show only last 4 characters)
                masked_key = "*" * (len(settings.api_key) - 4) + settings.api_key[-4:]

                configs.append({
                    "config_name": settings.config_name,
                    "provider": settings.provider,
                    "api_key_masked": masked_key,
                    "model": settings.model,
                    "base_url": settings.base_url,
                    "max_retries": settings.max_retries,
                    "timeout": settings.timeout,
                    "is_active": settings.is_active
                })

            return {
                "has_settings": True,
                "configs": configs
            }

        return {
            "has_settings": False,
            "configs": []
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

    # MCP Server Settings Methods
    def save_mcp_server_settings(
        self,
        user_id: str,
        tenant: str,
        server_name: str,
        enabled: bool = True,
        transport: str = "http",
        url: Optional[str] = None,
        command: Optional[str] = None,
        args: Optional[list] = None,
        env_vars: Optional[Dict[str, str]] = None,
        headers: Optional[Dict[str, str]] = None
    ) -> bool:
        """Save MCP server settings"""
        args_json = json.dumps(args or [])
        env_vars_json = json.dumps(env_vars or {})
        headers_json = json.dumps(headers or {})

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            cursor.execute("""
                INSERT INTO mcp_server_settings (user_id, tenant, server_name, enabled, transport, url, command, args, env_vars, headers)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id, tenant, server_name) DO UPDATE SET
                    enabled = excluded.enabled,
                    transport = excluded.transport,
                    url = excluded.url,
                    command = excluded.command,
                    args = excluded.args,
                    env_vars = excluded.env_vars,
                    headers = excluded.headers,
                    updated_at = CURRENT_TIMESTAMP
            """, (user_id, tenant, server_name, int(enabled), transport, url, command, args_json, env_vars_json, headers_json))

            conn.commit()

        return True

    def get_mcp_server_settings(
        self,
        user_id: str,
        tenant: str,
        server_name: str
    ) -> Optional[MCPServerSettings]:
        """Get MCP server settings"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            cursor.execute("""
                SELECT server_name, enabled, transport, url, command, args, env_vars, headers
                FROM mcp_server_settings
                WHERE user_id = ? AND tenant = ? AND server_name = ?
            """, (user_id, tenant, server_name))

            row = cursor.fetchone()

            if row:
                server_name, enabled, transport, url, command, args_json, env_vars_json, headers_json = row
                return MCPServerSettings(
                    server_name=server_name,
                    enabled=bool(enabled),
                    transport=transport or "http",
                    url=url,
                    command=command,
                    args=json.loads(args_json) if args_json else None,
                    env_vars=json.loads(env_vars_json) if env_vars_json else None,
                    headers=json.loads(headers_json) if headers_json else None
                )

        return None

    def get_all_mcp_servers(self, user_id: str, tenant: str) -> list[MCPServerSettings]:
        """Get all MCP server settings for a user"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            cursor.execute("""
                SELECT server_name, enabled, transport, url, command, args, env_vars, headers
                FROM mcp_server_settings
                WHERE user_id = ? AND tenant = ?
            """, (user_id, tenant))

            servers = []
            for row in cursor.fetchall():
                server_name, enabled, transport, url, command, args_json, env_vars_json, headers_json = row
                servers.append(MCPServerSettings(
                    server_name=server_name,
                    enabled=bool(enabled),
                    transport=transport or "http",
                    url=url,
                    command=command,
                    args=json.loads(args_json) if args_json else None,
                    env_vars=json.loads(env_vars_json) if env_vars_json else None,
                    headers=json.loads(headers_json) if headers_json else None
                ))

            return servers

    def delete_mcp_server_settings(
        self,
        user_id: str,
        tenant: str,
        server_name: str
    ) -> bool:
        """Delete MCP server settings"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            cursor.execute("""
                DELETE FROM mcp_server_settings
                WHERE user_id = ? AND tenant = ? AND server_name = ?
            """, (user_id, tenant, server_name))

            deleted = cursor.rowcount > 0
            conn.commit()

        return deleted

    # Chat History Methods
    def save_chat_message(
        self,
        session_id: str,
        user_id: str,
        tenant: str,
        role: str,
        content: str
    ) -> bool:
        """Save a chat message to history"""
        print(f"[SettingsManager] Attempting to save {role} message to DB - session_id={session_id}, db_path={self.db_path}")
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                cursor.execute("""
                    INSERT INTO chat_history (session_id, user_id, tenant, role, content)
                    VALUES (?, ?, ?, ?, ?)
                """, (session_id, user_id, tenant, role, content))

                conn.commit()

            print(f"[SettingsManager] {role} message saved to DB successfully")
            return True
        except Exception as e:
            print(f"[SettingsManager] ERROR saving message to DB: {e}")
            import traceback
            traceback.print_exc()
            raise

    def get_chat_history(
        self,
        session_id: str,
        limit: Optional[int] = None
    ) -> list[ChatMessage]:
        """Get chat history for a session"""
        print(f"[SettingsManager] Getting chat history - session_id={session_id}, limit={limit}, db_path={self.db_path}")
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                if limit:
                    # Get last N messages
                    cursor.execute("""
                        SELECT id, session_id, user_id, tenant, role, content, created_at
                        FROM chat_history
                        WHERE session_id = ?
                        ORDER BY created_at DESC
                        LIMIT ?
                    """, (session_id, limit))
                else:
                    # Get all messages
                    cursor.execute("""
                        SELECT id, session_id, user_id, tenant, role, content, created_at
                        FROM chat_history
                        WHERE session_id = ?
                        ORDER BY created_at ASC
                    """, (session_id,))

                messages = []
                rows = cursor.fetchall()
                print(f"[SettingsManager] Found {len(rows)} messages in DB")

                # If we used LIMIT with DESC, reverse to get chronological order
                if limit:
                    rows = reversed(rows)

                for row in rows:
                    msg_id, session_id, user_id, tenant, role, content, created_at = row
                    messages.append(ChatMessage(
                        id=msg_id,
                        session_id=session_id,
                        user_id=user_id,
                        tenant=tenant,
                        role=role,
                        content=content,
                        created_at=created_at
                    ))

                print(f"[SettingsManager] Returning {len(messages)} messages")
                return messages
        except Exception as e:
            print(f"[SettingsManager] ERROR getting chat history: {e}")
            import traceback
            traceback.print_exc()
            raise

    def delete_chat_history(self, session_id: str) -> bool:
        """Delete all chat history for a session"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            cursor.execute("""
                DELETE FROM chat_history
                WHERE session_id = ?
            """, (session_id,))

            deleted = cursor.rowcount > 0
            conn.commit()

        return deleted

    def delete_all_chat_history(self, user_id: str, tenant: str) -> bool:
        """Delete all chat history for a user/tenant"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            cursor.execute("""
                DELETE FROM chat_history
                WHERE user_id = ? AND tenant = ?
            """, (user_id, tenant))

            deleted = cursor.rowcount > 0
            conn.commit()

        return deleted

    # Execution Results Methods
    def save_execution_result(
        self,
        session_id: str,
        user_id: str,
        tenant: str,
        request_text: str,
        results_json: str
    ) -> bool:
        """Save execution results (structured tool outputs) to history"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            cursor.execute("""
                INSERT INTO execution_results (session_id, user_id, tenant, request_text, results_json)
                VALUES (?, ?, ?, ?, ?)
            """, (session_id, user_id, tenant, request_text, results_json))

            conn.commit()

        return True

    def get_recent_execution_results(
        self,
        session_id: str,
        limit: int = 5
    ) -> list[ExecutionResult]:
        """Get recent execution results for a session"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Get last N execution results
            cursor.execute("""
                SELECT id, session_id, user_id, tenant, request_text, results_json, created_at
                FROM execution_results
                WHERE session_id = ?
                ORDER BY created_at DESC
                LIMIT ?
            """, (session_id, limit))

            results = []
            rows = cursor.fetchall()

            # Reverse to get chronological order
            for row in reversed(rows):
                result_id, session_id, user_id, tenant, request_text, results_json, created_at = row
                results.append(ExecutionResult(
                    id=result_id,
                    session_id=session_id,
                    user_id=user_id,
                    tenant=tenant,
                    request_text=request_text,
                    results_json=results_json,
                    created_at=created_at
                ))

            return results

    def delete_execution_results(self, session_id: str) -> bool:
        """Delete all execution results for a session"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            cursor.execute("""
                DELETE FROM execution_results
                WHERE session_id = ?
            """, (session_id,))

            deleted = cursor.rowcount > 0
            conn.commit()

        return deleted

    # Session Management Methods
    def create_session(
        self,
        session_id: str,
        user_id: str,
        tenant: str,
        title: Optional[str] = None
    ) -> bool:
        """Create a new chat session"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            cursor.execute("""
                INSERT OR IGNORE INTO sessions (session_id, user_id, tenant, title)
                VALUES (?, ?, ?, ?)
            """, (session_id, user_id, tenant, title))

            conn.commit()

        return True

    def get_session(self, session_id: str) -> Optional[ChatSession]:
        """Get a specific session"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            cursor.execute("""
                SELECT session_id, user_id, tenant, title, created_at, updated_at
                FROM sessions
                WHERE session_id = ?
            """, (session_id,))

            row = cursor.fetchone()

            if row:
                session_id, user_id, tenant, title, created_at, updated_at = row
                return ChatSession(
                    session_id=session_id,
                    user_id=user_id,
                    tenant=tenant,
                    title=title,
                    created_at=created_at,
                    updated_at=updated_at
                )

        return None

    def get_all_sessions(
        self,
        user_id: str,
        tenant: str,
        limit: Optional[int] = None
    ) -> list[ChatSession]:
        """Get all sessions for a user/tenant, ordered by most recent"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            if limit:
                cursor.execute("""
                    SELECT session_id, user_id, tenant, title, created_at, updated_at
                    FROM sessions
                    WHERE user_id = ? AND tenant = ?
                    ORDER BY updated_at DESC
                    LIMIT ?
                """, (user_id, tenant, limit))
            else:
                cursor.execute("""
                    SELECT session_id, user_id, tenant, title, created_at, updated_at
                    FROM sessions
                    WHERE user_id = ? AND tenant = ?
                    ORDER BY updated_at DESC
                """, (user_id, tenant))

            sessions = []
            for row in cursor.fetchall():
                session_id, user_id, tenant, title, created_at, updated_at = row
                sessions.append(ChatSession(
                    session_id=session_id,
                    user_id=user_id,
                    tenant=tenant,
                    title=title,
                    created_at=created_at,
                    updated_at=updated_at
                ))

            return sessions

    def update_session_title(
        self,
        session_id: str,
        title: str
    ) -> bool:
        """Update session title"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            cursor.execute("""
                UPDATE sessions
                SET title = ?, updated_at = CURRENT_TIMESTAMP
                WHERE session_id = ?
            """, (title, session_id))

            updated = cursor.rowcount > 0
            conn.commit()

        return updated

    def update_session_timestamp(self, session_id: str) -> bool:
        """Update session timestamp (when new message is added)"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            cursor.execute("""
                UPDATE sessions
                SET updated_at = CURRENT_TIMESTAMP
                WHERE session_id = ?
            """, (session_id,))

            conn.commit()

        return True

    def delete_session(self, session_id: str) -> bool:
        """Delete a session and all its related data"""
        print(f"[SettingsManager] Attempting to delete session - session_id={session_id}, db_path={self.db_path}")

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Delete chat history
            cursor.execute("""
                DELETE FROM chat_history
                WHERE session_id = ?
            """, (session_id,))
            chat_deleted = cursor.rowcount
            print(f"[SettingsManager] Deleted {chat_deleted} chat messages")

            # Delete execution results
            cursor.execute("""
                DELETE FROM execution_results
                WHERE session_id = ?
            """, (session_id,))
            results_deleted = cursor.rowcount
            print(f"[SettingsManager] Deleted {results_deleted} execution results")

            # Delete session
            cursor.execute("""
                DELETE FROM sessions
                WHERE session_id = ?
            """, (session_id,))
            session_deleted = cursor.rowcount
            print(f"[SettingsManager] Deleted {session_deleted} session records")

            deleted = session_deleted > 0
            conn.commit()

        print(f"[SettingsManager] Delete operation result: {deleted}")
        return deleted
