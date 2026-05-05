"""Cliente de Netlify para auto-publicar landings.

Estrategia: usar el endpoint "deploy by file digest" — sube el HTML como un
deploy single-file que Netlify hostea bajo el subdominio del site.

Por cada negocio creamos UN site nuevo (un subdominio único). Si ya existe
guardado en clients.json `netlify_site_id`, reutilizamos ese site para el
nuevo deploy (así si actualizas la landing, la URL pública no cambia).
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
import time
from typing import Optional

import requests

import config

logger = logging.getLogger(__name__)

API_BASE = "https://api.netlify.com/api/v1"
TIMEOUT = 30


class NetlifyError(Exception):
    """Error de Netlify (token inválido, cuota, red, etc.)."""


def _headers() -> dict:
    if not config.NETLIFY_API_TOKEN:
        raise NetlifyError("NETLIFY_API_TOKEN no está configurado en .env")
    return {
        "Authorization": f"Bearer {config.NETLIFY_API_TOKEN}",
        "Content-Type": "application/json",
    }


def _slugify(name: str, max_len: int = 40) -> str:
    s = (name or "site").lower().strip()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = re.sub(r"-+", "-", s).strip("-")
    if len(s) > max_len:
        s = s[:max_len].rstrip("-")
    return s or "site"


def _request(method: str, path: str, **kwargs) -> requests.Response:
    """Wrapper con retries y manejo de errores."""
    url = f"{API_BASE}{path}" if path.startswith("/") else path
    last_err: Exception | None = None
    for attempt in range(3):
        try:
            r = requests.request(method, url, timeout=TIMEOUT, **kwargs)
            if r.status_code == 429:
                wait = int(r.headers.get("Retry-After", "5"))
                logger.warning("Rate limit Netlify, esperando %ds", wait)
                time.sleep(wait)
                continue
            return r
        except requests.RequestException as e:
            last_err = e
            logger.warning("Netlify request falló (intento %d): %s", attempt + 1, e)
            time.sleep(2 ** attempt)
    raise NetlifyError(f"Falló request a Netlify: {last_err}")


def _create_site(name_base: str) -> dict:
    """Crea un site nuevo. Si el nombre choca, agrega sufijo."""
    base = _slugify(name_base)
    candidates = [base, f"{base}-raio", f"{base}-{int(time.time()) % 100000}"]
    last_err = None
    for candidate in candidates:
        try:
            r = _request(
                "POST", "/sites",
                headers=_headers(),
                json={"name": candidate},
            )
            if r.status_code == 200 or r.status_code == 201:
                site = r.json()
                logger.info("Site creado: %s (id=%s)", site.get("ssl_url") or site.get("url"), site.get("id"))
                return site
            elif r.status_code == 422:
                # nombre ocupado
                logger.info("Nombre %r ocupado, probando otro", candidate)
                last_err = f"422 — nombre ocupado: {candidate}"
                continue
            else:
                last_err = f"{r.status_code} — {r.text[:200]}"
                logger.warning("Falló crear site: %s", last_err)
        except NetlifyError as e:
            last_err = str(e)
            continue
    raise NetlifyError(f"No pude crear site después de 3 intentos: {last_err}")


def _deploy_html(site_id: str, html: str) -> dict:
    """Despliega un HTML como single-file site bajo el path /index.html.

    Usa el endpoint /sites/{id}/deploys con el atomic file digest API:
    1) POST con el manifest {files: {"/index.html": <sha1>}}
    2) PUT del contenido del archivo a la URL que devuelve Netlify
    """
    digest = hashlib.sha1(html.encode("utf-8")).hexdigest()
    manifest = {"files": {"/index.html": digest}}

    r = _request(
        "POST", f"/sites/{site_id}/deploys",
        headers=_headers(),
        json=manifest,
    )
    if r.status_code not in (200, 201):
        raise NetlifyError(f"Crear deploy falló: {r.status_code} — {r.text[:300]}")

    deploy = r.json()
    deploy_id = deploy.get("id")
    required = deploy.get("required") or []

    if digest in required:
        # Subir el HTML
        put_url = f"{API_BASE}/deploys/{deploy_id}/files/index.html"
        put_headers = {
            "Authorization": f"Bearer {config.NETLIFY_API_TOKEN}",
            "Content-Type": "application/octet-stream",
        }
        put = _request("PUT", put_url, headers=put_headers, data=html.encode("utf-8"))
        if put.status_code not in (200, 201):
            raise NetlifyError(f"Subir HTML falló: {put.status_code} — {put.text[:300]}")

    # Refrescar deploy state
    for _ in range(15):
        chk = _request("GET", f"/deploys/{deploy_id}", headers=_headers())
        if chk.status_code != 200:
            break
        d = chk.json()
        if d.get("state") == "ready":
            return d
        if d.get("state") == "error":
            raise NetlifyError(f"Deploy quedó en error: {d.get('error_message')}")
        time.sleep(1)

    return deploy


def publish_html(html: str, business_name: str, site_id: Optional[str] = None) -> dict:
    """Publica un HTML como landing en Netlify.

    Args:
        html: contenido HTML completo
        business_name: nombre del negocio (para el subdominio)
        site_id: si ya tienes uno (reutilizar), pásalo. Si es None, se crea nuevo.

    Returns:
        {
          "url": "https://...",       # URL pública lista para WhatsApp
          "site_id": "...",            # para guardarlo en clients.json
          "deploy_id": "...",
          "ssl_url": "...",
          "admin_url": "..."           # https://app.netlify.com/sites/{name}
        }
    """
    if not config.NETLIFY_API_TOKEN:
        raise NetlifyError("NETLIFY_API_TOKEN no configurado en .env")

    if not html or not html.strip():
        raise NetlifyError("HTML vacío")

    if site_id:
        # Verificar que el site existe
        chk = _request("GET", f"/sites/{site_id}", headers=_headers())
        if chk.status_code != 200:
            logger.warning("Site %s no existe, creando uno nuevo", site_id)
            site = _create_site(business_name)
        else:
            site = chk.json()
    else:
        site = _create_site(business_name)

    deploy = _deploy_html(site["id"], html)

    public_url = site.get("ssl_url") or site.get("url") or deploy.get("ssl_url") or deploy.get("url")
    return {
        "url": public_url,
        "site_id": site["id"],
        "deploy_id": deploy.get("id"),
        "ssl_url": site.get("ssl_url"),
        "admin_url": site.get("admin_url"),
        "site_name": site.get("name"),
    }


def url_is_alive(url: str) -> bool:
    """HEAD a la URL para validar que responde 200."""
    if not url:
        return False
    try:
        r = requests.head(url, timeout=10, allow_redirects=True)
        return 200 <= r.status_code < 400
    except Exception as e:
        logger.warning("HEAD %s falló: %s", url, e)
        return False


def delete_site(site_id: str) -> bool:
    """Elimina un site (limpieza)."""
    if not site_id or not config.NETLIFY_API_TOKEN:
        return False
    try:
        r = _request("DELETE", f"/sites/{site_id}", headers=_headers())
        return r.status_code in (200, 204)
    except NetlifyError as e:
        logger.warning("No pude borrar site %s: %s", site_id, e)
        return False
