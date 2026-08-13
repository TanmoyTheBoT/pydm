import sys
from pathlib import Path
from urllib.parse import urlparse

from PySide6.QtCore import QEvent, QTimer, Signal, Qt, QRectF
from PySide6.QtGui import QIcon, QAction, QPainter, QColor, QPen, QLinearGradient, QFont
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
    QDialog,
    QProgressBar,
    QTextEdit,
    QGroupBox,
    QSystemTrayIcon,
    QMenu,
    QSizePolicy,
    QScrollArea,
    QGridLayout,
)
# QDialog and form layout for download dialog are provided in ui/download_progress_dialog.py

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
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet("QWidget { background: transparent; }")
        self.connections = 1
        self.progress = [0]
        self.setMinimumHeight(8)
        self.setMaximumHeight(10)

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

            rect = self.rect().adjusted(1, 1, -1, -1)
            if rect.width() <= 0 or rect.height() <= 0:
                return

            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor("#e6e6e6"))
            painter.drawRoundedRect(rect, 4, 4)

            all_full = all(pct >= 100 for pct in self.progress)
            gradient = QLinearGradient(rect.topLeft(), rect.bottomLeft())
            # Use blue gradient for connection progress (IDM-style)
            gradient.setColorAt(0, QColor("#4f8cff"))
            gradient.setColorAt(0.5, QColor("#7fb3ff"))
            gradient.setColorAt(1, QColor("#1d4fe6"))

            if all_full:
                painter.setBrush(gradient)
                painter.drawRoundedRect(rect, 4, 4)
                return

            segment_width = rect.width() / self.connections
            for idx in range(self.connections):
                left = rect.left() + idx * segment_width
                seg_rect = QRectF(left, rect.top(), segment_width, rect.height())
                painter.setPen(Qt.NoPen)
                painter.setBrush(QColor("#eaf0ff"))
                painter.drawRoundedRect(seg_rect, 4, 4)

                filled = int(seg_rect.width() * self.progress[idx] / 100 + 0.5)
                if filled > 0:
                    fill_rect = QRectF(seg_rect.left(), seg_rect.top(), min(filled, seg_rect.width()), seg_rect.height())
                    painter.setPen(Qt.NoPen)
                    painter.setBrush(gradient)
                    # Use rounded fill for first and last segments for nicer appearance
                    seg_left = seg_rect.left()
                    seg_right = seg_rect.right()
                    if idx == 0:
                        # rounded left edge
                        painter.drawRoundedRect(fill_rect, 4, 4)
                    elif idx == (self.connections - 1):
                        # rounded right edge
                        painter.drawRoundedRect(fill_rect, 4, 4)
                    else:
                        painter.drawRect(fill_rect)
        finally:
            painter.end()


