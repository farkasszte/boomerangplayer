# Boomerang Player

A high-performance, frame-accurate Windows 11 style video player designed for professional analysis, looping, and variable-speed playback.

![Main Interface](https://raw.githubusercontent.com/user-attachments/assets/your-screenshot-here)

## Key Features

- **RAM-Resident Playback**: Extract videos to RAM for lag-free, frame-perfect scrubbing and looping.
- **Variable Speed Control**: Smooth playback from 10% to 400% speed using real-time synchronization.
- **Frame-Accurate Markers**: Set loop start and end points precisely on specific frames.
- **Ping-Pong Looping**: Seamlessly bounce playback between markers.
- **Smart Playlist**: Drag-and-drop support with high-quality thumbnails (including blurred backgrounds for portrait videos).
- **Windows 11 Aesthetics**: Fluent Design interface with dark mode support.
- **Zoom & Pan**: Interactive zoom with smooth panning for detailed inspection.
- **Export Segments**: Save marked loops as new video files using lossless or high-quality encoding.

## Installation

### Prerequisites
- Python 3.10+
- `ffmpeg` and `ffprobe` (included in the release or should be in your PATH)

### Setup
1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd win11-video-player
   ```
2. Install dependencies:
   ```bash
   pip install PyQt6 PyQt6-QtMultimedia PyQt6-QtMultimediaWidgets qfluentwidgets
   ```

## Usage

1. Run the application:
   ```bash
   python main.py
   ```
2. Drag and drop videos into the playlist or use the **Add** button.
3. Use `[` and `]` or the UI buttons to set loop markers.
4. Adjust speed and zoom using the sliders in the bottom panel.

## Building for Distribution

To create a single-file EXE:
1. Ensure `ffmpeg.exe` and `ffprobe.exe` are in the root directory.
2. Run the build script:
   ```bash
   python build_dist.py
   ```
3. Find your EXE in the `dist/` folder.

## License
MIT
