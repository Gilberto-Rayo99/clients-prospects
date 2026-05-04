"""Almacén JSON de clientes guardados.

Estructura del archivo `outputs/clients.json`:
{
  "clients": [
    { "id": "...", "fecha_guardado": "...", ... }
  ]
}

Cada cliente tiene id único derivado del place_id + slug.
"""
from __future__ import annotations

import json
import logging
import re
import threading
from datetime import datetime
from pathlib import Path

import config

logger = logging.getLogger(__name__)

CLIENTS_FILE = config.OUTPUTS_DIR / "clients.json"
_LOCK = threading.Lock()


CLIENT_STATUSES = config.PIPELINE_STAGE_NAMES


# ============================================================
# Persistencia
# ============================================================
def _read_raw() -> dict:
    if not CLIENTS_FILE.exists():
        return {"clients": []}
    try:
        return json.loads(CLIENTS_FILE.read_text(encoding="utf-8"))
    except Exception as e:
        logger.exception("clients.json corrupto, devuelvo vacío: %s", e)
        return {"clients": []}


def _write_raw(data: dict) -> None:
    CLIENTS_FILE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _slugify(name: str) -> str:
    s = (name or "cliente").lower().strip()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = re.sub(r"-+", "-", s).strip("-")
    return s or "cliente"


# ============================================================
# Modelo
# ============================================================
def _make_client_id(business: dict) -> str:
    """ID estable a partir del place_id (o slug del nombre si no hay)."""
    pid = business.get("place_id")
    if pid:
        return f"{_slugify(business.get('name', ''))}__{pid}"
    return _slugify(business.get("name", "")) + "__" + datetime.now().strftime("%Y%m%d%H%M%S")


def _build_client_record(business: dict) -> dict:
    """Convierte un prospecto enriquecido en registro de cliente guardado."""
    now = datetime.now().isoformat(timespec="seconds")
    return {
        "id": _make_client_id(business),
        "fecha_guardado": now,
        "fecha_modificado": now,
        # Datos del negocio
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
        # Calculados
        "score": business.get("score"),
        "contact_channel": business.get("contact_channel"),
        "contact_value": business.get("contact_value"),
        # Landing
        "landing_html": None,
        "landing_path": None,
        # Seguimiento (campos editables por el usuario)
        "estado": "Pendiente",
        "notas": "",
        "fecha_proximo_contacto": None,   # YYYY-MM-DD
        "precio_cotizado": None,           # número en MXN
        "pdf_path": None,
    }


# ============================================================
# CRUD
# ============================================================
def list_all() -> list[dict]:
    """Devuelve todos los clientes guardados."""
    with _LOCK:
        return list(_read_raw().get("clients", []))


def get(client_id: str) -> dict | None:
    """Busca un cliente por id."""
    for c in list_all():
        if c["id"] == client_id:
            return c
    return None


def exists_by_place_id(place_id: str | None) -> bool:
    """Verifica si ya existe un cliente con ese place_id."""
    if not place_id:
        return False
    return any(c.get("place_id") == place_id for c in list_all())


def save_from_business(business: dict) -> dict:
    """Crea y guarda un nuevo cliente desde un prospecto enriquecido.

    Si ya existía (mismo place_id), devuelve el existente sin duplicar.
    """
    pid = business.get("place_id")
    with _LOCK:
        data = _read_raw()
        if pid:
            for c in data["clients"]:
                if c.get("place_id") == pid:
                    logger.info("Cliente ya existía: %s", c["id"])
                    return c
        record = _build_client_record(business)
        data["clients"].append(record)
        _write_raw(data)
        logger.info("Cliente guardado: %s", record["id"])
        return record


def update(client_id: str, **fields) -> dict | None:
    """Actualiza campos del cliente. Devuelve el registro actualizado."""
    with _LOCK:
        data = _read_raw()
        for c in data["clients"]:
            if c["id"] == client_id:
                c.update(fields)
                c["fecha_modificado"] = datetime.now().isoformat(timespec="seconds")
                _write_raw(data)
                logger.info("Cliente actualizado: %s (campos: %s)", client_id, list(fields.keys()))
                return c
    return None


def delete(client_id: str) -> bool:
    """Elimina un cliente. Devuelve True si se eliminó."""
    with _LOCK:
        data = _read_raw()
        before = len(data["clients"])
        data["clients"] = [c for c in data["clients"] if c["id"] != client_id]
        if len(data["clients"]) != before:
            _write_raw(data)
            logger.info("Cliente eliminado: %s", client_id)
            return True
    return False


def save_landing_html(client_id: str, html: str) -> dict | None:
    """Guarda el HTML de la landing en archivo y referencia en el cliente."""
    cli = get(client_id)
    if not cli:
        return None
    slug = _slugify(cli.get("name", "cliente"))
    path = config.LANDINGS_DIR / f"{slug}.html"
    path.write_text(html, encoding="utf-8")
    return update(client_id, landing_html=html, landing_path=str(path))
