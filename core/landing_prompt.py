"""Generador de prompt premium para landing pages, adaptado por categoría.

El prompt resultante se pega en claude.ai (Pro/Max) o se manda a Anthropic API.
"""
from __future__ import annotations

import config


# ============================================================
# Secciones específicas por categoría
# ============================================================
CATEGORY_SECTIONS: dict[str, list[str]] = {
    "Restaurantes": [
        "Hero con imagen de fondo (placeholder) y CTA 'Reservar mesa' / 'Ver menú'",
        "Carrusel de platos destacados (4–6 cards con imagen placeholder, nombre y precio)",
        "Sección de menú estructurado con categorías (Entradas, Platos fuertes, Postres, Bebidas), 3–4 ítems por categoría",
        "Sobre nosotros con historia del lugar",
        "Galería tipo masonry de 6 imágenes placeholder del lugar",
        "Bloque de rating con testimonios destacados (3 reseñas)",
        "Mapa embebido (placeholder con dirección) + horarios de atención por día",
        "Footer con redes sociales + teléfono + reservas",
    ],
    "Cafeterías": [
        "Hero acogedor con tagline y CTA 'Visítanos'",
        "Sección 'Nuestro café' con storytelling sobre el grano y el método",
        "Menú con 4 categorías (Café, Tés, Postres, Snacks)",
        "Carrusel de fotos del lugar y los productos",
        "Bloque de horarios + Wi-Fi + ambiente para trabajar",
        "Testimonios de clientes (3)",
        "Mapa + dirección + footer",
    ],
    "Estéticas y barberías": [
        "Hero con imagen de fondo (look profesional) y CTA 'Reservar cita'",
        "Galería antes/después o catálogo de cortes (6 placeholders con nombre del estilo)",
        "Lista de servicios con precios (Corte, Barba, Tinte, Tratamientos…)",
        "Formulario de reserva: nombre, teléfono, servicio (select), fecha (date), hora (time), notas",
        "Sección del equipo (3 estilistas con foto placeholder y especialidad)",
        "Reseñas con estrellas",
        "Horarios y contacto en footer",
    ],
    "Talleres mecánicos": [
        "Hero con CTA 'Cotiza tu reparación'",
        "Lista de servicios técnicos con iconos (Diagnóstico, Frenos, Suspensión, Eléctrico, Aire acondicionado…)",
        "Formulario de cotización: nombre, teléfono, marca/modelo del auto, año, problema (textarea)",
        "Sección 'Por qué elegirnos' con 4 puntos de confianza (años de experiencia, garantía, repuestos originales, certificaciones)",
        "Galería del taller (4 imágenes placeholder)",
        "Mapa + horarios + emergencias 24h si aplica",
    ],
    "Tiendas de abarrotes": [
        "Hero con CTA 'Pedir a domicilio'",
        "Sección de categorías de productos (grid de 6 con icono)",
        "Bloque de promociones de la semana (3 cards)",
        "Formulario de pedido a domicilio: nombre, dirección, teléfono, lista de productos (textarea)",
        "Mapa + horarios extensos + zonas de entrega",
    ],
    "Consultorios dentales": [
        "Hero profesional con CTA 'Agendar consulta'",
        "Servicios con iconos (Limpieza, Ortodoncia, Blanqueamiento, Implantes, Endodoncia, Estética dental)",
        "Formulario de cita: nombre, teléfono, email, servicio (select), fecha preferida",
        "Sección del doctor (foto placeholder, cédula profesional, especialidades)",
        "Antes/después de tratamientos (4 placeholders)",
        "Testimonios con estrellas",
        "FAQs sobre tratamientos y precios",
        "Mapa + horarios + urgencias",
    ],
    "Gimnasios": [
        "Hero impactante con CTA 'Empieza tu prueba gratis'",
        "Sección de planes y precios (3 cards: Básico, Plus, Premium con tabla de beneficios)",
        "Horario de clases grupales en formato tabla (Lun–Dom × turnos)",
        "Galería de instalaciones (6 placeholders)",
        "Equipo de entrenadores (3 con foto y especialidad)",
        "Formulario de prueba gratis: nombre, teléfono, objetivo (select)",
        "Testimonios + transformaciones",
        "Mapa + horarios + footer",
    ],
    "Veterinarias": [
        "Hero cálido con CTA 'Agenda consulta'",
        "Servicios (Consultas, Vacunación, Cirugía, Estética, Hospitalización, Urgencias)",
        "Formulario de cita: nombre dueño, teléfono, especie/raza mascota, motivo",
        "Sección del equipo veterinario (3 con foto placeholder)",
        "Galería de la clínica",
        "FAQs de cuidados",
        "Mapa + horarios + número de emergencias",
    ],
    "Lavanderías": [
        "Hero con CTA 'Pedir recolección'",
        "Lista de servicios con precios por kilo o pieza",
        "Formulario de recolección: nombre, dirección, teléfono, fecha y hora preferida",
        "Bloque '¿Cómo funciona?' en 4 pasos (Recolección, Lavado, Entrega, Pago)",
        "Tiempos de entrega (Express, Normal)",
        "Mapa + horarios",
    ],
    "Florerías": [
        "Hero romántico con CTA 'Pide tus flores'",
        "Carrusel de arreglos (8 placeholders con nombre y precio)",
        "Categorías por ocasión (Cumpleaños, Aniversario, Condolencias, Bodas, Eventos)",
        "Formulario de pedido: tipo de arreglo, fecha de entrega, dirección destinatario, mensaje de tarjeta",
        "Galería de bodas y eventos",
        "Mapa + horarios + redes",
    ],
    "Panaderías": [
        "Hero apetitoso con CTA 'Ver productos'",
        "Catálogo del día (6 cards: pan, pasteles, postres, repostería)",
        "Formulario de encargo: producto, cantidad, fecha de entrega, dirección, teléfono",
        "Sección 'Nuestra historia' con storytelling artesanal",
        "Galería del horno y productos",
        "Horarios extensos + mapa",
    ],
    "Inmobiliarias": [
        "Hero con buscador de propiedades (filtros: tipo, ciudad, rango de precio)",
        "Listado destacado de 6 propiedades (cards con foto, precio, m², habitaciones, ubicación)",
        "Sección de servicios (Compra, Venta, Renta, Asesoría)",
        "Formulario de contacto detallado: nombre, teléfono, email, qué busca, presupuesto, zona, mensaje",
        "Sección del equipo de asesores",
        "Testimonios de clientes",
        "Mapa de cobertura + footer",
    ],
}

