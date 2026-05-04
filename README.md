# Prospector Web — RAIO Development

Sistema de prospección de clientes para agencia de desarrollo web. Busca negocios locales en Google Maps que no tienen página web (o la tienen desactualizada), enriquece sus datos de contacto, genera una landing de muestra con Claude, y exporta a Excel o PDF imprimible para presentar la propuesta al cliente.

## Etapa actual: MVP (Etapa 1)

- ✅ Búsqueda de negocios (con datos mock para probar la UI sin API keys)
- ✅ Scoring de oportunidad 1–10
- ✅ Sugerencia automática de canal de contacto (email / WhatsApp / Facebook / visita)
- ✅ Tabla y detalles en Streamlit
- 🔜 Enriquecimiento de email (Outscraper / Hunter)
- 🔜 Generación de landing con Claude
- 🔜 Export Excel + PDF

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
│   ├── enrich.py       ← (próximo) email enrichment
│   └── landing.py      ← (próximo) landing con Claude
├── export/
│   ├── excel.py        ← (próximo)
│   └── pdf_proposal.py ← (próximo)
└── outputs/
    ├── landings/
    ├── excel/
    └── pdf/
```
