import sys
from pathlib import Path

from PySide6.QtCore import QEvent, QTimer, QThread, Signal
from PySide6.QtGui import QIcon, QAction
from PySide6.QtNetwork import QTcpServer, QTcpSocket, QHostAddress
from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QFileDialog,
    QProgressBar,
    QTextEdit,
    QGroupBox,
    QSystemTrayIcon,
    QMenu,
)


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

from pydm.downloader import download_file
from pydm.version import __version__, __app_name__



def get_download_folder():
    """
    Get system Downloads folder.
    """

    return str(
        Path.home() / "Downloads"
    )



class DownloadWorker(QThread):

    progress = Signal(int)
    message = Signal(str)
    finished = Signal(str)


    def __init__(self, url, folder):

        super().__init__()

        self.url = url
        self.folder = folder



    def run(self):

        try:

            for data in download_file(
                self.url,
                self.folder
            ):

                if "total" in data:

                    percent = 0

                    if data["total"] > 0:

                        percent = int(
                            data["downloaded"]
                            /
                            data["total"]
                            *
                            100
                        )


                    self.progress.emit(
                        percent
                    )


                    self.message.emit(
                        f"{data['filename']} - {percent}%"
                    )


                if "completed" in data:

                    self.finished.emit(
                        data["path"]
                    )


        except Exception as e:

            self.message.emit(
                f"Error: {e}"
            )

class NativeReceiver(QTcpServer):

    url_received = Signal(str)


    def __init__(self):

        super().__init__()

        self.newConnection.connect(
            self.handle_connection
        )


    def start_server(self):
        self.listen(
            QHostAddress.LocalHost,
            8765
            )


    def handle_connection(self):

        socket = self.nextPendingConnection()

        socket.readyRead.connect(
            lambda: self.read_data(socket)
        )


    def read_data(self, socket):

        data = socket.readAll()

        url = bytes(data).decode(
            "utf-8"
        )


        if url:

            self.url_received.emit(
                url
            )


        socket.close()


