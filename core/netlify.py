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


_MAX_RETRY_WAIT_S = 60  # nunca dormir más de 60s entre reintentos


def _parse_retry_after(value: str | None, default: int = 5) -> int:
    """Parsea Retry-After de manera robusta.

    El estándar HTTP (RFC 7231) define dos formatos:
      - Delta-seconds:  "120"
      - HTTP-date:      "Wed, 21 Oct 2026 07:28:00 GMT"

    Pero algunos servidores mandan otra cosa (ej. timestamp Unix absoluto)
    y pueden tirar valores absurdos. Esta función:
      1. Si es int "razonable" (≤300) → úsalo directo.
      2. Si es int grande pero parece timestamp Unix futuro próximo →
         calcula delta = ts - now y capa a _MAX_RETRY_WAIT_S.
      3. Si parece HTTP-date → parsea y capa a _MAX_RETRY_WAIT_S.
      4. Cualquier otra cosa → default 5s.

    Siempre retorna como máximo _MAX_RETRY_WAIT_S — si Netlify legítimamente
    nos pide esperar más, mejor abortar la operación que bloquear el thread.
    """
    if not value:
        return default
    s = value.strip()

    # Intento 1: int (delta-seconds o timestamp absoluto)
    try:
        n = int(s)
        if n <= 0:
            return default
        if n <= _MAX_RETRY_WAIT_S:
            return n
        # Valores muy grandes — quizá timestamp Unix
        now = int(time.time())
        if n > now and (n - now) < 86400:
            delta = n - now
            capped = min(delta, _MAX_RETRY_WAIT_S)
            logger.warning(
                "Retry-After parece timestamp absoluto (%s) → delta=%ds, capando a %ds",
                s, delta, capped,
            )
            return capped
        # Demasiado grande para tener sentido → asumimos basura
        logger.warning(
            "Retry-After absurdo (%s, %ds), capando a %ds", s, n, _MAX_RETRY_WAIT_S,
        )
        return _MAX_RETRY_WAIT_S
    except ValueError:
        pass

    # Intento 2: HTTP-date
    try:
        from email.utils import parsedate_to_datetime
        dt = parsedate_to_datetime(s)
        delta = int(dt.timestamp() - time.time())
        return max(default, min(delta, _MAX_RETRY_WAIT_S))
    except Exception:
        pass

    return default


def _request(method: str, path: str, **kwargs) -> requests.Response:
    """Wrapper con retries y manejo de errores."""
    url = f"{API_BASE}{path}" if path.startswith("/") else path
    last_err: Exception | None = None
    for attempt in range(3):
        try:
            r = requests.request(method, url, timeout=TIMEOUT, **kwargs)
            if r.status_code == 429:
                wait = _parse_retry_after(r.headers.get("Retry-After"))
                logger.warning(
                    "Rate limit Netlify (429), esperando %ds (intento %d/3)",
                    wait, attempt + 1,
                )
                time.sleep(wait)
                continue
            return r
        except requests.RequestException as e:
            last_err = e
            logger.warning("Netlify request falló (intento %d): %s", attempt + 1, e)
            time.sleep(min(2 ** attempt, _MAX_RETRY_WAIT_S))
    raise NetlifyError(
        f"Falló request a Netlify tras 3 intentos: {last_err or 'rate limit persistente'}"
    )


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


# ============================================================
# Tracking de credits (sistema unificado de Netlify, 2024+)
# ============================================================
# Plan Free: 300 credits/mes · Production deploy = 15 credits.
# → ~20 deploys/mes free. Para no quemar credits sin querer:
#   1. Hash-check antes de re-deployar (skip si HTML idéntico).
#   2. Contador mensual persistido en app_kv para mostrar en la UI.
CREDITS_PER_DEPLOY = 15
CREDITS_FREE_MONTHLY = 300


def _hash_html(html: str) -> str:
    import hashlib
    return hashlib.md5(html.encode("utf-8")).hexdigest()


def _month_key() -> str:
    from datetime import date
    return f"netlify_deploys:{date.today().strftime('%Y-%m')}"


def deploys_this_month() -> int:
    """Cuántos deploys hicimos este mes (incrementado dentro de publish_html)."""
    try:
        from core import app_kv
        return int(app_kv.get(_month_key(), 0) or 0)
    except Exception:
        return 0


def credits_used_this_month() -> int:
    return deploys_this_month() * CREDITS_PER_DEPLOY


def credits_remaining_this_month() -> int:
    return max(0, CREDITS_FREE_MONTHLY - credits_used_this_month())


def publish_html(
    html: str,
    business_name: str,
    site_id: Optional[str] = None,
    force: bool = False,
) -> dict:
    """Publica un HTML como landing en Netlify.

    Optimizaciones contra el sistema de credits (2024+):
    - **Hash-check**: si el `site_id` dado ya tiene un deploy con el mismo
      HTML (cacheado en app_kv), se devuelve la URL existente sin gastar
      credits. Pasar `force=True` salta esta verificación.
    - Tras un deploy real, se incrementa el contador mensual en app_kv
      para que la UI pueda mostrar credits consumidos.

    Args:
        html: contenido HTML completo
        business_name: nombre del negocio (para el subdominio)
        site_id: si ya tienes uno (reutilizar), pásalo. Si es None, se crea nuevo.
        force: si True, ignora el hash-check y siempre re-deployea.

    Returns:
        {
          "url": "https://...",       # URL pública lista para WhatsApp
          "site_id": "...",
          "deploy_id": "...",          # None si fue skip por hash
          "ssl_url": "...",
          "admin_url": "...",
          "site_name": "...",
          "skipped": bool,             # True si fue skip por hash idéntico
        }
    """
    if not config.NETLIFY_API_TOKEN:
        raise NetlifyError("NETLIFY_API_TOKEN no configurado en .env")

    if not html or not html.strip():
        raise NetlifyError("HTML vacío")

    html_hash = _hash_html(html)

    # Hash-check: si re-deploy con HTML idéntico, skip (ahorra 15 credits)
    if site_id and not force:
        try:
            from core import app_kv
            cached = app_kv.get(f"netlify_hash:{site_id}", default=None)
            if isinstance(cached, dict):
                if cached.get("hash") == html_hash and cached.get("url"):
                    logger.info(
                        "Hash-check: HTML idéntico al último deploy del site %s "
                        "→ skip, ahorrando %d credits.",
                        site_id, CREDITS_PER_DEPLOY,
                    )
                    return {
                        "url": cached["url"],
                        "site_id": site_id,
                        "deploy_id": None,
                        "ssl_url": cached.get("ssl_url"),
                        "admin_url": cached.get("admin_url"),
                        "site_name": cached.get("site_name"),
                        "skipped": True,
                    }
        except Exception as e:
            logger.debug("Hash-check falló (sigo deployando): %s", e)

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
    result = {
        "url": public_url,
        "site_id": site["id"],
        "deploy_id": deploy.get("id"),
        "ssl_url": site.get("ssl_url"),
        "admin_url": site.get("admin_url"),
        "site_name": site.get("name"),
        "skipped": False,
    }

    # Cachear hash + URL para próximo hash-check, e incrementar contador mensual
    try:
        from core import app_kv
        app_kv.set(
            f"netlify_hash:{site['id']}",
            {
                "hash": html_hash,
                "url": public_url,
                "ssl_url": site.get("ssl_url"),
                "admin_url": site.get("admin_url"),
                "site_name": site.get("name"),
            },
        )
        app_kv.increment(_month_key(), delta=1)
    except Exception as e:
        logger.debug("No pude actualizar tracking de credits: %s", e)

    return result


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
