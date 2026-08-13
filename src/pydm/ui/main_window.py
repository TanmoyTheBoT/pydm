"""
PyDM Main Window - Professional Download Manager with Sequential Download Queue
Integrates downloader.py logic and gui.py components
"""
import os
import sys
from pathlib import Path
from urllib.parse import urlparse
from datetime import datetime

from PySide6.QtCore import Qt, QTimer, QSize, QThread, Signal, QObject, QEvent
from PySide6.QtGui import QIcon, QAction, QKeySequence
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QMenuBar, QMenu, QToolBar, QStatusBar, QDialog, QLabel,
    QMessageBox, QSystemTrayIcon, QApplication, QInputDialog
)
from PySide6.QtNetwork import QTcpServer, QHostAddress

from pydm.ui.styles import IDM_STYLESHEET, COLORS
from pydm.ui.widgets import (
    SidebarCategoryWidget, DownloadListWidget, ToolbarButton,
    StatisticsWidget, StatusLabel
)
from pydm.ui.download_dialog import DownloadOptionsDialog, AddDownloadDialog
from pydm.gui import DownloadProgressDialog
from pydm.ui.download_complete_dialog import DownloadCompleteDialog
from pydm.downloader import SegmentedDownloadWorker, resolve_url_metadata
from pydm.managers import DownloadQueueManager, QueuedDownload
from pydm.version import __version__, __app_name__
from pydm.config import get_config


class NativeReceiver(QTcpServer):
    """Receiver for URLs from browser extension"""
    url_received = Signal(str)

    def __init__(self):
        super().__init__()
        self.newConnection.connect(self.handle_connection)

    def start_server(self):
        """Start listening for browser URLs"""
        try:
            self.listen(QHostAddress.LocalHost, 8765)
            print("[NativeReceiver] Server started on localhost:8765")
        except Exception as e:
            print(f"[NativeReceiver] Failed to start: {e}")

    def handle_connection(self):
        """Handle incoming connection"""
        socket = self.nextPendingConnection()
        socket.readyRead.connect(lambda: self.read_data(socket))

    def read_data(self, socket):
        """Read URL from socket"""
        data = socket.readAll()
        url = bytes(data).decode("utf-8").strip()
        if url:
            print(f"[NativeReceiver] Received URL: {url}")
            self.url_received.emit(url)
        socket.close()


