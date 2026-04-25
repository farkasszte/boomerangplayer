# 🪃 Boomerang Player

A high-performance, frame-accurate video player built for Windows 11. Designed for professional motion analysis, sports coaching, and frame-perfect annotation.

<p align="center">
  <img src="app_icon.png" width="128" height="128" alt="Boomerang Player Icon">
</p>

## 🌟 Premium Features

*   **⚡ Dual-Direction Playback**: Independent forward and backward play buttons. Switch directions instantly with perfect state synchronization.
*   **🎯 Frame-Accurate Precision**: Powered by `ffprobe` metadata. Zero-drift playback ensures the UI, counter, and visuals are always in 100% sync.
*   **🎨 Advanced Annotations**: Professional drawing suite including lines, arrows, shapes, and text.
*   **✨ Laser Mode**: Revolutionary temporary drawing mode. Annotations and erasures vanish after interaction—perfect for live presentations and coaching.
*   **↩️ Transactional Undo**: Robust multi-step undo system that tracks every stroke, text addition, and precise eraser "bite".
*   **💾 Smart Persistence**: Remembers everything. Your last viewed frame, markers, zoom level, and color adjustments are automatically saved per video.
*   **⏩ Variable Speed Engine**: Smooth playback from **10% to 400%** using high-speed RAM caching.
*   **🔄 Multi-Segment Looping**: Create complex looping patterns with smart marker placement.
*   **🔍 Interactive Zoom & Pan**: Deep-dive into details with fluid zoom and cursor-anchored panning.
*   **🖌️ Modern Aesthetics**: Built with the latest Fluent Design guidelines. Features dark mode, glassmorphism, and smooth micro-animations.

## 🚀 Getting Started

### Prerequisites
- **Python 3.10+**
- **FFmpeg & FFprobe**: Included in pre-built releases. If running from source, ensure they are in your PATH.

### Quick Start
1. Clone the repository:
   ```bash
   git clone https://github.com/farkasszte/boomerangplayer.git
   cd win11-video-player
   ```
2. Install dependencies:
   ```bash
   pip install PyQt6 qfluentwidgets numpy
   ```
3. Launch:
   ```bash
   python main.py
   ```

## 🛠️ Building
To create a portable, single-file Windows executable:
```bash
python build_dist.py
```
*The build includes all icons, translations, and FFmpeg binaries.*

## ⌨️ Shortcuts
| Action | Key |
| :--- | :--- |
| **Play / Pause** | `Space` |
| **Add Marker** | `S` |
| **Toggle Loop Mode** | `L` |
| **Next Frame** | `.` |
| **Previous Frame** | `,` |
| **Toggle Mute** | `M` |
| **Undo Drawing** | `Ctrl + Z` |

---
*Built with ❤️ for detail-oriented professionals.*
