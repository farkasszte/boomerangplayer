# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[('ffmpeg.exe', '.'), ('ffprobe.exe', '.')],
    datas=[('resources', 'resources')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['torch', 'torchvision', 'torchaudio', 'scipy', 'pandas', 'sklearn', 'cv2', 'matplotlib', 'pyarrow', 'lxml', 'openpyxl', 'jinja2', 'numba', 'llvmlite', 'lz4', 'fsspec', 'astropy', 'PIL', 'h5py', 'sympy', 'IPython', 'yt_dlp', 'requests', 'urllib3', 'curl_cffi', 'brotli', 'mutagen', 'secretstorage', 'Cryptodome'],
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
    name='BoomerangPlayer',
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
    icon=['resources/app_icon.ico'],
)
