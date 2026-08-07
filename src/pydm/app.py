import sys
from pathlib import Path


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
    return Path(__file__).resolve().parent.joinpath(*parts)


from pydm.host_register import ensure_browser_host_registered
from pydm.gui import MainWindow
from pydm.version import (
    __version__,
    __app_name__
)



def main():
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



    window = MainWindow()



    window.show()



    sys.exit(
        app.exec()
    )




if __name__ == "__main__":

    main()