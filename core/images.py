"""Generación de imágenes para landings con Gemini 2.5 Flash Image (Nano Banana).

Plan gratuito: 100 imágenes/día por API key. Aquí guardamos un contador local
para no pasarnos del cupo, cacheamos por place_id para no regenerar lo mismo
y caemos a Unsplash Source si falla.
"""
from __future__ import annotations

import logging
import re
import threading
from datetime import date
from pathlib import Path
from typing import Optional

import config
from core import app_kv

logger = logging.getLogger(__name__)


IMG_ROOT = config.LANDINGS_DIR / "img"
IMG_ROOT.mkdir(parents=True, exist_ok=True)

# Lock para serializar el read-modify-write del contador cuando varios
# threads corren en paralelo (las llamadas Gemini son secuenciales por
# paquete pero los paquetes corren en paralelo).
_USAGE_LOCK = threading.Lock()


def _usage_key() -> str:
    """Key de app_kv para el contador del día. Formato `gemini_usage:YYYY-MM-DD`."""
    return f"gemini_usage:{date.today().isoformat()}"


# ============================================================
# Contador diario de cuota (persistido en app_kv → Supabase si está disponible,
# JSON local si no). Sobrevive reboots de Streamlit Cloud.
# ============================================================
def _get_used_today() -> int:
    return int(app_kv.get(_usage_key(), 0) or 0)


def remaining_today() -> int:
    return max(0, config.GEMINI_DAILY_BUDGET - _get_used_today())


def reserve(n: int) -> int:
    """Reserva atómicamente `n` imágenes del cupo diario.

    Devuelve cuántas pudo reservar (puede ser menos si el cupo no alcanza).
    Pensado para paralelo: el caller llama `reserve(8)` antes de lanzar el
    paquete; si devuelve menos de 8, parte del paquete caerá a Unsplash.
    Si después no consume todas las reservadas (cache hit o error) puede
    llamar `release` para devolverlas.
    """
    with _USAGE_LOCK:
        used = _get_used_today()
        avail = max(0, config.GEMINI_DAILY_BUDGET - used)
        granted = min(avail, max(0, n))
        if granted > 0:
            app_kv.set(_usage_key(), used + granted)
        return granted


def release(n: int) -> None:
    """Devuelve al cupo `n` imágenes reservadas que no se llegaron a usar."""
    if n <= 0:
        return
    with _USAGE_LOCK:
        used = _get_used_today()
        app_kv.set(_usage_key(), max(0, used - n))


# ============================================================
# Plan de imágenes por giro
# ============================================================
# Cada entrada: lista de tuplas (slot_name, prompt_template, width, height)
# slot_name → nombre del archivo final (sin extensión)
# El prompt se completa con datos del negocio (nombre, dirección, etc.)

# Prompt base: tono fotográfico realista, sin texto sobreimpreso, México
_PHOTO_BASE = (
    "Fotografía profesional, realista, iluminación natural cálida, "
    "ambiente mexicano auténtico, alta resolución editorial, sin texto, "
    "sin logos sobreimpresos, sin marca de agua. "
)

