"""Validación ligera de HTML pegado por el usuario.

No usamos un validador estricto W3C — queremos solo bloquear pegadas accidentales
(texto plano, JSON, markdown, fragmentos vacíos).
"""
from __future__ import annotations

import re

REQUIRED_TAGS = ("html", "head", "body")
SUSPICIOUS_PATTERNS = (
    r"^\s*\{",          # JSON
    r"^\s*\[",          # JSON array
    r"^```",            # bloque markdown
    r"^Voy a generar",  # respuesta de Claude sin HTML
    r"^Aquí está",
    r"^Sure,",
    r"^Here is",
)


def validate_html(html: str) -> tuple[bool, str]:
    """Valida HTML pegado.

    Returns:
        (ok, mensaje). Si ok=False, mensaje describe el problema para mostrar al usuario.
    """
    if not html or not html.strip():
        return False, "El HTML está vacío."

    text = html.strip()

    # 1) Detectar pegadas accidentales obvias (no es HTML)
    for pat in SUSPICIOUS_PATTERNS:
        if re.match(pat, text, re.IGNORECASE):
            return False, "El contenido pegado no parece HTML — empieza como texto plano, JSON o markdown. Asegúrate de copiar solo el HTML que devolvió Claude."

    # 2) Si viene envuelto en ```html ... ```, se lo rechazamos para que el usuario quite los backticks
    if text.startswith("```"):
        return False, "Quita los bloques ``` (markdown). Pega solo el HTML, desde `<!DOCTYPE html>` hasta `</html>`."

    # 3) Comprobar que tiene las etiquetas mínimas
    lower = text.lower()
    missing = [t for t in REQUIRED_TAGS if f"<{t}" not in lower or f"</{t}>" not in lower]
    if missing:
        return False, f"Faltan etiquetas obligatorias: {', '.join(missing)}. El HTML debe ser un documento completo."

    # 4) Debe tener un balance básico de < y >
    if text.count("<") < 5 or text.count(">") < 5:
        return False, "El HTML parece muy corto o incompleto."

    # 5) DOCTYPE recomendado pero no obligatorio
    if "<!doctype" not in lower and "<!DOCTYPE" not in text:
        # Solo warning, no bloqueamos
        return True, "OK (recomendación: incluye `<!DOCTYPE html>` al inicio)."

    # Nota: no validamos balance estricto de <html>...</html> a propósito.
    # Los archivos descargados de claude.ai vienen envueltos en un visor que
    # contiene el HTML real escapado dentro de un string (\n, \"), lo que
    # produce más ocurrencias de "<html" que de "</html>" sin que sea un error.

    return True, "HTML válido."
