# PyDM

PyDM is a Windows desktop download manager with browser integration for Chrome and Edge. It lets you start downloads from a desktop app or trigger them from a browser extension, forwarding download-like URLs into a local desktop workflow with progress updates and tray support.

## What it does

- Provides a lightweight PySide6 desktop UI for entering URLs and downloading files
- Supports browser-to-app handoff through a native messaging host
- Registers the browser host automatically on Windows when the app starts
- Works with browser download-style links and redirect-based URLs
- Packages the app as a portable build or a Windows installer

## Key features

- Desktop download UI with a system tray icon
- Native messaging bridge for Chrome and Edge
- Automatic host registration and manifest generation
- Redirect-aware download handling via HTTP streaming
- Portable and installer-based packaging for Windows

## Project structure

- src/pydm/app.py – application entry point and startup logic
- src/pydm/gui.py – main PySide6 window, tray integration, and URL handling
- src/pydm/downloader.py – streaming download engine using httpx
- src/pydm/native_host.py – native messaging host used by the browser extension
- src/pydm/host_register.py – manifest generation and Windows browser registration
- pydm-extension/ – Chrome/Edge extension files
- native/ – native messaging manifest template and host assets
- scripts/build_installer.py – helper that builds the Inno Setup installer from the portable package
- Makefile – build, packaging, and installer targets

## Requirements

- Python 3.12+
- Windows 10/11
- Chrome or Edge
- Optional: Inno Setup 6 for creating the installer

## Quick start

### 1. Install dependencies

From the repository root:

```bash
uv sync
```

Or, with pip:

```bash
python -m pip install --upgrade pip
pip install -e .
```

### 2. Run the app locally

```bash
uv run pydm
```

Or:

```bash
python -m pydm.app
```

### 3. Load the browser extension

1. Open chrome://extensions or edge://extensions
2. Enable Developer mode
3. Click Load unpacked
4. Select the pydm-extension folder from this repository

When the desktop app is launched, it will attempt to register the browser host automatically on Windows.

## Build and package

The repository includes a Makefile for building packaged artifacts.

### Portable build

```bash
make portable
```

This creates a versioned portable package in dist/.

### Installer build

```bash
make installer
```

This expects the portable package to exist and creates a Windows installer using Inno Setup.

## How the flow works

1. The browser extension detects a download-like link click.
2. The link is forwarded to the native messaging host.
3. The native host sends the URL to the desktop app over localhost.
4. PyDM starts the download and shows progress in the UI.

## Development notes

Run the app directly for local testing:

```bash
uv run pydm
```

You can also check the Python sources for syntax issues with:

```bash
python -m py_compile src/pydm/gui.py src/pydm/native_host.py
```

## Troubleshooting

- If the browser extension does not forward links, make sure the desktop app is running.
- If the host registration fails, verify that the app was launched on Windows and that the browser has permission to use native messaging hosts.
- If the build fails, confirm that your environment has the required Python dependencies and, for installer builds, Inno Setup installed.

## License

This project is provided as-is for local use and development.