class DownloadProgressDialog(QDialog):
    """Dialog showing download progress with controls (UI only).

    The dialog connects to a downloader worker for runtime updates;
    download logic remains in `pydm.downloader`.
    """

    def __init__(self, download_info=None, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet("QDialog { background: #f5f5f5; color: #1f1f1f; } QPushButton { background: #f0f0f0; border: 1px solid #b9c2d0; border-radius: 4px; color: #1f1f1f; }")
        self.download_info = download_info or {}
        self.worker = None
        self._is_paused = False
        self.setWindowTitle(f"Downloading: {self.download_info.get('filename', 'File')}")
        self.resize(560, 300)
        self.setWindowFlags(self.windowFlags() | Qt.Window | Qt.WindowMinimizeButtonHint | Qt.WindowMaximizeButtonHint | Qt.WindowCloseButtonHint)
        self.setWindowModality(Qt.NonModal)

        self._setup_ui()

    def _setup_ui(self):
                self.setContentsMargins(0, 0, 0, 0)
                layout = QVBoxLayout(self)
                layout.setContentsMargins(8, 6, 8, 6)
                layout.setSpacing(2)

                # Clean title-less header like the reference UI
                header_h = QHBoxLayout()
                header_h.setContentsMargins(0, 0, 0, 0)
                header_h.setSpacing(0)
                self.url_label = QLabel(self._truncate_url(self.download_info.get("url", "")))
                self.url_label.setWordWrap(False)
                self.url_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
                self.url_label.setContentsMargins(0, 0, 0, 0)
                self.url_label.setMaximumHeight(20)
                self.url_label.setMinimumHeight(20)
                self.url_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
                self.url_label.setToolTip(self.download_info.get("url", ""))
                header_h.addWidget(self.url_label)
                layout.addLayout(header_h)
                layout.setSpacing(0)

                # Details / stats grid (compact)

                details = QGroupBox("")
                details.setStyleSheet("QGroupBox { border: none; background: transparent; padding: 0px; margin: 0px; }")
                details.setContentsMargins(0, 0, 0, 0)
                form = QGridLayout()
                form.setContentsMargins(0, 0, 0, 0)
                form.setHorizontalSpacing(6)
                form.setVerticalSpacing(0)
                form.setColumnMinimumWidth(0, 80)
                form.setColumnStretch(0, 0)
                form.setColumnStretch(1, 1)

                # Filename and destination
                left_label_style = "font-size: 11px; color: #222;"
                right_value_style = "font-size: 11px; color: #111;"

                file_label = QLabel("File:")
                file_label.setStyleSheet(left_label_style)
                form.addWidget(file_label, 0, 0)
                self.filename_label = QLabel(self.download_info.get("filename", ""))
                self.filename_label.setStyleSheet("font-size: 11px; color: #000; font-weight: 500;")
                self.filename_label.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
                form.addWidget(self.filename_label, 0, 1)

                save_label = QLabel("Save to:")
                save_label.setStyleSheet(left_label_style)
                form.addWidget(save_label, 1, 0)
                self.folder_label = QLabel(self.download_info.get("folder", get_download_folder()))
                self.folder_label.setStyleSheet("font-size: 11px; color: #000;")
                self.folder_label.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
                form.addWidget(self.folder_label, 1, 1)

                # Stats
                size_label = QLabel("File size")
                size_label.setStyleSheet(left_label_style)
                form.addWidget(size_label, 2, 0)
                self.filesize_label = QLabel("Calculating...")
                self.filesize_label.setStyleSheet("font-size: 11px; color: #000;")
                self.filesize_label.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
                form.addWidget(self.filesize_label, 2, 1)

                downloaded_label = QLabel("Downloaded")
                downloaded_label.setStyleSheet(left_label_style)
                form.addWidget(downloaded_label, 3, 0)
                self.downloaded_label = QLabel("0 B")
                self.downloaded_label.setStyleSheet("font-size: 11px; color: #000;")
                self.downloaded_label.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
                form.addWidget(self.downloaded_label, 3, 1)

                transfer_label = QLabel("Transfer rate")
                transfer_label.setStyleSheet(left_label_style)
                form.addWidget(transfer_label, 4, 0)
                self.speed_label = QLabel("0 B/s")
                self.speed_label.setStyleSheet("font-size: 11px; color: #000;")
                self.speed_label.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
                form.addWidget(self.speed_label, 4, 1)

                eta_label = QLabel("Time left")
                eta_label.setStyleSheet(left_label_style)
                form.addWidget(eta_label, 5, 0)
                self.eta_label = QLabel("-")
                self.eta_label.setStyleSheet("font-size: 11px; color: #000;")
                self.eta_label.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
                form.addWidget(self.eta_label, 5, 1)

                resume_label = QLabel("Resume capability")
                resume_label.setStyleSheet(left_label_style)
                form.addWidget(resume_label, 6, 0)
                self.resume_cap_label = QLabel("Unknown")
                self.resume_cap_label.setStyleSheet("font-size: 11px; color: #000;")
                self.resume_cap_label.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
                form.addWidget(self.resume_cap_label, 6, 1)

                details.setLayout(form)
                layout.addWidget(details)

                # Overall progress bar with percent on the right
                progress_h = QHBoxLayout()
                progress_h.setContentsMargins(0, 0, 0, 0)
                progress_h.setSpacing(4)
                self.overall_progress = QProgressBar()
                self.overall_progress.setContentsMargins(0, 0, 0, 0)
                self.overall_progress.setMinimum(0)
                self.overall_progress.setMaximum(100)
                self.overall_progress.setValue(0)
                try:
                        self.overall_progress.setTextVisible(False)
                        self.overall_progress.setFormat("")
                        self.overall_progress.setStyleSheet(
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
                self.percent_label.setMinimumWidth(35)
                self.percent_label.setContentsMargins(0, 0, 0, 0)
                progress_h.addWidget(self.overall_progress)
                progress_h.addWidget(self.percent_label)
                layout.addLayout(progress_h)

                # Compact action row above connection progress, aligned right
                connection_actions = QHBoxLayout()
                connection_actions.setContentsMargins(0, 2, 0, 0)
                connection_actions.setSpacing(2)
                connection_actions.addStretch()

                self.pause_btn = QPushButton("Pause")
                self.pause_btn.clicked.connect(self._toggle_pause_state)
                self.pause_btn.setEnabled(False)
                connection_actions.addWidget(self.pause_btn)

                self.cancel_btn = QPushButton("Cancel")
                self.cancel_btn.clicked.connect(self._on_cancel)
                connection_actions.addWidget(self.cancel_btn)
                layout.addLayout(connection_actions)

                # Segmented per-connection progress
                conn_label = QLabel("Connection Progress:")
                conn_label.setStyleSheet("font-size: 10px; color: #555;")
                conn_label.setContentsMargins(0, 0, 0, 0)
                layout.addWidget(conn_label)
                self.segmented = SegmentedProgressBar()
                self.segmented.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
                self.segmented.setMinimumHeight(10)
                self.segmented.setMaximumHeight(10)
                self.segmented.setContentsMargins(0, 0, 0, 0)
                layout.addWidget(self.segmented)

                # Status and final actions row
                bottom_h = QHBoxLayout()
                bottom_h.setContentsMargins(0, 2, 0, 0)
                bottom_h.setSpacing(2)
                self.status_text = QLabel("Starting...")
                self.status_text.setContentsMargins(0, 0, 0, 0)
                bottom_h.addWidget(self.status_text)
                bottom_h.addStretch()

                self.close_btn = QPushButton("Close")
                self.close_btn.setEnabled(False)
                self.close_btn.clicked.connect(self.accept)
                bottom_h.addWidget(self.close_btn)

                layout.addLayout(bottom_h)

                # track total size for downloaded bytes computation
                self._total_size = 0

    def _truncate_url(self, url, max_len=110):
        if not url:
            return ""
        if len(url) <= max_len:
            return url
        return url[:max_len - 3] + "..."

    def set_worker(self, worker):
        self.worker = worker
        try:
            worker.progress.connect(self._on_progress)
            worker.filesize.connect(self._on_filesize)
            worker.transfer_rate.connect(self._on_transfer_rate)
            worker.eta_text.connect(self._on_eta)
            worker.message.connect(self._on_message)
            worker.finished.connect(self._on_finished)
            worker.part_progress.connect(self._on_part_progress)
            worker.filename_changed.connect(self._on_filename_changed)
            worker.connections_changed.connect(self._on_connections_changed)
            worker.resume_capability.connect(self._on_resume_capability)
        except Exception:
            pass

    def _on_resume_capability(self, can_resume):
        if hasattr(self, 'pause_btn'):
            self.pause_btn.setEnabled(bool(can_resume))
            self.pause_btn.setText("Pause" if not self._is_paused else "Resume")
        self.resume_cap_label.setText("Yes" if bool(can_resume) else "No")
        if not bool(can_resume):
            self._is_paused = False
            if hasattr(self, 'pause_btn'):
                self.pause_btn.setText("Pause")

    def start_download(self, url, folder, connections=None):
        """Create worker, wire signals, and start download (dialog-managed)."""
        # Prefill UI
        self.url_label.setText(self._truncate_url(url))
        self.url_label.setToolTip(url)
        filename = Path(urlparse(url).path).name or self.download_info.get('filename') or 'download.bin'
        try:
            self.filename_label.setText(filename)
        except Exception:
            pass
        try:
            self.folder_label.setText(folder)
        except Exception:
            pass
        self.filesize_label.setText("Calculating...")
        self.overall_progress.setValue(0)
        try:
            self.status_text.setText("Starting download...")
        except Exception:
            pass
        QApplication.processEvents()

        # Create and configure worker
        self.worker = SegmentedDownloadWorker(url, folder, connections=connections)
        self.set_worker(self.worker)

        # Connect additional main signals to keep UI responsive
        try:
            self.worker.progress.connect(self._on_progress)
            self.worker.message.connect(self._on_message)
            self.worker.filesize.connect(self._on_filesize)
            self.worker.transfer_rate.connect(self._on_transfer_rate)
            self.worker.eta_text.connect(self._on_eta)
        except Exception:
            pass

        # Enable/disable controls
        self._is_paused = False
        try:
            self.pause_btn.setText("Pause")
            self.pause_btn.setEnabled(False)
        except Exception:
            pass
        try:
            self.cancel_btn.setEnabled(True)
        except Exception:
            pass
        try:
            self.close_btn.setEnabled(False)
        except Exception:
            pass

        # Start worker thread
        self.worker.start()
        try:
            self.status_text.setText("Connecting...")
        except Exception:
            pass
        QApplication.processEvents()

    def _format_bytes(self, b):
        try:
            b = float(b)
        except Exception:
            return "-"
        for unit in ["B", "KB", "MB", "GB"]:
            if b < 1024:
                return f"{b:.1f} {unit}"
            b /= 1024
        return f"{b:.1f} TB"

    def _on_progress(self, pct):
        try:
            self.overall_progress.setValue(int(pct))
            # Update downloaded bytes display if we know total size
            try:
                ts = int(getattr(self, '_total_size', 0) or 0)
                if ts > 0:
                    downloaded = int(ts * (int(pct) / 100.0))
                    self.downloaded_label.setText(f"Downloaded: {self._format_bytes(downloaded)}")
                else:
                    self.downloaded_label.setText("Downloaded: -")
            except Exception:
                pass
            # Mirror overall progress into segmented bar when only 1 connection
            try:
                if getattr(self, 'segmented', None) is not None and getattr(self.segmented, 'connections', 1) == 1:
                    self.segmented.set_part_progress(0, int(pct))
            except Exception:
                pass
            # update percent label in dialog
            try:
                if getattr(self, 'percent_label', None) is not None:
                    self.percent_label.setText(f"{int(pct)}%")
            except Exception:
                pass
        except Exception:
            pass

    def _on_filesize(self, size):
        try:
            self._total_size = int(size) if size else 0
        except Exception:
            self._total_size = 0
        self.filesize_label.setText(self._format_bytes(self._total_size))

    def _on_transfer_rate(self, rate):
        self.speed_label.setText(f"Speed: {self._format_bytes(rate)}/s")

    def _on_eta(self, eta):
        self.eta_label.setText(f"ETA: {eta}")

    def _on_message(self, msg):
        try:
            # For compact UI we display the latest message
            self.status_text.setText(msg)
        except Exception:
            pass

    def _on_finished(self, path):
        self.overall_progress.setValue(100)
        try:
            self.status_text.setText(f"✅ Completed: {path}")
        except Exception:
            pass
        self._is_paused = False
        try:
            self.pause_link.setText("Pause")
            self.pause_link.setEnabled(False)
        except Exception:
            pass
        try:
            self.pause_btn.setText("Pause")
            self.pause_btn.setEnabled(False)
        except Exception:
            pass
        try:
            self.cancel_btn.setEnabled(False)
        except Exception:
            pass
        try:
            self.close_btn.setEnabled(True)
        except Exception:
            pass

    def _on_part_progress(self, idx, pct):
        self.segmented.set_part_progress(idx, pct)

    def _on_filename_changed(self, filename):
        self.filename_label.setText(filename)

    def _on_connections_changed(self, connections):
        self.segmented.set_connections(connections)

    def _toggle_pause_state(self):
        if not self.worker:
            return
        if self._is_paused:
            self._on_resume()
        else:
            self._on_pause()

    def _on_pause(self):
        if self.worker:
            try:
                self.worker.pause()
                self._is_paused = True
                if hasattr(self, 'pause_link'):
                    self.pause_link.setText("Resume")
                if hasattr(self, 'pause_btn'):
                    self.pause_btn.setText("Resume")
                try:
                    self.status_text.setText("Paused")
                except Exception:
                    pass
            except Exception:
                pass

    def _on_resume(self):
        if self.worker:
            try:
                self.worker.resume()
                self._is_paused = False
                if hasattr(self, 'pause_link'):
                    self.pause_link.setText("Pause")
                if hasattr(self, 'pause_btn'):
                    self.pause_btn.setText("Pause")
                try:
                    self.status_text.setText("Resumed")
                except Exception:
                    pass
            except Exception:
                pass

    def _on_cancel(self):
        if self.worker:
            try:
                self.worker.cancel()
                try:
                    self.pause_link.setEnabled(False)
                except Exception:
                    pass
                try:
                    self.cancel_btn.setEnabled(False)
                except Exception:
                    pass
                try:
                    self.status_text.setText("✕ Cancelled")
                except Exception:
                    pass
                # Close the dialog when user cancels the download
                try:
                    self.close()
                except Exception:
                    pass
            except Exception:
                pass
 


 


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
        # Attempt clean shutdown of workers before quitting
        self.quit_by_tray = True
        try:
            if getattr(self, 'worker', None) and self.worker.isRunning():
                try:
                    self.worker.cancel()
                    self.worker.wait(1000)
                except Exception:
                    try:
                        self.worker.terminate()
                        self.worker.wait()
                    except Exception:
                        pass
        except Exception:
            pass

        # Hide tray icon and quit application
        try:
            if self.tray_icon:
                self.tray_icon.hide()
        except Exception:
            pass

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
            self.progress.setFormat("")
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

        # Open the download progress dialog and let it manage the worker
        dlg_info = {
            "url": url,
            "filename": self.current_filename,
            "folder": folder,
            "category": "General",
        }
        dlg = DownloadProgressDialog(dlg_info, parent=self)
        dlg.start_download(url, folder, connections=connections)
        dlg.show()
        dlg.raise_()
        dlg.activateWindow()

        # Keep a reference to the worker so top-level controls still work
        try:
            self.worker = dlg.worker
        except Exception:
            self.worker = None

        self.pause_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)
        self.download_btn.setEnabled(False)

        self.status.setText("Downloading...")
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
            # Apply IDM-like styling to per-part bars so colors match overall progress
            try:
                # Blue gradient for per-part bars to match connection progress
                b.setStyleSheet(
                    """
QProgressBar {
  border: 1px solid #9e9e9e;
  border-radius: 6px;
  background: #eaf0ff;
  height: 12px;
}
QProgressBar::chunk {
  border-radius: 6px;
  background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
    stop:0 #6fb3ff, stop:0.5 #4f8cff, stop:1 #1d4fe6);
}
                    """
                )
            except Exception:
                pass
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