class DownloadQueueProcessor(QObject):
    """Manages sequential download processing"""
    download_started = Signal(str)  # download_id
    download_next = Signal()
    download_finished = Signal(str, str, int)  # download_id, filepath, filesize
    filesize_emitted = Signal(str, int)  # download_id, filesize

    def __init__(self, queue_manager: DownloadQueueManager):
        super().__init__()
        self.queue_manager = queue_manager
        self.current_worker = None
        self.current_download_id = None
        self.current_progress_dialog = None
        self.active_workers = {}
        self.active_dialogs = {}
        self._is_paused = False
        self._current_progress = 0
        self._current_speed = 0.0
        self._current_eta = "-"
        self._current_filesize = 0

        # Timer to check for next download
        self.check_timer = QTimer()
        self.check_timer.timeout.connect(self._check_and_start_next)

    def start(self):
        """Start processing queue"""
        self.check_timer.start(100)  # Check every 100ms
        # Try to start first download immediately
        self._check_and_start_next()

    def _check_and_start_next(self):
        """Check if we should start the next queued download while slots are available."""
        if self._is_paused:
            return

        slots_available = max(0, self.queue_manager.max_concurrent - self.queue_manager.get_active_count())
        if slots_available <= 0:
            return

        while slots_available > 0:
            download = self.queue_manager.get_next_download()
            if not download:
                break
            self._start_download(download)
            slots_available -= 1

    def _start_download(self, download: QueuedDownload):
        """Start a download"""
        print(f"[QueueProcessor] Starting download: {download.filename}")
        self.current_download_id = download.download_id

        # Create worker with temp folder for storing .part files
        worker = SegmentedDownloadWorker(
            download.url,
            download.folder,
            connections=download.connections,
            temp_folder=download.temp_folder if download.temp_folder else download.folder
        )
        self.active_workers[download.download_id] = worker

        # Create progress dialog
        dialog = DownloadProgressDialog(
            {
                "url": download.url,
                "filename": download.filename,
                "folder": download.folder,
                "category": download.category,
            }
        )
        dialog.set_worker(worker)
        self.active_dialogs[download.download_id] = dialog
        self.current_progress_dialog = dialog
        self.current_worker = worker

        # Update queued download filename when worker discovers actual filename
        try:
            worker.filename_changed.connect(lambda fn, did=download.download_id: self._update_download_filename(did, fn))
        except Exception:
            pass

        # Connect signals BEFORE showing dialog
        worker.progress.connect(lambda p, did=download.download_id: self._on_progress(did, p))
        worker.filesize.connect(lambda s, did=download.download_id: self._on_filesize(did, s))
        try:
            worker.filesize.connect(lambda s, did=download.download_id: self.filesize_emitted.emit(did, int(s)))
        except Exception:
            pass
        worker.transfer_rate.connect(lambda r, did=download.download_id: self._on_rate(did, r))
        worker.eta_text.connect(lambda e, did=download.download_id: self._on_eta(did, e))
        worker.message.connect(lambda m, did=download.download_id: self._on_message(did, m))
        worker.finished.connect(lambda p, did=download.download_id: self._on_download_finished(did, p))

        # Show dialog
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()

        # Start worker thread
        worker.start()
        self.download_started.emit(download.download_id)
        print(f"[QueueProcessor] Worker started for: {download.filename}")
    
    def _on_progress(self, download_id, progress):
        """Handle progress update for one specific download."""
        dl = self.queue_manager.get_download(download_id)
        if dl is None:
            return
        self._current_progress = progress
        self._current_download_id = download_id
        self.current_download_id = download_id
        self.current_worker = self.active_workers.get(download_id)
        worker = self.active_workers.get(download_id)
        speed = getattr(worker, "_last_speed", 0.0) if worker is not None else dl.speed
        self.queue_manager.update_progress(download_id, progress, speed, dl.eta)

    def _update_download_filename(self, download_id: str, filename: str):
        """Update the queued/download entry filename when the worker discovers the final filename."""
        try:
            download = self.queue_manager.get_download(download_id)
            if download:
                download.filename = filename or download.filename
                # Also update database with actual filename
                self.config.update_download_filename(download_id, download.filename)
            dialog = self.active_dialogs.get(download_id)
            if dialog is not None and filename:
                dialog.update_filename(filename)
        except Exception as e:
            print(f"[MainWindow] Error updating filename: {e}")

    def _on_filesize(self, download_id, size):
        """Handle filesize update for one specific download."""
        dl = self.queue_manager.get_download(download_id)
        if dl is not None:
            dl.size = int(size) if size is not None else 0
        if size is not None:
            self._current_filesize = int(size)
        dialog = self.active_dialogs.get(download_id)
        if dialog is not None and size is not None:
            dialog.filesize_label.setText(dialog._format_bytes(int(size)))

    def _on_rate(self, download_id, rate):
        """Handle transfer rate update for one specific download."""
        dl = self.queue_manager.get_download(download_id)
        if dl is None:
            return
        dl.speed = float(rate)
        self._current_speed = float(rate)
        self.queue_manager.update_progress(download_id, dl.progress, float(rate), dl.eta)

    def _on_eta(self, download_id, eta):
        """Handle ETA update for one specific download."""
        dl = self.queue_manager.get_download(download_id)
        if dl is None:
            return
        dl.eta = eta
        self._current_eta = eta
        self.queue_manager.update_progress(download_id, dl.progress, dl.speed, eta)

    def _on_message(self, download_id, msg):
        """Handle status message for one specific download."""
        print(f"[Worker:{download_id}] {msg}")
        if "Error" in msg or "error" in msg.lower():
            print(f"[QueueProcessor] Download failed: {msg}")
            self.queue_manager.mark_failed(download_id, msg)
            self.active_workers.pop(download_id, None)
            dialog = self.active_dialogs.pop(download_id, None)
            if dialog is not None:
                try:
                    dialog.close()
                except Exception:
                    pass
            if self.current_download_id == download_id:
                self.current_worker = None
                self.current_download_id = None

    def _on_download_finished(self, download_id, filepath):
        """Handle download completion for one specific download."""
        print(f"[QueueProcessor] Download completed: {filepath}")
        dl = self.queue_manager.get_download(download_id)
        if dl is not None:
            self.queue_manager.mark_completed(download_id, filepath)
            self.download_finished.emit(download_id, filepath, self._current_filesize)
        dialog = self.active_dialogs.pop(download_id, None)
        if dialog is not None:
            try:
                dialog.close()
            except Exception:
                pass
        self.active_workers.pop(download_id, None)
        if self.current_download_id == download_id:
            self.current_worker = None
            self.current_download_id = None
        self._current_filesize = 0
        self._current_progress = 0
        self._current_speed = 0.0
        self._current_eta = "-"
    
    def pause(self):
        """Pause queue processing"""
        self._is_paused = True
        if self.current_worker and self.current_worker.isRunning():
            self.current_worker.pause()
    
    def resume(self):
        """Resume queue processing"""
        self._is_paused = False
        # Ensure timer is always running
        if self.check_timer.isActive():
            self.check_timer.stop()
        self.check_timer.start(100)
        if self.current_worker:
            self.current_worker.resume()
        # Force immediate check
        self._check_and_start_next()
    
    def stop(self):
        """Stop processing"""
        self._is_paused = True
        if self.check_timer.isActive():
            self.check_timer.stop()
        if self.current_worker and self.current_worker.isRunning():
            self.current_worker.cancel()
        if self.current_progress_dialog:
            try:
                self.current_progress_dialog.close()
            except:
                pass


