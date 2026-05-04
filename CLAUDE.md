# CLAUDE.md — Prospector Web
> Instrucciones para Claude Code. Lee este archivo completo antes de tocar cualquier archivo.

---

## Qué es este proyecto

Sistema de prospección de clientes para agencia de desarrollo web. Busca negocios locales en Google Maps que no tienen página web o la tienen desactualizada, enriquece sus datos de contacto, genera una landing page de muestra usando la API de Claude, y exporta todo a Excel o PDF imprimible para presentar la propuesta al cliente.

El usuario final no es desarrollador. La interfaz es una app web local con **Streamlit**. Se corre con un solo comando desde la terminal.

---

## Stack tecnológico

| Capa | Tecnología |
|---|---|
| Interfaz | Streamlit |
| Búsqueda de negocios | Google Places API (googlemaps) |
| Enriquecimiento de email | Outscraper API + Hunter.io API (fallback) |
| Generación de landing page | Anthropic Claude API (claude-sonnet-4-5) |
| Export Excel | openpyxl |
| Export PDF | reportlab |
| Lenguaje | Python 3.10+ |

---

## Estructura de carpetas

```
prospector-web/
├── CLAUDE.md               ← este archivo
├── README.md
├── .env.example            ← plantilla de variables de entorno (sin secrets)
├── .env                    ← secrets reales (en .gitignore)
├── .gitignore
├── requirements.txt
├── app.py                  ← entrada principal de Streamlit
├── config.py               ← carga .env y constantes globales
├── core/
│   ├── __init__.py
│   ├── search.py           ← búsqueda en Google Places
│   ├── enrich.py           ← enriquecimiento de email/contacto
│   ├── score.py            ← calcula score de oportunidad (1-10)
│   ├── landing.py          ← genera landing HTML con Claude API
│   └── contact.py          ← determina canal de contacto óptimo
├── export/
│   ├── __init__.py
│   ├── excel.py            ← genera el Excel de prospectos
│   └── pdf_proposal.py     ← genera PDF de propuesta para visita presencial
├── outputs/
│   ├── landings/           ← HTMLs generados por prospecto
│   ├── excel/              ← archivos .xlsx exportados
│   └── pdf/                ← propuestas PDF para imprimir
└── tests/
    └── test_score.py
```

---

## Variables de entorno (.env)

```env
GOOGLE_PLACES_API_KEY=
OUTSCRAPER_API_KEY=
HUNTER_API_KEY=
ANTHROPIC_API_KEY=
```

El archivo `.env.example` debe existir con las keys vacías. El `.env` real va en `.gitignore`.

---

## Módulos — responsabilidades exactas

### `core/search.py`
- Función principal: `search_businesses(zone: str, radius_km: int, category: str) -> list[dict]`
- Usa `googlemaps.Client` con `places_nearby` o `text_search`
- Cada resultado debe devolver: `name`, `address`, `phone`, `rating`, `reviews_count`, `website` (puede ser None), `place_id`, `lat`, `lng`, `maps_url`
- Filtrar por `website is None` o detectar webs básicas (solo dominio de Facebook/Wix/Blogspot cuenta como "sin web real")

### `core/enrich.py`
- Función: `enrich_contact(business: dict) -> dict`
- Pipeline en cascada:
  1. Si `business['website']` existe → hacer GET y buscar emails con regex `[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}`
  2. Si no → llamar Outscraper API con el dominio o nombre del negocio
  3. Si no → llamar Hunter.io con el dominio
  4. Si no → marcar `email: None`, `contact_channel: "whatsapp"` o `"visit"` según si hay teléfono
- Agregar campo `social_links: dict` con facebook, instagram si Outscraper los devuelve

### `core/score.py`
- Función: `calculate_score(business: dict) -> int` (1-10)
- Criterios de scoring:
  - Sin web en absoluto: +4 puntos
  - Web desactualizada (detectada por año en copyright o tecnología obsoleta): +2 puntos
  - Rating >= 4.0: +2 puntos
  - Más de 20 reseñas: +1 punto
  - Tiene teléfono: +1 punto
- Score mínimo 1, máximo 10

### `core/landing.py`
- Función: `generate_landing(business: dict) -> str` (devuelve HTML completo)
- Llama a `anthropic.Anthropic().messages.create()` con `model="claude-sonnet-4-5"`
- El prompt debe incluir: nombre, categoría, dirección, rating, descripción si existe, colores sugeridos por categoría
- El HTML generado debe ser standalone (todo inline, sin dependencias externas), responsivo, y verse profesional
- Guardar el HTML en `outputs/landings/{slug_nombre}.html`
- Devolver la ruta del archivo guardado además del HTML

### `core/contact.py`
- Función: `suggest_contact_channel(business: dict) -> dict`
- Lógica:
  - Tiene email → `{"channel": "email", "value": email}`
  - No tiene email pero tiene teléfono → `{"channel": "whatsapp", "value": f"https://wa.me/52{phone_clean}"}`
  - Tiene Facebook → `{"channel": "facebook", "value": facebook_url}`
  - Nada → `{"channel": "visit", "value": business['address']}`
