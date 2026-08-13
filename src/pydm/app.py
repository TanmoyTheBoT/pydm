import sys
from pathlib import Path
import os


from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QIcon


def get_data_path(*parts):
    if getattr(sys, "frozen", False):
        base = Path(sys._MEIPASS)
        candidate = base.joinpath(*parts)
        if candidate.exists():
            return candidate
        candidate = base.joinpath("src", "pydm", *parts)
        if candidate.exists():
            return candidate
        candidate = base.joinpath("assets", *parts[1:]) if len(parts) > 1 and parts[0] == "assets" else None
        if candidate and candidate.exists():
            return candidate

    for base in (
        Path(__file__).resolve().parent,
        Path(__file__).resolve().parent.parent,
        Path.cwd(),
    ):
        candidate = base.joinpath(*parts)
        if candidate.exists():
            return candidate

    return Path(__file__).resolve().parent.joinpath(*parts)


from pydm.host_register import ensure_browser_host_registered
from pydm.ui import PyDMMainWindow
from pydm.gui import MainWindow
from pydm.version import (
    __version__,
    __app_name__
)



def main():
    # Handle help and version before Qt initialization
    if '--help' in sys.argv or '-h' in sys.argv:
        print(f"{__app_name__} v{__version__}")
        print()
        print("Usage: pydm [OPTIONS]")
        print()
        print("Options:")
        print("  --start-in-tray    Start application minimized to system tray")
        print("  --help, -h         Show this help message")
        print()
        print("Environment Variables:")
        print("  PYDM_START_IN_TRAY Set to 1/true/yes to start in tray")
        print()
        sys.exit(0)

    if sys.platform == "win32":
        ensure_browser_host_registered()

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    app.setApplicationName(
        __app_name__
    )


    app.setApplicationVersion(
        __version__
    )



    # Application icon

    ICON_PATH = get_data_path("assets", "icon.ico")


    app.setWindowIcon(
        QIcon(
            str(ICON_PATH)
        )
    )

    # Check if app should start minimized to tray
    # Support command-line argument: --start-in-tray
    # Support environment variable: PYDM_START_IN_TRAY=1
    start_in_tray = (
        '--start-in-tray' in sys.argv or
        os.environ.get('PYDM_START_IN_TRAY', '').lower() in ('1', 'true', 'yes')
    )

    window = PyDMMainWindow()

    # Show window only if not starting in tray
    if not start_in_tray:
        window.show()
    else:
        # Keep window hidden in tray on startup
        # The window is still created and functional, just not visible
        window.hide()
        if hasattr(window, 'tray') and window.tray:
            window.tray.showMessage(
                __app_name__,
                "Application started and minimized to tray",
                window.windowIcon(),
                5000  # Show message for 5 seconds
            )



    sys.exit(
        app.exec()
    )




if __name__ == "__main__":

    main()