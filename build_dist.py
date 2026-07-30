import os
import shutil
import sys
import traceback

# Final EXE name
APP_NAME = "BoomerangPlayer"

# Ensure running within the virtual environment (.venv)
venv_py = os.path.abspath(os.path.join(os.path.dirname(__file__), ".venv", "Scripts", "python.exe"))
if os.path.exists(venv_py) and os.path.normpath(sys.executable).lower() != os.path.normpath(venv_py).lower():
    print(f"Re-executing with virtual environment python: {venv_py}")
    os.execv(venv_py, [venv_py] + sys.argv)

try:
    print(f"Building {APP_NAME}...")

    # Move non-standard imports inside try block to catch ImportError/ModuleNotFoundError
    import PyInstaller.__main__  # type: ignore

    # Check for ffmpeg and ffprobe
    ffmpeg_found = os.path.exists("ffmpeg.exe")
    ffprobe_found = os.path.exists("ffprobe.exe")

    if not ffmpeg_found or not ffprobe_found:
        print("Warning: ffmpeg.exe or ffprobe.exe not found in current directory!")
        print("They will not be bundled. The app will rely on system PATH.")

    args = [
        'main.py',
        '--onefile',           # Single EXE
        '--windowed',          # No console window
        f'--name={APP_NAME}',
        '--icon=resources/app_icon.ico',
        '--add-data=resources;resources', # Bundle resources folder including SVGs and window icon
        '--runtime-tmpdir=%TEMP%\\BoomerangPlayer',
        '--clean',
    ]

    # Exclude heavy machine learning and scientific modules to keep the build size minimal (~147MB)
    excludes = [
        'torch', 'torchvision', 'torchaudio', 'scipy', 'pandas', 'sklearn', 'cv2',
        'matplotlib', 'pyarrow', 'lxml', 'openpyxl', 'jinja2', 'numba',
        'llvmlite', 'lz4', 'fsspec', 'astropy', 'PIL', 'h5py', 'sympy', 'IPython',
        'yt_dlp', 'requests', 'urllib3', 'curl_cffi', 'brotli', 'mutagen', 'secretstorage',
        'Cryptodome'
    ]
    for ex in excludes:
        args.append(f'--exclude-module={ex}')

    # Add binaries if they exist
    if ffmpeg_found:
        args.append('--add-binary=ffmpeg.exe;.')
    if ffprobe_found:
        args.append('--add-binary=ffprobe.exe;.')

    # Run PyInstaller
    PyInstaller.__main__.run(args)

    print("\nBuild finished!")
    print(f"Your single EXE file is in the 'dist' folder: dist/{APP_NAME}.exe")

except SystemExit as se:
    if se.code != 0:
        print(f"\nPyInstaller exited with error code: {se.code}")
    else:
        print("\nBuild finished successfully!")
except BaseException as e:
    print("\nError occurred during build:")
    traceback.print_exc()
finally:
    input("\nPress Enter to exit...")
