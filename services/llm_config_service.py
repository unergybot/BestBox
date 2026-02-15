"""LLM configuration service with encrypted API key storage."""

import json
import logging
import os
from typing import Any, Dict, List, Optional

from cryptography.fernet import Fernet

logger = logging.getLogger(__name__)


class LLMConfigService:
    """Manage LLM provider configurations with encryption and env overrides."""

    def __init__(self, db_connection: Any = None, encryption_key: Optional[str] = None):
        self.db = db_connection
        key = encryption_key or os.getenv("ENCRYPTION_KEY")
        if not key:
            key = Fernet.generate_key().decode()
            logger.warning("ENCRYPTION_KEY not set; using temporary key")
        self.fernet = Fernet(key.encode())

    def _encrypt_key(self, api_key: str) -> str:
        return self.fernet.encrypt(api_key.encode()).decode()

    def _decrypt_key(self, encrypted_key: str) -> str:
        return self.fernet.decrypt(encrypted_key.encode()).decode()

    def get_active_config(self) -> Dict[str, Any]:
        """Return active config with decrypted API key and env overrides."""
        try:
            config = self._get_db_config()

            encrypted = config.get("api_key_encrypted")
            if encrypted:
                config["api_key"] = self._decrypt_key(encrypted)
            config.pop("api_key_encrypted", None)

            return self._apply_env_overrides(config)
        except Exception as exc:
            logger.error("Database unavailable, falling back to env vars: %s", exc)
            return self._get_config_from_env()

    def save_config(
        self,
        provider: str,
        model: str,
        api_key: Optional[str],
        base_url: str,
        parameters: Dict[str, Any],
        user: str,
    ) -> int:
        """Save a new active config, deactivating previous active config."""
        encrypted_key = self._encrypt_key(api_key) if api_key else None

        if self.db is not None:
            return self._save_with_adapter(
                provider=provider,
                model=model,
                encrypted_key=encrypted_key,
                base_url=base_url,
                parameters=parameters,
                user=user,
            )

        import psycopg2
        from psycopg2.extras import RealDictCursor

        connection = psycopg2.connect(
            host=os.getenv("POSTGRES_HOST", "localhost"),
            port=int(os.getenv("POSTGRES_PORT", "5432")),
            user=os.getenv("POSTGRES_USER", "bestbox"),
            password=os.getenv("POSTGRES_PASSWORD", "bestbox"),
            dbname=os.getenv("POSTGRES_DB", "bestbox"),
        )

        try:
            with connection:
                with connection.cursor(cursor_factory=RealDictCursor) as cursor:
                    cursor.execute(
                        "UPDATE llm_configurations SET is_active = false, updated_at = NOW(), updated_by = %s",
                        (user,),
                    )

                    cursor.execute(
                        """
                        INSERT INTO llm_configurations
                            (provider, is_active, base_url, api_key_encrypted, model, parameters, created_by, updated_by)
                        VALUES
                            (%s, true, %s, %s, %s, %s::jsonb, %s, %s)
                        RETURNING id
                        """,
                        (
                            provider,
                            base_url,
                            encrypted_key,
                            model,
                            json.dumps(parameters),
                            user,
                            user,
                        ),
                    )
                    row = cursor.fetchone() or {}

            config_id = int(row.get("id", 0))
            logger.info("LLM config saved by %s: %s/%s (id=%s)", user, provider, model, config_id)
            return config_id
        except Exception:
            logger.exception("Failed to save LLM config")
            raise
        finally:
            connection.close()

    def get_provider_models(self, provider: str) -> List[Dict[str, Any]]:
        """Return provider model options from database."""
        if self.db is not None:
            rows = self.db.query(
                """
                SELECT model_id, display_name, description, is_recommended
                FROM llm_provider_models
                WHERE provider = %s
                ORDER BY sort_order ASC
                """,
                (provider,),
            )
            if isinstance(rows, list):
                return rows
            return [rows] if rows else []

        import psycopg2
        from psycopg2.extras import RealDictCursor

        connection = psycopg2.connect(
            host=os.getenv("POSTGRES_HOST", "localhost"),
            port=int(os.getenv("POSTGRES_PORT", "5432")),
            user=os.getenv("POSTGRES_USER", "bestbox"),
            password=os.getenv("POSTGRES_PASSWORD", "bestbox"),
            dbname=os.getenv("POSTGRES_DB", "bestbox"),
        )

        try:
            with connection.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(
                    """
                    SELECT model_id, display_name, description, is_recommended
                    FROM llm_provider_models
                    WHERE provider = %s
                    ORDER BY sort_order ASC
                    """,
                    (provider,),
                )
                return [dict(row) for row in cursor.fetchall()]
        finally:
            connection.close()

    def _save_with_adapter(
        self,
        provider: str,
        model: str,
        encrypted_key: Optional[str],
        base_url: str,
        parameters: Dict[str, Any],
        user: str,
    ) -> int:
        try:
            self.db.execute(
                "UPDATE llm_configurations SET is_active = false, updated_at = NOW(), updated_by = %s",
                (user,),
            )
            result = self.db.query(
                """
                INSERT INTO llm_configurations
                    (provider, is_active, base_url, api_key_encrypted, model, parameters, created_by, updated_by)
                VALUES
                    (%s, true, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (provider, base_url, encrypted_key, model, json.dumps(parameters), user, user),
            )
            if hasattr(self.db, "commit"):
                self.db.commit()
            if isinstance(result, dict):
                return int(result.get("id", 0))
            if isinstance(result, list) and result:
                return int(result[0].get("id", 0))
            return 0
        except Exception:
            if hasattr(self.db, "rollback"):
                self.db.rollback()
            raise

    def _get_db_config(self) -> Dict[str, Any]:
        if self.db is not None:
            config = self.db.query(
                "SELECT * FROM llm_configurations WHERE is_active = true ORDER BY updated_at DESC LIMIT 1"
            )
            if config:
                return dict(config)
            return self._get_config_from_env()

        import psycopg2
        from psycopg2.extras import RealDictCursor

        connection = psycopg2.connect(
            host=os.getenv("POSTGRES_HOST", "localhost"),
            port=int(os.getenv("POSTGRES_PORT", "5432")),
            user=os.getenv("POSTGRES_USER", "bestbox"),
            password=os.getenv("POSTGRES_PASSWORD", "bestbox"),
            dbname=os.getenv("POSTGRES_DB", "bestbox"),
        )

        try:
            with connection:
                with connection.cursor(cursor_factory=RealDictCursor) as cursor:
                    cursor.execute(
                        """
                        SELECT provider, base_url, api_key_encrypted, model, parameters
                        FROM llm_configurations
                        WHERE is_active = true
                        ORDER BY updated_at DESC, id DESC
                        LIMIT 1
                        """
                    )
                    row = cursor.fetchone()
                    if not row:
                        cursor.execute(
                            """
                            INSERT INTO llm_configurations
                                (provider, is_active, base_url, model, created_by, updated_by)
                            VALUES
                                ('local_vllm', true, 'http://localhost:8001/v1', 'qwen3-30b', 'system', 'system')
                            RETURNING provider, base_url, api_key_encrypted, model, parameters
                            """
                        )
                        row = cursor.fetchone()

                    config = dict(row)
                    if isinstance(config.get("parameters"), str):
                        config["parameters"] = json.loads(config["parameters"])
                    return config
        finally:
            connection.close()

    def _apply_env_overrides(self, config: Dict[str, Any]) -> Dict[str, Any]:
        provider = config.get("provider", "local_vllm")

        if provider == "nvidia" and os.getenv("NVIDIA_API_KEY"):
            config["api_key"] = os.getenv("NVIDIA_API_KEY")
        elif provider == "openrouter" and os.getenv("OPENROUTER_API_KEY"):
            config["api_key"] = os.getenv("OPENROUTER_API_KEY")

        if os.getenv("LLM_BASE_URL"):
            config["base_url"] = os.getenv("LLM_BASE_URL")
        if os.getenv("LLM_MODEL"):
            config["model"] = os.getenv("LLM_MODEL")

        if "parameters" not in config or not isinstance(config["parameters"], dict):
            config["parameters"] = {
                "temperature": 0.7,
                "max_tokens": 4096,
                "streaming": True,
                "max_retries": 2,
            }

        return config

    def _get_config_from_env(self) -> Dict[str, Any]:
        return {
            "provider": "local_vllm",
            "base_url": os.getenv("LLM_BASE_URL", "http://localhost:8001/v1"),
            "model": os.getenv("LLM_MODEL", "qwen3-30b"),
            "api_key": None,
            "parameters": {
                "temperature": 0.7,
                "max_tokens": 4096,
                "streaming": True,
                "max_retries": 2,
            },
        }