- Limpiar teléfono: quitar `+52`, espacios, guiones, dejar solo dígitos

### `export/excel.py`
- Función: `export_to_excel(prospects: list[dict]) -> str` (devuelve ruta del archivo)
- Columnas: Nombre, Dirección, Teléfono, Email, Canal de contacto, Score, Estrellas, Reseñas, Tiene web, Link Maps, Link Landing, Estado
- Columna "Estado" con dropdown: Pendiente / Contactado / Propuesta enviada / Cerrado
- Aplicar color verde a filas con score >= 8, amarillo a score >= 6
- Guardar en `outputs/excel/prospectos_{fecha}.xlsx`

### `export/pdf_proposal.py`
- Función: `generate_pdf_proposal(business: dict, landing_html_path: str) -> str`
- Genera un PDF de 1 página A4 con:
  - Header con nombre del negocio y categoría
  - Sección "¿Por qué necesitas una página web?" con 3 puntos clave
  - Captura o descripción de la landing generada
  - Sección de contacto con teléfono y dirección
  - Footer con datos del prospector (configurables en .env: `AGENCY_NAME`, `AGENCY_PHONE`, `AGENCY_EMAIL`)
- Usar reportlab con diseño limpio, tipografía Helvetica, colores corporativos configurables
- Guardar en `outputs/pdf/{slug_nombre}_propuesta.pdf`

### `app.py` — interfaz Streamlit
Estructura de la app:

```
Sidebar:
  - Campos: Zona (text), Radio (slider 1-30km), Categoría (select), Filtro (sin web / web desact. / todos)
  - Botón "Buscar prospectos"

Main area:
  - Métricas: total encontrados, sin web, con email, landings generadas
  - Tabla de prospectos con columnas: Score, Nombre, Canal, Acciones
  - Por cada prospecto: botón "Ver landing" (abre en nueva pestaña o modal), botón "Generar PDF"
  - Botones de exportación: "Exportar Excel", "Exportar PDF propuestas"

Estado:
  - Guardar lista de prospectos en st.session_state['prospects']
  - No repetir búsquedas si ya hay resultados cargados
```

---

## Convenciones de código

- Todas las funciones con type hints
- Manejo de errores con try/except en llamadas a APIs externas — nunca crashear la app completa por un prospecto que falla
- Logging con `logging.getLogger(__name__)` en cada módulo
- Si una API key no está configurada, mostrar warning en Streamlit y continuar sin esa fuente
- No hardcodear textos en español dentro del código — usar constantes en `config.py`

---

## Orden de implementación sugerido

1. `config.py` + `.env.example` + `requirements.txt`
2. `core/search.py` — búsqueda básica funcional
3. `core/score.py` — scoring sin dependencias externas
4. `core/contact.py` — lógica de canal de contacto
5. `app.py` — interfaz básica con búsqueda y tabla
6. `core/enrich.py` — enriquecimiento de email
7. `core/landing.py` — generación de landing con Claude
8. `export/excel.py`
9. `export/pdf_proposal.py`
10. Pulir UI, mensajes de error, estados de carga

---

## Cómo correr el proyecto

```bash
# 1. Clonar / copiar carpeta
cd prospector-web

# 2. Instalar dependencias
pip install -r requirements.txt

# 3. Copiar y rellenar variables de entorno
cp .env.example .env
# editar .env con tus API keys

# 4. Correr la app
streamlit run app.py
```

Se abre automáticamente en `http://localhost:8501`

---

## APIs externas — notas importantes

### Google Places API
- Endpoint recomendado: `Text Search` para búsquedas por zona + categoría en español
- Quota gratuita: 200 USD/mes (~5,000 búsquedas)
- Documentación: https://developers.google.com/maps/documentation/places/web-service

### Outscraper
- Endpoint: `Google Maps Scraper` + `Emails & Contacts Scraper`
- Tier gratuito disponible
- SDK: `pip install outscraper`

### Hunter.io
- Endpoint: `Domain Search` — devuelve emails asociados a un dominio
- Plan gratuito: 25 búsquedas/mes
- SDK: llamada HTTP directa a `https://api.hunter.io/v2/domain-search`

### Anthropic Claude API
- Modelo: `claude-sonnet-4-5`
- SDK: `pip install anthropic`
- El prompt de generación de landing debe ser en español e incluir instrucciones de diseño

---

## Notas del negocio (contexto para el LLM)

- Los prospectos objetivo son negocios locales pequeños en México (CDMX / EDOMEX principalmente)
- El canal más efectivo para contacto sin email es WhatsApp al número de Maps
- Para negocios completamente offline (sin email, sin redes), el PDF imprimible es el entregable clave — se lleva en persona
- El score de oportunidad es la métrica más importante — priorizar siempre score >= 7
- Las landings generadas son demostraciones, no sitios finales — deben verse bien pero son para mostrar el potencial
