# PyDM

PyDM is a Windows desktop download manager built with Python and PySide6. It combines a native desktop client, browser integration for Chrome and Edge, and a sequential download queue for a streamlined download workflow.

<div align="center">
  <img src="docs\assets\Screenshot 2026-08-15 193129.png" alt="PyDM main application window" width="1100" />
</div>

## Overview

PyDM lets you:

- add downloads from the desktop app or from the browser extension
- download files with a queue-based workflow
- monitor progress through a real-time download dialog
- minimize to the system tray and start with the tray option
- register the native browser host automatically on Windows
- build both portable packages and a Windows installer

## Main features

- PySide6 desktop interface with a category sidebar and download table
- Sequential queue processing via DownloadQueueManager
- Real-time progress and ETA reporting
- Tray support and Windows auto-start option
- Chrome/Edge native messaging host integration
- Redirect-aware URL and filename resolution with httpx
- Portable build and Inno Setup installer generation

## Application architecture

The project is organized around a few key modules:

- src/pydm/app.py – application entry point and startup flow
- src/pydm/ui/main_window.py – main window, tray, queue processing, and actions
- src/pydm/gui.py – progress dialog and UI helpers for downloads
- src/pydm/downloader.py – HTTP download worker logic and URL metadata handling
- src/pydm/managers/download_queue_manager.py – sequential queue management
- src/pydm/host_register.py – browser host registration and native messaging setup
- src/pydm/native_host.py – localhost bridge that receives browser URLs
- pydm-extension/ – Chrome/Edge extension files
- scripts/build_installer.py – Inno Setup installer generation
- Makefile – packaging targets for portable builds and installers

## Requirements

- Python 3.12+
- Windows 10/11
- Chrome or Edge for browser integration
- Optional: Inno Setup 6 for generating the Windows installer

## Quick start

### 1. Install dependencies

From the repository root:

```bash
uv sync
```



### 2. Start the app

```bash
uv run pydm
```

or:

```bash
python -m pydm.app
```

### 3. Start minimized to tray

```bash
uv run pydm --start-in-tray
```

You can also set:

```powershell
$env:PYDM_START_IN_TRAY = "1"
uv run pydm
```

### 4. Load the browser extension

1. Open chrome://extensions or edge://extensions
2. Enable Developer mode
3. Click Load unpacked
4. Select the pydm-extension folder in this repository

On Windows, the app will also try to register the native messaging host automatically when it starts.

## Usage flow

1. Click Add URL in the main window or send a URL from the browser extension.
2. PyDM validates the target and adds the item to the queue.
3. The queue manager starts the next download one at a time.
4. A real-time progress dialog updates speed, ETA, download size, and completion.
5. The task is marked completed and the next queued item begins automatically.

## Build and packaging

The project includes a Makefile for packaging targets.

### Portable build

```bash
make portable
```

This creates a versioned portable package under dist/.

### Installer build

```bash
make installer
```

This expects the portable build to exist and then generates a Windows installer through Inno Setup.

## Development commands

```bash
uv run pydm
python -m py_compile src/pydm/gui.py src/pydm/native_host.py
```

## Browser integration notes

The browser extension sends URLs to the native host, which in turn communicates with the desktop app over localhost. The app listens on port 8765 and accepts browser-triggered downloads while staying available in the tray.

## Troubleshooting

- If the browser extension does not send URLs, make sure the desktop app is running.
- If the host is not registered, launch PyDM on Windows and confirm browser native messaging is enabled.
- If packaging fails, verify Python dependencies are installed and Inno Setup is available for installer builds.

## Project status

This repository currently contains a functional desktop download manager with browser integration, tray support, queue management, and portable/installer packaging support.

## License

This project is provided as-is for local use and development.
