# -*- mode: python ; coding: utf-8 -*-
"""Spec de PyInstaller para Prospector Web.

Build:
    pyinstaller build_exe.spec --noconfirm
"""
from PyInstaller.utils.hooks import (
    collect_all,
    collect_data_files,
    collect_submodules,
)

# Streamlit + dependencias necesitan que se incluyan TODOS sus archivos
# (templates, static, runtime metadata) y submódulos cargados dinámicamente.
streamlit_data, streamlit_bin, streamlit_hidden = collect_all("streamlit")
altair_data, altair_bin, altair_hidden = collect_all("altair")
pyarrow_data, pyarrow_bin, pyarrow_hidden = collect_all("pyarrow")

datas = [
    ("app.py", "."),
    ("config.py", "."),
    (".env.example", "."),
    ("core", "core"),
    ("export", "export"),
]
datas += streamlit_data + altair_data + pyarrow_data
datas += collect_data_files("googlemaps")
datas += collect_data_files("reportlab")
datas += collect_data_files("openpyxl")

binaries = streamlit_bin + altair_bin + pyarrow_bin

hiddenimports = [
    "streamlit",
    "streamlit.web",
    "streamlit.web.cli",
    "streamlit.runtime",
    "streamlit.runtime.scriptrunner.magic_funcs",
    "streamlit.web.server.websocket_headers",
    "streamlit.components.v1",
    "altair",
    "pandas",
    "googlemaps",
    "reportlab",
    "reportlab.lib",
    "reportlab.platypus",
    "openpyxl",
    "openpyxl.styles",
    "openpyxl.utils",
    "openpyxl.worksheet.datavalidation",
    "anthropic",
    "outscraper",
    "dotenv",
    "core",
    "core.search",
    "core.score",
    "core.contact",
    "core.enrich",
    "core.landing",
    "core.landing_prompt",
    "core.html_validator",
    "core.clients_store",
    "export",
    "export.excel",
    "export.pdf_proposal",
]
hiddenimports += streamlit_hidden + altair_hidden + pyarrow_hidden
hiddenimports += collect_submodules("streamlit")

block_cipher = None

a = Analysis(
    ["launcher.py"],
    pathex=["."],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "test", "unittest"],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="ProspectorWeb",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,  # Ventana de consola visible (para debug). Cambiar a False luego.
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,  # Pendiente: icon='assets/icon.ico'
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="ProspectorWeb",
)