DEFAULT_SECTIONS = [
    "Hero con CTA principal",
    "Sobre nosotros (storytelling breve)",
    "3 servicios o productos clave con iconos",
    "Bloque de rating con testimonios",
    "Galería de 4 imágenes placeholder",
    "Formulario de contacto (nombre, teléfono, email, mensaje)",
    "Mapa embebido + horarios + footer",
]


CATEGORY_PALETTES: dict[str, dict] = {
    "Restaurantes":          {"primary": "#C0392B", "accent": "#F39C12", "bg": "#FFF8F0"},
    "Cafeterías":            {"primary": "#6F4E37", "accent": "#D2A679", "bg": "#FAF6F1"},
    "Estéticas y barberías": {"primary": "#1C1C1C", "accent": "#C9A227", "bg": "#F8F6F2"},
    "Talleres mecánicos":    {"primary": "#2C3E50", "accent": "#E67E22", "bg": "#F4F6F8"},
    "Tiendas de abarrotes":  {"primary": "#27AE60", "accent": "#F1C40F", "bg": "#F6FBF6"},
    "Consultorios dentales": {"primary": "#1F6FEB", "accent": "#56C2E6", "bg": "#F4F9FE"},
    "Gimnasios":             {"primary": "#111111", "accent": "#FF3B30", "bg": "#F4F4F4"},
    "Veterinarias":          {"primary": "#16A085", "accent": "#F39C12", "bg": "#F2FBF8"},
    "Lavanderías":           {"primary": "#3498DB", "accent": "#2ECC71", "bg": "#F4F9FD"},
    "Florerías":             {"primary": "#C0397A", "accent": "#9B59B6", "bg": "#FBF4F9"},
    "Panaderías":            {"primary": "#A0522D", "accent": "#F4A460", "bg": "#FFF8EE"},
    "Inmobiliarias":         {"primary": "#0F4C81", "accent": "#D4AF37", "bg": "#F7F9FC"},
    "Otros":                 {"primary": "#1F6FEB", "accent": "#22C55E", "bg": "#F5F7FB"},
}


