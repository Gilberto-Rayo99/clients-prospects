"""Contenido del FAQ / Ayuda embebido en la app."""

HELP_SECTIONS = [
    {
        "title": "🆕 Novedades de este release",
        "content": """
**D. 🎯 Diversificar por nicho en lotes (prompts y PDFs)**
- Tanto en "📋 Prompts en lote" como en "📄 PDFs en lote" hay un nuevo checkbox **"🎯 Diversificar por nicho — top N por categoría"**.
- Al activarlo, en lugar de exportar 10 prompts del mismo giro, te da **uno (o N) por categoría disponible** — el de mayor score dentro de cada nicho.
- Útil para campañas balanceadas: probar mensaje con dentista + barbería + veterinaria + cafetería simultáneamente sin spamear un solo nicho.
- Ej: tienes 30 clientes filtrados en 6 categorías → con N=1 te quedan 6 (uno mejor de cada). Con N=3 → 18 (los 3 mejores de cada).

**C. 📄 Propuestas PDF rediseñadas + lote**
- El PDF de propuesta ahora es **mucho más profesional**: hero con rating en estrellas grandes, bloque de diagnóstico cuantificado (PageSpeed cacheado si lo analizaste), QR a la landing publicada (si tiene netlify_url), beneficios por giro, precio cotizado del cliente.
- **Si tienes URL Netlify para el cliente**, el PDF lleva un QR escaneable — el prospecto saca el celular, escanea, ve la demo. Impacto enorme en visitas presenciales.
- Pestaña **📤 Exportar → 📄 Propuestas PDF en lote** con los mismos filtros que prompts (estado, categoría, score, web, email) + filtro extra "Solo con landing publicada (QR funcional)". Genera N PDFs en un zip plano.

**B. 📲 Cierre de ciclo en bulk upload**
- Después de **💾 Guardar N landings** en la carga masiva aparece una lista **"📲 Listos para mandar"** con cada cliente recién cargado.
- Cada fila trae: estado actual + URL Netlify + botón **📲 WhatsApp** (con plantilla y URL ya rellenadas) + ✅ para marcar como enviado en un click.
- Botón al pie: **🚀 Pre-cargar N en Automatización** que pasa los IDs a la pestaña 🔄 Automatización con filtros deshabilitados — perfecto para procesar el lote en una sola corrida sin reseleccionar nada.

**A. 📋 Estructura del prompt simplificada (TXT plano)**
- Tanto el botón individual como el lote ahora generan **`.txt` plano** (no zip-de-zips, no subcarpetas).
- El nombre del archivo es el slug del negocio (ej. `el-lugar-de-victor.txt`).
- **Truco**: cuando claude.ai te devuelva el HTML, guárdalo con **el mismo nombre** + `.html` (`el-lugar-de-victor.html`). Al subirlo en la **carga masiva** el fuzzy match acierta al 100% sin revisión manual.

**0. ⚡ PageSpeed Insights — argumento de venta automático**
- En **👥 Mis clientes → Datos del negocio**, si el cliente tiene web aparece un botón **"🔄 Analizar con PageSpeed"**.
- Llama a la API gratis de Google (25k req/día) y trae el score real: móvil + desktop, LCP, FCP.
- Si el score móvil es <50, la app **selecciona automáticamente la plantilla "⚡ Inicial — web lenta"** que mete la frase: *"Tu sitio actual saca 23/100 en velocidad móvil según Google…"*. Pitch brutal.
- Resultado cacheado 30 días — un análisis dura todo el mes.
- API key opcional en `PAGESPEED_API_KEY` (sube cuota). Sin key también funciona, con cuota reducida.

**0b. 🔔 Cola de follow-ups automática**
- Al entrar a **👥 Mis clientes** verás un banner arriba: *"3 clientes necesitan follow-up"*.
- Lista clientes en estado `Mensaje enviado` ≥ 7 días, `Llamada/visita` ≥ 3 días, `Propuesta enviada` ≥ 5 días, etc.
- Click en **Abrir** → salta al cliente con la plantilla de follow-up ya seleccionada. Ahorra 10-20 min/día y duplica la tasa de respuesta.

**1. Imágenes a medida con Gemini Nano Banana (opcional, paid tier)**
- Cada landing puede llevar **8 fotos generadas a medida** del giro real del negocio.
- ⚠️ `gemini-2.5-flash-image` **NO está en free tier** (Google cambió las reglas). Costo: **~$0.039 USD/img × 8 = ~$0.31/paquete**.
- Para activarlo: https://aistudio.google.com/ → Settings → Plan → Upgrade. Sin upgrade la app cae a Unsplash automáticamente.
- Si solo quieres landings sin fotos a medida, **deja la key vacía** y todo funciona con Unsplash.

**2. Lote en paralelo**
- Pestaña Exportar → "📦 Paquetes premium en lote" genera **hasta 10 paquetes en paralelo** (1-3 min para 10 clientes).
- Cap dinámico: solo procesa los que entran en tu cupo Gemini de hoy.

**3. Auto-publicar a Netlify**
- Al subir un HTML, hay un toggle "🚀 Auto-publicar a Netlify" → guarda + publica + URL pública en un solo click.
- También funciona en la **carga masiva**: marca el toggle y publica todas a la vez.

**4. Bulk upload con auto-asignación inteligente**
- Si los nombres de archivo coinciden ≥85% con un cliente, se asignan **solo**. Solo revisas los ambiguos.

**5. Recalcular scores en bloque**
- Pestaña Exportar → botón "🔄 Recalcular scores de todos" si cambias el algoritmo.

**6. Búsqueda 10× más rápida**
- El enriquecimiento de prospectos ahora corre en paralelo (8 hilos): **5 min → 30 s** para 12 prospectos.

**7. Prompt v2 más rico**
- El prompt detecta automáticamente nivel de precio y horarios cuando Google Places los devuelve, y forza variación visual entre prospectos similares.
""",
    },
    {
        "title": "¿Qué hace esta app?",
        "content": """
Prospector Web busca negocios locales en Google Maps que no tienen página web o la tienen desactualizada,
les genera una landing de muestra y te arma el mensaje de WhatsApp listo para enviar.

**Flujo completo:**
1. Buscas negocios en una zona → la app calcula quién es mejor prospecto
2. Guardas los que te interesan como clientes
3. Generas el prompt → lo pegas en claude.ai → descargas el HTML
4. La app publica la landing en Netlify (link público automático)
5. Das click en "Abrir WhatsApp" → el mensaje con precio y link ya viene escrito
6. Marcas como enviado → sigues el seguimiento desde "Mis clientes"
""",
    },
    {
        "title": "¿Cómo arrancar la app?",
        "content": """
**Opción A — Versión web (acceso desde cualquier dispositivo)**
- Entra a la URL que te compartió Gilberto desde cualquier navegador, celular o computadora
- No necesitas instalar nada — funciona directo en el navegador
- Tus datos se guardan en la nube (Supabase) y están disponibles desde donde sea

**Opción B — Icono en el escritorio (local)**
- Doble clic en **"Prospector Web"** en el escritorio
- Espera ~15 segundos → el navegador se abre solo en `http://localhost:8501`
- La ventana negra que aparece es normal — es el servidor. No la cierres.

**Opción C — Terminal**
```
cd "...ruta del proyecto..."
streamlit run app.py
```
""",
    },
    {
        "title": "¿Cómo buscar prospectos?",
        "content": """
1. En el **sidebar izquierdo**: escribe la zona (ej. "Naucalpan, EDOMEX"), ajusta el radio y elige la categoría
2. Selecciona el **Filtro inteligente** — "Top prospects" es el recomendado
3. Click en **Buscar prospectos**
4. Usa los **Filtros locales** (arriba de la tabla) para afinar: score mínimo, solo sin web, solo con email, etc.
5. Da click en **💾 Guardar** en los que quieras trabajar (o usa "Guardar en lote" para varios a la vez)

**Score 1–10:** mientras más alto mejor. 8–10 (verde) son prioridad. Toma en cuenta si tienen web, rating, reseñas y categoría.
""",
    },
    {
        "title": "¿Cómo generar una landing y mandar WhatsApp?",
        "content": """
Hay **dos modos**: rápido (sin imágenes a medida) y premium (con fotos generadas por IA).

**🅰️ Modo rápido (Unsplash, sin gastar cuota Gemini):**
1. **👥 Mis clientes** → selecciona el cliente
2. Sub-pestaña **📋 Prompt para Claude** → bloque "🅰️ Prompt rápido" → copia el texto
3. Abre **claude.ai** → pega el prompt → descarga el HTML
4. Regresa a la app → sub-pestaña **📥 Cargar HTML** → sube el archivo
5. Marca **🚀 Auto-publicar a Netlify al guardar** si quieres link público al instante

**🅱️ Modo premium (con imágenes generadas a medida con Gemini):**
1. Mismo lugar, bloque "🅱️ Paquete premium" → click **📦 Generar paquete**
2. Espera ~1-2 min mientras Gemini genera 8 fotos del giro real
3. Click **⬇️ Descargar zip** → descomprime el archivo
4. En **claude.ai**, nuevo chat: arrastra `prompt.txt` + todas las imágenes de `img/`
5. Pídele "Sigue las instrucciones del prompt.txt y genera el HTML completo"
6. Guarda el HTML como `index.html` **junto a la carpeta `img/`** del zip
7. Vuelve a la app y súbelo en **📥 Cargar HTML**

**Mensaje WhatsApp (igual para ambos modos):**
- Elige plantilla → pega la URL Netlify (si ya publicaste) → click **📲 Abrir WhatsApp**
- Revisa, manda → click **✅ Marcar como enviado**
""",
    },
    {
        "title": "¿Qué es el lote premium y cómo lo uso?",
        "content": """
Si quieres procesar **varios clientes al mismo tiempo** con imágenes Gemini:

1. Pestaña **📤 Exportar** → sección **📦 Paquetes premium en lote**
2. Filtra por estado (ej. solo "Pendiente" o "Falta landing")
3. La app te dice cuántos paquetes alcanzan con tu cupo Gemini de hoy (100/día gratis)
4. Click **📦 Generar N paquetes en paralelo** → ~1-3 min para 10 paquetes
5. Click **⬇️ Descargar zip-de-zips** → te da un .zip con todos los paquetes adentro
6. Descomprime → cada subcarpeta tiene su `prompt.txt` + `img/`
7. Procesa cada uno en claude.ai como en el modo premium individual

**Tip:** este modo aprovecha que las imágenes Gemini se generan en paralelo (10 a la vez), así que es mucho más rápido que hacer cada paquete uno por uno.
""",
    },
    {
        "title": "¿Cómo cargar muchos HTML de claude.ai a la vez?",
        "content": """
Cuando ya descargaste varios HTML de claude.ai (uno por cliente):

1. Pestaña **📤 Exportar** → sección **📤 Carga masiva de landings**
2. Arrastra todos los `.html` al uploader (puedes seleccionar múltiples)
3. La app **auto-asigna** los archivos al cliente correcto si el nombre del archivo coincide ≥85% con el nombre del cliente
4. Los que tienen menos del 85% aparecen para revisión manual
5. Marca **🚀 Auto-publicar a Netlify** si quieres que cada landing se publique al guardar
6. Click **💾 Guardar N landing(s)**

**Tip:** nombra los archivos como el cliente (ej. `tacos-el-compa.html`) para que el fuzzy match acierte sin que tengas que revisar nada.
""",
    },
    {
        "title": "¿Qué es Netlify y cómo publicar la landing?",
        "content": """
**Netlify** es el servicio donde se publica la landing para que el cliente pueda verla desde su celular.
Es gratuito y ya está configurado.

**Opción A — Automático (desde Automatización masiva)**
- La app sube el HTML y te devuelve el link automáticamente

**Opción B — Manual (30 segundos)**
1. Ve a https://app.netlify.com/drop en otra pestaña
2. Arrastra el archivo `.html` que descargaste de claude.ai
3. Netlify te da un link tipo `https://nombre.netlify.app`
4. Pega ese link en el campo "URL Netlify" de la app

Ese link es lo que mandas al cliente en WhatsApp para que vea la demo.
""",
    },
    {
        "title": "¿Qué hace la pestaña Automatización?",
        "content": """
Sirve para procesar **muchos clientes de un jalón**.

**Fase A — Los que ya tienen landing:**
1. Sube el Excel exportado → click "Importar"
2. Ajusta filtros (score, estado, categoría)
3. Click "Iniciar pipeline" → publica todas las landings en Netlify + arma todos los mensajes WhatsApp
4. Aparece la lista de listos → das click en "Enviar" uno por uno

**Fase B — Los que no tienen landing:**
- La app te los muestra con su prompt
- Generas el HTML en claude.ai y lo subes
- Luego vuelves a correr Fase A

**Importante:** necesitas haber cargado el HTML de la landing a cada cliente antes de que Fase A lo procese.
""",
    },
    {
        "title": "¿Cómo exportar a Excel o PDF?",
        "content": """
**Excel:**
- Pestaña **📤 Exportar** → "Exportar a Excel"
- El archivo tiene 3 hojas: Prospectos (con todos los datos), Prompts para Claude (listo para copiar), Resumen

**PDF de propuesta:**
- En **👥 Mis clientes** → sección PDF → "Generar PDF"
- Es una hoja A4 imprimible con datos del negocio, propuesta de valor y tus datos de contacto
- Útil para visitas presenciales

Los archivos se guardan en la carpeta `outputs/` junto al ejecutable.
""",
    },
    {
        "title": "¿Cómo dar seguimiento a los clientes?",
        "content": """
En **👥 Mis clientes**, cada cliente tiene:

- **Estado** (pipeline): Pendiente → Mensaje enviado → Respondió → Llamada/visita → Propuesta enviada → Negociación → Cerrado
- **Próximo contacto**: fecha para hacer follow-up
- **Precio cotizado**: cuánto le dijiste
- **Notas**: campo libre para escribir lo que pasó en cada contacto

**Tip:** después de cada interacción actualiza el estado y escribe una nota corta. Cuando vuelvas a abrir la app sabes exactamente dónde quedaste con cada uno.
""",
    },
    {
        "title": "¿Dónde se guardan mis datos?",
        "content": """
Tus clientes y todo el seguimiento se guardan en **Supabase**, una base de datos en la nube.

Esto significa:
- ✅ Tus datos están disponibles desde cualquier dispositivo o navegador
- ✅ No se pierden si reinicias la computadora o el servidor
- ✅ Si usas la versión web y la versión local al mismo tiempo, ambas ven los mismos datos
- ✅ El servicio es gratuito para el volumen que usamos

Las landings HTML también se guardan ahí, por lo que no necesitas archivos locales para verlas o reenviarlas.

**Nota:** los archivos PDF se generan en el momento — no se guardan permanentemente, se descargan directo.
""",
    },
    {
        "title": "Algo no funciona, ¿qué hago?",
        "content": """
**La app no abre:**
- Cierra la ventana negra si está abierta y vuelve a hacer doble clic al icono
- Si sigue sin abrir, abre una terminal y corre `streamlit run app.py`

**"No encontró negocios":**
- Verifica que la zona esté bien escrita (ej. "Coyoacán, CDMX" no "coyoacan")
- Cambia el filtro a "Todos" para ver si hay resultados sin filtrar
- Aumenta el radio de búsqueda

**El mensaje de WhatsApp no abre:**
- Verifica que el número del cliente tenga 10 dígitos
- Asegúrate de tener WhatsApp Web abierto en el navegador

**Error al subir HTML:**
- El archivo debe ser el `.html` descargado directo de claude.ai
- No debe estar dentro de una carpeta zip

**Contacto:**
Gilberto Rayo — RAIO Development
55 4117 7890 · raio-agency.support@gmail.com
""",
    },
]