CATEGORY_IMAGE_PLANS: dict[str, list[tuple[str, str, int, int]]] = {
    "Restaurantes": [
        ("hero",      "Interior acogedor de un restaurante mexicano de barrio, mesas de madera con manteles, luz cálida del atardecer entrando por la ventana, plato emblemático en primer plano, ambiente lleno pero sin caos", 1600, 900),
        ("service-1", "Plato estrella mexicano servido sobre mesa rústica, vista cenital, decorado con cilantro y limón fresco, vapor visible", 800, 600),
        ("service-2", "Manos de cocinero preparando un platillo a la plancha en cocina abierta, con fuego visible y verduras frescas alrededor", 800, 600),
        ("service-3", "Mesero sirviendo bebidas frías a comensales sonriendo en el restaurante, ambiente familiar", 800, 600),
        ("service-4", "Variedad de salsas caseras en molcajetes pequeños sobre mesa de madera, enfoque selectivo", 800, 600),
        ("gallery-1", "Detalle macro de tortillas hechas a mano apiladas y humeantes sobre comal", 600, 400),
        ("gallery-2", "Familia mexicana comiendo y conversando alegremente en una mesa del restaurante", 600, 400),
        ("gallery-3", "Fachada del restaurante de noche con luces cálidas encendidas y mesas afuera", 600, 400),
    ],
    "Cafeterías": [
        ("hero",      "Interior moderno de una cafetería de especialidad con barra de madera, máquina de espresso reluciente, luz natural amplia, plantas y obras de arte en pared", 1600, 900),
        ("service-1", "Latte art profesional servido en taza blanca sobre platillo de madera, vista cenital, granos de café alrededor", 800, 600),
        ("service-2", "Barista preparando un café de filtro V60, vapor y goteo visibles, manos en acción", 800, 600),
        ("service-3", "Vitrina de pasteles y croissants recién horneados con etiquetas escritas a mano", 800, 600),
        ("service-4", "Persona joven trabajando en laptop en una mesa de la cafetería con un cappuccino al lado y luz natural", 800, 600),
        ("gallery-1", "Saco de granos de café verde abierto mostrando detalle, sobre madera oscura", 600, 400),
        ("gallery-2", "Detalle cenital de un cuaderno abierto, taza de café y croissant sobre mesa de mármol", 600, 400),
        ("gallery-3", "Fachada de la cafetería con plantas en la entrada y pizarrón con menú del día", 600, 400),
    ],
    "Estéticas y barberías": [
        ("hero",      "Interior moderno y minimalista de una barbería mexicana, sillón de barbero clásico de cuero, espejos con marco metálico, luz cálida focalizada", 1600, 900),
        ("service-1", "Barbero profesional terminando un fade preciso a un cliente joven, manos con tijera o máquina, enfoque selectivo", 800, 600),
        ("service-2", "Cliente recostado recibiendo afeitado clásico con navaja y toalla caliente, vapor visible", 800, 600),
        ("service-3", "Detalle macro de tijeras profesionales, navaja recta y peines sobre superficie de mármol", 800, 600),
        ("service-4", "Cliente sonriente mirándose al espejo después del corte, con capa de barbero todavía puesta", 800, 600),
        ("gallery-1", "Estantería con productos de aseo masculino: pomadas, ceras, aceites, etiquetas elegantes", 600, 400),
        ("gallery-2", "Vista de la barbería completa con tres clientes siendo atendidos al mismo tiempo", 600, 400),
        ("gallery-3", "Fachada urbana de la barbería con letrero retro encendido al atardecer", 600, 400),
    ],
    "Talleres mecánicos": [
        ("hero",      "Taller mecánico mexicano amplio y ordenado, dos autos sobre rampas hidráulicas, mecánicos uniformados trabajando, luz natural entrando por portones abiertos", 1600, 900),
        ("service-1", "Mecánico revisando el motor de un auto con linterna, primer plano de manos con guante y herramienta, ambiente real de taller", 800, 600),
        ("service-2", "Cambio de aceite en proceso, aceite nuevo siendo vertido, vista cenital con bandeja", 800, 600),
        ("service-3", "Computadora de diagnóstico automotriz conectada al puerto OBD del coche, pantalla con datos visibles", 800, 600),
        ("service-4", "Llantas nuevas alineadas listas para montar, balanceadora al fondo", 800, 600),
        ("gallery-1", "Caja de herramientas profesional abierta mostrando llaves organizadas, detalle macro", 600, 400),
        ("gallery-2", "Mecánico explicando con calma a un cliente lo que detectó, ambos junto al cofre abierto", 600, 400),
        ("gallery-3", "Fachada del taller mexicano con letrero, autos estacionados afuera, banderitas", 600, 400),
    ],
    "Tiendas de abarrotes": [
        ("hero",      "Interior de una tienda de abarrotes mexicana de barrio, estantes llenos de productos coloridos, dueña sonriendo detrás del mostrador, luz cálida", 1600, 900),
        ("service-1", "Sección de frutas y verduras frescas mexicanas en cajas de madera, naranjas, jitomates, chiles, aguacates", 800, 600),
        ("service-2", "Mostrador con báscula clásica pesando producto, manos de la dueña atendiendo a un cliente", 800, 600),
        ("service-3", "Refrigerador con lácteos, jugos y refrescos mexicanos típicos visibles", 800, 600),
        ("service-4", "Estante de despensa con frijoles, arroz, harinas y especias en bolsas y frascos", 800, 600),
        ("gallery-1", "Cliente regular conversando con la dueña mientras paga, ambiente vecinal", 600, 400),
        ("gallery-2", "Bolsa reutilizable llena de productos sobre el mostrador, ticket arriba", 600, 400),
        ("gallery-3", "Fachada de la tiendita pintada con colores vivos, anuncios de Coca-Cola y bimbo", 600, 400),
    ],
    "Consultorios dentales": [
        ("hero",      "Consultorio dental moderno y limpio, sillón odontológico nuevo, lámpara LED encendida, ventanal con luz natural, estética minimalista profesional", 1600, 900),
        ("service-1", "Dentista con cubrebocas explicando una radiografía digital en pantalla a paciente sentado, ambiente cálido y de confianza", 800, 600),
        ("service-2", "Limpieza dental profesional en proceso, manos enguantadas con instrumento, paciente con babero", 800, 600),
        ("service-3", "Modelo de dientes con brackets sobre mesa de exploración, detalle macro nítido", 800, 600),
        ("service-4", "Paciente sonriendo después del tratamiento, mirando un espejo de mano, dentista al lado satisfecho", 800, 600),
        ("gallery-1", "Sala de espera moderna con sillones beige, plantas y revistas, sin pacientes, ambiente sereno", 600, 400),
        ("gallery-2", "Instrumental dental esterilizado y ordenado sobre charola azul, vista cenital", 600, 400),
        ("gallery-3", "Fachada profesional del consultorio con vitrina de cristal y logo discreto", 600, 400),
    ],
    "Gimnasios": [
        ("hero",      "Interior de gimnasio funcional moderno con racks de pesas, cuerdas de batalla y suelo de caucho, atletas entrenando intensamente, iluminación industrial", 1600, 900),
        ("service-1", "Entrenador personal corrigiendo la postura de sentadilla a un cliente con barra olímpica", 800, 600),
        ("service-2", "Clase grupal de funcional en plena acción, varias personas haciendo burpees, energía alta", 800, 600),
        ("service-3", "Mancuernas y kettlebells alineadas sobre rack metálico, detalle nítido", 800, 600),
        ("service-4", "Persona sudada usando cuerda de batalla, fondo desenfocado del gym, dinamismo", 800, 600),
        ("gallery-1", "Reloj de pared estilo crossfit marcando un WOD, pizarra con resultados al fondo", 600, 400),
        ("gallery-2", "Atleta tomando agua después de entrenar, secándose con toalla, ambiente real", 600, 400),
        ("gallery-3", "Fachada urbana del gimnasio con vitrina y nombre, motos y autos afuera", 600, 400),
    ],
    "Veterinarias": [
        ("hero",      "Interior de una clínica veterinaria mexicana moderna y luminosa, mesa de exploración limpia, doctora veterinaria con bata revisando con cariño a un perro mediano", 1600, 900),
        ("service-1", "Vacunación de un cachorro tranquilo siendo sostenido por su dueño, jeringa pequeña, ambiente sereno", 800, 600),
        ("service-2", "Veterinario revisando los oídos de un gato adulto con otoscopio, paciencia, primer plano", 800, 600),
        ("service-3", "Cirugía menor en proceso bajo lámpara quirúrgica, equipo con cubrebocas y guantes, sin sangre visible", 800, 600),
        ("service-4", "Sala de baño y estética canina, perro pequeño siendo bañado con espuma, sonriente", 800, 600),
        ("gallery-1", "Sala de espera con dueños y mascotas: perro, gato en transportadora, ambiente amable", 600, 400),
        ("gallery-2", "Estantería con alimento premium y suplementos para mascotas, etiquetas claras", 600, 400),
        ("gallery-3", "Fachada de la veterinaria con letrero claro y huellas decorativas en la entrada", 600, 400),
    ],
    "Lavanderías": [
        ("hero",      "Interior de lavandería moderna con hilera de lavadoras de carga frontal industriales, suelo limpio, luz natural, ropa doblada en estantes", 1600, 900),
        ("service-1", "Empleada doblando ropa limpia con cuidado sobre mesa amplia, pilas ordenadas", 800, 600),
        ("service-2", "Lavadora industrial girando a media velocidad, detalle del tambor con espuma y ropa colorida", 800, 600),
        ("service-3", "Plancha profesional planchando una camisa blanca sobre tabla, vapor visible", 800, 600),
        ("service-4", "Cliente entregando bolsa de ropa sucia a la encargada en mostrador, sonrisa amable", 800, 600),
        ("gallery-1", "Bolsas de ropa lista con etiqueta y ticket grapado, listas para entregar", 600, 400),
        ("gallery-2", "Detalle de detergentes y suavizantes profesionales en estantería", 600, 400),
        ("gallery-3", "Fachada de la lavandería con letrero claro y horario en la puerta", 600, 400),
    ],
    "Florerías": [
        ("hero",      "Interior de florería boutique con paredes de flores frescas de colores variados, mesa central de trabajo con rollos de papel y listones, luz natural amplia", 1600, 900),
        ("service-1", "Florista creando ramo de novia con rosas blancas y verdes, manos cuidadosas, primer plano", 800, 600),
        ("service-2", "Variedad de ramos coloridos exhibidos en cubetas metálicas en hilera, llenos de vida", 800, 600),
        ("service-3", "Arreglo grande para evento sobre pedestal, girasoles y tulipanes mezclados, fondo neutro", 800, 600),
        ("service-4", "Manos envolviendo un ramo en papel kraft con listón satinado, detalle nítido", 800, 600),
        ("gallery-1", "Detalle macro de pétalos de rosa con gotas de agua, enfoque selectivo", 600, 400),
        ("gallery-2", "Repartidor entregando un ramo a clienta sonriendo en la puerta de su casa", 600, 400),
        ("gallery-3", "Fachada de la florería con macetas afuera y nombre pintado en cristal", 600, 400),
    ],
    "Panaderías": [
        ("hero",      "Interior de panadería mexicana tradicional, vitrinas llenas de pan dulce: conchas, cuernitos, orejas, polvorones, ambiente cálido con luz dorada", 1600, 900),
        ("service-1", "Panadero amasando masa sobre mesa de acero, harina volando, manos blancas", 800, 600),
        ("service-2", "Charola de bolillos recién horneados saliendo del horno con guantes de tela gruesos", 800, 600),
        ("service-3", "Pastel de cumpleaños decorado con buttercream, frutos rojos arriba, sobre tabla giratoria", 800, 600),
        ("service-4", "Niño escogiendo conchas con pinzas en la panadería tradicional, charola de aluminio", 800, 600),
        ("gallery-1", "Vitrina con galletas decoradas y pan de muerto en temporada", 600, 400),
        ("gallery-2", "Detalle macro de un cuernito de mantequilla recién horneado, hojaldre visible", 600, 400),
        ("gallery-3", "Fachada de la panadería con olor casi visible, letrero de neón cálido", 600, 400),
    ],
    "Inmobiliarias": [
        ("hero",      "Sala amplia y luminosa de una casa moderna mexicana, ventanal grande, decoración minimalista, sofá gris, planta grande, fotografía editorial inmobiliaria", 1600, 900),
        ("service-1", "Asesor inmobiliario mostrando llaves a una pareja sonriente frente a una casa nueva", 800, 600),
        ("service-2", "Cocina moderna integral con isla de mármol y taburetes altos, perfectamente iluminada", 800, 600),
        ("service-3", "Recámara principal con cama king y vista a balcón, decoración cálida", 800, 600),
        ("service-4", "Plano arquitectónico desplegado sobre mesa con lápiz y maqueta pequeña al lado", 800, 600),
        ("gallery-1", "Fachada de casa residencial mexicana moderna con jardín y portón eléctrico", 600, 400),
        ("gallery-2", "Vista aérea de fraccionamiento residencial al atardecer, calles arboladas", 600, 400),
        ("gallery-3", "Llaves de casa colgando de cerradura nueva, detalle simbólico", 600, 400),
    ],
    "Otros": [
        ("hero",      "Interior de comercio local mexicano de barrio, ambiente cálido y profesional, dueño atendiendo con amabilidad, luz natural", 1600, 900),
        ("service-1", "Empleado mostrando producto o servicio característico al cliente, ambiente cordial", 800, 600),
        ("service-2", "Mostrador principal del negocio con productos exhibidos en orden", 800, 600),
        ("service-3", "Detalle del trabajo o producto principal, primer plano nítido", 800, 600),
        ("service-4", "Cliente satisfecho saliendo del negocio con bolsa o producto, sonriente", 800, 600),
        ("gallery-1", "Detalle decorativo o elemento característico del negocio", 600, 400),
        ("gallery-2", "Equipo de trabajo posando frente al negocio con orgullo", 600, 400),
        ("gallery-3", "Fachada del negocio con letrero y horario visible, día soleado", 600, 400),
    ],
}


