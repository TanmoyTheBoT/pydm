"""
PyDM Custom Widgets - Reusable UI Components
"""
from PySide6.QtCore import Qt, Signal, QSize, QRect
from PySide6.QtGui import QIcon, QPixmap, QColor, QCursor
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QTreeWidget, QTreeWidgetItem, QTableWidget, QTableWidgetItem,
    QHeaderView, QProgressBar, QPushButton
)


class ResizableHeaderView(QHeaderView):
    """Custom header view with visual cursor feedback for resizing columns"""
    
    def __init__(self, orientation, parent=None):
        super().__init__(orientation, parent)
        self.setCursor(Qt.PointingHandCursor)
        self._resize_zone_width = 4  # pixels from border to detect resize
    
    def mouseMoveEvent(self, event):
        """Change cursor when hovering over resize area"""
        pos = event.position().toPoint() if hasattr(event, 'position') else event.pos()
        x_pos = pos.x()
        
        # Accumulate section widths to find column borders
        cumulative_pos = 0
        is_resize_area = False
        
        for i in range(self.count()):
            section_width = self.sectionSize(i)
            if section_width <= 0:
                continue
                
            # Right edge of this section
            right_edge = cumulative_pos + section_width
            
            # Check if cursor is near this section's right edge
            if abs(x_pos - right_edge) <= self._resize_zone_width:
                is_resize_area = True
                break
            
            cumulative_pos = right_edge
        
        # Set appropriate cursor
        if is_resize_area:
            self.setCursor(Qt.SplitHCursor)  # ↔ Resize cursor
        else:
            self.setCursor(Qt.PointingHandCursor)  # 👆 Normal pointer
        
        super().mouseMoveEvent(event)
    
    def leaveEvent(self, event):
        """Reset cursor when leaving header"""
        self.setCursor(Qt.PointingHandCursor)
        super().leaveEvent(event)


class SidebarCategoryWidget(QTreeWidget):
    """Left sidebar showing download categories"""
    
    category_selected = Signal(str)
    
    # Root category with children
    CATEGORIES = {
        "all": {
            "name": "All",
            "icon": "⭐",
            "children": [
                ("general", "General", "📁"),
                ("image", "Image", "🖼️"),
                ("music", "Music", "🎵"),
                ("video", "Video", "🎬"),
                ("program", "Apps", "💻"),
                ("document", "Document", "📄"),
                ("compressed", "Compressed", "📦"),
                ("other", "Other", "📁"),
            ]
        }
    }
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setHeaderLabels(["Category"])
        self.setColumnCount(1)
        self.setRootIsDecorated(True)
        self.setAnimated(True)
        self.setUniformRowHeights(True)
        self.setMinimumWidth(180)
        self.setMaximumWidth(280)
        
        self.itemClicked.connect(self._on_item_clicked)
        self._setup_categories()
    
    def _setup_categories(self):
        """Setup category tree items with hierarchy"""
        for key, config in self.CATEGORIES.items():
            # Create root item
            root_item = QTreeWidgetItem()
            root_item.setText(0, f"{config['icon']} {config['name']}")
            root_item.setData(0, Qt.UserRole, key)
            root_item.setToolTip(0, config['name'])
            self.addTopLevelItem(root_item)
            
            # Add child categories
            for child_key, child_name, child_icon in config['children']:
                child_item = QTreeWidgetItem()
                child_item.setText(0, f"{child_icon} {child_name}")
                child_item.setData(0, Qt.UserRole, child_key)
                child_item.setToolTip(0, child_name)
                root_item.addChild(child_item)
        
        self.expandAll()
    
    def _on_item_clicked(self, item, column):
        """Emit category selection"""
        category = item.data(0, Qt.UserRole)
        if category:
            self.category_selected.emit(category)


