import sys
from pathlib import Path
from urllib.parse import urlparse

from PySide6.QtCore import QEvent, QTimer, Signal, Qt, QRectF
from PySide6.QtGui import QIcon, QAction, QPainter, QColor, QPen, QLinearGradient
from PySide6.QtNetwork import QTcpServer, QTcpSocket, QHostAddress
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QComboBox,
    QFileDialog,
    QProgressBar,
    QTextEdit,
    QGroupBox,
    QSystemTrayIcon,
    QMenu,
    QSizePolicy,
    QScrollArea,
    QGridLayout,
)

from pydm.version import __version__, __app_name__
from pydm.downloader import DownloadWorker, SegmentedDownloadWorker


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


def get_download_folder():
    return str(Path.home() / "Downloads")


class SegmentedProgressBar(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.connections = 1
        self.progress = [0]
        self.setMinimumHeight(24)

    def set_connections(self, count):
        count = max(1, int(count))
        self.connections = count
        self.progress = [0] * count
        self.update()

    def reset(self):
        self.set_connections(1)

    def set_part_progress(self, index, pct):
        if index < 0 or index >= self.connections:
            return
        self.progress[index] = max(0, min(100, int(pct)))
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        try:
            painter.setRenderHint(QPainter.Antialiasing)

            rect = self.rect().adjusted(2, 2, -2, -2)
            if rect.width() <= 0 or rect.height() <= 0:
                return

            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor("#e6e6e6"))
            painter.drawRoundedRect(rect, 8, 8)

            all_full = all(pct >= 100 for pct in self.progress)
            gradient = QLinearGradient(rect.topLeft(), rect.bottomLeft())
            gradient.setColorAt(0, QColor("#4f8cff"))
            gradient.setColorAt(1, QColor("#1d4fe6"))

            if all_full:
                painter.setBrush(gradient)
                painter.drawRoundedRect(rect, rect.height() / 2, rect.height() / 2)
                return

            segment_width = rect.width() / self.connections
            for idx in range(self.connections):
                left = rect.left() + idx * segment_width
                seg_rect = QRectF(left, rect.top(), segment_width, rect.height())
                painter.setPen(Qt.NoPen)
                painter.setBrush(QColor("#dfe7ff"))
                painter.drawRoundedRect(seg_rect, rect.height() / 2, rect.height() / 2)

                filled = int(seg_rect.width() * self.progress[idx] / 100 + 0.5)
                if filled > 0:
                    fill_rect = QRectF(seg_rect.left(), seg_rect.top(), min(filled, seg_rect.width()), seg_rect.height())
                    painter.setPen(Qt.NoPen)
                    painter.setBrush(gradient)
                    if idx == 0:
                        painter.drawRoundedRect(fill_rect, rect.height() / 2, rect.height() / 2)
                    else:
                        painter.drawRect(fill_rect)
        finally:
            painter.end()


# DownloadWorker now lives in `pydm.downloader` (imported above)


