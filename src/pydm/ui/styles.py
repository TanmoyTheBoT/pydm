"""
PyDM Stylesheet and Styling Constants
"""

IDM_STYLESHEET = """
/* Main Window */
QMainWindow {
    background-color: #f5f5f5;
}

/* Menu Bar */
QMenuBar {
    background-color: #f0f0f0;
    border-bottom: 1px solid #d0d0d0;
    padding: 2px;
}

QMenuBar::item:selected {
    background-color: #e0e0e0;
}

QMenu {
    background-color: #ffffff;
    border: 1px solid #d0d0d0;
}

QMenu::item:selected {
    background-color: #e8f4f8;
}

QMenu::item:disabled {
    color: #b0b0b0;
    background-color: transparent;
}

/* Toolbar */
QToolBar {
    background-color: #f0f0f0;
    border-bottom: 1px solid #d0d0d0;
    padding: 4px;
    spacing: 2px;
}

QToolButton {
    background-color: transparent;
    border: none;
    padding: 4px;
    border-radius: 2px;
}

QToolButton:hover {
    background-color: #e0e0e0;
    border: 1px solid #c0c0c0;
}

QToolButton:pressed {
    background-color: #d0d0d0;
}

QToolButton:disabled {
    background-color: #f3f3f3;
    color: #b0b0b0;
    border: 1px solid #d9d9d9;
    opacity: 0.65;
}

/* Splitter */
QSplitter::handle {
    background-color: #e0e0e0;
    width: 4px;
}

QSplitter::handle:hover {
    background-color: #b0b0b0;
}

/* Sidebar */
QTreeWidget {
    background-color: #ffffff;
    border: 1px solid #d0d0d0;
    border-radius: 2px;
    padding: 4px;
    outline: none;
}

QTreeWidget::item {
    padding: 4px;
}

QTreeWidget::item:hover {
    background-color: #f0f0f0;
}

QTreeWidget::item:selected {
    background-color: #4da6ff;
    color: white;
    border-radius: 2px;
}

QTreeWidget::branch:has-children:closed:hover {
    background: transparent;
}

QTreeWidget::branch:has-children:open:hover {
    background: transparent;
}

/* Table Widget */
QTableWidget {
    background-color: #ffffff;
    border: 1px solid #d0d0d0;
    gridline-color: #e8e8e8;
    outline: none;
}

QTableWidget::item {
    padding: 4px;
    border: none;
}

QTableWidget::item:selected {
    background-color: #b3d9ff;
}

QHeaderView::section {
    background-color: #f0f0f0;
    color: #333333;
    padding: 4px;
    border: none;
    border-right: 1px solid #d0d0d0;
    border-bottom: 1px solid #d0d0d0;
}

QHeaderView::section:hover {
    background-color: #e0e0e0;
}

/* Progress Bar */
QProgressBar {
    border: 1px solid #d0d0d0;
    border-radius: 4px;
    background: #f0f0f0;
    height: 18px;
}

QProgressBar::chunk {
    border-radius: 3px;
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #7fe07f, stop:0.5 #3fbf3f, stop:1 #2f8f2f);
}

/* Buttons */
QPushButton {
    background-color: #f0f0f0;
    border: 1px solid #c0c0c0;
    padding: 4px 12px;
    border-radius: 2px;
    color: #333333;
}

QPushButton:hover {
    background-color: #e0e0e0;
    border: 1px solid #b0b0b0;
}

QPushButton:pressed {
    background-color: #d0d0d0;
}

QPushButton:disabled {
    background-color: #f5f5f5;
    border: 1px solid #d9d9d9;
    color: #a7a7a7;
    opacity: 0.7;
}

/* Groupbox */
QGroupBox {
    border: 1px solid #d0d0d0;
    border-radius: 4px;
    margin-top: 8px;
    padding-top: 8px;
    color: #333333;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0px 4px;
}

/* Spinbox and Line Edit */
QSpinBox, QLineEdit, QComboBox {
    background-color: #ffffff;
    border: 1px solid #c0c0c0;
    padding: 4px;
    border-radius: 2px;
    color: #333333;
}

QSpinBox:focus, QLineEdit:focus, QComboBox:focus {
    border: 2px solid #4da6ff;
}

/* Scrollbar */
QScrollBar:vertical {
    border: none;
    background-color: #f5f5f5;
    width: 14px;
}

QScrollBar::handle:vertical {
    background-color: #c0c0c0;
    border-radius: 6px;
    min-height: 20px;
}

QScrollBar::handle:vertical:hover {
    background-color: #a0a0a0;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    border: none;
    background: none;
}

/* Status Bar */
QStatusBar {
    border-top: 1px solid #d0d0d0;
    background-color: #f0f0f0;
}

/* Labels and Text */
QLabel {
    color: #333333;
}

QTextEdit, QPlainTextEdit {
    background-color: #ffffff;
    border: 1px solid #d0d0d0;
    border-radius: 2px;
    color: #333333;
}
"""

# Color scheme
COLORS = {
    "primary": "#4da6ff",
    "success": "#3fbf3f",
    "warning": "#ff9800",
    "error": "#f44336",
    "bg_primary": "#f5f5f5",
    "bg_secondary": "#ffffff",
    "text_primary": "#333333",
    "text_secondary": "#666666",
    "border": "#d0d0d0",
    "hover": "#e0e0e0",
}