def _slug(name: str) -> str:
    s = (name or "").lower().strip()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = re.sub(r"-+", "-", s).strip("-")
    return s or "negocio"


def _business_dir(business: dict) -> Path:
    # Prefiero place_id (estable) sobre slug del nombre
    pid = (business.get("place_id") or "").strip()
    folder = pid if pid else _slug(business.get("name", ""))
    folder = re.sub(r"[^A-Za-z0-9_-]+", "_", folder)
    d = IMG_ROOT / folder
    d.mkdir(parents=True, exist_ok=True)
    return d


# ============================================================
# Llamada real a Gemini
# ============================================================
def _gemini_generate_one(prompt: str, out_path: Path) -> bool:
    """Genera UNA imagen con gemini-2.5-flash-image. Retorna True si tuvo éxito."""
    from google import genai

    client = genai.Client(api_key=config.GEMINI_API_KEY)
    try:
        resp = client.models.generate_content(
            model=config.GEMINI_IMAGE_MODEL,
            contents=prompt,
        )
    except Exception as e:
        logger.warning("Gemini falló para %s: %s", out_path.name, e)
        return False

    # La SDK devuelve partes; la imagen viene como inline_data con mime image/png
    try:
        for part in resp.candidates[0].content.parts:
            inline = getattr(part, "inline_data", None)
            if inline and getattr(inline, "data", None):
                out_path.write_bytes(inline.data)
                return True
    except Exception as e:
        logger.warning("No pude leer imagen de respuesta Gemini: %s", e)
    return False


