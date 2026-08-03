import sys
from pathlib import Path


from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QIcon


from pydm.gui import MainWindow
from pydm.version import (
    __version__,
    __app_name__
)



def main():

    app = QApplication(sys.argv)


    app.setApplicationName(
        __app_name__
    )


    app.setApplicationVersion(
        __version__
    )



    # Application icon

    ICON_PATH = (
        Path(__file__).parent
        /
        "assets"
        /
        "icon.ico"
    )


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