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
    '--clean',
]

# Add binaries if they exist
if ffmpeg_found:
    args.append('--add-binary=ffmpeg.exe;.')
if ffprobe_found:
    args.append('--add-binary=ffprobe.exe;.')

# Run PyInstaller
PyInstaller.__main__.run(args)

print("\nBuild finished!")
print(f"Your single EXE file is in the 'dist' folder: dist/{APP_NAME}.exe")
