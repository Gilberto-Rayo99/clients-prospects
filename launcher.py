"""Lanzador del Prospector Web — usado por el .exe.

Arranca Streamlit en localhost:8501 y abre el navegador automáticamente.
"""
from __future__ import annotations

import os
import socket
import sys
import threading
import time
import webbrowser
from pathlib import Path


def _resource_path(rel: str) -> Path:
    """Devuelve la ruta absoluta del recurso, funcione empaquetado o no."""
    if hasattr(sys, "_MEIPASS"):
        # PyInstaller extrae a este temp dir
        return Path(sys._MEIPASS) / rel
    return Path(__file__).resolve().parent / rel


def _find_free_port(start: int = 8501) -> int:
    for port in range(start, start + 20):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    return start


def _open_browser_when_ready(url: str, timeout: int = 30) -> None:
    """Espera hasta que el puerto responda y entonces abre el navegador."""
    parsed = url.split("://")[1].split(":")
    host = parsed[0]
    port = int(parsed[1].split("/")[0])
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection((host, port), timeout=1):
                webbrowser.open(url)
                return
        except OSError:
            time.sleep(0.4)


def main() -> None:
    # Si está empaquetado, asegurar que .env y outputs/ vivan junto al .exe
    if hasattr(sys, "_MEIPASS"):
        exe_dir = Path(sys.executable).resolve().parent
        os.chdir(exe_dir)
        # Copiar .env.example si no hay .env
        env_file = exe_dir / ".env"
        if not env_file.exists():
            example = _resource_path(".env.example")
            if example.exists():
                env_file.write_text(example.read_text(encoding="utf-8"), encoding="utf-8")

    port = _find_free_port(8501)
    url = f"http://localhost:{port}"

    threading.Thread(target=_open_browser_when_ready, args=(url,), daemon=True).start()

    app_path = _resource_path("app.py")

    # Lanzar Streamlit por su CLI interno (evita reabrir browser doble)
    sys.argv = [
        "streamlit", "run", str(app_path),
        "--server.port", str(port),
        "--server.address", "127.0.0.1",
        "--server.headless", "true",
        "--browser.gatherUsageStats", "false",
        "--global.developmentMode", "false",
    ]
    from streamlit.web import cli as stcli
    sys.exit(stcli.main())


if __name__ == "__main__":
    main()
