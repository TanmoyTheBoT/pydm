"""
PyDM Download Options - Configuration dialog for downloads
"""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QSpinBox,
    QCheckBox, QComboBox, QPushButton, QTabWidget, QWidget, QGroupBox,
    QGridLayout, QFileDialog
)
from pathlib import Path

from pydm.downloader import resolve_url_metadata


class DownloadOptionsDialog(QDialog):
    """Enhanced dialog for adding and configuring downloads"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Download Options")
        self.setMinimumWidth(600)
        self.setMinimumHeight(500)
        self.setModal(True)
        
        layout = QVBoxLayout(self)
        
        # Create tab widget
        tabs = QTabWidget()
        layout.addWidget(tabs)
        
        # Tab 1: Basic Settings
        tabs.addTab(self._create_basic_tab(), "Basic")
        
        # Tab 2: Advanced Settings
        tabs.addTab(self._create_advanced_tab(), "Advanced")
        
        # Tab 3: Scheduling
        tabs.addTab(self._create_scheduling_tab(), "Scheduling")
        
        # Buttons
        button_layout = QHBoxLayout()
        
        ok_btn = QPushButton("Start Download")
        ok_btn.clicked.connect(self.accept)
        ok_btn.setMinimumHeight(36)
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        cancel_btn.setMinimumHeight(36)
        
        button_layout.addStretch()
        button_layout.addWidget(ok_btn)
        button_layout.addWidget(cancel_btn)
        layout.addLayout(button_layout)
    
    def _create_basic_tab(self):
        """Create basic settings tab"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # URL
        layout.addWidget(QLabel("Download URL:"))
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("https://example.com/file.zip")
        layout.addWidget(self.url_input)
        
        # Folder selection
        layout.addWidget(QLabel("Save to:"))
        folder_layout = QHBoxLayout()
        self.folder_input = QLineEdit()
        self.folder_input.setText(str(Path.home() / "Downloads"))
        folder_layout.addWidget(self.folder_input)
        
        browse_btn = QPushButton("Browse")
        browse_btn.clicked.connect(self._select_folder)
        browse_btn.setMaximumWidth(80)
        folder_layout.addWidget(browse_btn)
        layout.addLayout(folder_layout)
        
        # Category
        layout.addWidget(QLabel("Category:"))
        self.category_combo = QComboBox()
        self.category_combo.addItems([
            "General",
            "Compressed",
            "Documents",
            "Music",
            "Video",
            "Programs"
        ])
        layout.addWidget(self.category_combo)
        
        # File name
        layout.addWidget(QLabel("File Name (optional):"))
        self.filename_input = QLineEdit()
        self.filename_input.setPlaceholderText("Leave empty to auto-detect")
        layout.addWidget(self.filename_input)
        
        # Comments
        layout.addWidget(QLabel("Comments (optional):"))
        self.comments_input = QLineEdit()
        layout.addWidget(self.comments_input)
        
        layout.addStretch()
        return widget
    
    def _create_advanced_tab(self):
        """Create advanced settings tab"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Connections group
        conn_group = QGroupBox("Connection Settings")
        conn_layout = QGridLayout(conn_group)
        
        conn_layout.addWidget(QLabel("Connections:"), 0, 0)
        self.connections_spin = QSpinBox()
        self.connections_spin.setMinimum(1)
        self.connections_spin.setMaximum(32)
        self.connections_spin.setValue(4)
        self.connections_spin.setToolTip("Number of parallel connections (2-32)")
        conn_layout.addWidget(self.connections_spin, 0, 1)
        
        conn_layout.addWidget(QLabel("Connection Timeout (sec):"), 1, 0)
        self.timeout_spin = QSpinBox()
        self.timeout_spin.setMinimum(5)
        self.timeout_spin.setMaximum(300)
        self.timeout_spin.setValue(30)
        self.timeout_spin.setToolTip("Timeout for network requests")
        conn_layout.addWidget(self.timeout_spin, 1, 1)
        
        conn_layout.addWidget(QLabel("Retry Count:"), 2, 0)
        self.retry_spin = QSpinBox()
        self.retry_spin.setMinimum(0)
        self.retry_spin.setMaximum(10)
        self.retry_spin.setValue(3)
        self.retry_spin.setToolTip("Number of retries on failure")
        conn_layout.addWidget(self.retry_spin, 2, 1)
        
        layout.addWidget(conn_group)
        
        # Speed limit group
        speed_group = QGroupBox("Speed Limit")
        speed_layout = QGridLayout(speed_group)
        
        speed_layout.addWidget(QLabel("Max Speed (KB/s):"), 0, 0)
        self.speed_limit_spin = QSpinBox()
        self.speed_limit_spin.setMinimum(0)
        self.speed_limit_spin.setMaximum(102400)
        self.speed_limit_spin.setValue(0)
        self.speed_limit_spin.setToolTip("0 = Unlimited")
        speed_layout.addWidget(self.speed_limit_spin, 0, 1)
        
        layout.addWidget(speed_group)
        
        # Resume options group
        resume_group = QGroupBox("Resume Options")
        resume_layout = QVBoxLayout(resume_group)
        
        self.resume_check = QCheckBox("Enable Resume (if supported by server)")
        self.resume_check.setChecked(True)
        resume_layout.addWidget(self.resume_check)
        
        self.skip_exist_check = QCheckBox("Skip if file already exists")
        self.skip_exist_check.setChecked(False)
        resume_layout.addWidget(self.skip_exist_check)
        
        layout.addWidget(resume_group)
        
        # Proxy group
        proxy_group = QGroupBox("Proxy Settings")
        proxy_layout = QVBoxLayout(proxy_group)
        
        self.use_proxy_check = QCheckBox("Use Proxy")
        self.use_proxy_check.setChecked(False)
        proxy_layout.addWidget(self.use_proxy_check)
        
        proxy_url_layout = QHBoxLayout()
        proxy_url_layout.addWidget(QLabel("Proxy URL:"))
        self.proxy_input = QLineEdit()
        self.proxy_input.setPlaceholderText("http://proxy.example.com:8080")
        self.proxy_input.setEnabled(False)
        self.use_proxy_check.toggled.connect(self.proxy_input.setEnabled)
        proxy_url_layout.addWidget(self.proxy_input)
        proxy_layout.addLayout(proxy_url_layout)
        
        layout.addWidget(proxy_group)
        
        layout.addStretch()
        return widget
    
    def _create_scheduling_tab(self):
        """Create scheduling tab"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Download timing group
        timing_group = QGroupBox("Download Timing")
        timing_layout = QVBoxLayout(timing_group)
        
        self.start_immediately_radio = QCheckBox("Start Immediately")
        self.start_immediately_radio.setChecked(True)
        timing_layout.addWidget(self.start_immediately_radio)
        
        # Queue options
        queue_group = QGroupBox("Queue Options")
        queue_layout = QVBoxLayout(queue_group)
        
        self.auto_start_check = QCheckBox("Auto-start when added to queue")
        self.auto_start_check.setChecked(True)
        queue_layout.addWidget(self.auto_start_check)
        
        self.queue_priority_check = QCheckBox("High Priority (move to front of queue)")
        self.queue_priority_check.setChecked(False)
        queue_layout.addWidget(self.queue_priority_check)
        
        layout.addWidget(timing_group)
        layout.addWidget(queue_group)
        
        # Post-download actions
        action_group = QGroupBox("After Download")
        action_layout = QVBoxLayout(action_group)
        
        action_layout.addWidget(QLabel("Action:"))
        self.post_action_combo = QComboBox()
        self.post_action_combo.addItems([
            "No Action",
            "Open Folder",
            "Open File",
            "Run Program",
            "Move to Folder",
            "Convert Media"
        ])
        action_layout.addWidget(self.post_action_combo)
        
        layout.addWidget(action_group)
        layout.addStretch()
        
        return widget
    
    def _select_folder(self):
        """Select download folder"""
        folder = QFileDialog.getExistingDirectory(self, "Select Download Folder")
        if folder:
            self.folder_input.setText(folder)
    
    def get_download_info(self):
        """Get all download information"""
        return {
            "url": self.url_input.text().strip(),
            "folder": self.folder_input.text().strip(),
            "filename": self.filename_input.text().strip(),
            "category": self.category_combo.currentText(),
            "comments": self.comments_input.text().strip(),
            "connections": self.connections_spin.value(),
            "timeout": self.timeout_spin.value(),
            "retry_count": self.retry_spin.value(),
            "speed_limit": self.speed_limit_spin.value(),
            "resume": self.resume_check.isChecked(),
            "skip_existing": self.skip_exist_check.isChecked(),
            "use_proxy": self.use_proxy_check.isChecked(),
            "proxy_url": self.proxy_input.text().strip(),
            "start_immediately": self.start_immediately_radio.isChecked(),
            "auto_start": self.auto_start_check.isChecked(),
            "high_priority": self.queue_priority_check.isChecked(),
            "post_action": self.post_action_combo.currentText(),
        }