def _palette_for(category: str) -> dict:
    return CATEGORY_PALETTES.get(category, CATEGORY_PALETTES["Otros"])


def _sections_for(category: str) -> list[str]:
    return CATEGORY_SECTIONS.get(category, DEFAULT_SECTIONS)


# ============================================================
# Detección de contexto específico del negocio
# ============================================================
# Mapea palabras del nombre a (descripción humana, keywords para imágenes)
NAME_KEYWORDS: dict[str, tuple[str, str]] = {
    # Comida mexicana
    "tacos":      ("tacos mexicanos al pastor / suadero / asada", "tacos,al-pastor,mexican-food"),
    "taquería":   ("taquería tradicional mexicana", "tacos,taqueria,mexican-food"),
    "taqueria":   ("taquería tradicional mexicana", "tacos,taqueria,mexican-food"),
    "tortas":     ("tortas mexicanas y comida rápida", "tortas,sandwich,mexican-food"),
    "antojitos":  ("antojitos mexicanos: quesadillas, sopes, tlacoyos", "quesadillas,mexican-food,antojitos"),
    "birria":     ("birria estilo Jalisco", "birria,mexican-stew"),
    "pozole":     ("pozole mexicano tradicional", "pozole,mexican-soup"),
    "mariscos":   ("mariscos: ceviche, aguachile, camarones", "mariscos,ceviche,seafood"),
    "pescado":    ("pescados y mariscos frescos", "fish,seafood,ceviche"),
    "ceviche":    ("ceviche y mariscos", "ceviche,seafood"),
    # Comida internacional
    "pizza":      ("pizzería italiana", "pizza,italian-food"),
    "pizzería":   ("pizzería italiana", "pizza,italian-food"),
    "pizzeria":   ("pizzería italiana", "pizza,italian-food"),
    "sushi":      ("sushi y comida japonesa", "sushi,japanese-food"),
    "ramen":      ("ramen y comida japonesa", "ramen,japanese-noodles"),
    "burger":     ("hamburguesas gourmet", "burger,hamburger,fries"),
    "hamburgues": ("hamburguesas gourmet", "burger,hamburger"),
    "wings":      ("alitas y comida americana", "chicken-wings,bbq"),
    "asad":       ("carnes asadas estilo norteño", "grilled-meat,bbq,steak"),
    "parrilla":   ("carnes a la parrilla", "grill,bbq,steak"),
    "pollo":      ("pollo rostizado / asado", "rotisserie-chicken,grilled-chicken"),
    "barbacoa":   ("barbacoa de borrego", "barbacoa,mexican-meat"),
    # Postres / café / panadería
    "café":       ("café de especialidad y postres", "coffee,latte-art,cafe"),
    "cafe":       ("café de especialidad y postres", "coffee,latte-art,cafe"),
    "barista":    ("café de especialidad", "coffee,barista,latte"),
    "pastel":     ("pastelería y repostería artesanal", "cake,pastry,bakery"),
    "reposter":   ("repostería artesanal", "pastry,dessert,bakery"),
    "panader":    ("panadería tradicional mexicana", "bread,bakery,pan-dulce"),
    "donut":      ("donas y postres", "donut,doughnut"),
    "helad":      ("heladería artesanal", "ice-cream,gelato"),
    "nieve":      ("nieves y helados", "ice-cream,sorbet"),
    "chocolate":  ("chocolatería y postres", "chocolate,dessert"),
    # Estética / barbería
    "barber":     ("barbería con estilo clásico/moderno", "barbershop,beard,haircut-men"),
    "estética":   ("estética / salón de belleza", "hairsalon,haircut,beauty"),
    "estetica":   ("estética / salón de belleza", "hairsalon,haircut,beauty"),
    "salón":      ("salón de belleza", "hairsalon,beauty,haircut"),
    "salon":      ("salón de belleza", "hairsalon,beauty,haircut"),
    "uñas":       ("estudio de uñas / nail art", "nails,manicure,nail-art"),
    "spa":        ("spa y bienestar", "spa,massage,wellness"),
    "masajes":    ("centro de masajes", "massage,spa,wellness"),
    # Talleres
    "taller":     ("taller mecánico automotriz", "auto-repair,mechanic,car-engine"),
    "mecánico":   ("taller mecánico automotriz", "auto-repair,mechanic"),
    "mecanico":   ("taller mecánico automotriz", "auto-repair,mechanic"),
    "llantas":    ("llantera / servicio de neumáticos", "tires,car-wheels"),
    "llantera":   ("llantera / servicio de neumáticos", "tires,car-wheels"),
    "hojalater":  ("hojalatería y pintura automotriz", "auto-body,car-paint"),
    # Salud
    "dental":     ("clínica dental", "dental,dentist,teeth"),
    "dentista":   ("consultorio dental", "dental,dentist,teeth"),
    "óptica":     ("óptica y lentes", "eyewear,glasses,optical"),
    "optica":     ("óptica y lentes", "eyewear,glasses,optical"),
    "farmacia":   ("farmacia", "pharmacy,medicine"),
    "veterinar":  ("veterinaria y cuidado de mascotas", "veterinarian,pets,dog-cat"),
    # Fitness
    "gimnasio":   ("gimnasio y fitness", "gym,fitness,workout"),
    "gym":        ("gimnasio y fitness", "gym,fitness,workout"),
    "crossfit":   ("box de crossfit", "crossfit,fitness,gym"),
    "yoga":       ("estudio de yoga", "yoga,meditation,wellness"),
    "pilates":    ("estudio de pilates", "pilates,fitness"),
    "box":        ("gimnasio de boxeo", "boxing,gym"),
    # Servicios
    "lavander":   ("lavandería y tintorería", "laundry,washing-machine"),
    "tintorer":   ("tintorería profesional", "dry-cleaning,laundry"),
    "florería":   ("florería y arreglos", "flowers,florist,bouquet"),
    "floreria":   ("florería y arreglos", "flowers,florist,bouquet"),
    "abarrotes":  ("tienda de abarrotes / miscelánea", "grocery-store,small-shop"),
    "miscelánea": ("miscelánea de barrio", "small-shop,grocery"),
    "miscelanea": ("miscelánea de barrio", "small-shop,grocery"),
    "papeler":    ("papelería", "stationery,office-supplies"),
    "ferreter":   ("ferretería", "hardware-store,tools"),
    "boutique":   ("boutique de ropa", "boutique,fashion,clothing"),
    "ropa":       ("tienda de ropa", "fashion,clothing-store"),
    # Inmobiliaria
    "inmobiliar": ("inmobiliaria / venta y renta", "real-estate,modern-house,apartment"),
    "bienes":     ("bienes raíces", "real-estate,house,property"),
}


