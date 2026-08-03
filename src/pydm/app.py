import sys
import threading
from pathlib import Path


from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QIcon


from pydm.gui import MainWindow
from pydm.version import (
    __version__,
    __app_name__
)


from pydm.native_host import (
    native_host,
    start_native_host
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



    # Native Messaging -> GUI

    native_host.url_received.connect(
        window.receive_url
    )



    # Start Native Host listener

    # threading.Thread(

    #     target=start_native_host,

    #     daemon=True

    # ).start()



    window.show()



    sys.exit(
        app.exec()
    )




if __name__ == "__main__":

    main()