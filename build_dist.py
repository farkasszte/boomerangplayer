import PyInstaller.__main__
import os
import shutil

# Final EXE name
APP_NAME = "BoomerangPlayer"

print(f"Building {APP_NAME}...")

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
    '--icon=app_icon.ico',
    '--add-data=app_icon.ico;.', # Add icon to data so QIcon can load it
    '--clean',
]

# Exclude heavy machine learning and scientific modules to keep the build size minimal (~147MB)
excludes = [
    'torch', 'torchvision', 'torchaudio', 'scipy', 'pandas', 'sklearn', 'cv2',
    'matplotlib', 'numpy', 'pyarrow', 'lxml', 'openpyxl', 'jinja2', 'numba',
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
