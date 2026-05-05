"""Almacén de clientes.

Usa Supabase como backend principal cuando SUPABASE_URL y SUPABASE_SERVICE_KEY
están configurados. Si no, cae automáticamente a JSON local (outputs/clients.json).
La API pública es idéntica en ambos modos.
"""
from __future__ import annotations

import json
import logging
import re
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional

import config

logger = logging.getLogger(__name__)

CLIENTS_FILE = config.OUTPUTS_DIR / "clients.json"
_LOCK = threading.Lock()

CLIENT_STATUSES = config.PIPELINE_STAGE_NAMES

# ============================================================
# Cliente Supabase (singleton, lazy)
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
            logger.info("Supabase conectado: %s", config.SUPABASE_URL)
        except Exception as e:
            logger.warning("No pude conectar a Supabase, usando JSON local: %s", e)
    return _supa


def _use_supabase() -> bool:
    return _client() is not None


# ============================================================
# Helpers comunes
# ============================================================
def _slugify(name: str) -> str:
    s = (name or "cliente").lower().strip()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = re.sub(r"-+", "-", s).strip("-")
    return s or "cliente"


def _make_client_id(business: dict) -> str:
    pid = business.get("place_id")
    if pid:
        return f"{_slugify(business.get('name', ''))}__{pid}"
    return _slugify(business.get("name", "")) + "__" + datetime.now().strftime("%Y%m%d%H%M%S")


def _build_client_record(business: dict) -> dict:
    now = datetime.now().isoformat(timespec="seconds")
    return {
        "id": _make_client_id(business),
        "fecha_guardado": now,
        "fecha_modificado": now,
        "name": business.get("name", ""),
        "category": business.get("category", ""),
        "address": business.get("address", ""),
        "phone": business.get("phone"),
        "email": business.get("email"),
        "website": business.get("website"),
        "rating": business.get("rating"),
        "reviews_count": business.get("reviews_count", 0),
        "place_id": business.get("place_id"),
        "lat": business.get("lat"),
        "lng": business.get("lng"),
        "maps_url": business.get("maps_url"),
        "social_links": business.get("social_links", {}),
        "score": business.get("score"),
        "contact_channel": business.get("contact_channel"),
        "contact_value": business.get("contact_value"),
        "landing_html": None,
        "landing_path": None,
        "netlify_url": None,
        "netlify_site_id": None,
        "netlify_deploy_at": None,
        "estado": "Pendiente",
        "notas": "",
        "fecha_proximo_contacto": None,
        "precio_cotizado": None,
        "pdf_path": None,
    }


# ============================================================
# Backend JSON (fallback local)
# ============================================================
def _json_read() -> dict:
    if not CLIENTS_FILE.exists():
        return {"clients": []}
    try:
        return json.loads(CLIENTS_FILE.read_text(encoding="utf-8"))
    except Exception as e:
        logger.exception("clients.json corrupto, devuelvo vacío: %s", e)
        return {"clients": []}


def _json_write(data: dict) -> None:
    CLIENTS_FILE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


# Columnas "ligeras": excluyen campos pesados como `landing_html` (50-200 KB
# por fila). Se usan en `list_all` por defecto para que la tabla cargue rápido
# y no consuma RAM. El HTML completo se baja bajo demanda con `get(id, include_html=True)`.
_LIGHT_COLUMNS = (
    "id,fecha_guardado,fecha_modificado,name,category,address,phone,email,"
    "website,rating,reviews_count,place_id,lat,lng,maps_url,social_links,"
    "score,contact_channel,contact_value,landing_path,netlify_url,"
    "netlify_site_id,netlify_deploy_at,estado,notas,fecha_proximo_contacto,"
    "precio_cotizado,pdf_path"
)


def _strip_html(records: list[dict]) -> list[dict]:
    """Elimina `landing_html` de cada registro (para el fallback JSON)."""
    return [{k: v for k, v in r.items() if k != "landing_html"} for r in records]


# ============================================================
# CRUD — API pública (misma interfaz para Supabase y JSON)
# ============================================================
def list_all(include_html: bool = False) -> list[dict]:
    """Lista todos los clientes.

    Por defecto NO incluye el campo `landing_html` (puede pesar cientos de KB
    por fila). Pasa `include_html=True` solo si realmente lo necesitas.
    """
    cols = "*" if include_html else _LIGHT_COLUMNS

    if _use_supabase():
        try:
            res = (
                _client().table("clients")
                .select(cols)
                .order("fecha_guardado", desc=True)
                .execute()
            )
            return res.data or []
        except Exception as e:
            logger.exception("Supabase list_all falló: %s", e)
            return []
    with _LOCK:
        records = list(_json_read().get("clients", []))
        return records if include_html else _strip_html(records)


def get(client_id: str, include_html: bool = True) -> Optional[dict]:
    """Trae un cliente específico. `include_html=True` por defecto porque
    cuando pides un cliente individual normalmente vas a verlo/editarlo."""
    cols = "*" if include_html else _LIGHT_COLUMNS

    if _use_supabase():
        try:
            res = _client().table("clients").select(cols).eq("id", client_id).execute()
            return res.data[0] if res.data else None
        except Exception as e:
            logger.exception("Supabase get falló: %s", e)
            return None
    for c in list_all(include_html=True):
        if c["id"] == client_id:
            return c if include_html else {k: v for k, v in c.items() if k != "landing_html"}
    return None


