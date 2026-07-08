# -*- mode: python ; coding: utf-8 -*-
import os
import sys
from PyInstaller.utils.hooks import collect_submodules, collect_all

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.join(PROJECT_DIR, 'kylin-secops-agent', 'backend')

# Collect ALL app/ submodules dynamically
app_hidden_imports = collect_submodules('app') if os.path.isdir(BACKEND_DIR) else []

# Core dependencies needed by backend
extra_hidden_imports = [
    'aiosqlite',
    'greenlet',
    'greenlet.context',
    'greenlet.hierarchy',
    'greenlet.std_context',
    'sqlalchemy',
    'sqlalchemy.ext.asyncio',
    'sqlalchemy.ext.baked',
    'sqlalchemy.orm',
    'sqlalchemy.pool',
    'sqlalchemy.dialects.sqlite',
    'sqlalchemy.dialects.postgresql',
    'sqlalchemy.sql',
    'sqlalchemy.event',
    'sqlalchemy.schema',
    'sqlalchemy.types',
    'sqlalchemy.ext.compiler',
    'sqlalchemy.future',
    'fastapi',
    'fastapi.responses',
    'fastapi.security',
    'fastapi.encoders',
    'uvicorn',
    'uvicorn.logging',
    'uvicorn.config',
    'uvicorn.lifespan',
    'uvicorn.lifespan.on',
    'uvicorn.loops',
    'uvicorn.loops.auto',
    'pydantic',
    'pydantic.networks',
    'pydantic_extra_types',
    'pydantic_settings',
    'starlette',
    'starlette.middleware',
    'starlette.middleware.cors',
    'jose',
    'jose.jwt',
    'jose.backends',
    'jose.backends.base',
    'passlib',
    'passlib.handlers',
    'passlib.handlers.bcrypt',
    'bcrypt',
    'httpx',
    'websockets',
    'websocket',
    'mako',
    'mako.cache',
    'mako.exceptions',
    'mako.filters',
    'mako.parsetree',
    'mako.parsing',
    'mako.util',
    'alembic',
    'alembic.config',
    'alembic.operations',
    'alembic.runtime',
    'alembic.script',
    'alembic.template',
    'alembic.ddl',
    'alembic.ddl.sqlite',
    'alembic.ddl.postgresql',
    'alembic.ddl.mysql',
    'yaml',
    'jinja2',
    'jinja2.ext',
    'cryptography',
    'cryptography.hazmat',
    'cryptography.hazmat.primitives',
    'cryptography.hazmat.primitives.serialization',
    'packaging',
    'markupsafe',
    'certifi',
    'charset_normalizer',
    'idna',
    'urllib3',
    'requests',
    'h11',
    'h2',
    'hyperframe',
    'httpcore',
    'anyio',
    'sniffio',
    'trio',
    'cffi',
    'pycparser',
    'zope.interface',
    'typing_extensions',
    'annotated_types',
    'email_validator',
    'dnspython',
    'dns',
    'setuptools',
    'pkg_resources',
    'exceptiongroup',
]

hidden_imports = list(app_hidden_imports) + list(set(extra_hidden_imports))

# Alembic assets
ALEMBIC_DIR = os.path.join(BACKEND_DIR, 'alembic')
ALEMBIC_INI = os.path.join(BACKEND_DIR, 'alembic.ini')

def collect_datas():
    datas = [
        (os.path.join(PROJECT_DIR, 'desktop', 'icon.png'), 'desktop/'),
        (BACKEND_DIR, 'backend/'),
    ]
    if os.path.isdir(ALEMBIC_DIR):
        for root, dirs, files in os.walk(ALEMBIC_DIR):
            for f in files:
                src = os.path.join(root, f)
                dst = os.path.relpath(src, BACKEND_DIR)
                datas.append((src, os.path.dirname(dst)))
    if os.path.isfile(ALEMBIC_INI):
        datas.append((ALEMBIC_INI, '.'))
    return datas


a = Analysis(
    ['D:/workbuddy workspace/2026-06-23-20-22-53/desktop/desktop_launcher.py'],
    pathex=[],
    binaries=[],
    datas=collect_datas(),
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'matplotlib', 'PIL', 'cv2', 'tensorflow', 'torch',
        'notebook', 'jupyter', 'ipython', 'pandas', 'numpy',
        'tkinter', 'unittest', 'pydoc',
        'asyncpg', 'psycopg2', 'psycopg2_binary',
        'celery', 'redis', 'flask', 'django',
    ],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='KylinSecOps',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
