# 🪃 Boomerang Player

A high-performance, frame-accurate Windows 11 style video player designed for professional analysis, looping, and variable-speed playback. 

<p align="center">
  <img src="app_icon.png" width="128" height="128" alt="Boomerang Player Icon">
</p>

## 🌟 Key Features

*   **⚡ RAM-Resident Playback**: Extract video frames directly to RAM for lag-free, frame-perfect scrubbing and looping.
*   **⏩ Variable Speed Control**: Smooth playback from **10% to 400%** speed using real-time frame synchronization.
*   **🔊 System Volume Sync**: Integrated with Windows Master Volume for seamless audio control directly from the player.
*   **🎯 Frame-Accurate Markers**: Set loop start and end points precisely on specific frames using dedicated keybindings or UI controls.
*   **🔄 Ping-Pong Looping**: Seamlessly bounce playback between markers for detailed motion analysis.
*   **🖼️ Smart Playlist**: Drag-and-drop support with high-quality thumbnails and blurred background effects for portrait videos.
*   **🎨 Windows 11 Aesthetics**: Fully compliant with Fluent Design guidelines, featuring a beautiful dark mode and glassmorphism.
*   **🔍 Zoom & Pan**: Interactive zoom with smooth panning to inspect every detail of your footage.
*   **💾 Export Segments**: Save your marked loops as high-quality video files with lossless options.

## 🚀 Getting Started

### Prerequisites
- **Python 3.10+** (3.12 recommended)
- **FFmpeg & FFprobe**: Required for frame extraction. Included in the pre-built releases.

### Installation
1. Clone the repository:
   ```bash
   git clone https://github.com/farkasszte/boomerangplayer.git
   cd win11-video-player
   ```
2. Install dependencies:
   ```bash
   pip install PyQt6 qfluentwidgets pycaw comtypes numpy
   ```

3. Run the player:
   ```bash
   python main.py
   ```

## 🛠️ Building the Distribution
To create a standalone Windows executable:
```bash
python build_dist.py
```
The resulting `BoomerangPlayer.exe` will be located in the `dist/` folder and includes all necessary dependencies (including FFmpeg).

## ⌨️ Shortcuts
| Action | Key |
| :--- | :--- |
| **Play / Pause** | `Space` |
| **Set Loop Start** | `[` |
| **Set Loop End** | `]` |
| **Toggle Loop** | `L` |
| **Next Frame** | `.` |
| **Previous Frame** | `,` |
| **Toggle Mute** | `M` |

---
*Built with ❤️ using PyQt6 and Fluent Design.*
