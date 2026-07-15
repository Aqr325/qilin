# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for backend.exe
Packages backend_entry.py + entire app/ package into a single windowed EXE.

Strategy:
- backend_entry.py is the single entry point (script)
- All app/ submodules are auto-discovered via hiddenimports
- app/ source files are packaged into the PyZ archive (not as datas)
- alembic/ directory is bundled as datas (templates + env.py)
- No console window (console=False)
"""
import os
import sys
from PyInstaller.utils.hooks import collect_submodules

try:
    BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
except NameError:
    # 某些 PyInstaller 调用方式不会向 spec 命名空间注入 __file__，回退到当前工作目录
    BACKEND_DIR = os.getcwd()

# Collect ALL app/ submodules dynamically
app_hidden_imports = collect_submodules('app')

# Plus uvicorn and web framework imports
extra_hidden_imports = [
    'uvicorn',
    'uvicorn.logging',
    'uvicorn.config',
    'uvicorn.loops',
    'uvicorn.loops.auto',
    'uvicorn.protocols',
    'uvicorn.protocols.http',
    'uvicorn.protocols.http.auto',
    'uvicorn.protocols.websockets',
    'uvicorn.protocols.websockets.auto',
    'uvicorn.lifespan',
    'uvicorn.lifespan.on',
    'aiosqlite',
    'sqlalchemy',
    'sqlalchemy.ext.asyncio',
    'sqlalchemy.ext.baked',
    'sqlalchemy.future',
    'sqlalchemy.orm',
    'sqlalchemy.pool',
    'sqlalchemy.dialects.sqlite',
    'sqlalchemy.dists.postgresql',
    'sqlalchemy.sql',
    'sqlalchemy.sql.default_comparator',
    'sqlalchemy.event',
    'sqlalchemy.schema',
    'sqlalchemy.types',
    'pydantic',
    'pydantic.networks',
    'pydantic_extra_types',
    'pydantic_settings',
    'jose',
    'jose.jwt',
    'jose.backends',
    'jose.backends.base',
    'passlib',
    'passlib.handlers',
    'passlib.handlers.bcrypt',
    'bcrypt',
    'httpx',
    'yaml',
    'jinja2',
    'jinja2.ext',
    'jinja2.defaults',
    'jinja2.asyncsupport',
    'mako',
    'mako.ext',
    'mako.ext.autoflushgen',
    'mako.ext.bzipp2gen',
    'mako.ext.gzipgen',
    'mako.ext.htmlgen',
    'mako.ext.parsegen',
    'mako.ext.pyfilter',
    'mako.ext.pylons',
    'mako.ext.twistedwebgen',
    'mako.ext.xssfilter',
    'mako.ext.zipp2gen',
    'mako.cache',
    'mako.cmd',
    'mako.compat',
    'mako.exceptions',
    'mako.ext.autoflushgen',
    'mako.ext.bzipp2gen',
    'mako.ext.gzipgen',
    'mako.ext.htmlgen',
    'mako.ext.parsegen',
    'mako.ext.pyfilter',
    'mako.ext.pylons',
    'mako.ext.twistedwebgen',
    'mako.ext.xssfilter',
    'mako.ext.zipp2gen',
    'mako.filters',
    'mako.functions',
    'mako.lexYaccParser',
    'mako.parsetree',
    'mako.parsing',
    'mako.pycompat',
    'mako.readme',
    'mako.remapper',
    'mako.saxutils',
    'mako.sentinel',
    'mako.testing',
    'mako.util',
    'alembic',
    'alembic.config',
    'alembic.operations',
    'alembic.runtime',
    'alembic.script',
    'alembic.template',
    'alembic.ddl',
    'alembic.ddl.impl',
    'alembic.ddl.mssql',
    'alembic.ddl.mysql',
    'alembic.ddl.oracle',
    'alembic.ddl.pg',
    'alembic.ddl.plat',
    'alembic.ddl.postgresql',
    'alembic.ddl.sqlite',
    'opentelemetry',
    'opentelemetry.api',
    'opentelemetry.sdk',
    'websockets',
    'websockets.http',
    'websockets.http11',
    'websocket',
    'starlette',
    'starlette.requests',
    'starlette.responses',
    'starlette.routing',
    'starlette.middleware',
    'starlette.middleware.cors',
    'starlette.staticfiles',
    'fastapi',
    'fastapi.responses',
    'fastapi.security',
    'fastapi.encoders',
    'typing_extensions',
    'email_validator',
    'annotated_types',
    'dnspython',
    'dns',
    'dns.name',
    'dns.rdata',
    'dns.rdtypes',
    'certifi',
    'charset_normalizer',
    'idna',
    'urllib3',
    'requests',
    'requests.adapters',
    'requests.utils',
    'requests.structures',
    # aiohttp (runtime import inside ai_service._call_model_api for real model calls)
    'aiohttp',
    'aiohttp.client',
    'aiohttp.client_exceptions',
    'aiohttp.client_proto',
    'aiohttp.connector',
    'aiohttp.http',
    'aiohttp.http_parser',
    'aiohttp.http_websocket',
    'aiohttp.streams',
    'aiohttp.web',
    'aiohttp.web_protocol',
    'multidict',
    'yarl',
    'attr',
    'attrs',
    'async_timeout',
    'frozenlist',
    'aiosignal',
    'aiohappyeyeballs',
    'propcache',
    'h11',
    'h2',
    'h2.connection',
    'h2.events',
    'h2.settings',
    'h2.streams',
    'hyperframe',
    'hyperframe.frame',
    'httpcore',
    'httpcore._async',
    'httpcore._sync',
    'anyio',
    'anyio._backends',
    'sniffio',
    'trio',
    'trio._core',
    'exceptiongroup',
    'packaging',
    'packaging.version',
    'packaging.utils',
    'markupsafe',
    'pycparser',
    'cffi',
    'cffi.backend_ctypes',
    'cffi.cffi_opcode',
    'cffi.commontypes',
    'cffi.error',
    'cffi.ffiplatform',
    'cffi.lock',
    'cffi.model',
    'cffi.parser',
    'cffi.recompiler',
    'cffi.setuptools_ext',
    'cffi.vengine_gen',
    'cryptography',
    'cryptography.hazmat',
    'cryptography.hazmat.primitives',
    'cryptography.hazmat.primitives.asymmetric',
    'cryptography.hazmat.primitives.asymmetric.rsa',
    'cryptography.hazmat.primitives.asymmetric.ec',
    'cryptography.hazmat.primitives.asymmetric.ed25519',
    'cryptography.hazmat.primitives.asymmetric.ed448',
    'cryptography.hazmat.primitives.asymmetric.x448',
    'cryptography.hazmat.primitives.asymmetric.x25519',
    'cryptography.hazmat.primitives.asymmetric.padding',
    'cryptography.hazmat.primitives.asymmetric.utils',
    'cryptography.hazmat.primitives.ciphers',
    'cryptography.hazmat.primitives.ciphers.algorithms',
    'cryptography.hazmat.primitives.ciphers.modes',
    'cryptography.hazmat.primitives.hashes',
    'cryptography.hazmat.primitives.serialization',
    'cryptography.hazmat.backends',
    'cryptography.hazmat.backends.openssl',
    'cryptography.hazmat.backends.openssl.backend',
    'cryptography.hazmat.backends.openssl.aead',
    'cryptography.hazmat.backends.openssl.biometric',
    'cryptography.hazmat.backends.openssl.cmac',
    'cryptography.hazmat.backends.openssl.constant_time',
    'cryptography.hazmat.backends.openssl.hkdf',
    'cryptography.hazmat.backends.openssl.hmac',
    'cryptography.hazmat.backends.openssl.ocsp',
    'cryptography.hazmat.backends.openssl.poly1305',
    'cryptography.hazmat.backends.openssl.rand',
    'cryptography.hazmat.backends.openssl.x509',
    'openssl',
    'setuptools',
    'pkg_resources',
    'zope.interface',
    ]

# greenlet is required by sqlalchemy for async support — must NOT be excluded
extra_hidden_imports.append('greenlet')
extra_hidden_imports.append('greenlet.context')
extra_hidden_imports.append('greenlet.hierarchy')
extra_hidden_imports.append('greenlet.std_context')

# psutil for local-status endpoint
extra_hidden_imports.append('psutil')

hidden_imports = list(app_hidden_imports) + list(set(extra_hidden_imports))

# Alembic assets to bundle
datas = []
ALEMBIC_DIR = os.path.join(BACKEND_DIR, 'alembic')
ALEMBIC_INI = os.path.join(BACKEND_DIR, 'alembic.ini')

if os.path.isdir(ALEMBIC_DIR):
    for root, dirs, files in os.walk(ALEMBIC_DIR):
        for f in files:
            src = os.path.join(root, f)
            dst = os.path.relpath(src, BACKEND_DIR)
            datas.append((src, os.path.dirname(dst)))

if os.path.isfile(ALEMBIC_INI):
    datas.append((ALEMBIC_INI, '.'))

a = Analysis(
    ['backend_entry.py'],
    pathex=[BACKEND_DIR],
    binaries=[],
    datas=datas,
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
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='backend',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,        # ← windowed mode, no console
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    contents_directory='.',
)