# Pistas por categoría — siempre se incluyen como base
CATEGORY_IMAGE_HINTS: dict[str, str] = {
    "Restaurantes":          "mexican-food,restaurant,dining,plated-dish",
    "Cafeterías":            "coffee,cafe,latte,pastry",
    "Estéticas y barberías": "hairsalon,barbershop,haircut,beauty",
    "Talleres mecánicos":    "auto-repair,mechanic,car-engine,workshop",
    "Tiendas de abarrotes":  "grocery-store,small-shop,fresh-produce",
    "Consultorios dentales": "dental,dentist,clean-clinic,smile",
    "Gimnasios":             "gym,fitness,workout,training",
    "Veterinarias":          "veterinarian,pet-clinic,dog-cat,animal-care",
    "Lavanderías":           "laundry,washing,clean-clothes",
    "Florerías":             "flowers,bouquet,florist,arrangement",
    "Panaderías":            "bread,bakery,pan-dulce,pastry",
    "Inmobiliarias":         "real-estate,modern-house,apartment,interior",
    "Otros":                 "small-business,storefront,local-shop",
}


def _detect_business_context(name: str, category: str) -> dict:
    """Analiza el nombre del negocio y devuelve descripción + keywords de imagen.

    Returns:
        {
          "description": "tacos mexicanos al pastor / suadero / asada",
          "image_keywords": "tacos,al-pastor,mexican-food,restaurant",
          "matched_terms": ["tacos"],  # palabras del nombre que activaron coincidencia
        }
    """
    name_lower = (name or "").lower()
    descriptions: list[str] = []
    keywords: list[str] = []
    matched: list[str] = []

    for term, (desc, kws) in NAME_KEYWORDS.items():
        if term in name_lower:
            if desc not in descriptions:
                descriptions.append(desc)
            for k in kws.split(","):
                k = k.strip()
                if k and k not in keywords:
                    keywords.append(k)
            matched.append(term)

    # Solo usar hints de categoría como fallback cuando NO hubo match específico
    if not matched:
        base_kws = CATEGORY_IMAGE_HINTS.get(category, CATEGORY_IMAGE_HINTS["Otros"]).split(",")
        for k in base_kws:
            k = k.strip()
            if k and k not in keywords:
                keywords.append(k)

    if not descriptions:
        descriptions.append(f"negocio del giro: {category.lower()}")

    return {
        "description": " · ".join(descriptions),
        "image_keywords": ",".join(keywords[:6]),  # tope de 6 para no saturar
        "matched_terms": matched,
    }


