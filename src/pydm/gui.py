from pathlib import Path

from PySide6.QtCore import QThread, Signal
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
)

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



class MainWindow(QMainWindow):


    def closeEvent(self, event):

        if self.worker and self.worker.isRunning():

            self.worker.terminate()

            self.worker.wait()


        event.accept()


    def __init__(self):

        super().__init__()


        self.setWindowTitle(
            f"{__app_name__} - Python Download Manager {__version__}"
        )


        self.resize(
            750,
            500
        )


        self.worker = None


        self.setup_ui()



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