def exists_by_place_id(place_id: Optional[str]) -> bool:
    if not place_id:
        return False
    if _use_supabase():
        try:
            res = _client().table("clients").select("id").eq("place_id", place_id).execute()
            return bool(res.data)
        except Exception as e:
            logger.exception("Supabase exists_by_place_id falló: %s", e)
            return False
    return any(c.get("place_id") == place_id for c in list_all())


def save_from_business(business: dict) -> dict:
    """Crea y guarda un cliente desde un prospecto enriquecido. No duplica si ya existe."""
    pid = business.get("place_id")

    if _use_supabase():
        try:
            if pid:
                res = _client().table("clients").select("*").eq("place_id", pid).execute()
                if res.data:
                    logger.info("Cliente ya existía en Supabase: %s", res.data[0]["id"])
                    return res.data[0]
            record = _build_client_record(business)
            ins = _client().table("clients").insert(record).execute()
            logger.info("Cliente guardado en Supabase: %s", record["id"])
            return ins.data[0] if ins.data else record
        except Exception as e:
            logger.exception("Supabase save_from_business falló: %s", e)
            return {}

    with _LOCK:
        data = _json_read()
        if pid:
            for c in data["clients"]:
                if c.get("place_id") == pid:
                    logger.info("Cliente ya existía: %s", c["id"])
                    return c
        record = _build_client_record(business)
        data["clients"].append(record)
        _json_write(data)
        logger.info("Cliente guardado: %s", record["id"])
        return record


def update(client_id: str, **fields) -> Optional[dict]:
    """Actualiza campos del cliente. Devuelve el registro actualizado."""
    fields["fecha_modificado"] = datetime.now().isoformat(timespec="seconds")

    if _use_supabase():
        try:
            res = _client().table("clients").update(fields).eq("id", client_id).execute()
            logger.info("Cliente actualizado en Supabase: %s", client_id)
            return res.data[0] if res.data else None
        except Exception as e:
            logger.exception("Supabase update falló: %s", e)
            return None

    with _LOCK:
        data = _json_read()
        for c in data["clients"]:
            if c["id"] == client_id:
                c.update(fields)
                _json_write(data)
                logger.info("Cliente actualizado: %s", client_id)
                return c
    return None


def delete(client_id: str) -> bool:
    if _use_supabase():
        try:
            _client().table("clients").delete().eq("id", client_id).execute()
            logger.info("Cliente eliminado de Supabase: %s", client_id)
            return True
        except Exception as e:
            logger.exception("Supabase delete falló: %s", e)
            return False

    with _LOCK:
        data = _json_read()
        before = len(data["clients"])
        data["clients"] = [c for c in data["clients"] if c["id"] != client_id]
        if len(data["clients"]) != before:
            _json_write(data)
            logger.info("Cliente eliminado: %s", client_id)
            return True
    return False


def save_landing_html(client_id: str, html: str) -> Optional[dict]:
    """Guarda el HTML de la landing. En Supabase lo almacena en la columna.
    Localmente también escribe el archivo .html si es posible."""
    cli = get(client_id)
    if not cli:
        return None

    # `landing_path` se usa además como marcador "tiene landing" en listas
    # ligeras (donde no traemos el HTML). En Supabase usamos un marker lógico.
    if _use_supabase():
        landing_path = f"supabase://clients/{client_id}/landing.html"
    else:
        landing_path = None
        try:
            slug = _slugify(cli.get("name", "cliente"))
            path = config.LANDINGS_DIR / f"{slug}.html"
            path.write_text(html, encoding="utf-8")
            landing_path = str(path)
        except Exception as e:
            logger.warning("No pude escribir landing a disco: %s", e)

    # Avanzar estado automáticamente si todavía estaba en etapa pre-landing
    fields: dict = {"landing_html": html, "landing_path": landing_path}
    if cli.get("estado") in ("Pendiente", "Falta landing"):
        fields["estado"] = "Mensaje listo"

    return update(client_id, **fields)


# ============================================================
# Migración de datos JSON → Supabase (ejecutar una sola vez)
# ============================================================
def migrate_json_to_supabase() -> tuple[int, int]:
    """Importa todos los clientes del JSON local a Supabase.

    Devuelve (importados, ya_existían).
    Solo funciona si Supabase está configurado.
    """
    if not _use_supabase():
        raise RuntimeError("Supabase no está configurado.")
    if not CLIENTS_FILE.exists():
        return 0, 0

    local_clients = _json_read().get("clients", [])
    imported, skipped = 0, 0

    for c in local_clients:
        pid = c.get("place_id")
        if pid and exists_by_place_id(pid):
            skipped += 1
            continue
        try:
            _client().table("clients").insert(c).execute()
            imported += 1
        except Exception as e:
            logger.warning("No pude migrar %s: %s", c.get("id"), e)
            skipped += 1

    logger.info("Migración completada: %d importados, %d ya existían", imported, skipped)
    return imported, skipped