# ============================================================
# Constructor del prompt
# ============================================================
def build_landing_prompt(business: dict) -> str:
    """Genera un prompt completo, profesional y adaptado a la categoría.

    Pensado para pegarse en claude.ai (Pro/Max) o enviarse a Anthropic API.
    """
    name = business.get("name", "")
    category = business.get("category", "Otros")
    address = business.get("address", "")
    phone = business.get("phone") or "no disponible"
    rating = business.get("rating") or "—"
    reviews = business.get("reviews_count") or 0
    website = business.get("website") or "no tiene"
    palette = _palette_for(category)
    sections = _sections_for(category)
    ctx = _detect_business_context(name, category)

    sections_md = "\n".join(f"  {i+1}. {s}" for i, s in enumerate(sections))

    matched_line = (
        f"Palabras detectadas en el nombre: {', '.join(ctx['matched_terms'])}"
        if ctx["matched_terms"]
        else "No se detectaron palabras clave específicas en el nombre — apóyate en la categoría."
    )

    prompt = f"""Eres un diseñador web senior especializado en landing pages premium para negocios locales en México. Crea una **landing page profesional, completa y standalone** (todo inline: CSS dentro de <style>, sin dependencias externas, sin CDN, sin JS opcional salvo que sea para interactividad básica vanilla).

# DATOS DEL NEGOCIO
- **Nombre:** {name}
- **Categoría:** {category}
- **Dirección:** {address}
- **Teléfono:** {phone}
- **Web actual:** {website}
- **Rating Google Maps:** {rating}★ ({reviews} reseñas)

# CONTEXTO ESPECÍFICO DEL NEGOCIO ⚠️ CRÍTICO
- **Giro real detectado:** {ctx['description']}
- {matched_line}

⚠️ **Toda la landing debe reflejar ESTE giro específico, no la categoría genérica.** Si el negocio es "Tacos El Compa", no es "un restaurante" — es **una taquería mexicana** con tacos al pastor, suadero, asada, salsas, tortillas hechas a mano. Los textos, fotos, menú, servicios y testimonios deben sentirse de ese negocio en particular, no de un restaurante cualquiera.

# PALETA DE COLORES (úsala con precisión)
- Primario: {palette['primary']}
- Acento: {palette['accent']}
- Fondo claro: {palette['bg']}
- Texto oscuro: #1A1A1A
- Texto secundario: #555
- Bordes/líneas: #E5E5E5

# SECCIONES OBLIGATORIAS (en este orden)
{sections_md}

# REQUISITOS DE DISEÑO (calidad agencia, no genérico)
- **Estética:** moderna, premium, espaciosa. Mucho whitespace. Tipografía sans-serif del sistema (-apple-system, "Segoe UI", Inter, Roboto). Tamaños generosos en hero (h1 mínimo 3rem desktop).
- **Layout:** mobile-first con media queries. Grid CSS para galerías y cards. Flexbox donde aplique.
- **Microinteracciones:** transiciones suaves en hovers (transform: translateY, box-shadow), botones con efecto al pasar el cursor.
- **Iconos:** usa emojis Unicode pertinentes al giro (🌮, ☕, ✂️, 🔧, 🐾, 🌸, 🍞, 🏠) o SVG inline simples. NUNCA Font Awesome ni librerías externas.
- **Formularios:** estilo limpio con labels arriba, inputs con borde sutil, focus state, botón submit con color primario. Aunque no tenga backend, debe ser visualmente funcional.
- **Carruseles/galerías:** si necesitas carrusel, usa CSS scroll-snap (no JS). Si es galería, usa CSS Grid masonry o columnas.
- **Responsive:** breakpoints en 768px y 480px. En móvil: hero más compacto, navegación tipo hamburger CSS-only o nav simple, grids a 1 columna.
- **Accesibilidad:** alt en imágenes, labels en inputs, contrastes correctos.

# IMÁGENES — REGLA CRÍTICA, sigue esto al pie de la letra
**TODAS las imágenes DEBEN ser del giro específico del negocio.** Nada de fotos aleatorias.

Usa **LoremFlickr** que sirve fotos reales por palabra clave:
```
https://loremflickr.com/<ancho>/<alto>/<keywords>?lock=<seed-único>
```

- `<keywords>` = una o más palabras separadas por comas, **siempre relevantes al giro**.
  - Keywords base sugeridos para ESTE negocio: `{ctx['image_keywords']}`
  - Puedes añadir más específicas según la sección (ej. `mexican-food,salsa` para una sección de salsas).
- `<seed-único>` = un número distinto por cada imagen para que NO se repita la misma foto.
- `<ancho>` y `<alto>` = tamaño que necesitas (ej. 800/600 para cards, 1600/900 para hero).

Ejemplos VÁLIDOS para este negocio:
- Hero: `https://loremflickr.com/1600/900/{ctx['image_keywords'].split(',')[0]}?lock=1`
- Card de servicio 1: `https://loremflickr.com/600/400/{ctx['image_keywords']}?lock=2`
- Galería imagen 3: `https://loremflickr.com/800/600/{ctx['image_keywords']}?lock=10`

❌ PROHIBIDO:
- `picsum.photos` (da imágenes aleatorias sin contexto)
- `via.placeholder.com` (placeholders grises)
- `unsplash.com/random` o keywords genéricos como "business" o "store"
- SVG geométricos como reemplazo de fotos

✅ Cada `alt=""` debe describir la imagen contextualmente (ej. `alt="Tacos al pastor recién servidos"`).

# TONO Y CONTENIDO
- Español de México, cálido pero profesional
- Copy persuasivo, NO genérico (nada de "calidad y servicio")
- Inventa textos, productos, platos o servicios **del giro real detectado**, no de la categoría genérica
- Si es taquería, inventa nombres de tacos creíbles ("Taco al pastor con piña", "Suadero con cebolla y cilantro"). Si es barbería, nombres de cortes ("Fade clásico", "Pompadour", "Diseño de barba"). Sé específico.
- Testimonios: nombres mexicanos comunes (María, Carlos, Andrea, Luis, Sofía…), comentarios creíbles que mencionen productos/servicios específicos del negocio
- En el footer SIEMPRE: "Sitio de demostración generado por **{config.AGENCY_NAME}**"

# FORMATO DE SALIDA
Devuelve **SOLO el HTML completo desde `<!DOCTYPE html>` hasta `</html>`**. Sin explicaciones previas ni posteriores. Sin bloques de código markdown — HTML puro listo para guardar como .html y abrir en el navegador.
"""
    return prompt


def build_short_summary(business: dict) -> str:
    """Resumen corto en JSON-like para pegar en proyectos custom de Claude.ai."""
    import json
    return json.dumps({
        "name": business.get("name"),
        "category": business.get("category"),
        "address": business.get("address"),
        "phone": business.get("phone"),
        "rating": business.get("rating"),
        "reviews_count": business.get("reviews_count"),
        "website": business.get("website"),
    }, ensure_ascii=False, indent=2)