class DownloadListWidget(QTableWidget):
    """Main download list with detailed columns"""
    
    # Signal emitted when column widths change (no parameters to avoid Shiboken issues)
    column_widths_changed = Signal()
    
    COLUMNS = [
        ("File Name", 200),
        ("Size", 110),
        ("Status", 110),
        ("Speed", 110),
        ("ETA", 100),
        ("Progress", 150),
        ("Date Added", 140),
    ]
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setColumnCount(len(self.COLUMNS))
        self.setSelectionBehavior(QTableWidget.SelectRows)
        self.setSelectionMode(QTableWidget.ExtendedSelection)
        self.setAlternatingRowColors(True)
        self.setShowGrid(True)
        self.setGridStyle(Qt.SolidLine)
        self.setMinimumHeight(150)  # Reduced for more compact layout
        
        # Set column headers
        headers = [col[0] for col in self.COLUMNS]
        self.setHorizontalHeaderLabels(headers)
        
        # Set column widths
        for i, (_, width) in enumerate(self.COLUMNS):
            self.setColumnWidth(i, width)
        
        # Replace default header with custom header that shows resize cursor
        custom_header = ResizableHeaderView(Qt.Horizontal, self)
        custom_header.setStretchLastSection(False)
        self.setHorizontalHeader(custom_header)
        
        # Configure header with resizing and moving
        header = self.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents)
        header.setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        header.setDefaultSectionSize(22)
        header.setMinimumSectionSize(50)  # Minimum width for any column
        header.setStyleSheet("QHeaderView { padding: 0px; margin: 0px; }")
        
        # Enable column resizing and moving (like IDM)
        header.setSectionsMovable(True)  # Allow column dragging/reordering
        header.setSectionsClickable(True)  # Make header clickable
        header.setStretchLastSection(False)
        
        # Track when user finishes resizing
        header.sectionResized.connect(self._on_section_resized)
        
        # Configure vertical header
        self.verticalHeader().setVisible(False)
        self.verticalHeader().setDefaultSectionSize(28)  # Comfortable row height for readability
        
        # Minimize spacing
        self.setShowGrid(False)
        self.setShowGrid(True)
        self.setStyleSheet("""
            QTableWidget {
                gridline-color: #e0e0e0;
                padding: 0px;
                margin: 0px;
            }
            QTableWidget::item {
                padding: 0px;
                margin: 0px;
            }
        """)
    
    def add_download(self, filename, size, status, speed, eta, progress, date_added, download_id=None):
        """Add a download row"""
        row = self.rowCount()
        self.insertRow(row)
        
        # File name
        name_item = QTableWidgetItem(filename)
        if download_id is not None:
            name_item.setData(Qt.UserRole, download_id)
        self.setItem(row, 0, name_item)
        
        # Size
        size_item = QTableWidgetItem(size)
        size_item.setTextAlignment(Qt.AlignCenter)
        self.setItem(row, 1, size_item)
        
        # Status
        status_item = QTableWidgetItem(status)
        status_item.setTextAlignment(Qt.AlignCenter)
        self.setItem(row, 2, status_item)
        
        # Speed
        speed_item = QTableWidgetItem(speed)
        speed_item.setTextAlignment(Qt.AlignCenter)
        self.setItem(row, 3, speed_item)
        
        # ETA
        eta_item = QTableWidgetItem(eta)
        eta_item.setTextAlignment(Qt.AlignCenter)
        self.setItem(row, 4, eta_item)
        
        # Progress with progress bar
        progress_widget = QWidget()
        progress_layout = QHBoxLayout(progress_widget)
        progress_layout.setContentsMargins(2, 1, 2, 1)  # Minimal margins
        progress_layout.setSpacing(2)  # Minimal spacing
        
        progress_bar = QProgressBar()
        progress_bar.setMaximumHeight(14)  # Compact progress bar
        progress_bar.setTextVisible(False)  # Hide text in bar
        progress_bar.setStyleSheet("QProgressBar { border: 1px solid #ccc; }")
        try:
            progress_value = int(progress.rstrip('%'))
            progress_bar.setValue(progress_value)
        except:
            progress_bar.setValue(0)
        
        percent_label = QLabel(progress)
        percent_label.setMaximumWidth(40)
        percent_label.setStyleSheet("QLabel { padding: 0px; margin: 0px; }")
        
        progress_layout.addWidget(progress_bar)
        progress_layout.addWidget(percent_label)
        
        self.setCellWidget(row, 5, progress_widget)
        
        # Date added
        date_item = QTableWidgetItem(date_added)
        self.setItem(row, 6, date_item)
        self.setRowHidden(row, False)
        self.setCurrentCell(row, 0)
        return row

    def get_download_id(self, row):
        """Get download ID stored in the row"""
        item = self.item(row, 0)
        if item:
            return item.data(Qt.UserRole)
        return None

    def update_download_row(self, row, status=None, speed=None, eta=None, progress=None):
        """Update download row status, speed, ETA, and progress"""
        if status is not None and self.item(row, 2):
            self.item(row, 2).setText(status)
        if speed is not None and self.item(row, 3):
            self.item(row, 3).setText(speed)
        if eta is not None and self.item(row, 4):
            self.item(row, 4).setText(eta)
        if progress is not None:
            widget = self.cellWidget(row, 5)
            if widget:
                progress_bar = widget.findChild(QProgressBar)
                percent_label = widget.findChild(QLabel)
                if progress_bar is not None:
                    progress_bar.setValue(progress)
                if percent_label is not None:
                    percent_label.setText(f"{progress}%")

    def _on_section_resized(self, logicalIndex, oldSize, newSize):
        """Handle column width changes"""
        if newSize != oldSize:
            # Just emit signal without parameters to avoid Shiboken dict conversion issues
            try:
                col_name = self.COLUMNS[logicalIndex][0] if logicalIndex < len(self.COLUMNS) else f"Col{logicalIndex}"
                print(f"[DownloadListWidget] Column '{col_name}' resized: {oldSize} -> {newSize}")
                self.column_widths_changed.emit()
            except Exception as e:
                print(f"[DownloadListWidget] [ERROR] Error emitting column_widths_changed: {e}")
    
    def get_column_widths(self) -> dict:
        """Get current column widths as a dictionary"""
        column_widths = {}
        for i in range(len(self.COLUMNS)):
            try:
                column_widths[i] = self.columnWidth(i)
            except Exception:
                pass
        return column_widths
    
    def restore_column_widths(self, column_widths: dict):
        """Restore column widths from saved settings"""
        if column_widths:
            print(f"[DownloadListWidget] Restoring {len(column_widths)} column widths...")
            for col_idx, width in column_widths.items():
                try:
                    if isinstance(col_idx, str):
                        col_idx = int(col_idx)
                    if 0 <= col_idx < len(self.COLUMNS) and width >= 50:
                        col_name = self.COLUMNS[col_idx][0]
                        self.setColumnWidth(col_idx, width)
                        print(f"[DownloadListWidget]   - Column {col_idx} '{col_name}': {width}px")
                except (ValueError, TypeError) as e:
                    print(f"[DownloadListWidget]   [ERROR] Failed to restore column {col_idx}: {e}")

    def remove_row(self, row):
        """Remove a row from the table"""
        self.removeRow(row)
    
    def clear_all_downloads(self):
        """Clear all rows"""
        self.setRowCount(0)
    
    def get_selected_rows(self):
        """Get indices of selected rows"""
        return list(set(index.row() for index in self.selectedIndexes()))


