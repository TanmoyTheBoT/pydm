# PyDM

PyDM is a lightweight desktop download manager for Windows that lets you start downloads from a desktop app or from a browser extension. It is designed to capture download-like links from Chrome or Edge, forward them to the desktop app, and stream the file into your chosen download folder.

## Features

- Desktop download UI built with PySide6
- Browser extension integration for Chrome and Edge
- Native messaging bridge for handing links from the browser to the desktop app
- Automatic handling of direct downloads and redirect-style download URLs such as `/latest` and `/download`
- Progress updates and download logging inside the app

## Project Structure

- `src/pydm/app.py` – application entry point
- `src/pydm/gui.py` – main Qt window and download workflow
- `src/pydm/downloader.py` – download engine using `httpx`
- `src/pydm/native_host.py` – native messaging host that forwards browser URLs to the desktop app
- `pydm-extension/` – Chrome/Edge extension files
- `native/` – native messaging host manifest
- `install_native_host.reg` – Windows registry helper for registering the host

## Requirements

- Python 3.12+
- Windows (for native messaging and registry registration)
- Chrome or Edge browser

## Installation

### 1. Install dependencies

From the repository root:

```bash
python -m pip install --upgrade pip
pip install -e .
```

If you use `uv`, this also works:

```bash
uv pip install -e .
```

### 2. Run the desktop app

```bash
python -m pydm.app
```

Or with `uv`:

```bash
uv run pydm
```

## Browser Extension Setup

### 1. Build the Windows executable

From the repository root:

```bash
python -m pip install -e .[build]
pyinstaller --noconfirm --clean --windowed --onefile --name pydm --icon src/pydm/assets/icon.ico --add-data "src/pydm/assets;src/pydm/assets" src/pydm/app.py
```

This creates a standalone Windows executable at `dist/pydm.exe`.

### 2. Run the executable once

Launching `pydm.exe` installs the browser host registration automatically and starts the desktop app. No manual `com.pydm.host.json` edit or registry import is required.

### 3. Load the extension in Chrome or Edge

1. Open `chrome://extensions` or `edge://extensions`
2. Enable Developer mode
3. Click Load unpacked
4. Select the `pydm-extension` folder from this repository

### 2. Register the native host

The native host manifest is stored in `native/com.pydm.host.json` and the launcher script is `src/pydm/native_host_launcher.bat`.

On Windows, you can import `install_native_host.reg` to register the host for Chrome and Edge. If you cloned the repository to a different location, update the paths in the registry file and manifest before importing.

### 3. Start the app before using the extension

The browser extension sends URLs to the desktop app over the native host bridge. The desktop app must be running for the handoff to work.

## How the Flow Works

1. The browser extension detects click events for download-like links.
2. It blocks the browser’s default download behavior.
3. It sends the URL to the native messaging host.
4. The native host forwards the URL to the desktop app over a local TCP connection.
5. PyDM starts the download and shows progress in the UI.

This includes redirect-style links such as `/latest` or `/download` endpoints that eventually resolve to the actual file.

## Usage

### From the desktop app

- Launch PyDM
- Paste or type a download URL into the URL field
- Choose a save folder if needed
- Click Download

### From the browser extension

- Open a page that contains a download link
- Click the link
- PyDM will receive the URL and begin downloading instead of relying on the browser’s usual download flow

## Development Notes

To validate the Python package after changes:

```bash
python -m py_compile src/pydm/gui.py src/pydm/native_host.py
```

If you want to test the native host in isolation, the project includes a simple test script at `src/pydm/test_native.py`.

## Troubleshooting

- If the browser extension does not send URLs, confirm that the desktop app is running.
- If the native host does not work, verify that the host manifest points to the correct launcher script.
- If the extension is not loading, reload it from the browser extension page.
- If the download path is wrong, select a different folder in the app before starting the download.

## License

This project is provided as-is for local use and development.
