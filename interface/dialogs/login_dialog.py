from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
                             QPushButton,QSpacerItem, QSizePolicy, QFormLayout,
                             QCheckBox)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPixmap
import os

class LoginDialog(QDialog):
    def __init__(self, database, current_server_ip="127.0.0.1", parent=None):
        super().__init__(parent)
        self.database = database
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
        # --- IMPORTANTE: Crie uma pasta 'assets' dentro de 'interface' e coloque seu logo lá ---
        # --- Exemplo: c:\Users\Sonu\Desktop\projetos github\visionAlign\interface\assets\logo_login.png ---
        logo_path = os.path.join(os.path.dirname(__file__), "..", "assets", "logo_login.png") # <-- Ajuste aqui para o nome/extensão correto do seu arquivo!
        if os.path.exists(logo_path):
            pixmap = QPixmap(logo_path)
            # Ajuste 'scaledToWidth' conforme o tamanho do seu logo
            logo_label.setPixmap(pixmap.scaledToWidth(180, Qt.SmoothTransformation))
        else:
            logo_label.setText("VisionAlign") # Fallback se não houver logo
            logo_label.setStyleSheet("font-size: 24px; font-weight: bold; color: #333;")
        logo_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(logo_label)
        main_layout.addSpacerItem(QSpacerItem(20, 15, QSizePolicy.Minimum, QSizePolicy.Fixed)) # Espaço após o logo

        # --- Widgets ---
        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("Digite seu usuário")
        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("Digite sua senha")
        self.password_input.setEchoMode(QLineEdit.Password) # Mask password
        
        self.server_input = QLineEdit()
        self.server_input.setPlaceholderText("IP do Servidor (ex: 192.168.1.10)")
        self.server_input.setText(self.server_ip)

        self.error_label = QLabel("") # To display login errors
        self.error_label.setObjectName("errorLabel") # Para estilizar via QSS
        self.error_label.setAlignment(Qt.AlignCenter)
        self.error_label.setWordWrap(True)
        self.error_label.setFixedHeight(30) # Altura fixa para não deslocar layout
        self.error_label.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)

        self.guest_checkbox = QCheckBox("Entrar como visitante")
        self.guest_checkbox.stateChanged.connect(self.toggle_guest_mode)
        checkbox_layout.addWidget(self.guest_checkbox, alignment=Qt.AlignCenter) # Centraliza checkbox

        login_button = QPushButton("Login")
        login_button.setObjectName("loginButton") # Para estilizar
        login_button.setDefault(True) # Permite pressionar Enter no diálogo
        cancel_button = QPushButton("Cancelar")
        cancel_button.setObjectName("cancelButton") # Para estilizar

        # --- Setup Form Layout ---
        user_label = QLabel("Usuário:")
        pass_label = QLabel("Senha:")
        server_label = QLabel("Servidor IP:")
        form_layout.addRow(user_label, self.username_input)
        form_layout.addRow(pass_label, self.password_input)
        form_layout.addRow(server_label, self.server_input)

        # --- Setup Button Layout ---
        button_layout.addSpacerItem(QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))
        button_layout.addWidget(cancel_button)
        button_layout.addWidget(login_button)

        # --- Add Widgets to Main Layout ---
        main_layout.addLayout(form_layout)
        main_layout.addLayout(checkbox_layout) # Adiciona layout do checkbox
        main_layout.addWidget(self.error_label)
        main_layout.addSpacerItem(QSpacerItem(20, 10, QSizePolicy.Minimum, QSizePolicy.Fixed)) # Espaço antes dos botões
        main_layout.addLayout(button_layout)

        # --- Connections ---
        login_button.clicked.connect(self.attempt_login)
        cancel_button.clicked.connect(self.reject)
        self.password_input.returnPressed.connect(self.attempt_login) # Login on Enter
        self.username_input.returnPressed.connect(self.password_input.setFocus) # Pula para senha com Enter

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
        # Estilo QSS - Sinta-se à vontade para ajustar cores e fontes
        return """
            QDialog {
                background-color: #f0f0f0; /* Cor de fundo geral */
                font-family: 'Segoe UI', Arial, sans-serif; /* Fonte padrão */
            }
            QLabel {
                font-size: 14px;
                color: #333;
            }
            QLineEdit {
                padding: 8px;
                border: 1px solid #ccc;
                border-radius: 4px;
                font-size: 14px;
                background-color: #fff;
            }
            QLineEdit:focus {
                border: 1px solid #0078d7; /* Cor ao focar */
            }
            QPushButton {
                padding: 10px 20px;
                font-size: 14px;
                border-radius: 4px;
                min-width: 80px; /* Largura mínima */
            }
            QPushButton#loginButton {
                background-color: #0078d7; /* Azul primário */
                color: white;
                font-weight: bold;
            }
            QPushButton#loginButton:hover {
                background-color: #005a9e; /* Azul mais escuro no hover */
            }
            QPushButton#cancelButton {
                background-color: #e0e0e0; /* Cinza claro */
                color: #333;
            }
            QPushButton#cancelButton:hover {
                background-color: #d0d0d0; /* Cinza um pouco mais escuro */
            }
            QLabel#errorLabel {
                color: #d9534f; /* Vermelho para erros */
                font-size: 13px;
                font-weight: bold;
            }
        """