class ToolbarButton(QPushButton):
    """Custom toolbar button with icon"""
    
    def __init__(self, text, icon_path=None, tooltip=None, parent=None):
        super().__init__(text, parent)
        self.setMinimumHeight(32)
        self.setMaximumHeight(32)
        self.setMaximumWidth(80)
        self.setCursor(Qt.PointingHandCursor)
        
        if icon_path:
            self.setIcon(QIcon(icon_path))
            self.setIconSize(QSize(24, 24))
        
        if tooltip:
            self.setToolTip(tooltip)


class StatusLabel(QLabel):
    """Status indicator label"""
    
    STATUS_COLORS = {
        "downloading": "#4da6ff",
        "paused": "#ff9800",
        "completed": "#3fbf3f",
        "error": "#6b7280",
        "idle": "#999999",
    }
    
    def __init__(self, text="Ready", status="idle", parent=None):
        super().__init__(text, parent)
        self.set_status(status)
    
    def set_status(self, status):
        """Set status with color"""
        color = self.STATUS_COLORS.get(status, "#999999")
        self.setStyleSheet(f"""
            QLabel {{
                color: {color};
                font-weight: bold;
                padding: 2px 4px;
            }}
        """)
    
    def set_text_with_status(self, text, status):
        """Set both text and status"""
        self.setText(text)
        self.set_status(status)


class StatisticsWidget(QWidget):
    """Download statistics panel"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(8, 4, 8, 4)
        
        # Total downloads
        self.total_label = QLabel("Total: 0")
        self.layout.addWidget(self.total_label)
        
        self.layout.addSpacing(20)
        
        # Active downloads
        self.active_label = QLabel("Active: 0")
        self.layout.addWidget(self.active_label)
        
        self.layout.addSpacing(20)
        
        # Total speed
        self.speed_label = QLabel("Speed: 0 KB/s")
        self.layout.addWidget(self.speed_label)
        
        self.layout.addSpacing(20)
        
        # Total downloaded
        self.downloaded_label = QLabel("Downloaded: 0 MB")
        self.layout.addWidget(self.downloaded_label)
        
        self.layout.addStretch()
    
    def update_statistics(self, total=0, active=0, speed=0, downloaded=0):
        """Update statistics display"""
        self.total_label.setText(f"Total: {total}")
        self.active_label.setText(f"Active: {active}")
        
        if speed >= 1024 * 1024:
            speed_text = f"Speed: {speed / (1024*1024):.2f} MB/s"
        elif speed >= 1024:
            speed_text = f"Speed: {speed / 1024:.2f} KB/s"
        else:
            speed_text = f"Speed: {speed:.0f} B/s"
        self.speed_label.setText(speed_text)
        
        if downloaded >= 1024 * 1024:
            downloaded_text = f"Downloaded: {downloaded / (1024*1024):.2f} MB"
        elif downloaded >= 1024:
            downloaded_text = f"Downloaded: {downloaded / 1024:.2f} KB"
        else:
            downloaded_text = f"Downloaded: {downloaded} B"
        self.downloaded_label.setText(downloaded_text)
