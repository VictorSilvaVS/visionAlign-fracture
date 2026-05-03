from PyQt5.QtWidgets import QInputDialog, QWidget, QLineEdit

class InputDialog:
    """
    Um wrapper simples para QInputDialog com suporte ao tema Dark Premium.
    """

    @staticmethod
    def getText(parent: QWidget, title: str, label: str, text: str = "", password: bool = False) -> tuple[str, bool]:
        dialog = QInputDialog(parent)
        dialog.setWindowTitle(title)
        dialog.setLabelText(label)
        dialog.setTextValue(text)
        
        if password:
            dialog.setTextEchoMode(QLineEdit.Password)
            
        # Aplica o tema dark consistente
        dialog.setStyleSheet("""
            QInputDialog {
                background-color: #0f172a;
                color: #f8fafc;
            }
            QLabel {
                color: #94a3b8;
                font-weight: 600;
            }
            QLineEdit {
                padding: 10px;
                border: 1px solid #334155;
                border-radius: 6px;
                background-color: #1e293b;
                color: #f8fafc;
            }
            QPushButton {
                padding: 8px 16px;
                background-color: #1e293b;
                border: 1px solid #334155;
                border-radius: 4px;
                color: #f8fafc;
            }
            QPushButton:hover {
                background-color: #3b82f6;
            }
        """)
        
        ok = dialog.exec_()
        return dialog.textValue(), bool(ok)