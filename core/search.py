"""Búsqueda de negocios locales en Google Places (con fallback a mock)."""
from __future__ import annotations

import logging
import random
from typing import Optional
from urllib.parse import urlparse

import config

logger = logging.getLogger(__name__)


# ============================================================
# Heurística de "web real"
# ============================================================
def _is_real_website(url: Optional[str]) -> bool:
    """Devuelve True si la URL parece un sitio web real (no Facebook/Wix/etc)."""
    if not url:
        return False
    try:
        host = urlparse(url).netloc.lower().replace("www.", "")
    except Exception:
        return False
    if not host:
        return False
    return not any(host.endswith(d) for d in config.DOMAINS_NOT_REAL_WEB)


# ============================================================
# MOCK DATA — para desarrollar UI sin gastar API quota
# ============================================================
_MOCK_BUSINESSES: list[dict] = [
    {
        "name": "Tacos El Compa",
        "address": "Av. Insurgentes Sur 1234, Del Valle, CDMX",
        "phone": "+52 55 1234 5678",
        "rating": 4.6,
        "reviews_count": 312,
        "website": None,
        "place_id": "mock_001",
        "lat": 19.3829, "lng": -99.1755,
        "maps_url": "https://maps.google.com/?cid=mock_001",
        "category": "Restaurantes",
    },
    {
        "name": "Estética Glamour",
        "address": "Calle Reforma 88, Roma Norte, CDMX",
        "phone": "+52 55 2233 4455",
        "rating": 4.2,
        "reviews_count": 47,
        "website": "https://www.facebook.com/esteticaglamour",
        "place_id": "mock_002",
        "lat": 19.4194, "lng": -99.1614,
        "maps_url": "https://maps.google.com/?cid=mock_002",
        "category": "Estéticas y barberías",
    },
    {
        "name": "Taller Mecánico Don Beto",
        "address": "Eje 8 Sur 450, Iztapalapa, CDMX",
        "phone": "+52 55 7788 9900",
        "rating": 4.8,
        "reviews_count": 156,
        "website": None,
        "place_id": "mock_003",
        "lat": 19.3573, "lng": -99.0867,
        "maps_url": "https://maps.google.com/?cid=mock_003",
        "category": "Talleres mecánicos",
    },
    {
        "name": "Café La Esquina",
        "address": "Av. Álvaro Obregón 23, Roma Norte, CDMX",
        "phone": "+52 55 5544 3322",
        "rating": 4.5,
        "reviews_count": 89,
        "website": "https://cafelaesquina.wixsite.com/inicio",
        "place_id": "mock_004",
        "lat": 19.4150, "lng": -99.1680,
        "maps_url": "https://maps.google.com/?cid=mock_004",
        "category": "Cafeterías",
    },
    {
        "name": "Abarrotes Doña Mary",
        "address": "Calle 5 de Mayo 12, Coyoacán, CDMX",
        "phone": "+52 55 1010 2020",
        "rating": 4.4,
        "reviews_count": 28,
        "website": None,
        "place_id": "mock_005",
        "lat": 19.3499, "lng": -99.1620,
        "maps_url": "https://maps.google.com/?cid=mock_005",
        "category": "Tiendas de abarrotes",
    },
    {
        "name": "Dental Sonrisa Plus",
        "address": "Av. Universidad 800, Del Valle, CDMX",
        "phone": "+52 55 3030 4040",
        "rating": 4.9,
        "reviews_count": 421,
        "website": "https://dentalsonrisa.com",
        "place_id": "mock_006",
        "lat": 19.3760, "lng": -99.1730,
        "maps_url": "https://maps.google.com/?cid=mock_006",
        "category": "Consultorios dentales",
    },
    {
        "name": "Gimnasio FuerzaMax",
        "address": "Av. Cuauhtémoc 510, Narvarte, CDMX",
        "phone": "+52 55 5050 6060",
        "rating": 4.1,
        "reviews_count": 73,
        "website": None,
        "place_id": "mock_007",
        "lat": 19.3920, "lng": -99.1530,
        "maps_url": "https://maps.google.com/?cid=mock_007",
        "category": "Gimnasios",
    },
    {
        "name": "Veterinaria Patitas Felices",
        "address": "Calle Madero 145, Centro, CDMX",
        "phone": "+52 55 7070 8080",
        "rating": 4.7,
        "reviews_count": 198,
        "website": "https://patitasfelices.blogspot.com",
        "place_id": "mock_008",
        "lat": 19.4339, "lng": -99.1390,
        "maps_url": "https://maps.google.com/?cid=mock_008",
        "category": "Veterinarias",
    },
    {
        "name": "Lavandería Express",
        "address": "Av. División del Norte 2200, Portales, CDMX",
        "phone": "+52 55 9090 1010",
        "rating": 3.9,
        "reviews_count": 14,
        "website": None,
        "place_id": "mock_009",
        "lat": 19.3650, "lng": -99.1480,
        "maps_url": "https://maps.google.com/?cid=mock_009",
        "category": "Lavanderías",
    },
    {
        "name": "Florería Margaritas",
        "address": "Calle Amsterdam 50, Condesa, CDMX",
        "phone": "+52 55 2020 3030",
        "rating": 4.6,
        "reviews_count": 64,
        "website": None,
        "place_id": "mock_010",
        "lat": 19.4108, "lng": -99.1730,
        "maps_url": "https://maps.google.com/?cid=mock_010",
        "category": "Florerías",
    },
    {
        "name": "Panadería La Espiga de Oro",
        "address": "Calle Zaragoza 88, Tlalpan, CDMX",
        "phone": "+52 55 4040 5050",
        "rating": 4.8,
        "reviews_count": 245,
        "website": None,
        "place_id": "mock_011",
        "lat": 19.2925, "lng": -99.1680,
        "maps_url": "https://maps.google.com/?cid=mock_011",
        "category": "Panaderías",
    },
    {
        "name": "Barbería The Don",
        "address": "Av. Revolución 1500, San Ángel, CDMX",
        "phone": "+52 55 6060 7070",
        "rating": 4.3,
        "reviews_count": 52,
        "website": "https://www.instagram.com/barberiathedon",
        "place_id": "mock_012",
        "lat": 19.3465, "lng": -99.1900,
        "maps_url": "https://maps.google.com/?cid=mock_012",
        "category": "Estéticas y barberías",
    },
]


