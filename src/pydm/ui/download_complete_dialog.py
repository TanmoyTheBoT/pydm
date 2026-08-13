"""
Download Complete Dialog - Shows completion info and provides file actions
"""
import os
from pathlib import Path
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QCheckBox, QGroupBox, QFormLayout, QLineEdit
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QPixmap, QIcon


def _format_bytes(bytes_value):
    """Format bytes to human readable"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if bytes_value < 1024:
            return f"{bytes_value:.2f} {unit}"
        bytes_value /= 1024
    return f"{bytes_value:.2f} TB"


class DownloadCompleteDialog(QDialog):
    """Dialog shown when download completes with file info and actions"""
    
    def __init__(self, download_info, parent=None):
        super().__init__(parent)
        self.download_info = download_info
        self.setWindowTitle("Download complete")
        self.setMinimumWidth(500)
        # Make this a top-level non-modal window with minimize/maximize/close
        try:
            self.setWindowFlags(self.windowFlags() | Qt.Window | Qt.WindowMinimizeButtonHint | Qt.WindowMaximizeButtonHint | Qt.WindowCloseButtonHint)
            self.setWindowModality(Qt.NonModal)
        except Exception:
            pass
        
        self._setup_ui()
    
    def _setup_ui(self):
        """Setup UI components"""
        layout = QVBoxLayout(self)
        
        # Title with icon
        title_layout = QHBoxLayout()
        
        # Icon (download complete emoji or file icon)
        icon_label = QLabel("📥")
        icon_font = QFont()
        icon_font.setPointSize(32)
        icon_label.setFont(icon_font)
        title_layout.addWidget(icon_label)
        
        # Title and message
        title_text_layout = QVBoxLayout()
        title = QLabel("Download complete")
        title_font = QFont()
        title_font.setPointSize(11)
        title_font.setBold(True)
        title.setFont(title_font)
        title_text_layout.addWidget(title)
        
        # File size info
        filepath = self.download_info.get("filepath", "")
        file_size_bytes = self.download_info.get("file_size", 0)
        filename = Path(filepath).name if filepath else "File"
        
        size_text = f"Downloaded {_format_bytes(file_size_bytes)} ({file_size_bytes:,} Bytes)"
        size_label = QLabel(size_text)
        size_font = QFont()
        size_font.setPointSize(9)
        size_label.setFont(size_font)
        title_text_layout.addWidget(size_label)
        
        title_layout.addLayout(title_text_layout)
        title_layout.addStretch()
        layout.addLayout(title_layout)
        
        layout.addSpacing(10)
        
        # Details group without a heavy box, like IDM
        details_group = QGroupBox()
        details_group.setStyleSheet("QGroupBox { border: none; background: transparent; padding: 0px; margin: 0px; }")
        form_layout = QFormLayout(details_group)
        form_layout.setSpacing(8)
        form_layout.setContentsMargins(0, 0, 0, 0)
        
        # Address (URL) as a read-only input field
        url = self.download_info.get("url", "")
        url_field = QLineEdit(url)
        url_field.setReadOnly(True)
        url_field.setCursorPosition(0)
        url_field.setStyleSheet(
            "QLineEdit { border: 1px solid #d0d0d0; border-radius: 4px; background: #f7f7f7; color: #1a1a1a; padding: 4px 6px; }"
        )
        form_layout.addRow("Address", url_field)

        # File saved as (path) as a read-only input field
        file_path_field = QLineEdit(filepath)
        file_path_field.setReadOnly(True)
        file_path_field.setCursorPosition(0)
        file_path_field.setStyleSheet(
            "QLineEdit { border: 1px solid #d0d0d0; border-radius: 4px; background: #f7f7f7; color: #1a1a1a; padding: 4px 6px; }"
        )
        form_layout.addRow("The file saved as", file_path_field)
        
        layout.addWidget(details_group)
        
        layout.addSpacing(15)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        open_btn = QPushButton("Open")
        open_btn.setMinimumWidth(80)
        open_btn.clicked.connect(self._open_file)
        button_layout.addWidget(open_btn)
        
        open_with_btn = QPushButton("Open with...")
        open_with_btn.setMinimumWidth(80)
        open_with_btn.clicked.connect(self._open_with)
        button_layout.addWidget(open_with_btn)
        
        open_folder_btn = QPushButton("Open folder")
        open_folder_btn.setMinimumWidth(80)
        open_folder_btn.clicked.connect(self._open_folder)
        button_layout.addWidget(open_folder_btn)
        
        button_layout.addStretch()
        
        close_btn = QPushButton("Close")
        close_btn.setMinimumWidth(80)
        close_btn.clicked.connect(self.accept)
        button_layout.addWidget(close_btn)
        
        layout.addLayout(button_layout)
        
        # Don't show again checkbox
        self.dont_show_check = QCheckBox("Don't show this dialog again")
        layout.addWidget(self.dont_show_check)
    
    def _open_file(self):
        """Open the downloaded file"""
        filepath = self.download_info.get("filepath", "")
        if filepath and Path(filepath).exists():
            try:
                os.startfile(filepath)
                self.accept()
            except Exception as e:
                print(f"Error opening file: {e}")
    
    def _open_with(self):
        """Open file with dialog (placeholder)"""
        print("Open with... not yet implemented")
    
    def _open_folder(self):
        """Open folder containing the file"""
        filepath = self.download_info.get("filepath", "")
        if filepath:
            folder = str(Path(filepath).parent)
            try:
                os.startfile(folder)
                self.accept()
            except Exception as e:
                print(f"Error opening folder: {e}")
    
    def dont_show_again(self):
        """Check if user wants to hide this dialog in future"""
        return self.dont_show_check.isChecked()