def _build_prompt(business: dict, scene_prompt: str, w: int, h: int) -> str:
    name = business.get("name", "")
    category = business.get("category", "")
    address = business.get("address", "")
    aspect = "horizontal panorámica 16:9" if w >= h * 1.5 else "horizontal estándar 4:3"
    return (
        f"{_PHOTO_BASE}"
        f"Negocio: {name} ({category}) en {address}. "
        f"Escena requerida: {scene_prompt}. "
        f"Composición {aspect}, lista para usar como imagen de landing page."
    )


# ============================================================
# Punto de entrada
# ============================================================
def generate_business_images(business: dict) -> Optional[dict[str, str]]:
    """Genera el set de imágenes para una landing.

    Returns:
        dict {slot_name: ruta_relativa_al_html} si al menos hubo 1 éxito,
        None si no se pudo generar nada (caller debe caer a Unsplash).
    """
    if not config.GEMINI_API_KEY:
        logger.info("Sin GEMINI_API_KEY → fallback a Unsplash")
        return None

    category = business.get("category", "Otros")
    plan = CATEGORY_IMAGE_PLANS.get(category, CATEGORY_IMAGE_PLANS["Otros"])
    plan = plan[: config.GEMINI_IMAGES_PER_LANDING]

    biz_dir = _business_dir(business)
    rel_base = f"img/{biz_dir.name}"

    result: dict[str, str] = {}
    needed: list[tuple[str, str, int, int]] = []

    # Cache: si ya existe el archivo, reusar
    for slot, scene, w, h in plan:
        path = biz_dir / f"{slot}.png"
        if path.exists() and path.stat().st_size > 1024:
            result[slot] = f"{rel_base}/{slot}.png"
        else:
            needed.append((slot, scene, w, h))

    # Reservar atómicamente la cuota que necesitamos. Esto es seguro aunque
    # haya varios threads llamándonos en paralelo.
    if needed:
        granted = reserve(len(needed))
        if granted == 0:
            logger.warning("Cuota Gemini agotada hoy (%d/día). Fallback a Unsplash.",
                           config.GEMINI_DAILY_BUDGET)
            return None
        if granted < len(needed):
            logger.warning("Solo se reservaron %d de %d imágenes pedidas para %s.",
                           granted, len(needed), business.get("name"))
            needed = needed[:granted]

    # Generar secuencialmente dentro del paquete
    fallos = 0
    for slot, scene, w, h in needed:
        prompt = _build_prompt(business, scene, w, h)
        path = biz_dir / f"{slot}.png"
        ok = _gemini_generate_one(prompt, path)
        if ok:
            result[slot] = f"{rel_base}/{slot}.png"
            logger.info("Gemini OK → %s/%s (uso hoy: %d/%d)",
                        biz_dir.name, path.name,
                        _get_used_today(), config.GEMINI_DAILY_BUDGET)
        else:
            fallos += 1
            logger.warning("Gemini falló slot=%s para %s, hueco caerá a Unsplash",
                           slot, business.get("name"))

    # Devolver al cupo las que reservé pero no consumí (fallos)
    if fallos:
        release(fallos)

    if not result:
        return None
    return result