def _filter_mock(category: str, web_filter: str) -> list[dict]:
    """Filtra el mock por categoría y por estado de web."""
    results = list(_MOCK_BUSINESSES)
    if category and category != "Otros":
        results = [b for b in results if b["category"].lower() == category.lower()]

    if web_filter == "no_web":
        results = [b for b in results if not _is_real_website(b.get("website"))]
    elif web_filter == "outdated":
        # En mock marcamos como "desactualizada" a las que tienen Wix/Blogspot/redes
        results = [
            b for b in results
            if b.get("website") and not _is_real_website(b["website"])
        ]
    # "all" → no filtra

    return results


# ============================================================
# Google Places real (stub — listo cuando haya API key)
# ============================================================
def _search_google_places(zone: str, radius_km: int, category: str) -> list[dict]:
    """Llama a Google Places API. Solo si GOOGLE_PLACES_API_KEY está configurada."""
    import googlemaps

    client = googlemaps.Client(key=config.GOOGLE_PLACES_API_KEY)
    query = f"{category} en {zone}"
    logger.info("Google Places text_search: query=%r radius=%dkm", query, radius_km)

    try:
        resp = client.places(query=query, radius=radius_km * 1000)
    except Exception as e:
        logger.exception("Falló Google Places: %s", e)
        return []

    out: list[dict] = []
    for r in resp.get("results", []):
        place_id = r.get("place_id")
        # Pedir details para teléfono y website
        try:
            d = client.place(
                place_id=place_id,
                fields=[
                    "name", "formatted_address", "formatted_phone_number",
                    "international_phone_number", "rating", "user_ratings_total",
                    "website", "geometry", "url",
                ],
            ).get("result", {})
        except Exception:
            d = {}

        loc = d.get("geometry", {}).get("location", {}) or r.get("geometry", {}).get("location", {})
        out.append({
            "name": d.get("name") or r.get("name", ""),
            "address": d.get("formatted_address") or r.get("formatted_address", ""),
            "phone": d.get("international_phone_number") or d.get("formatted_phone_number"),
            "rating": d.get("rating") or r.get("rating"),
            "reviews_count": d.get("user_ratings_total") or r.get("user_ratings_total", 0),
            "website": d.get("website"),
            "place_id": place_id,
            "lat": loc.get("lat"),
            "lng": loc.get("lng"),
            "maps_url": d.get("url") or f"https://www.google.com/maps/place/?q=place_id:{place_id}",
            "category": category,
        })
    return out


# ============================================================
# Punto de entrada
# ============================================================
def search_businesses(
    zone: str,
    radius_km: int,
    category: str,
    web_filter: str = "no_web",
) -> list[dict]:
    """Busca negocios. Usa mock si USE_MOCK_DATA o si falta la API key.

    Args:
        zone: Zona o colonia (ej. "Coyoacán, CDMX").
        radius_km: Radio de búsqueda en km.
        category: Categoría del negocio.
        web_filter: 'no_web', 'outdated' o 'all'.
    """
    if config.USE_MOCK_DATA or not config.GOOGLE_PLACES_API_KEY:
        logger.info(
            "Modo MOCK activo (USE_MOCK_DATA=%s, has_key=%s)",
            config.USE_MOCK_DATA, bool(config.GOOGLE_PLACES_API_KEY),
        )
        results = _filter_mock(category, web_filter)
        # Pequeña aleatoriedad para que cada búsqueda no devuelva siempre lo mismo
        random.shuffle(results)
        return results

    real = _search_google_places(zone, radius_km, category)
    if web_filter == "no_web":
        real = [b for b in real if not _is_real_website(b.get("website"))]
    elif web_filter == "outdated":
        real = [b for b in real if b.get("website") and not _is_real_website(b["website"])]
    return real
