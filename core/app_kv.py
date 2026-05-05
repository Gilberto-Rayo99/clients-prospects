"""Almacén key-value para estado pequeño que debe sobrevivir reboots.

Casos de uso:
- Contador diario de uso de Gemini (evita pasarse del cupo gratuito).
- Cualquier estado que en Streamlit Cloud se perdería con el filesystem efímero.

Backend:
- Si `SUPABASE_URL` + `SUPABASE_SERVICE_KEY` están configurados → tabla `app_kv`.
- Si no → archivo JSON local en `outputs/.app_kv.json` (efímero en Cloud).

Schema esperado (idempotente, lo crea automáticamente al primer write si no existe):
    CREATE TABLE app_kv (
      key        TEXT PRIMARY KEY,
      value      JSONB NOT NULL,
      updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
    );
    ALTER TABLE app_kv ENABLE ROW LEVEL SECURITY;
"""
from __future__ import annotations

import json
import logging
import threading
from pathlib import Path
from typing import Any, Optional

import config

logger = logging.getLogger(__name__)


_LOCAL_FILE = config.OUTPUTS_DIR / ".app_kv.json"
_LOCK = threading.Lock()


# ============================================================
# Cliente Supabase (lazy, mismo patrón que clients_store)
# ============================================================
_supa = None
_supa_init_attempted = False


def _client():
    global _supa, _supa_init_attempted
    if _supa_init_attempted:
        return _supa
    _supa_init_attempted = True
    if config.SUPABASE_URL and config.SUPABASE_SERVICE_KEY:
        try:
            from supabase import create_client
            _supa = create_client(config.SUPABASE_URL, config.SUPABASE_SERVICE_KEY)
        except Exception as e:
            logger.warning("app_kv: Supabase no disponible, fallback JSON local: %s", e)
    return _supa


def _use_supabase() -> bool:
    return _client() is not None


# ============================================================
# Backend JSON local
# ============================================================
def _json_read() -> dict:
    if not _LOCAL_FILE.exists():
        return {}
    try:
        return json.loads(_LOCAL_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _json_write(data: dict) -> None:
    try:
        _LOCAL_FILE.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception as e:
        logger.warning("app_kv: no pude escribir JSON local: %s", e)


# ============================================================
# API pública
# ============================================================
def get(key: str, default: Any = None) -> Any:
    """Lee un valor. Si no existe, devuelve `default`."""
    if _use_supabase():
        try:
            res = _client().table("app_kv").select("value").eq("key", key).execute()
            if res.data:
                return res.data[0]["value"]
            return default
        except Exception as e:
            # La primera llamada puede fallar si la tabla no existe; logueamos
            # con nivel info y caemos a JSON para no romper.
            logger.info("app_kv.get fallback JSON (key=%s): %s", key, e)

    with _LOCK:
        return _json_read().get(key, default)


def set(key: str, value: Any) -> None:
    """Guarda (upsert) un valor."""
    if _use_supabase():
        try:
            _client().table("app_kv").upsert(
                {"key": key, "value": value},
                on_conflict="key",
            ).execute()
            return
        except Exception as e:
            logger.info("app_kv.set fallback JSON (key=%s): %s", key, e)

    with _LOCK:
        data = _json_read()
        data[key] = value
        _json_write(data)


def increment(key: str, delta: int = 1, default: int = 0) -> int:
    """Incrementa atómicamente un contador entero. Retorna el valor nuevo.

    Implementación:
    - Supabase: read-modify-write con un mini lock local. No es transaccional
      a través de instancias del proceso, pero sí entre threads del mismo
      proceso (Streamlit corre como un solo proceso por sesión).
    - JSON: lock local.

    Para uso real concurrente entre instancias, mejor pasar a un Postgres
    function `INSERT ... ON CONFLICT ... DO UPDATE SET value = value + delta`.
    """
    with _LOCK:
        cur = get(key, default) or default
        new_val = int(cur) + int(delta)
        set(key, new_val)
        return new_val


def decrement(key: str, delta: int = 1, default: int = 0) -> int:
    return increment(key, -delta, default)