class NativeReceiver(QTcpServer):
    url_received = Signal(str)

    def __init__(self):
        super().__init__()
        self.newConnection.connect(self.handle_connection)

    def start_server(self):
        self.listen(QHostAddress.LocalHost, 8765)

    def handle_connection(self):
        socket = self.nextPendingConnection()
        socket.readyRead.connect(lambda: self.read_data(socket))

    def read_data(self, socket):
        data = socket.readAll()
        url = bytes(data).decode("utf-8")
        if url:
            self.url_received.emit(url)
        socket.close()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.quit_by_tray = False
        self.worker = None
        self.part_bars = []
        self.resume_supported = False

        self.setWindowTitle(f"{__app_name__} - Python Download Manager {__version__}")
        self.resize(750, 500)

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
                self.tray_icon.showMessage(__app_name__, "Application is still running in the system tray.", QSystemTrayIcon.Information, 3000)

    def closeEvent(self, event):
        if self.quit_by_tray or not self.tray_icon:
            if self.worker and self.worker.isRunning():
                try:
                    self.worker.cancel()
                    self.worker.wait(500)
                except Exception:
                    self.worker.terminate()
                    self.worker.wait()

            if self.tray_icon:
                self.tray_icon.hide()

            super().closeEvent(event)
            return

        event.ignore()
        self.hide()
        if self.tray_icon and self.tray_icon.isVisible():
            self.tray_icon.showMessage(__app_name__, "Application is still running in the system tray.", QSystemTrayIcon.Information, 3000)

    def setup_ui(self):
        main = QWidget()
        self.setCentralWidget(main)

        layout = QVBoxLayout(main)

        # Download box
        group = QGroupBox("New Download")
        box = QVBoxLayout()
        box.addWidget(QLabel("URL:"))
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("Paste download URL or use browser extension")
        box.addWidget(self.url_input)

        folder_layout = QHBoxLayout()
        self.folder_input = QLineEdit(get_download_folder())
        browse = QPushButton("Browse")
        browse.clicked.connect(self.select_folder)
        folder_layout.addWidget(self.folder_input)
        folder_layout.addWidget(browse)
        box.addLayout(folder_layout)

        group.setLayout(box)
        layout.addWidget(group)

        # Progress (with percent label)
        progress_h = QHBoxLayout()
        self.progress = QProgressBar()
        self.progress.setValue(0)
        # hide the internal percent text to avoid duplicate percent display
        try:
            self.progress.setTextVisible(False)
        except Exception:
            pass

        # IDM-like styling: green gradient chunk, rounded bar
        try:
            self.progress.setStyleSheet(
                """
QProgressBar {
  border: 1px solid #9e9e9e;
  border-radius: 6px;
  background: #f0f0f0;
  height: 18px;
}
QProgressBar::chunk {
  border-radius: 6px;
  background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
    stop:0 #7fe07f, stop:0.5 #3fbf3f, stop:1 #2f8f2f);
}
                """
            )
        except Exception:
            pass
        self.percent_label = QLabel("0%")
        progress_h.addWidget(self.progress)
        progress_h.addWidget(self.percent_label)
        layout.addLayout(progress_h)

        # Status
        self.status = QLabel("Ready")
        layout.addWidget(self.status)

        self.filename_label = QLabel("File: -")
        layout.addWidget(self.filename_label)

        # Connections status (auto-detect)
        conn_layout = QHBoxLayout()
        conn_layout.addWidget(QLabel("Connections:"))

        self.conn_status_label = QLabel("Auto")
        conn_layout.addWidget(self.conn_status_label)
        layout.addLayout(conn_layout)

        # Buttons
        buttons = QHBoxLayout()
        self.download_btn = QPushButton("Download")
        self.download_btn.clicked.connect(self.start_download)
        buttons.addWidget(self.download_btn)

        self.pause_btn = QPushButton("Pause")
        self.pause_btn.setEnabled(False)
        self.pause_btn.clicked.connect(self.pause_resume)
        buttons.addWidget(self.pause_btn)

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.clicked.connect(self.cancel_download)
        buttons.addWidget(self.cancel_btn)

        layout.addLayout(buttons)

        # transfer info
        info = QHBoxLayout()
        self.filesize_label = QLabel("Size: -")
        self.rate_label = QLabel("Rate: -")
        self.eta_label = QLabel("ETA: -")
        self.resume_label = QLabel("Resume: unknown")
        info.addWidget(self.filesize_label)
        info.addWidget(self.rate_label)
        info.addWidget(self.eta_label)
        info.addWidget(self.resume_label)
        layout.addLayout(info)

        # IDM-style segmented per-connection progress bar
        self.segmented_progress_bar = SegmentedProgressBar()
        self.segmented_progress_bar.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        layout.addWidget(self.segmented_progress_bar)

        # Log
        self.log = QTextEdit()
        self.log.setReadOnly(True)
        layout.addWidget(self.log)

    def receive_url(self, url):
        clean_url = url.strip().replace("\r", "").replace("\n", "")
        self.url_input.setText(clean_url)
        self.status.setText("URL received from browser")
        self.log.append("Native Messaging:")
        self.log.append(clean_url)
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def select_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Folder")
        if folder:
            self.folder_input.setText(folder)

    def start_download(self):
        url = self.url_input.text().strip()
        folder = self.folder_input.text().strip()
        if not url:
            self.status.setText("Enter URL first")
            return

        self.progress.setMinimum(0)
        self.progress.setMaximum(0)
        self.progress.setValue(0)
        self.status.setText("Starting download...")
        self.log.append(f"Starting:\n{url}")
        self.conn_status_label.setText("Auto (detecting...)")

        self.segmented_progress_bar.reset()
        connections = None

        self.current_filename = Path(urlparse(url).path).name or "download.bin"
        self.filename_label.setText(f"File: {self.current_filename}")
        self.filesize_label.setText("Size: -")
        self.rate_label.setText("Rate: -")
        self.eta_label.setText("ETA: -")
        self.resume_label.setText("Resume: unknown")
        self.percent_label.setText("0%")
        self.pause_btn.setText("Pause")
        self.pause_btn.setEnabled(False)
        self.resume_supported = False

        QApplication.processEvents()

        self.worker = SegmentedDownloadWorker(url, folder, connections=connections)
        self.worker.connections_changed.connect(self.update_connections)
        self.worker.part_progress.connect(self.update_part_progress)
        self.worker.filename_changed.connect(self.update_filename)

        # common connections
        self.worker.progress.connect(self.update_progress)
        self.worker.message.connect(self.update_message)
        self.worker.finished.connect(self.download_finished)
        self.worker.transfer_rate.connect(self.update_rate)
        self.worker.eta_text.connect(self.update_eta)
        self.worker.resume_capability.connect(self.update_resume_capability)
        self.worker.filesize.connect(self.update_filesize)

        self.pause_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)
        self.download_btn.setEnabled(False)

        self.worker.start()
        self.status.setText("Connecting...")
        QApplication.processEvents()

    def update_message(self, text):
        self.status.setText(text)
        self.log.append(text)
        QApplication.processEvents()

    def update_progress(self, val):
        try:
            if self.progress.maximum() == 0:
                # Unknown total size: keep indeterminate progress bar active
                self.progress.setValue(0)
                self.percent_label.setText("...")
            else:
                self.progress.setValue(val)
                self.percent_label.setText(f"{int(val)}%")

            if self.segmented_progress_bar.connections == 1:
                self.segmented_progress_bar.set_part_progress(0, int(val))
        except Exception:
            pass

    def update_filename(self, filename):
        try:
            self.current_filename = filename or self.current_filename
            self.filename_label.setText(f"File: {self.current_filename}")
        except Exception:
            pass

    def update_rate(self, rate):
        try:
            if rate >= 1024 * 1024:
                self.rate_label.setText(f"Rate: {rate / (1024 * 1024):.2f} MB/s")
            elif rate >= 1024:
                self.rate_label.setText(f"Rate: {rate / 1024:.2f} KB/s")
            else:
                self.rate_label.setText(f"Rate: {rate:.0f} B/s")
        except Exception:
            self.rate_label.setText("Rate: -")

    def update_connections(self, count):
        try:
            count = int(count)
            self.conn_status_label.setText(f"Auto ({count})")
        except Exception:
            self.conn_status_label.setText("Auto")
            count = 1

        self.segmented_progress_bar.set_connections(count)

    def clear_part_bars(self):
        for i in reversed(range(self.part_bars_layout.count())):
            w = self.part_bars_layout.itemAt(i).widget()
            if w:
                w.setParent(None)
        self.part_bars = []

    def create_part_bars(self, count):
        self.clear_part_bars()
        if count < 1:
            count = 1
        cols = min(4, count)
        for i in range(count):
            b = QProgressBar()
            b.setMinimum(0)
            b.setMaximum(100)
            b.setValue(0)
            b.setFixedHeight(12)
            b.setTextVisible(True)
            b.setFormat("%p %")
            b.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            row = i // cols
            col = i % cols
            self.part_bars_layout.addWidget(b, row, col)
            self.part_bars.append(b)

    def update_part_progress(self, idx, pct):
        try:
            if idx < 0:
                return
            self.segmented_progress_bar.set_part_progress(idx, pct)
            self.status.setText(f"Downloading part {idx + 1}: {int(pct)}%")
            QApplication.processEvents()
        except Exception:
            pass

    def update_eta(self, text):
        self.eta_label.setText(f"ETA: {text}")

    def update_resume_capability(self, can_resume):
        self.resume_supported = bool(can_resume)
        self.resume_label.setText("Resume: yes" if self.resume_supported else "Resume: no")
        self.pause_btn.setText("Pause")
        self.pause_btn.setEnabled(self.resume_supported)

    def update_filesize(self, size):
        if size and size > 0:
            mb = size / (1024 * 1024)
            self.filesize_label.setText(f"Size: {mb:.2f} MB")
            self.progress.setMinimum(0)
            self.progress.setMaximum(100)
        else:
            self.filesize_label.setText("Size: unknown")
            self.progress.setMinimum(0)
            self.progress.setMaximum(0)

    def pause_resume(self):
        if not self.worker:
            return
        if not self.resume_supported:
            self.status.setText("Pause unavailable")
            self.log.append("Pause unavailable: file is not resumable")
            return
        if self.pause_btn.text() == "Pause":
            try:
                self.worker.pause()
                self.pause_btn.setText("Resume")
                self.status.setText("Paused")
                self.log.append("Paused")
            except Exception:
                pass
        else:
            try:
                self.worker.resume()
                self.pause_btn.setText("Pause")
                self.status.setText("Resuming...")
                self.log.append("Resuming...")
            except Exception:
                pass

    def cancel_download(self):
        if not self.worker:
            return
        try:
            self.worker.cancel()
            self.pause_btn.setEnabled(False)
            self.cancel_btn.setEnabled(False)
            self.download_btn.setEnabled(True)
            self.status.setText("Cancelling...")
            # reset percent UI
            self.percent_label.setText("0%")
        except Exception:
            pass

    def download_finished(self, path):
        if self.progress.maximum() == 0:
            self.progress.setMaximum(100)
        self.progress.setValue(100)
        self.percent_label.setText("100%")
        self.status.setText("Completed")
        self.log.append(f"Saved:\n{path}")
        self.pause_btn.setEnabled(False)
        self.pause_btn.setText("Pause")
        self.cancel_btn.setEnabled(False)
        self.download_btn.setEnabled(True)
