# Prospector Web — RAIO Development

Sistema de prospección de clientes para agencia de desarrollo web. Busca negocios locales en Google Maps que no tienen página web (o la tienen desactualizada), enriquece sus datos de contacto, genera una landing de muestra con Claude, y exporta a Excel o PDF imprimible para presentar la propuesta al cliente.

## Estado: MVP completo

- ✅ Búsqueda de negocios (mock + Google Places listo)
- ✅ Scoring de oportunidad 1–10
- ✅ Canal de contacto automático (email / WhatsApp / Facebook / visita)
- ✅ Enriquecimiento de email (scrape + Outscraper + Hunter, todos con mock)
- ✅ Generación de landing con Claude (mock con 11 paletas por categoría)
- ✅ Export Excel con dropdown de estado y colores por score
- ✅ PDF imprimible 1 página A4 para visita presencial
- ✅ Vista previa de landing embebida en la app

## Requisitos

- Python 3.10+
- pip

## Instalación

```bash
pip install -r requirements.txt
cp .env.example .env
```

El `.env` ya viene con `USE_MOCK_DATA=true`, así que **puedes correr la app sin ninguna API key** y ver datos de prueba.

## Correr la app

```bash
streamlit run app.py
```

Se abre en `http://localhost:8501`.

## API keys (cuando vayas a producción)

| Variable | Para qué | Tier gratuito |
|---|---|---|
| `GOOGLE_PLACES_API_KEY` | Búsqueda de negocios reales | $200/mes |
| `OUTSCRAPER_API_KEY` | Email del negocio (1ª opción) | Sí, limitado |
| `HUNTER_API_KEY` | Email del negocio (fallback) | 25/mes |
| `ANTHROPIC_API_KEY` | Generar landings con Claude | Sin tier gratis |

Cuando tengas alguna, ponla en `.env` y cambia `USE_MOCK_DATA=false`.

## Estructura

```
prospector-web/
├── app.py              ← entrada Streamlit
├── config.py           ← carga .env y constantes
├── core/
│   ├── search.py       ← búsqueda en Google Places (+ mock)
│   ├── score.py        ← scoring de oportunidad
│   ├── contact.py      ← canal de contacto óptimo
│   ├── enrich.py       ← email enrichment (scrape + Outscraper + Hunter)
│   └── landing.py      ← landing HTML con Claude
├── export/
│   ├── excel.py        ← export Excel con dropdown y colores
│   └── pdf_proposal.py ← PDF imprimible A4
└── outputs/
    ├── landings/
    ├── excel/
    └── pdf/
```