class MainWindow(QMainWindow):

    def __init__(self):

        super().__init__()

        self.quit_by_tray = False
        self.worker = None

        self.setWindowTitle(
            f"{__app_name__} - Python Download Manager {__version__}"
        )

        self.resize(
            750,
            500
        )

        self.native_receiver = NativeReceiver()
        self.native_receiver.url_received.connect(self.receive_url)
        self.native_receiver.start_server()

        self.setup_tray()
        self.setup_ui()

    def setup_tray(self):

        if not QSystemTrayIcon.isSystemTrayAvailable():
            self.tray_icon = None
            return

        icon_path = get_data_path("assets", "icon.ico")
        tray_icon = QIcon(str(icon_path))

        self.tray_icon = QSystemTrayIcon(tray_icon, self)
        self.tray_icon.setToolTip(__app_name__)

        tray_menu = QMenu(self)

        restore_action = QAction("Restore", self)
        restore_action.triggered.connect(self.restore_window)
        tray_menu.addAction(restore_action)

        tray_menu.addSeparator()

        quit_action = QAction("Quit", self)
        quit_action.triggered.connect(self.quit_app)
        tray_menu.addAction(quit_action)

        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self.tray_activated)
        self.tray_icon.show()

    def restore_window(self):

        self.showNormal()
        self.raise_()
        self.activateWindow()

    def tray_activated(self, reason):

        if reason == QSystemTrayIcon.Trigger:
            self.restore_window()

    def quit_app(self):

        self.quit_by_tray = True
        from PySide6.QtWidgets import QApplication

        QApplication.instance().quit()

    def changeEvent(self, event):

        super().changeEvent(event)

        if event.type() == QEvent.WindowStateChange and self.isMinimized():
            QTimer.singleShot(0, self.hide)

            if self.tray_icon and self.tray_icon.isVisible():
                self.tray_icon.showMessage(
                    __app_name__,
                    "Application is still running in the system tray.",
                    QSystemTrayIcon.Information,
                    3000
                )

    def closeEvent(self, event):

        if self.quit_by_tray or not self.tray_icon:
            if self.worker and self.worker.isRunning():
                self.worker.terminate()
                self.worker.wait()

            if self.tray_icon:
                self.tray_icon.hide()

            super().closeEvent(event)
            return

        event.ignore()
        self.hide()

        if self.tray_icon and self.tray_icon.isVisible():
            self.tray_icon.showMessage(
                __app_name__,
                "Application is still running in the system tray.",
                QSystemTrayIcon.Information,
                3000
            )


    def setup_ui(self):

        main = QWidget()

        self.setCentralWidget(
            main
        )


        layout = QVBoxLayout(
            main
        )


        # -------------------------
        # Download box
        # -------------------------

        group = QGroupBox(
            "New Download"
        )


        box = QVBoxLayout()



        box.addWidget(
            QLabel("URL:")
        )


        self.url_input = QLineEdit()


        self.url_input.setPlaceholderText(
            "Paste download URL or use browser extension"
        )


        box.addWidget(
            self.url_input
        )



        folder_layout = QHBoxLayout()



        self.folder_input = QLineEdit(
            get_download_folder()
        )



        browse = QPushButton(
            "Browse"
        )


        browse.clicked.connect(
            self.select_folder
        )


        folder_layout.addWidget(
            self.folder_input
        )


        folder_layout.addWidget(
            browse
        )


        box.addLayout(
            folder_layout
        )


        group.setLayout(
            box
        )


        layout.addWidget(
            group
        )



        # -------------------------
        # Progress
        # -------------------------

        self.progress = QProgressBar()


        self.progress.setValue(
            0
        )


        layout.addWidget(
            self.progress
        )



        # -------------------------
        # Status
        # -------------------------

        self.status = QLabel(
            "Ready"
        )


        layout.addWidget(
            self.status
        )



        # -------------------------
        # Buttons
        # -------------------------

        buttons = QHBoxLayout()



        self.download_btn = QPushButton(
            "Download"
        )


        self.download_btn.clicked.connect(
            self.start_download
        )


        buttons.addWidget(
            self.download_btn
        )


        layout.addLayout(
            buttons
        )



        # -------------------------
        # Log
        # -------------------------

        self.log = QTextEdit()


        self.log.setReadOnly(
            True
        )


        layout.addWidget(
            self.log
        )



    # -------------------------
    # Native Host Receiver
    # -------------------------

    def receive_url(self, url):

        """
        Receive URL from Chrome/Edge Native Messaging.
        """

        self.url_input.setText(
            url
        )


        self.status.setText(
            "URL received from browser"
        )


        self.log.append(
            "Native Messaging:"
        )


        self.log.append(
            url
        )


        # Bring application to front

        self.showNormal()

        self.raise_()

        self.activateWindow()



    def select_folder(self):

        folder = QFileDialog.getExistingDirectory(
            self,
            "Select Folder"
        )


        if folder:

            self.folder_input.setText(
                folder
            )



    def start_download(self):

        url = self.url_input.text().strip()


        folder = self.folder_input.text().strip()



        if not url:

            self.status.setText(
                "Enter URL first"
            )

            return



        self.progress.setValue(
            0
        )


        self.status.setText(
            "Downloading..."
        )


        self.log.append(
            f"Starting:\n{url}"
        )



        self.worker = DownloadWorker(
            url,
            folder
        )



        self.worker.progress.connect(
            self.progress.setValue
        )


        self.worker.message.connect(
            self.update_message
        )


        self.worker.finished.connect(
            self.download_finished
        )


        self.worker.start()



    def update_message(self, text):

        self.status.setText(
            text
        )


        self.log.append(
            text
        )



    def download_finished(self, path):

        self.progress.setValue(
            100
        )


        self.status.setText(
            "Completed"
        )


        self.log.append(
            f"Saved:\n{path}"
        )