from __future__ import annotations


def get_main_stylesheet() -> str:
    return """
    QMainWindow {
        background: #f5f1ea;
    }
    QWidget {
        color: #2a2825;
        font-family: "Segoe UI", "Trebuchet MS", sans-serif;
        font-size: 13px;
    }
    QLabel#ValueLabel {
        font-size: 14px;
        font-weight: 600;
        color: #24211f;
    }
    QLineEdit {
        background: #fffdf8;
        border: 1px solid #d7c7b0;
        border-radius: 8px;
        padding: 8px 10px;
        selection-background-color: #2f6e5e;
    }
    QLineEdit:focus {
        border: 1px solid #2f6e5e;
    }
    QPushButton {
        background: #2f6e5e;
        color: #ffffff;
        border: none;
        border-radius: 9px;
        padding: 8px 14px;
        font-weight: 600;
    }
    QPushButton:hover {
        background: #25584b;
    }
    QPushButton:pressed {
        background: #1f4a3f;
    }
    QPushButton#NeutralButton {
        background: #8f6d40;
    }
    QPushButton#NeutralButton:hover {
        background: #775a34;
    }
    QPushButton#DisconnectButton {
        background: #8f3c37;
    }
    QPushButton#DisconnectButton:hover {
        background: #742d2a;
    }
    QGroupBox {
        font-size: 14px;
        font-weight: 700;
        color: #3f3a35;
        border: 1px solid #ddcfba;
        border-radius: 12px;
        margin-top: 12px;
        background: #fffdf9;
    }
    QGroupBox::title {
        subcontrol-origin: margin;
        left: 12px;
        padding: 0 6px;
    }
    QListWidget {
        border: 1px solid #dfd1bc;
        border-radius: 10px;
        background: #fffcf7;
        padding: 4px;
    }
    """
