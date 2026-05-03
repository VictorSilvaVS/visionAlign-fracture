from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
                             QPushButton, QSpacerItem, QSizePolicy, QFormLayout,
                             QCheckBox, QWidget)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPixmap
import os

class LoginDialog(QDialog):
    def __init__(self, database, settings, current_server_ip="127.0.0.1", parent=None):
        super().__init__(parent)
        self.database = database
        self.settings = settings
        self.user_info = None  # Store user info on successful login
        self.server_ip = current_server_ip

        self.setWindowTitle("Login - VisionAlign")
        self.setModal(True)
        self.setMinimumWidth(400) # Um pouco mais largo para o visual
        self.setStyleSheet(self.get_stylesheet())

        # --- Layouts ---
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(25, 25, 25, 25) # Margens gerais
        main_layout.setSpacing(20) # Espaçamento entre elementos principais

        form_layout = QFormLayout()
        form_layout.setHorizontalSpacing(15)
        form_layout.setVerticalSpacing(10)
        form_layout.setLabelAlignment(Qt.AlignRight)

        checkbox_layout = QHBoxLayout() # Layout para o checkbox
        checkbox_layout.setContentsMargins(0, 10, 0, 5) # Espaçamento para o checkbox

        button_layout = QHBoxLayout()

        # --- Logo ---
        logo_label = QLabel()
        logo_path = os.path.join(os.path.dirname(__file__), "..", "assets", "logo_login.png")
        if os.path.exists(logo_path):
            pixmap = QPixmap(logo_path)
            logo_label.setPixmap(pixmap.scaledToWidth(180, Qt.SmoothTransformation))
        else:
            logo_label.setText("VISIONALIGN") 
            logo_label.setStyleSheet("font-size: 28px; font-weight: 800; color: #3b82f6; letter-spacing: 2px;")
        logo_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(logo_label)
        main_layout.addSpacerItem(QSpacerItem(20, 15, QSizePolicy.Minimum, QSizePolicy.Fixed)) # Espaço após o logo

        # --- Widgets ---
        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("Usuário")
        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("Senha")
        self.password_input.setEchoMode(QLineEdit.Password) 
        
        # --- Campo do Servidor (Bloqueado por padrão) ---
        server_container = QWidget()
        server_container_layout = QHBoxLayout(server_container)
        server_container_layout.setContentsMargins(0, 0, 0, 0)
        server_container_layout.setSpacing(5)

        self.server_input = QLineEdit()
        self.server_input.setPlaceholderText("IP do Servidor")
        self.server_input.setText(self.server_ip)
        self.server_input.setReadOnly(True) # <<< BLOQUEADO POR PADRÃO
        self.server_input.setStyleSheet("background-color: #0f172a; color: #475569;") # Cor mais escura

        self.unlock_btn = QPushButton("🔒")
        self.unlock_btn.setFixedSize(35, 35)
        self.unlock_btn.setCursor(Qt.PointingHandCursor)
        self.unlock_btn.setToolTip("Desbloquear configuração de servidor (Requer chave admin)")
        self.unlock_btn.clicked.connect(self.unlock_server_field)
        
        server_container_layout.addWidget(self.server_input)
        server_container_layout.addWidget(self.unlock_btn)

        self.error_label = QLabel("") 
        self.error_label.setObjectName("errorLabel") 
        self.error_label.setAlignment(Qt.AlignCenter)
        self.error_label.setWordWrap(True)
        self.error_label.setFixedHeight(30) 
        self.error_label.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)

        self.guest_checkbox = QCheckBox("Entrar como visitante")
        self.guest_checkbox.stateChanged.connect(self.toggle_guest_mode)
        checkbox_layout.addWidget(self.guest_checkbox, alignment=Qt.AlignCenter) 

        login_button = QPushButton("Login")
        login_button.setObjectName("loginButton") 
        login_button.setDefault(True) 
        cancel_button = QPushButton("Cancelar")
        cancel_button.setObjectName("cancelButton") 

        # --- Setup Form Layout ---
        form_layout.addRow("Usuário:", self.username_input)
        form_layout.addRow("Senha:", self.password_input)
        form_layout.addRow("Servidor:", server_container)

        # --- Setup Button Layout ---
        button_layout.addStretch()
        button_layout.addWidget(cancel_button)
        button_layout.addWidget(login_button)

        # --- Add Widgets to Main Layout ---
        main_layout.addLayout(form_layout)
        main_layout.addLayout(checkbox_layout) 
        main_layout.addWidget(self.error_label)
        main_layout.addLayout(button_layout)

        # --- Connections ---
        login_button.clicked.connect(self.attempt_login)
        cancel_button.clicked.connect(self.reject)
        self.password_input.returnPressed.connect(self.attempt_login)
        self.username_input.returnPressed.connect(self.password_input.setFocus)

    def unlock_server_field(self):
        """Verifica chave de gerenciamento antes de desbloquear o IP."""
        from .input_dialog import InputDialog
        key, ok = InputDialog.getText(self, "Desbloqueio de Segurança", "Digite a chave de gerenciamento:", password=True)
        
        expected_key = self.settings.get('SYSTEM_CONFIG', {}).get('management_key', 'admin123')
        
        if ok and key == expected_key:
            self.server_input.setReadOnly(False)
            self.server_input.setStyleSheet("background-color: #1e293b; color: #f8fafc;")
            self.unlock_btn.setText("🔓")
            self.unlock_btn.setEnabled(False)
            self.server_input.setFocus()
        elif ok:
            self.error_label.setText("Chave de gerenciamento inválida.")

    def toggle_guest_mode(self, state):
        is_guest = (state == Qt.Checked)
        self.username_input.setEnabled(not is_guest)
        self.password_input.setEnabled(not is_guest)
        if is_guest:
            self.username_input.clear()
            self.password_input.clear()
            self.error_label.clear()

    def attempt_login(self):
        self.error_label.clear() # Limpa erros anteriores

        self.server_ip = self.server_input.text().strip() or "127.0.0.1"
        
        if self.guest_checkbox.isChecked():
            self.user_info = {'username': 'guest', 'role': 'guest', 'permissions': ['view'], 'is_guest': True}
            self.accept()
            return

        username = self.username_input.text().strip()
        password = self.password_input.text()

        if not username or not password:
            self.error_label.setText("Usuário e senha são obrigatórios.")
            return

        # Assume database.verify_user returns user_info dict on success, None on failure
        # This method should handle password hashing verification internally using SecurityManager
        self.user_info = self.database.verify_user(username, password)

        if self.user_info:
            # Garante que a flag is_guest não esteja presente para usuários autenticados
            self.user_info.pop('is_guest', None)
            self.accept() # Close dialog successfully
        else:
            self.error_label.setText("Usuário ou senha inválidos.")
            self.password_input.clear() # Clear password field on failure
            self.username_input.setFocus() # Focus username field
            self.username_input.selectAll()

    def get_stylesheet(self):
        # Estilo QSS Premium Dark
        return """
            QDialog {
                background-color: #0f172a;
                color: #f8fafc;
                font-family: 'Inter', 'Segoe UI', sans-serif;
            }
            QLabel {
                font-size: 13px;
                color: #94a3b8;
                font-weight: 600;
                background: transparent;
            }
            QLineEdit {
                padding: 12px;
                border: 1px solid #334155;
                border-radius: 8px;
                font-size: 14px;
                background-color: #1e293b;
                color: #f8fafc;
            }
            QLineEdit:focus {
                border: 2px solid #3b82f6;
                background-color: #0f172a;
            }
            QPushButton {
                padding: 12px 24px;
                font-size: 13px;
                border-radius: 8px;
                font-weight: 700;
                min-width: 60px;
                background-color: #1e293b;
                border: 1px solid #334155;
                color: #f8fafc;
            }
            QPushButton:hover {
                background-color: #334155;
            }
            QPushButton#loginButton {
                background-color: #3b82f6;
                color: white;
                border: none;
            }
            QPushButton#loginButton:hover {
                background-color: #2563eb;
            }
            QPushButton#cancelButton {
                background-color: transparent;
                border: 1px solid #334155;
                color: #94a3b8;
            }
            QPushButton#cancelButton:hover {
                background-color: #1e293b;
                color: #f8fafc;
            }
            QLabel#errorLabel {
                color: #ef4444;
                font-size: 12px;
                font-weight: 600;
            }
            QCheckBox {
                color: #94a3b8;
                font-size: 13px;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
                border: 1px solid #334155;
                border-radius: 4px;
                background: #1e293b;
            }
            QCheckBox::indicator:checked {
                background-color: #3b82f6;
                image: url(check.png); /* Fallback */
            }
        """