class PyDMMainWindow(QMainWindow):
    """PyDM Main Window - Professional Download Manager"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{__app_name__} - Python Download Manager v{__version__}")
        self.setWindowIcon(self._get_icon("assets/icon.ico"))
        self.resize(1200, 700)
        
        # Initialize config and database
        self.config = get_config()
        
        # Browser integration - receive URLs from browser extension
        self.native_receiver = NativeReceiver()
        self.native_receiver.url_received.connect(self._on_browser_url_received)
        self.native_receiver.start_server()
        
        # Download queue
        self.queue_manager = DownloadQueueManager(max_concurrent=3)
        self.queue_processor = DownloadQueueProcessor(self.queue_manager)
        
        # Data
        self.download_id_counter = 0
        self.download_progress_dialogs = {}  # {id: dialog}
        # Keep references to non-modal completion dialogs so they are not GC'd
        self._completion_dialogs = []
        # Track current category filter
        self._current_category_filter = "all"
        # Store download category mapping: {download_id: category}
        self._download_categories = {}
        
        # Setup UI
        self._setup_ui()
        self._setup_menu_bar()
        self._setup_toolbar()
        self._setup_status_bar()
        self._setup_tray()
        
        # Apply stylesheet
        self.setStyleSheet(IDM_STYLESHEET)
        
        # Setup callbacks (after UI is initialized)
        self.queue_manager.on_queue_changed = self._on_queue_changed
        self.queue_manager.on_progress = self._on_download_progress
        self.queue_manager.on_completed = self._on_download_completed
        self.queue_manager.on_failed = self._on_download_failed
        self.queue_processor.download_started.connect(self._on_download_started)
        self.queue_processor.download_finished.connect(self._on_download_finished_with_info)
        # Update UI when worker reports filesize early
        try:
            self.queue_processor.filesize_emitted.connect(self._on_filesize_emitted)
        except Exception:
            pass
        
        # Load previous downloads from database
        self._load_downloads_from_database()
        
        # Start queue processor AFTER everything is set up
        self.queue_processor.start()
    
    def _on_browser_url_received(self, url):
        """Handle URL received from browser extension"""
        clean_url = str(url).strip().replace("\r", "").replace("\n", "")
        print(f"[MainWindow] URL received from browser: {clean_url}")
        final_url, filename = resolve_url_metadata(clean_url)
        self.status_label.set_text_with_status(
            f"URL from browser: {final_url[:50]}...", "downloading"
        )

        # Open a non-modal AddDownloadDialog (no parent) so it stays visible
        # independently when the main window is minimized to tray.
        dialog = AddDownloadDialog({"url": final_url, "filename": filename}, None)
        dialog.finished.connect(lambda result, dlg=dialog: self._on_add_dialog_finished(dlg, result))
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()
    
    def _get_icon(self, icon_name: str) -> QIcon:
        """Get application icon with support for built apps (nuitka, pyinstaller)"""
        try:
            # Import here to avoid circular imports with app.py
            from pydm.app import get_data_path
            icon_path = get_data_path(*icon_name.split('/'))
            return QIcon(str(icon_path))
        except Exception:
            pass
        return QIcon()
    
    def _get_current_date(self) -> str:
        """Get current date formatted"""
        return datetime.now().strftime("%b %d %Y")
    
    def _setup_ui(self):
        """Setup main UI layout"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Splitter for sidebar and content
        splitter = QSplitter(Qt.Horizontal)
        
        # Left sidebar - categories
        self.sidebar = SidebarCategoryWidget()
        self.sidebar.setMaximumWidth(200)
        self.sidebar.category_selected.connect(self._on_category_selected)
        splitter.addWidget(self.sidebar)
        
        # Right side - downloads list and statistics
        right_layout = QVBoxLayout()
        right_layout.setContentsMargins(0, 0, 0, 0)
        
        # Downloads list
        self.download_list = DownloadListWidget()
        self.download_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.download_list.customContextMenuRequested.connect(self._on_download_context_menu)
        
        # Connect column width changes to save them
        self.download_list.column_widths_changed.connect(self._on_column_widths_changed)
        
        # Restore saved column widths
        saved_widths = self.config.load_column_widths()
        if saved_widths:
            print(f"[MainWindow] Restoring {len(saved_widths)} saved column widths...")
            self.download_list.restore_column_widths(saved_widths)
        else:
            print(f"[MainWindow] No saved column widths found, using defaults")
        
        right_layout.addWidget(self.download_list)
        
        # Statistics panel
        self.statistics_widget = StatisticsWidget()
        right_layout.addWidget(self.statistics_widget)
        
        right_widget = QWidget()
        right_widget.setLayout(right_layout)
        splitter.addWidget(right_widget)
        
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)
        
        layout.addWidget(splitter)
        central_widget.setLayout(layout)
    
    def _setup_menu_bar(self):
        """Setup menu bar"""
        menubar = self.menuBar()
        
        # File Menu
        file_menu = menubar.addMenu("&File")
        
        add_action = QAction("&Add Download...", self)
        add_action.setShortcut(QKeySequence.New)
        add_action.triggered.connect(self._add_download)
        file_menu.addAction(add_action)
        
        file_menu.addSeparator()
        exit_action = QAction("E&xit", self)
        exit_action.setShortcut(QKeySequence.Quit)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # Downloads Menu
        downloads_menu = menubar.addMenu("&Downloads")
        
        start_all_action = QAction("&Start All", self)
        start_all_action.triggered.connect(self._start_all_downloads)
        downloads_menu.addAction(start_all_action)
        
        pause_all_action = QAction("&Pause All", self)
        pause_all_action.triggered.connect(self._pause_all_downloads)
        downloads_menu.addAction(pause_all_action)
        
        stop_all_action = QAction("Sto&p All", self)
        stop_all_action.triggered.connect(self._stop_all_downloads)
        downloads_menu.addAction(stop_all_action)
        
        downloads_menu.addSeparator()
        
        remove_action = QAction("&Remove Selected", self)
        remove_action.triggered.connect(self._remove_selected_downloads)
        downloads_menu.addAction(remove_action)
        
        clear_action = QAction("&Clear Completed", self)
        clear_action.triggered.connect(self._clear_completed_downloads)
        downloads_menu.addAction(clear_action)
        
        # View Menu
        view_menu = menubar.addMenu("&View")
        
        refresh_action = QAction("&Refresh", self)
        refresh_action.setShortcut(Qt.CTRL | Qt.Key_R)
        refresh_action.triggered.connect(self._refresh_view)
        view_menu.addAction(refresh_action)
        
        view_menu.addSeparator()
        
        tray_action = QAction("Show in &Tray", self)
        tray_action.setCheckable(True)
        tray_action.setChecked(True)
        view_menu.addAction(tray_action)
        
        # Tools Menu
        tools_menu = menubar.addMenu("&Tools")
        
        options_action = QAction("&Options", self)
        options_action.setShortcut(Qt.CTRL | Qt.Key_Comma)
        options_action.triggered.connect(self._show_options)
        tools_menu.addAction(options_action)
        
        batch_action = QAction("&Batch Download", self)
        batch_action.triggered.connect(self._batch_download)
        tools_menu.addAction(batch_action)
        
        # Tasks Menu
        tasks_menu = menubar.addMenu("&Tasks")
        
        scheduler_action = QAction("&Scheduler", self)
        scheduler_action.triggered.connect(self._show_scheduler)
        tasks_menu.addAction(scheduler_action)
        
        # Help Menu
        help_menu = menubar.addMenu("&Help")
        
        about_action = QAction("&About", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)
    
    def _setup_toolbar(self):
        """Setup toolbar"""
        toolbar = self.addToolBar("Main Toolbar")
        toolbar.setMovable(False)
        toolbar.setIconSize(QSize(24, 24))
        
        # Add URL button
        add_btn = ToolbarButton("Add URL", tooltip="Add new download")
        add_btn.clicked.connect(self._add_download)
        toolbar.addWidget(add_btn)
        
        toolbar.addSeparator()
        
        # Control buttons
        resume_btn = ToolbarButton("Resume", tooltip="Start all downloads")
        resume_btn.clicked.connect(self._start_all_downloads)
        toolbar.addWidget(resume_btn)
        
        pause_btn = ToolbarButton("Pause", tooltip="Pause all downloads")
        pause_btn.clicked.connect(self._pause_all_downloads)
        toolbar.addWidget(pause_btn)
        
        stop_btn = ToolbarButton("Stop All", tooltip="Stop all downloads")
        stop_btn.clicked.connect(self._stop_all_downloads)
        toolbar.addWidget(stop_btn)
        
        toolbar.addSeparator()
        
        # Delete button
        delete_btn = ToolbarButton("Delete", tooltip="Delete selected downloads")
        delete_btn.clicked.connect(self._remove_selected_downloads)
        toolbar.addWidget(delete_btn)
        
        toolbar.addSeparator()
        
        # Options
        options_btn = ToolbarButton("Options", tooltip="Settings")
        options_btn.clicked.connect(self._show_options)
        toolbar.addWidget(options_btn)
    
    def _setup_status_bar(self):
        """Setup status bar"""
        self.status_label = StatusLabel("Ready")
        self.statusBar().addWidget(self.status_label, 1)
    
    def _setup_tray(self):
        """Setup system tray"""
        try:
            self.tray = QSystemTrayIcon(self)
            self.tray.setIcon(self.windowIcon())

            tray_menu = QMenu()

            restore_action = QAction("Restore", self)
            restore_action.triggered.connect(self.showNormal)
            tray_menu.addAction(restore_action)

            tray_menu.addSeparator()

            exit_action = QAction("Exit", self)
            # Ensure exit performs clean application shutdown
            exit_action.triggered.connect(self._on_exit)
            tray_menu.addAction(exit_action)

            self.tray.setContextMenu(tray_menu)
            self.tray.activated.connect(self._on_tray_activated)
            self.tray.show()
        except Exception:
            # If tray isn't available or setup fails, continue silently
            try:
                self.tray = None
            except Exception:
                pass
    
    def _on_tray_activated(self, reason):
        """Handle tray icon activation"""
        if reason == QSystemTrayIcon.DoubleClick:
            if self.isVisible():
                self.hide()
            else:
                self.showNormal()

    def _on_exit(self):
        """Clean shutdown invoked from tray Exit action."""
        try:
            # Stop queue processing timer and prevent new starts
            try:
                self.queue_processor.stop()
            except Exception:
                pass

            # Cancel currently running worker if any
            try:
                w = getattr(self.queue_processor, 'current_worker', None)
                if w is not None and hasattr(w, 'isRunning') and w.isRunning():
                    try:
                        w.cancel()
                        w.wait(1000)
                    except Exception:
                        try:
                            w.terminate()
                            w.wait(500)
                        except Exception:
                            pass
            except Exception:
                pass

            # Close any outstanding completion dialogs we keep references to
            try:
                for d in list(getattr(self, '_completion_dialogs', [])):
                    try:
                        d.close()
                    except Exception:
                        pass
            except Exception:
                pass

            # Hide tray icon
            try:
                if getattr(self, 'tray', None):
                    self.tray.hide()
            except Exception:
                pass

        finally:
            # Quit the application
            try:
                QApplication.instance().quit()
            except Exception:
                try:
                    sys.exit(0)
                except Exception:
                    pass
    
    def _add_download(self):
        """Show download options dialog"""
        dialog = DownloadOptionsDialog(self)
        if dialog.exec() == QDialog.Accepted:
            info = dialog.get_download_info()
            # Use helper to enqueue download (keeps logic centralized)
            self._enqueue_download(info)

    def _load_downloads_from_database(self):
        """Load previous downloads from database on startup"""
        try:
            downloads = self.config.get_all_downloads(include_deleted=False)
            for dl_info in downloads:
                # Reconstruct QueuedDownload from database
                download_id = dl_info["download_id"]
                filename = dl_info["filename"]
                url = dl_info["url"]
                category = dl_info["category"]
                folder = dl_info["save_folder"]
                status = dl_info["status"]
                temp_folder = dl_info["temp_folder"]
                
                # Update counter if needed
                if download_id.startswith("dl_"):
                    try:
                        counter = int(download_id.split("_")[1])
                        self.download_id_counter = max(self.download_id_counter, counter)
                    except:
                        pass
                
                # Restore boolean fields (stored as 0/1 in database)
                resume = bool(dl_info.get("resume", 1))
                skip_existing = bool(dl_info.get("skip_existing", 0))
                use_proxy = bool(dl_info.get("use_proxy", 0))
                start_immediately = bool(dl_info.get("start_immediately", 1))
                auto_start = bool(dl_info.get("auto_start", 1))
                high_priority = bool(dl_info.get("high_priority", 0))
                
                # Recreate QueuedDownload object
                queued = QueuedDownload(
                    download_id=download_id,
                    url=url,
                    folder=folder,
                    filename=filename,
                    category=category,
                    comments=dl_info.get("comments", ""),
                    connections=int(dl_info.get("connections", 4)),
                    timeout=int(dl_info.get("timeout", 30)),
                    retry_count=int(dl_info.get("retry_count", 3)),
                    speed_limit=int(dl_info.get("speed_limit", 0)),
                    resume=resume,
                    skip_existing=skip_existing,
                    use_proxy=use_proxy,
                    proxy_url=dl_info.get("proxy_url", ""),
                    start_immediately=start_immediately,
                    auto_start=auto_start,
                    high_priority=high_priority,
                    post_action=dl_info.get("post_action", "No Action"),
                    temp_folder=temp_folder or "",
                    status=status,
                )
                
                # Format size display - show "Unknown" if 0, otherwise format it
                total_size = int(dl_info.get("total_size", 0))
                if total_size > 0:
                    size_display = self._format_size_for_table(total_size)
                else:
                    size_display = "Unknown"
                
                # For completed downloads, show 100% progress
                progress_pct = "100%" if status == "completed" else "0%"
                
                # Add to UI list with proper size formatting
                row = self.download_list.add_download(
                    filename, size_display, status.capitalize(), 
                    "0 KB/s", "-", progress_pct,
                    self._get_current_date(),
                    download_id=download_id,
                )
                
                # Store category
                self._download_categories[download_id] = category
                if self.download_list.item(row, 0):
                    self.download_list.item(row, 0).setData(Qt.UserRole + 1, category)
                
                # Re-queue if download was pending or paused
                if status in ["pending", "paused"]:
                    self.queue_manager.add_download(queued)
                    print(f"[MainWindow] Restored and re-queued: {filename}")
                else:
                    # Store as completed or failed without re-queuing
                    if status == "completed":
                        self.queue_manager.completed[download_id] = queued
                    elif status == "failed":
                        self.queue_manager.failed[download_id] = queued
                    print(f"[MainWindow] Loaded completed/failed download: {filename} ({status})")
        except Exception as e:
            print(f"[MainWindow] Error loading downloads from database: {e}")
            import traceback
            traceback.print_exc()

    def _on_add_dialog_finished(self, dialog: AddDownloadDialog, result: int):
        """Handle finished AddDownloadDialog (non-modal)."""
        # Only handle accepted results and when user chose add/download
        try:
            action = getattr(dialog, 'action', None)
            if result == QDialog.Accepted and action in ("add", "download"):
                info = dialog.get_download_info()
                self._enqueue_download(info)
        except Exception:
            pass

    def _enqueue_download(self, info: dict):
        """Create QueuedDownload from info dict and add to queue/UI."""
        url = info.get("url", "").strip()
        if not url:
            QMessageBox.warning(self, "Error", "Please enter a valid URL")
            return

        # Create unique ID
        self.download_id_counter += 1
        download_id = f"dl_{self.download_id_counter}"

        # Create queued download
        folder = info.get("folder") or str(Path.home() / "Downloads")
        final_url, resolved_filename = resolve_url_metadata(url)
        filename = info.get("filename") or resolved_filename or Path(urlparse(final_url).path).name or "download.bin"
        if not info.get("filename") and filename:
            info["filename"] = filename
        url = info.get("url") or final_url
        category_display = info.get("category", "General")
        # Map display names to category keys for filtering
        category_map = {
            "General": "general",
            "Compressed": "compressed",
            "Documents": "document",
            "Music": "music",
            "Video": "video",
            "Programs": "program",
        }
        category = category_map.get(category_display, "general")

        # Get temp folder for this download (like IDM structure)
        temp_folder = self.config.get_download_temp_folder(download_id, filename)

        queued = QueuedDownload(
            download_id=download_id,
            url=url,
            folder=folder,
            filename=filename,
            category=category,
            comments=info.get("comments", ""),
            connections=info.get("connections", 4),
            timeout=info.get("timeout", 30),
            retry_count=info.get("retry_count", 3),
            speed_limit=info.get("speed_limit", 0),
            resume=info.get("resume", True),
            skip_existing=info.get("skip_existing", False),
            use_proxy=info.get("use_proxy", False),
            proxy_url=info.get("proxy_url", ""),
            start_immediately=info.get("start_immediately", True),
            auto_start=info.get("auto_start", True),
            high_priority=info.get("high_priority", False),
            post_action=info.get("post_action", "No Action"),
            temp_folder=str(temp_folder),
            added_at=datetime.now().isoformat(),
        )
        
        # Save to database with complete download information
        self.config.save_download(
            download_id=download_id,
            filename=filename,
            url=url,
            save_folder=folder,
            category=category,
            total_size=0,  # Will be updated during download
            temp_folder=str(temp_folder),
            status='pending',
            comments=queued.comments,
            connections=queued.connections,
            timeout=queued.timeout,
            retry_count=queued.retry_count,
            speed_limit=queued.speed_limit,
            resume=queued.resume,
            skip_existing=queued.skip_existing,
            use_proxy=queued.use_proxy,
            proxy_url=queued.proxy_url,
            start_immediately=queued.start_immediately,
            auto_start=queued.auto_start,
            high_priority=queued.high_priority,
            post_action=queued.post_action,
        )

        # Add to queue
        self.queue_manager.add_download(queued)

        # Store category for filtering
        self._download_categories[download_id] = category

        # Add to list UI
        row = self.download_list.add_download(
            filename, "Unknown", "Queued", "0 KB/s", "-", "0%",
            self._get_current_date(),
            download_id=download_id,
        )
        # Store category in the row for filtering
        if self.download_list.item(row, 0):
            self.download_list.item(row, 0).setData(Qt.UserRole + 1, category)
        self.download_list.scrollToBottom()
        self.download_list.resizeRowsToContents()
        self.download_list.repaint()

        # Ensure queue processing continues after a new download is added
        # Force an immediate timer restart to guarantee processing
        if not self.queue_processor.check_timer.isActive():
            self.queue_processor.check_timer.start(100)
        self.queue_processor._is_paused = False
        self.queue_processor._check_and_start_next()
        
        if self.queue_processor.current_worker is not None and self.queue_processor.current_worker.isRunning():
            self.status_label.set_text_with_status(
                f"Queued: {filename} ({category})", "idle"
            )
        else:
            self.status_label.set_text_with_status(
                f"Added: {filename} ({category})", "downloading"
            )
    
    def _find_row_for_download(self, download_id: str):
        """Find the row index for a download ID."""
        for row in range(self.download_list.rowCount()):
            if self.download_list.get_download_id(row) == download_id:
                return row
        return None

    def _format_speed(self, speed: float) -> str:
        """Format speed to human readable string."""
        if speed >= 1024 * 1024:
            return f"{speed / (1024*1024):.2f} MB/s"
        if speed >= 1024:
            return f"{speed / 1024:.2f} KB/s"
        if speed > 0:
            return f"{speed:.0f} B/s"
        return "-"

    def _on_download_started(self, download_id: str):
        """Handle download started"""
        download = self.queue_manager.get_download(download_id)
        if download:
            self.status_label.set_text_with_status(
                f"Downloading: {download.filename}", "downloading"
            )
            row = self._find_row_for_download(download_id)
            if row is not None:
                self.download_list.update_download_row(row, status="Downloading", speed="-", eta="-", progress=0)

    def _on_filesize_emitted(self, download_id: str, size: int):
        """Update the downloads list size cell when filesize is available."""
        try:
            download = self.queue_manager.get_download(download_id)
            if download is not None:
                download.size = int(size) if size is not None else 0
                # Update database with the discovered filesize
                self.config.update_download_status(download_id, download.status, total_size=int(size) if size else 0)
            row = self._find_row_for_download(download_id)
            if row is not None and size is not None:
                size_text = self._format_size_for_table(size)
                item = self.download_list.item(row, 1)
                if item:
                    item.setText(size_text)
        except Exception:
            pass

    def _format_size_for_table(self, size: int) -> str:
        try:
            if size is None or size <= 0:
                return "Unknown"
            mb = size / (1024 * 1024)
            if mb >= 1:
                return f"{mb:.2f} MB"
            kb = size / 1024
            if kb >= 1:
                return f"{kb:.0f} KB"
            return f"{size} B"
        except Exception:
            return "Unknown"

    def _on_download_progress(self, download_id: str, progress: int, speed: float = 0.0, eta: str = "-"):
        """Handle download progress updates"""
        row = self._find_row_for_download(download_id)
        if row is None:
            return
        download = self.queue_manager.get_download(download_id)
        if download is None:
            return
        if download.size and self.download_list.item(row, 1):
            self.download_list.item(row, 1).setText(self._format_size_for_table(download.size))
        if self.download_list.item(row, 0):
            self.download_list.item(row, 0).setText(download.filename)
        
        # Calculate downloaded bytes based on progress percentage
        downloaded = int((progress / 100.0) * download.size) if download.size and progress > 0 else 0
        
        # Update database with progress
        self.config.update_download_status(
            download_id, 
            download.status, 
            downloaded_size=downloaded, 
            total_size=download.size if download.size else 0
        )
        
        self.download_list.update_download_row(
            row,
            status=download.status.capitalize(),
            speed=self._format_speed(speed) if speed else self._format_speed(download.speed),
            eta=eta if eta != "-" else download.eta,
            progress=progress,
        )

    def _on_download_finished_with_info(self, download_id: str, filepath: str, filesize: int):
        """Handle download completion and show completion dialog"""
        download = self.queue_manager.get_download(download_id)
        if download:
            # Show completion dialog
            completion_info = {
                "url": download.url,
                "filepath": filepath,
                "file_size": filesize,
                "filename": download.filename,
            }
            # Create the completion dialog without a parent so it remains
            # independent (can be minimized/kept visible when main window is hidden)
            dialog = DownloadCompleteDialog(completion_info, None)
            dialog.setAttribute(Qt.WA_DeleteOnClose, True)
            dialog.show()
            dialog.raise_()
            dialog.activateWindow()
            # Keep a reference so Python doesn't garbage-collect it immediately
            try:
                self._completion_dialogs.append(dialog)
                # Remove from list when closed
                dialog.destroyed.connect(lambda _obj=None, d=dialog: self._completion_dialogs.remove(d) if d in self._completion_dialogs else None)
            except Exception:
                pass

    def _on_download_completed(self, download_id: str, filepath: str):
        """Handle download completion"""
        row = self._find_row_for_download(download_id)
        if row is not None:
            self.download_list.update_download_row(row, status="Completed", speed="0 KB/s", eta="-", progress=100)
        # Update database status AND filepath (actual saved path with unique name)
        self.config.update_download_status(download_id, "completed")
        self.config.update_download_filepath(download_id, filepath)
        self.status_label.set_text_with_status("Download completed", "completed")

    def _on_download_failed(self, download_id: str, error_message: str):
        """Handle download failure"""
        row = self._find_row_for_download(download_id)
        if row is not None:
            self.download_list.update_download_row(row, status="Failed", speed="0 KB/s", eta="-", progress=0)
        # Update database status
        self.config.update_download_status(download_id, "failed")
        self.status_label.set_text_with_status(f"Download failed: {error_message}", "error")

    def _on_queue_changed(self):
        """Handle queue changes"""
        stats = self.queue_manager.get_statistics()
        total_downloads = stats["queued"] + stats["active"] + stats["completed"] + stats["failed"]
        self.statistics_widget.update_statistics(
            total=total_downloads,
            active=stats["active"],
            speed=stats["total_speed"],
            downloaded=0  # TODO: Calculate total downloaded bytes for better info
        )
    
    def _start_all_downloads(self):
        """Start all downloads"""
        print("[UI] Starting all downloads")
        self.queue_processor.resume()
        self.status_label.set_text_with_status("Starting downloads...", "downloading")
    
    def _pause_all_downloads(self):
        """Pause all downloads"""
        print("[UI] Pausing all downloads")
        self.queue_manager.pause()
        self.queue_processor.pause()
        self.status_label.set_text_with_status("Downloads paused", "idle")
    
    def _stop_all_downloads(self):
        """Stop all downloads"""
        print("[UI] Stopping all downloads")
        self.queue_manager.pause()
        self.queue_processor.stop()
        self.status_label.set_text_with_status("Downloads stopped", "idle")
    
    def _remove_selected_downloads(self):
        """Remove selected downloads"""
        selected = self.download_list.get_selected_rows()
        if not selected:
            QMessageBox.information(self, "Info", "No downloads selected")
            return
        
        reply = QMessageBox.question(
            self, "Remove Downloads",
            f"Remove {len(selected)} download(s)?"
        )
        if reply == QMessageBox.Yes:
            rows = sorted(selected, reverse=True)
            for row in rows:
                download_id = self.download_list.get_download_id(row)
                if download_id:
                    self.queue_manager.cancel_download(download_id)
                    if download_id == self.queue_processor.current_download_id:
                        self.queue_processor.stop()
                    # Delete from database and remove temp files
                    self.config.delete_download(download_id, delete_files=True)
                self.download_list.remove_row(row)
            self.status_label.set_text_with_status(
                f"Removed {len(selected)} download(s)", "idle"
            )
    
    def _clear_completed_downloads(self):
        """Clear all completed downloads"""
        self.queue_manager.clear_completed()
        for row in range(self.download_list.rowCount() - 1, -1, -1):
            status_item = self.download_list.item(row, 2)
            if status_item and status_item.text().lower() == "completed":
                self.download_list.remove_row(row)
        self.status_label.set_text_with_status(
            "Cleared completed downloads", "idle"
        )
    
    def _refresh_view(self):
        """Refresh view"""
        self.status_label.set_text_with_status("Refreshed", "idle")
    
    def _on_download_context_menu(self, point):
        """Show right-click menu for download rows"""
        row = self.download_list.rowAt(point.y())
        if row < 0:
            return

        download_id = self.download_list.get_download_id(row)
        if not download_id:
            return

        menu = QMenu(self)
        open_file_action = QAction("Open File", self)
        open_file_action.triggered.connect(lambda: self._open_file(download_id))
        menu.addAction(open_file_action)

        open_folder_action = QAction("Open Folder", self)
        open_folder_action.triggered.connect(lambda: self._open_folder(download_id))
        menu.addAction(open_folder_action)

        pause_action = QAction("Pause", self)
        pause_action.triggered.connect(lambda: self._pause_download(download_id))
        menu.addAction(pause_action)

        resume_action = QAction("Resume", self)
        resume_action.triggered.connect(lambda: self._resume_download(download_id))
        menu.addAction(resume_action)

        cancel_action = QAction("Cancel", self)
        cancel_action.triggered.connect(lambda: self._cancel_download(download_id))
        menu.addAction(cancel_action)

        menu.addSeparator()

        remove_action = QAction("Remove", self)
        remove_action.triggered.connect(lambda: self._remove_download_row(row, download_id))
        menu.addAction(remove_action)

        # Add Redownload action to re-add and start the same download
        redownload_action = QAction("Redownload", self)
        def _redownload():
            dl = self.queue_manager.get_download(download_id)
            if not dl:
                return
            info = {
                "url": dl.url,
                "folder": dl.folder,
                "filename": dl.filename,
                "category": dl.category,
            }
            self._enqueue_download(info)
        redownload_action.triggered.connect(_redownload)
        menu.addAction(redownload_action)

        menu.exec(self.download_list.viewport().mapToGlobal(point))

    def _open_file(self, download_id: str):
        """Open downloaded file if available"""
        download = self.queue_manager.get_download(download_id)
        if not download or not download.completed_path:
            QMessageBox.warning(self, "Open File", "File is not available yet.")
            return
        try:
            os.startfile(download.completed_path)
        except Exception as exc:
            QMessageBox.warning(self, "Open File", f"Could not open file: {exc}")

    def _open_folder(self, download_id: str):
        """Open folder containing the downloaded file"""
        download = self.queue_manager.get_download(download_id)
        if not download or not download.completed_path:
            QMessageBox.warning(self, "Open Folder", "Download folder is not available yet.")
            return
        folder = Path(download.completed_path).parent
        try:
            os.startfile(folder)
        except Exception as exc:
            QMessageBox.warning(self, "Open Folder", f"Could not open folder: {exc}")

    def _pause_download(self, download_id: str):
        """Pause a specific download"""
        download = self.queue_manager.get_download(download_id)
        worker = self.queue_processor.active_workers.get(download_id)
        if worker is not None:
            try:
                worker.pause()
            except Exception:
                pass
            if download_id in self.queue_manager.active:
                try:
                    self.queue_manager.active[download_id].status = "paused"
                    self._on_download_progress(download_id, self.queue_manager.active[download_id].progress, self.queue_manager.active[download_id].speed, self.queue_manager.active[download_id].eta)
                except Exception:
                    pass
            self.status_label.set_text_with_status("Download paused", "paused")
            return

        # If it's queued but not running, mark as paused
        if download is not None:
            try:
                # If it's still in the queue list
                if download.download_id in [d.download_id for d in self.queue_manager.queue]:
                    download.status = "paused"
                    row = self._find_row_for_download(download_id)
                    if row is not None:
                        self.download_list.update_download_row(row, status="Paused")
                    self.status_label.set_text_with_status("Download paused", "paused")
                    return
            except Exception:
                pass

        # Otherwise cannot pause
        QMessageBox.information(self, "Pause", "Cannot pause this download")

    def _resume_download(self, download_id: str):
        """Resume a specific download"""
        download = self.queue_manager.get_download(download_id)
        worker = self.queue_processor.active_workers.get(download_id)
        if worker is not None:
            try:
                worker.resume()
            except Exception:
                pass
            if download_id in self.queue_manager.active:
                try:
                    self.queue_manager.active[download_id].status = "running"
                except Exception:
                    pass
            self.status_label.set_text_with_status("Download resumed", "downloading")
            return

        # If it's paused in the queue, mark as queued and resume processing
        if download is not None:
            try:
                if download.status == "paused":
                    download.status = "queued"
                    row = self._find_row_for_download(download_id)
                    if row is not None:
                        self.download_list.update_download_row(row, status="Queued")
                    self.queue_processor.resume()
                    self.status_label.set_text_with_status("Download resumed", "downloading")
                    return
            except Exception:
                pass

        QMessageBox.information(self, "Resume", "Cannot resume this download")

    def _cancel_download(self, download_id: str):
        """Cancel a specific download"""
        worker = self.queue_processor.active_workers.get(download_id)
        if worker is not None:
            try:
                worker.cancel()
            except Exception:
                pass
        self.queue_manager.cancel_download(download_id)
        self.queue_processor.active_workers.pop(download_id, None)
        self.queue_processor.active_dialogs.pop(download_id, None)
        self.status_label.set_text_with_status("Download cancelled", "idle")

    def _remove_download_row(self, row: int, download_id: str):
        """Remove a single download row from the table"""
        self.queue_manager.cancel_download(download_id)
        worker = self.queue_processor.active_workers.get(download_id)
        if worker is not None:
            try:
                worker.cancel()
            except Exception:
                pass
        self.queue_processor.active_workers.pop(download_id, None)
        self.queue_processor.active_dialogs.pop(download_id, None)
        self.download_list.remove_row(row)

    def _show_options(self):
        """Show options dialog"""
        QMessageBox.information(
            self, "Options",
            "Options dialog would appear here"
        )
    
    def _batch_download(self):
        """Show batch download dialog"""
        QMessageBox.information(
            self, "Batch Download",
            "Batch download feature coming soon"
        )
    
    def _show_scheduler(self):
        """Show scheduler"""
        QMessageBox.information(
            self, "Scheduler",
            "Scheduler feature coming soon"
        )
    
    def _show_about(self):
        """Show about dialog"""
        QMessageBox.about(
            self, f"About {__app_name__}",
            f"{__app_name__} v{__version__}\n"
            f"Professional Python Download Manager\n\n"
            f"Built with PySide6 and httpx"
        )
    
    def _on_category_selected(self, category):
        """Handle category selection and filter downloads"""
        category_names = {
            "all": "All Downloads",
            "general": "General Downloads",
            "compressed": "Compressed Archives",
            "document": "Documents",
            "music": "Music Files",
            "video": "Video Files",
            "program": "Programs & Installers",
        }
        
        # Update current category filter
        self._current_category_filter = category
        display_name = category_names.get(category, category)
        self.status_label.set_text_with_status(f"Category: {display_name}", "idle")
        
        # Filter downloads by category
        self._filter_downloads_by_category(category)
    
    def _filter_downloads_by_category(self, category: str):
        """Filter downloads to show only selected category"""
        for row in range(self.download_list.rowCount()):
            item = self.download_list.item(row, 0)
            if item:
                download_category = item.data(Qt.UserRole + 1)
                # Show row if: category is "all" OR row matches selected category
                show_row = (category == "all" or download_category == category)
                self.download_list.setRowHidden(row, not show_row)
    
    def _on_column_widths_changed(self):
        """Handle column width changes and save them"""
        try:
            # Get current column widths directly from the widget
            column_widths = self.download_list.get_column_widths()
            print(f"[MainWindow] Column widths changed signal received")
            self.config.save_column_widths(column_widths)
            print(f"[MainWindow] [OK] Column widths saved to database")
        except Exception as e:
            print(f"[MainWindow] [ERROR] Error saving column widths: {e}")
    
    def _populate_sample_downloads(self):
        """Populate with sample downloads for demonstration"""
        pass
    
    def closeEvent(self, event):
        """Handle window close"""
        self.queue_processor.stop()
        event.accept()