class AddDownloadDialog(QDialog):
    """Compact add-download popup similar to common download managers

    Shows a simple form with URL, save folder, filename, category and
    buttons for Add / Download / Cancel. Use `get_download_info()` after
    accept to retrieve the entered values and check the `action` attribute
    to know which button the user pressed ('add' or 'download').
    """

    def __init__(self, download_info=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add download")
        self.setMinimumWidth(560)
        # Make this dialog a top-level window with minimize button so it
        # remains visible independently when the main window is minimized
        # to tray.
        self.setWindowFlags(self.windowFlags() | Qt.Window | Qt.WindowMinimizeButtonHint | Qt.WindowCloseButtonHint)
        self.setModal(False)
        self.setWindowModality(Qt.NonModal)
        self.action = None

        layout = QVBoxLayout(self)

        # URL (read-only)
        layout.addWidget(QLabel("URL:"))
        self.url_input = QLineEdit()
        self.url_input.setReadOnly(True)
        layout.addWidget(self.url_input)

        # Save folder row
        layout.addWidget(QLabel("Save to:"))
        folder_row = QHBoxLayout()
        self.folder_input = QLineEdit()
        self.folder_input.setText(str(Path.home() / "Downloads"))
        folder_row.addWidget(self.folder_input)
        browse_btn = QPushButton("...")
        browse_btn.setMaximumWidth(36)
        browse_btn.clicked.connect(self._select_folder)
        folder_row.addWidget(browse_btn)
        layout.addLayout(folder_row)

        # Save as (filename)
        layout.addWidget(QLabel("Save As:"))
        self.filename_input = QLineEdit()
        layout.addWidget(self.filename_input)

        # Category + remember checkbox
        cat_row = QHBoxLayout()
        cat_row.addWidget(QLabel("Category:"))
        self.category_combo = QComboBox()
        self.category_combo.addItems([
            "General",
            "Compressed",
            "Documents",
            "Music",
            "Video",
            "Programs",
        ])
        cat_row.addWidget(self.category_combo)
        layout.addLayout(cat_row)

        self.remember_path_check = QCheckBox("Remember this path for the selected category")
        layout.addWidget(self.remember_path_check)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self.add_btn = QPushButton("Add")
        self.add_btn.clicked.connect(self._on_add)
        btn_row.addWidget(self.add_btn)

        self.download_btn = QPushButton("Download")
        self.download_btn.clicked.connect(self._on_download)
        self.download_btn.setDefault(True)
        btn_row.addWidget(self.download_btn)

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(self.cancel_btn)

        layout.addLayout(btn_row)

        # Prefill if provided
        if download_info:
            raw_url = download_info.get("url", "")
            final_url, final_filename = resolve_url_metadata(raw_url) if raw_url else (raw_url, "")
            self.url_input.setText(final_url)
            self.filename_input.setText(download_info.get("filename") or final_filename)
            self.category_combo.setCurrentText(download_info.get("category", "General"))
            self.folder_input.setText(download_info.get("folder", str(Path.home() / "Downloads")))

    def _select_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Download Folder")
        if folder:
            self.folder_input.setText(folder)

    def _on_add(self):
        self.action = "add"
        self.accept()

    def _on_download(self):
        self.action = "download"
        self.accept()

    def get_download_info(self):
        return {
            "url": self.url_input.text().strip(),
            "folder": self.folder_input.text().strip(),
            "filename": self.filename_input.text().strip(),
            "category": self.category_combo.currentText(),
            "remember_path": self.remember_path_check.isChecked(),
            "action": self.action,
        }
