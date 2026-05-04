import json
import logging
from PyQt5.QtWidgets import *
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QObject, QFileSystemWatcher, QThread, pyqtSlot # QDateTime removido
from PyQt5.QtGui import QImage, QPixmap, QIcon # Adicionar QIcon
import cv2
import socket # Adicionar socket
import time
import os
from PyQt5 import sip
import requests  # Para buscar stats remotamente
import numpy as np # Para criar frame vazio
from .dialogs.settings_dialog import BasicSettingsDialog, AdvancedSettingsDialog # <<< CORRIGIDO: Import relativo
from .configuracoes.settings import Settings # <<< CORRIGIDO: Import relativo
from utils.security import SecurityManager # <<< Importar SecurityManager
from .dialogs.input_dialog import InputDialog # <<< CORRIGIDO: Import relativo
from .dialogs.settings_dialog_detailed import SettingsDialogDetailed # <<< CORRIGIDO: Import relativo
from utils.logger_config import setup_logging, log_emitter # <<< Importar log_emitter também

from utils.timezone_utils import get_current_utc_timestamp, convert_utc_to_local_display # Para timestamps

class FrameUpdateSignal(QObject):
    signal = pyqtSignal(dict)

class ClickableLabel(QLabel):
    double_clicked = pyqtSignal()
    def mouseDoubleClickEvent(self, event):
        self.double_clicked.emit()

class FullScreenVideoDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Monitoramento Full Screen")
        self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0,0,0,0)
        self.video_label = QLabel()
        self.video_label.setAlignment(Qt.AlignCenter)
        self.video_label.setStyleSheet("background-color: black;")
        self.layout.addWidget(self.video_label)
        self.showFullScreen()
        
    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape or event.key() == Qt.Key_F11:
            self.accept()
    
    def mouseDoubleClickEvent(self, event):
        self.accept()

# --- Thread para buscar o stream MJPEG ---
class StreamClientThread(QThread):
    new_frame_signal = pyqtSignal(np.ndarray)
    connection_error_signal = pyqtSignal(str)

    def __init__(self, stream_url, parent=None):
        super().__init__(parent)
        self.stream_url = stream_url
        self._is_running = True
        self.logger = logging.getLogger("VisionAlign.StreamClient")

    def run(self):
        self.logger.info(f"Iniciando thread de captura do stream: {self.stream_url}")
        cap = None
        while self._is_running:
            try:
                if cap is None or not cap.isOpened():
                    # Tentar especificar o backend FFMPEG
                    cap = cv2.VideoCapture(self.stream_url, cv2.CAP_FFMPEG)
                    if not cap.isOpened():
                        error_msg = f"Não foi possível abrir o stream: {self.stream_url}"
                        self.logger.error(f"STREAM_CLIENT_FAIL: {error_msg}")
                        cap = None # Garante que cap seja None se falhar
                        self.connection_error_signal.emit(error_msg)
                        time.sleep(5) # Tenta reconectar após 5 segundos
                        continue
                    else:
                        self.logger.info(f"STREAM_CLIENT_SUCCESS: Conectado ao stream: {self.stream_url}")
                        
                ret, frame = cap.read()
                if ret:
                    self.new_frame_signal.emit(frame) # Emite frame BGR
                    self.logger.debug("StreamClientThread: Frame emitido.") # Log de emissão
                else:
                    self.logger.warning("Frame não recebido do stream. Tentando reabrir...")
                    cap.release()
                    cap = None
                    time.sleep(1)
            except Exception as e:
                error_msg = f"Erro na thread do stream: {e}"
                self.logger.error(error_msg, exc_info=True)
                self.connection_error_signal.emit(error_msg)
                if cap:
                    cap.release()
                    cap = None
                time.sleep(5)
        if cap:
            cap.release()
        self.logger.info("Thread de captura do stream finalizada.")

    def stop(self):
        self._is_running = False

class MainWindow(QMainWindow):

    def __init__(self, model, security, settings, database, shared_stats, stats_lock, frame_container, frame_lock,
                 user_info, is_client_only=False, remote_server_address=None,
                 api_session=None):
        super().__init__()
        self.security = security
        self.settings = settings
        self.current_user = user_info
        self.settings_manager = Settings()
        self.status_labels = {}
        self.frame_signal = FrameUpdateSignal()
        self.frame_signal.signal.connect(self.update_display)
        self.cap = None
        self.is_video_active = False
        self.current_frame = None
        self.conf_threshold = settings['AI_PARAMS']['conf_default']
        self.iou_threshold = settings['AI_PARAMS']['iou_default']
        self.is_paused = False
        self.frozen_frame = None
        self.model_dependent_widgets = []
        self.shared_stats = shared_stats
        self.stats_lock = stats_lock
        self.frame_container = frame_container
        self.frame_lock = frame_lock
        self.is_client_only = is_client_only
        self.remote_server_address = remote_server_address
        self.stream_thread = None
        self.stats_poll_timer = None
        self.siren_active = False
        self.last_username = None
        self.last_password = None
        self.last_api_auth = None 
        if api_session:
            self.api_session = api_session
        else:
            self.api_session = requests.Session()
        self.is_reconnecting = False
        self.reconnect_timer = None
        self.model = None
        self.frame_save_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'capturas') # Pasta 'capturas' na raiz do projeto
        self.video_btn = QPushButton("📁 Arquivo")
        self.camera_btn = QPushButton("📷 Webcam")
        self.stream_btn = QPushButton("🌐 Stream")
        self.console = QTextEdit()
        self.console.setReadOnly(True)
        self.console.setStyleSheet("""
            QTextEdit {
                background-color: #1a1a1a;
                color: #00ff00;
                font-family: 'Roboto Mono', monospace;
                font-size: 12px;
                border: 1px solid #3d3d3d;
                border-radius: 4px;
                padding: 8px;
            }
        """)
        
        # Inicializar logger após criar console
        self.logger = setup_logging(self.console)

        # --- Conectar o sinal do logger ao slot da UI ---
        log_emitter.log_signal.connect(self.append_log_message) # <<< CONECTAR SINAL

        # self.setup_console_handler() # Não é mais necessário, o handler já é criado em setup_logging
        
        # Continuar com a inicialização normal
        self.setup_theme()
        self.setup_ui()
        
        # Configurar timers e outros atributos (movido para depois de setup_ui)
        self.setup_timers()

        # <<< NOVO: Verificar status da segurança e atualizar label >>>
        if self.security and hasattr(self.security, 'cipher_suite'):
            security_status_text = "<font color='#00FF00'>ATIVADA</font>"
            self.logger.info("Verificação de segurança: ATIVADA.")
        else:
            security_status_text = "<font color='#FF0000'>DESATIVADA</font>"
            self.logger.warning("Verificação de segurança: DESATIVADA. Criptografia pode não funcionar.")
        # Atualiza o texto do label criado em create_status_bar
        self.system_indicator_label.setText(f"Segurança: {security_status_text} | Desenvolvido por Victor Silva")
        # <<< FIM NOVO >>>
        
        # Configurar modelo se fornecido
        if model:
            self.set_model(model)


        # --- Configurações específicas do modo ---
        if self.is_client_only:
            self.setup_client_mode()
            # Conectar botões de fonte à função de API no modo cliente
            self.video_btn.clicked.connect(lambda: self.handle_client_source_change('video'))
            self.camera_btn.clicked.connect(lambda: self.handle_client_source_change('camera'))
            self.stream_btn.clicked.connect(lambda: self.handle_client_source_change('stream'))
        else:
            # Modo Servidor/Completo
            if not self.model:
                self.disable_model_dependent_features()
            # Conectar botões de fonte às funções locais no modo servidor
            self.video_btn.clicked.connect(self.start_video)
            self.camera_btn.clicked.connect(self.start_camera)
            self.stream_btn.clicked.connect(self.start_stream)
            # Configurar monitoramento do arquivo de settings (apenas no servidor?)
            # Talvez o cliente também precise monitorar remote_host/port? Por enquanto, não.
            self.setup_settings_watcher()

        # Esconder controles de convidado (se aplicável, após setup_ui e definição de modo)
        # No modo cliente, talvez sempre esconder? Ou basear em login futuro?
        if not self.is_client_only and self.current_user and self.current_user.get('is_guest', False):
             self.hide_guest_restricted_controls()
        # <<< NOVO: Adicionar botão para extrair frame >>>
        extract_frame_btn = QPushButton("🖼️ Extrair Frame")
        extract_frame_btn.clicked.connect(self._request_and_save_frame)
        self.side_panel_layout.insertWidget(self.side_panel_layout.count() - 1, extract_frame_btn) # Insere antes do stretch

        # Botão Tela Cheia (Ideal para PC de Fábrica)
        self.fullscreen_btn = QPushButton("📺 Tela Cheia")
        self.fullscreen_btn.clicked.connect(self.toggle_fullscreen)
        self.fullscreen_btn.setToolTip("Alternar modo tela cheia (F11)")
        self.side_panel_layout.insertWidget(self.side_panel_layout.count() - 1, self.fullscreen_btn)

        # O timer _setup_frame_extraction_check() e o método _check_and_save_frame()
        # foram removidos pois a extração agora é direta pelo Flask.


    def setup_settings_watcher(self):
        """Configura o QFileSystemWatcher para monitorar settings.json."""
        # Garantir que settings_path seja um Path object
        settings_file_path = str(self.settings_manager.settings_path)
        self.settings_watcher = QFileSystemWatcher([settings_file_path], self)
        self.settings_watcher.fileChanged.connect(self.handle_settings_file_changed)
        self.logger.info(f"Monitorando alterações em: {settings_file_path}")

    def setup_client_mode(self):
        """Configura a interface e a lógica para o modo cliente."""
        self.logger.info("Configurando interface para Modo Cliente.")
        self.setWindowTitle(f"{self.windowTitle()} - Cliente Conectado a {self.remote_server_address}")

        # Verificar se o usuário é admin
        is_admin = bool(self.current_user and self.current_user.get('is_admin', False))
        is_guest = bool(self.current_user and self.current_user.get('is_guest', False))
        # 1. Desabilitar/Ocultar Controles Locais
        self.video_btn.setEnabled(is_admin)
        self.camera_btn.setEnabled(is_admin)
        self.stream_btn.setEnabled(is_admin)
        self.video_btn.setToolTip("Selecionar arquivo de vídeo para o SERVIDOR processar (Requer Admin)")
        self.camera_btn.setToolTip("Instruir o SERVIDOR a usar a webcam (Requer Admin)")
        self.stream_btn.setToolTip("Instruir o SERVIDOR a usar um stream RTSP/HTTP (Requer Admin)")

        # Habilitar Pause/Resume APENAS para admin no modo cliente
        self.play_pause_btn.setEnabled(is_admin)
        self.play_pause_btn.setText("⏸️ Pausar") # Texto inicial
        self.play_pause_btn.setToolTip("Pausar/Retomar o processamento no SERVIDOR (Admin)")
        if hasattr(self, 'detection_controls_group'):
            self.detection_controls_group.setEnabled(False)
        # Habilitar botão de desligar sirene para TODOS no modo cliente
        if hasattr(self, 'deactivate_siren_btn'):
# Habilitar para todos (admin e guest), a API fará a ação
            self.deactivate_siren_btn.setEnabled(False) # <<< INICIA DESABILITADO
            self.deactivate_siren_btn.setToolTip("Desativar sirene no SERVIDOR (Ativo apenas quando a sirene está ligada)") # <<< Tooltip atualizado

        # Desabilitar botão de Configurações ou adaptar o diálogo
        # Por simplicidade, vamos desabilitar (poderia enviar API /api/settings POST)
        settings_button = self.findChild(QPushButton, "settings_button") # Assumindo que demos um objectName
        if settings_button:
            # Habilitar Configurações para admin no modo cliente
            settings_button.setEnabled(is_admin)
            settings_button.setToolTip("Abrir configurações (Admin)") # Tooltip correto

        # 2. Iniciar Thread de Captura do Stream Remoto
        if is_guest:
            self.logger.info("Usuário visitante: stream remoto não iniciado.")
            self.update_default_message("Conectado como Visitante")
        elif self.remote_server_address:
            stream_url = f"{self.remote_server_address}/video_feed"
            self.stream_thread = StreamClientThread(stream_url, self)
            self.stream_thread.new_frame_signal.connect(self._handle_remote_frame)
            self.stream_thread.connection_error_signal.connect(self._handle_stream_error)
            self.stream_thread.start()
            self.logger.info("Polling de estatísticas iniciado (usuário autenticado).")
        else:
            self.logger.error("Endereço do servidor remoto não fornecido para o modo cliente.")
            self.update_default_message("Erro: Servidor não configurado")

        # 3. Iniciar Timer para Buscar Estatísticas Remotas
        if self.remote_server_address and not is_guest:  # Não buscar stats para guest
            self.stats_poll_timer = QTimer(self)
            self.stats_poll_timer.timeout.connect(self._fetch_remote_stats)
            self.stats_poll_timer.start(1000)  # Busca stats a cada 1 segundo

        # 4. Timer para Reconexão (inicia parado)
        self.reconnect_timer = QTimer(self)
        self.reconnect_timer.timeout.connect(self._attempt_reconnection)
        self.reconnect_interval = 5000 # Tentar reconectar a cada 5 segundos

        # 4. Mensagem inicial
        self.update_default_message("CARREGANDO...") # <<< MENSAGEM INICIAL ALTERADA
        self.status_label.setText("Status: Conectando...")

    def authenticate_with_server_api(self, username, password):
        """Tenta autenticar com a API /api/login do servidor usando a sessão."""
        if not self.remote_server_address:
            self.logger.error("Não é possível autenticar com a API: Endereço do servidor não configurado.")
            return False

        login_url = f"{self.remote_server_address}/api/login"
        credentials = {'username': username, 'password': password}
        self.logger.info(f"Tentando autenticar com a API do servidor em {login_url} para o usuário '{username}'...")

        try:
            # Usar a sessão do requests que já tem gerenciamento de cookies
            response = self.api_session.post(login_url, json=credentials, timeout=5)
            response.raise_for_status()

            if response.json().get("success"):
                # Guardar credenciais para possível re-autenticação
                self.last_username = username
                self.last_password = password
                self.last_api_auth = response.json()
                self.logger.info("Autenticação via API bem-sucedida para '{}'. A sessão está ativa.".format(username))
                return True
            else:
                self.logger.warning(f"Autenticação via API falhou para '{username}': {response.json().get('message')}")
                return False

        except requests.exceptions.RequestException as e:
            self.logger.error(f"Erro de conexão/requisição ao autenticar via API: {e}", exc_info=True)
            QMessageBox.critical(self, "Erro de Conexão API", 
                               f"Erro ao tentar conectar à API de login do servidor:\n{e}")
            # Limpar credenciais em caso de falha
            self.last_username = None
            self.last_password = None
            self.last_api_auth = None
            return False

    def handle_client_source_change(self, source_type):
        """Lida com cliques nos botões de fonte no modo cliente, enviando API."""
        if not self.is_client_only: return # Segurança extra

        payload = {'type': source_type}
        param = None # Inicializa param como None

        if source_type == 'video':
            # IMPORTANTE: O QFileDialog seleciona um arquivo LOCAL. O SERVIDOR precisa ter acesso a esse MESMO path.
            # Isso só funciona se o servidor e o cliente rodam na mesma máquina ou usam um disco de rede mapeado da mesma forma.
            file_name, _ = QFileDialog.getOpenFileName(
                self, "Selecionar Vídeo para o Servidor", "", "Vídeos (*.mp4 *.avi *.mkv)"
            )
            if not file_name: return # Usuário cancelou
            param = file_name
            payload['param'] = param

        elif source_type == 'camera':
            # Por simplicidade, vamos assumir a câmera 0 no servidor.
            # Poderíamos pedir um ID com QInputDialog.
            camera_id = 0 # Ou pedir com InputDialog
            ok = True
            # Exemplo pedindo ID:
            # camera_id_str, ok = InputDialog.getText(self, "ID da Câmera no Servidor", "Digite o ID da câmera (ex: 0):", text="0")
            # if ok and camera_id_str.isdigit():
            #     camera_id = int(camera_id_str)
            # else:
            #     return # Cancelado ou inválido
            param = camera_id
            payload['param'] = param

        elif source_type == 'stream':
            url, ok = InputDialog.getText(self, "URL do Stream para o Servidor", "Digite a URL (RTSP/HTTP):", text=self.settings.get('AI_PARAMS',{}).get('advanced',{}).get('video_source',{}).get('stream_url',''))
            if not ok or not url: return # Usuário cancelou ou deixou em branco
            param = url
            payload['param'] = param

        if param is not None:
            self.send_source_change_request(payload)

    def _encrypt_payload(self, payload_dict):
        """Criptografa um dicionário para envio."""
        if not self.security:
            self.logger.error("SecurityManager não disponível para criptografar payload.")
            return None
        try:
            payload_json = json.dumps(payload_dict).encode('utf-8')
            encrypted_payload = self.security.encrypt_data(payload_json)
            return encrypted_payload
        except Exception as e:
            self.logger.error(f"Erro ao criptografar payload: {e}", exc_info=True)
            return None


    def send_source_change_request(self, payload):
        """Envia a requisição POST para /api/change_source."""
        if not self.remote_server_address:
            QMessageBox.critical(self, "Erro", "Endereço do servidor não configurado.")
            return

        api_url = f"{self.remote_server_address}/api/change_source"
        self.logger.info(f"Enviando requisição para {api_url} com payload: {payload}")

        try:
            # <<< CRIPTO: Criptografar payload >>>
            encrypted_payload = self._encrypt_payload(payload)
            if encrypted_payload is None:
                QMessageBox.critical(self, "Erro Interno", "Falha ao criptografar dados para envio.")
                return
            headers = {'Content-Type': 'application/octet-stream'}
            # <<< FIM CRIPTO >>>

            # <<< USA self.api_session em vez de requests.post >>>
            response = self.api_session.post(api_url, data=encrypted_payload, headers=headers, timeout=10) # Envia bytes criptografados
            response.raise_for_status() # Levanta erro para 4xx/5xx

            response_data = response.json()
            if response_data.get("success"):
                self.logger.info(f"Servidor confirmou mudança de fonte: {response_data.get('message')}")
                QMessageBox.information(self, "Sucesso", f"Comando enviado ao servidor:\n{response_data.get('message')}")
                # A UI deve atualizar automaticamente ao receber o novo stream/stats
            else:
                self.logger.error(f"Servidor recusou mudança de fonte: {response_data.get('message')}")
                QMessageBox.warning(self, "Falha no Servidor", f"O servidor não pôde alterar a fonte:\n{response_data.get('message')}")

        except requests.exceptions.ConnectionError:
            self.logger.error(f"Erro de conexão ao tentar mudar fonte em {api_url}")
            self._enter_reconnecting_mode("Erro de conexão ao mudar fonte.") # <<< Entrar em modo reconexão
            QMessageBox.critical(self, "Erro de Conexão", f"Não foi possível conectar ao servidor em {api_url}.")
        except requests.exceptions.Timeout:
            self.logger.error(f"Timeout ao tentar mudar fonte em {api_url}")
            QMessageBox.warning(self, "Timeout", f"A requisição para {api_url} demorou muito para responder.")
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Erro na requisição para mudar fonte: {e}", exc_info=True)
            status_code = e.response.status_code if e.response is not None else "N/A"
            error_detail = str(e)
            if e.response is not None:
                try:
                    error_detail = e.response.json().get('message', str(e))
                except ValueError: # Not JSON
                    error_detail = e.response.text[:200] # Primeiros 200 chars

            # <<< NOVO: Tratar especificamente o erro 409 de login duplicado >>>
            if status_code == 409: # Conflito - Login Duplicado
                QMessageBox.warning(self, "Login Duplicado", 
                                  f"Não foi possível fazer login:\n{error_detail}")
            elif status_code == 401 or status_code == 403:                 
                QMessageBox.critical(self, "Erro de Permissão", f"Acesso negado pelo servidor (Erro {status_code}).\nVerifique se você está logado como admin na interface web do servidor ou se a autenticação está configurada corretamente.")
            else:
                 QMessageBox.critical(self, "Erro de API", f"Erro ao comunicar com o servidor (Erro {status_code}):\n{error_detail}")

    def send_pause_resume_request(self, action):
        """Envia requisição para /api/pause ou /api/resume."""
        if not self.remote_server_address: return False

        api_url = f"{self.remote_server_address}/api/{action}" # action é 'pause' ou 'resume'
        self.logger.info(f"Enviando requisição para {api_url}")

        try:
            response = self.api_session.post(api_url, timeout=5)
            # Se chegamos aqui, a conexão funcionou, mesmo que a API retorne erro
            response.raise_for_status()
            response_data = response.json()
            if response_data.get("success"):
                self.logger.info(f"Servidor confirmou: {response_data.get('message')}")
                # A UI (texto do botão) será atualizada pelo _fetch_remote_stats
                return True
            else:
                self.logger.error(f"Servidor recusou {action}: {response_data.get('message')}")
                QMessageBox.warning(self, f"Falha no Servidor", f"O servidor não pôde {action}:\n{response_data.get('message')}")
                return False
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Erro na requisição para {action}: {e}", exc_info=True)
            self._enter_reconnecting_mode(f"Erro de conexão ao {action}.") # <<< Entrar em modo reconexão
            status_code = e.response.status_code if e.response is not None else "N/A"
            error_detail = str(e)
            if e.response is not None:
                try: error_detail = e.response.json().get('message', str(e))
                except ValueError: error_detail = e.response.text[:200]

# <<< NOVO: Tratar especificamente o erro 409 de login duplicado >>>
            if status_code == 409: # Conflito - Login Duplicado
                QMessageBox.warning(self, "Login Duplicado", 
                                  f"Não foi possível fazer login:\n{error_detail}")
            elif status_code == 401 or status_code == 403:                 QMessageBox.critical(self, "Erro de Permissão", f"Acesso negado pelo servidor (Erro {status_code}).")
            else:
                 QMessageBox.critical(self, "Erro de API", f"Erro ao comunicar com o servidor (Erro {status_code}):\n{error_detail}")
            return False

    def setup_timers(self):
        """Configura timers e atributos relacionados"""
        # self.fps_timer = QTimer() # Removido
        # self.fps_timer.timeout.connect(self.update_fps) # Removido
        # self.frame_count = 0 # Removido (não usado mais aqui)
        # --- NOVO: Atributo para rastrear estado de pausa do SERVIDOR ---
        # self.reconnect_timer = None # Inicializado no __init__ agora

        self.server_is_paused = False # Assume que começa não pausado
        # -------------------------------------------------------------
        self.last_fps_time = time.time()
        self.last_frame = None
        self.processing_active = False
        self.update_interval = self.settings['UI_PARAMS']['update_interval']
        self.last_update = time.time()
        self.total_frames = 0 # Resetar ao carregar novo vídeo
        self.current_frame_pos = 0 # <<< CORREÇÃO: Usar .get() com valor padrão >>>
        default_save_dir = self.settings.get('VIDEO_PARAMS', {}).get('save_path', 'capturas')
        self.default_save_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), # Vai para a raiz do projeto
                                           os.path.normpath(default_save_dir))
        

    def set_model(self, model):
        """Configura o modelo após carregamento assíncrono"""
        if self.is_client_only:
            self.logger.warning("Tentativa de definir modelo no modo cliente ignorada.")
            return

        self.model = model
        if self.model:
            self.model.set_callback(self.frame_signal.signal.emit)
            self.model.set_video_finished_callback(self.on_video_finished)
            # self.model.set_extract_flag_reference(self.extract_frame_flag) # Modelo não precisa mais da flag diretamente
            self.enable_model_dependent_features()
            self.logger.info("Modelo carregado com sucesso")
            
    def disable_model_dependent_features(self):
        """Desabilita recursos que dependem do modelo"""
        for widget in self.model_dependent_widgets:
            widget.setEnabled(False)
        if not self.is_client_only:
            self.update_default_message("Carregando modelo...")
            
    def enable_model_dependent_features(self):
        """Habilita recursos após o modelo ser carregado"""
        if self.is_client_only: return # Não habilitar no modo cliente

        for widget in self.model_dependent_widgets:
            widget.setEnabled(True)
        # Habilitar botão de configurações se não for cliente
        self.update_default_message()

    def setup_theme(self):
        """Define o sistema de cores e estilos CSS global da aplicação."""
        # Paleta de cores premium (Deep Ocean / Slate)
        self.colors = {
            'bg_main': '#0f172a',
            'bg_card': '#1e293b',
            'primary': '#3b82f6',
            'secondary': '#64748b',
            'accent': '#10b981',
            'danger': '#ef4444',
            'text_main': '#f8fafc',
            'text_muted': '#94a3b8',
            'border': '#334155'
        }
        
        self.setStyleSheet(f"""
            QMainWindow, QWidget {{
                background-color: {self.colors['bg_main']};
                color: {self.colors['text_main']};
                font-family: 'Inter', 'Segoe UI', 'Roboto', sans-serif;
            }}
            
            QGroupBox {{
                border: 1px solid {self.colors['border']};
                border-radius: 12px;
                margin-top: 20px;
                padding-top: 15px;
                font-weight: bold;
                background-color: rgba(30, 41, 59, 0.4);
            }}
            
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 15px;
                padding: 0 10px;
                color: {self.colors['primary']};
                font-size: 14px;
            }}
            
            QPushButton {{
                background-color: {self.colors['bg_card']};
                border: 1px solid {self.colors['border']};
                border-radius: 8px;
                padding: 10px 20px;
                color: {self.colors['text_main']};
                font-weight: 600;
                font-size: 13px;
            }}
            
            QPushButton:hover {{
                background-color: {self.colors['primary']};
                border-color: {self.colors['primary']};
            }}
            
            QPushButton:pressed {{
                background-color: #2563eb;
            }}
            
            QPushButton:disabled {{
                background-color: #0f172a;
                color: #475569;
                border-color: #1e293b;
            }}
            
            #primary_action {{
                background-color: {self.colors['primary']};
            }}
            
            #danger_action {{
                background-color: {self.colors['danger']};
            }}

            QScrollBar:vertical {{
                border: none;
                background: {self.colors['bg_main']};
                width: 10px;
                margin: 0px;
            }}
            
            QScrollBar::handle:vertical {{
                background: {self.colors['border']};
                min-height: 20px;
                border-radius: 5px;
            }}
            
            QStatusBar {{
                background-color: {self.colors['bg_main']};
                border-top: 1px solid {self.colors['border']};
                color: {self.colors['text_muted']};
                padding: 5px;
            }}
        """)

    def setup_ui(self):
        self.setWindowTitle("VisionAlign v3.0 | Industrial Monitoring")
        self.setWindowIcon(QIcon(os.path.join(os.path.dirname(__file__), 'assets', 'icon.png')))
        self.setGeometry(100, 100, 1500, 950)

        # Main Layout (Vertical)
        main_container = QWidget()
        self.setCentralWidget(main_container)
        main_layout = QVBoxLayout(main_container)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 1. Header Bar
        header = self.create_header()
        main_layout.addWidget(header)

        # 2. Content Area (Grid)
        content_wrapper = QWidget()
        content_layout = QGridLayout(content_wrapper)
        content_layout.setContentsMargins(20, 20, 20, 20)
        content_layout.setSpacing(20)
        
        # Vídeo (70% largura)
        video_container = self.create_video_container()
        content_layout.addWidget(video_container, 0, 0, 2, 2)
        
        # Painel lateral (30% largura)
        side_panel = self.create_side_panel()
        content_layout.addWidget(side_panel, 0, 2, 2, 1)
        
        # Console (Parte inferior)
        console_container = self.create_console_container()
        content_layout.addWidget(console_container, 2, 0, 1, 3)
        
        content_layout.setColumnStretch(0, 2)
        content_layout.setColumnStretch(1, 2)
        content_layout.setColumnStretch(2, 1)
        content_layout.setRowStretch(0, 3)
        content_layout.setRowStretch(2, 1)

        main_layout.addWidget(content_wrapper)
        
        # Status Bar
        self.create_status_bar()

    def create_header(self):
        header = QFrame()
        header.setFixedHeight(70)
        header.setStyleSheet(f"""
            QFrame {{
                background-color: {self.colors['bg_card']};
                border-bottom: 2px solid {self.colors['primary']};
            }}
        """)
        layout = QHBoxLayout(header)
        layout.setContentsMargins(25, 0, 25, 0)

        # Logo e Título
        title_container = QVBoxLayout()
        title = QLabel("VISIONALIGN 3.0")
        title.setStyleSheet(f"font-size: 22px; font-weight: 800; color: {self.colors['text_main']}; border: none; background: transparent;")
        subtitle = QLabel("SISTEMA DE INSPEÇÃO DE FRATURAS EM TEMPO REAL")
        subtitle.setStyleSheet(f"font-size: 11px; font-weight: 600; color: {self.colors['primary']}; border: none; background: transparent; letter-spacing: 2px;")
        title_container.addWidget(title)
        title_container.addWidget(subtitle)
        layout.addLayout(title_container)

        layout.addStretch()

        # Status Indicators
        self.conn_status_label = QLabel("● SERVER: CONNECTED")
        self.conn_status_label.setStyleSheet(f"color: {self.colors['accent']}; font-weight: bold; border: 1px solid {self.colors['border']}; padding: 8px 15px; border-radius: 20px; background: {self.colors['bg_main']};")
        layout.addWidget(self.conn_status_label)

        # User Info
        user_label = QLabel(f"👤 {self.current_user.get('username', 'Operador').upper()}")
        user_label.setStyleSheet(f"font-weight: 700; color: {self.colors['text_muted']}; border: none; background: transparent; padding-left: 20px;")
        layout.addWidget(user_label)

        return header

    def create_video_container(self):
        container = QGroupBox("MONITORAMENTO AO VIVO")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(15, 25, 15, 15)
        
        # --- Área do Vídeo com Filtros ---
        video_container = QWidget()
        video_layout = QVBoxLayout(video_container)
        video_layout.setContentsMargins(0, 0, 0, 0)
        video_layout.setSpacing(5)

        # Barra de Filtros (Pequenas funções solicitadas)
        filter_bar = QWidget()
        filter_layout = QHBoxLayout(filter_bar)
        filter_layout.setContentsMargins(5, 5, 5, 5)
        filter_layout.setSpacing(10)
        
        filter_label = QLabel("Filtros de Visão:")
        filter_label.setStyleSheet("font-weight: bold; color: #94a3b8;")
        filter_layout.addWidget(filter_label)

        self.filter_btns = {}
        # Mapeamento Humano -> Nome Interno do YOLO (visto em names_align)
        classes_to_filter = {
            "Normal": "lata_normal",
            "Invertida": "lata_invertida",
            "Tombada": "lata_tombada",
            "Fratura": "fracture"
        }
        
        for label, internal_name in classes_to_filter.items():
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setChecked(True) # Começa mostrando tudo
            btn.setMinimumHeight(30)
            btn.setStyleSheet("""
                QPushButton { 
                    background-color: #1e293b; border: 1px solid #334155; 
                    border-radius: 4px; padding: 2px 10px; color: #94a3b8;
                }
                QPushButton:checked { 
                    background-color: #3b82f6; color: white; border: none;
                }
            """)
            btn.clicked.connect(self._update_class_filters)
            self.filter_btns[internal_name] = btn
            filter_layout.addWidget(btn)
        
        filter_layout.addStretch()
        
        # Dica Full Screen
        fs_hint = QLabel("(Dê duplo clique para Full Screen)")
        fs_hint.setStyleSheet("color: #475569; font-size: 10px; font-style: italic;")
        filter_layout.addWidget(fs_hint)

        video_layout.addWidget(filter_bar)

        self.video_label = ClickableLabel()
        self.video_label.double_clicked.connect(self.toggle_video_full_screen)
        video_layout.addWidget(self.video_label, 1) # Expande
        
        self.fs_dialog = None # Guardará a janela full screen se aberta
        self.excluded_classes = []
        self.video_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.video_label.setMinimumSize(800, 500)
        self.video_label.setAlignment(Qt.AlignCenter)
        self.video_label.setStyleSheet(f"""
            QLabel {{
                border: 1px solid {self.colors['border']};
                border-radius: 12px;
                background-color: #000000;
                padding: 0px;
            }}
        """)
        
        # Adicionar texto padrão
        self.update_default_message()
        
        layout.addWidget(video_container, stretch=1)
        stats_grid = self.create_stats_grid()
        layout.addWidget(stats_grid)
        
        self.model_dependent_widgets.extend([
            self.video_btn, 
            self.camera_btn, 
            self.stream_btn
        ])
        
        return container

    def create_stats_grid(self):
        grid = QWidget()
        layout = QGridLayout(grid)
        layout.setSpacing(5)
        
        # Criar cards de estatísticas
        stats = [
            ("Processamento", "processamento"),
            ("FPS", "fps"),
            ("Memória GPU", "memoria"),
            ("Normais", "lata_normal"),  # Ajustado para corresponder
            ("Invertidas", "lata_invertida"),  # Ajustado para corresponder
            ("Tombadas", "lata_tombada")  # Ajustado para corresponder
        ]
        
        for i, (title, key) in enumerate(stats):
            card = self.create_stat_card(title, key)
            layout.addWidget(card, i // 3, i % 3)
            
        return grid

    def create_stat_card(self, title, key):
        card = QFrame()
        card.setMinimumHeight(100)
        card.setStyleSheet(f"""
            QFrame {{
                background-color: {self.colors['bg_card']};
                border: 1px solid {self.colors['border']};
                border-radius: 10px;
            }}
            QFrame:hover {{
                border-color: {self.colors['primary']};
            }}
        """)
        
        layout = QVBoxLayout(card)
        layout.setContentsMargins(15, 15, 15, 15)
        
        title_label = QLabel(title.upper())
        title_label.setStyleSheet(f"font-weight: 700; color: {self.colors['text_muted']}; font-size: 10px; border: none; background: transparent;")
        
        value_label = QLabel("0")
        value_label.setStyleSheet(f"font-size: 28px; font-weight: 800; color: {self.colors['text_main']}; border: none; background: transparent;")
        self.status_labels[key] = value_label
        
        layout.addWidget(title_label)
        layout.addWidget(value_label)
        layout.addStretch()
        return card

    def create_side_panel(self):
        panel = QGroupBox("Controles")
        layout = QVBoxLayout(panel)
        
        self.side_panel_layout = layout # <<< Guardar referência ao layout
        # Controles de fonte de vídeo
        source_group = QGroupBox("Fonte de Entrada")
        source_layout = QVBoxLayout()
        
        # Botões de fonte
        source_buttons = QHBoxLayout()
        
        # Adicionar os botões já criados
        for btn in [self.video_btn, self.camera_btn, self.stream_btn]:
            source_buttons.addWidget(btn)
        
        source_layout.addLayout(source_buttons)
        
        # Container para configurações específicas
        self.source_config = QWidget()
        self.source_config_layout = QVBoxLayout(self.source_config)
        source_layout.addWidget(self.source_config)
        
        source_group.setLayout(source_layout)
        layout.addWidget(source_group)
        
        # Controles de playback
        playback_group = QGroupBox("Controles de Playback")
        playback_layout = QHBoxLayout()
        
        self.play_pause_btn = QPushButton("⏸️ Pausar")
        self.play_pause_btn.setMinimumHeight(40)
        self.play_pause_btn.setStyleSheet("""
            QPushButton {
                background-color: #0066cc;
                font-size: 14px;
                font-weight: bold;
            }
        """)
        self.play_pause_btn.clicked.connect(self.toggle_video)
        
        playback_layout.addWidget(self.play_pause_btn)
        playback_group.setLayout(playback_layout)
        layout.addWidget(playback_group)
        
        # Botões de controle com ícones
        buttons = [
            # ("Salvar Frame", "📷", self.save_image), # Removido, agora é via flag/remoto
            # ("Exportar Relatório", "📊", self.export_report), # Removido, agora é via flag/remoto
            # Adicionar objectName ao botão de configurações para encontrá-lo depois
            ("Configurações", "⚙", self.show_settings)
        ] # Mantém apenas configurações por enquanto
        
        for text, icon, callback in buttons:
            btn = QPushButton(f"{icon} {text}")
            btn.setMinimumHeight(40)
            layout.addWidget(btn)
            if text == "Configurações": btn.setObjectName("settings_button") # Definir nome
            btn.clicked.connect(callback)
        
        # Controles de detecção
        # Criar e armazenar referência ao grupo de controles de detecção
        self.detection_controls_group = self.create_detection_controls()
        layout.addWidget(self.detection_controls_group)
        # Adicionar grupo de Alertas Externos (Sirene PLC)
        self.external_alerts_group = self.create_external_alerts_group()
        layout.addWidget(self.external_alerts_group)
        layout.addStretch()
        return panel

    def create_console_container(self):
        """Cria o container do console sem recriar o QTextEdit"""
        container = QGroupBox("Console de Logs")
        layout = QVBoxLayout(container)
        layout.addWidget(self.console)
        return container
    def create_external_alerts_group(self):
        """Cria o grupo para alertas externos como a sirene do PLC."""
        group = QGroupBox("Alertas Externos")
        group = QGroupBox("Sirene PLC") # Renomeado para Sirene PLC
        layout = QVBoxLayout()
        # Indicador da Sirene
        siren_container = QFrame()
        siren_container.setStyleSheet(f"""
            QFrame {{
                background-color: {self.colors['bg_main']};
                border: 1px solid {self.colors['border']};
                border-radius: 8px;
                padding: 10px;
            }}
        """)
        siren_layout = QHBoxLayout(siren_container)
        siren_layout.setContentsMargins(10, 5, 10, 5)

        siren_title_label = QLabel("STATUS DA SIRENE:")
        siren_title_label.setStyleSheet(f"font-weight: 800; color: {self.colors['text_muted']}; font-size: 10px; border: none; background: transparent;")
        self.siren_status_label = QLabel("DESATIVADA")
        self.siren_status_label.setStyleSheet(f"font-size: 12px; font-weight: 800; color: {self.colors['danger']}; background: transparent; border: none;")

        siren_layout.addWidget(siren_title_label)
        siren_layout.addStretch()
        siren_layout.addWidget(self.siren_status_label)

        layout.addWidget(siren_container)

        # Botão Desligar Sirene
        self.deactivate_siren_btn = QPushButton("🚨 DESLIGAR SIRENE")
        self.deactivate_siren_btn.setObjectName("danger_action")
        self.deactivate_siren_btn.setMinimumHeight(45)
        self.deactivate_siren_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {self.colors['danger']};
                color: white;
                font-weight: 800;
                border-radius: 8px;
            }}
            QPushButton:hover {{
                background-color: #dc2626;
            }}
            QPushButton:disabled {{
                background-color: {self.colors['bg_main']};
                color: {self.colors['secondary']};
                border: 1px solid {self.colors['border']};
            }}
        """)
        self.deactivate_siren_btn.setEnabled(False) # Começa desabilitado
        self.deactivate_siren_btn.clicked.connect(self.deactivate_siren_clicked)
        layout.addWidget(self.deactivate_siren_btn)

        group.setLayout(layout)
        return group
    def update_siren_status(self, is_active):
        """Atualiza o label e o botão da sirene na interface."""
        self.siren_active = is_active
        if is_active:
            self.siren_status_label.setText("ATIVADA")
            # Estilo para ATIVADA (Verde)
            self.siren_status_label.setStyleSheet("font-size: 14px; font-weight: bold; color: white; background-color: #28a745; padding: 2px 5px; border-radius: 3px; border: none;") # Adicionado border: none
            self.deactivate_siren_btn.setEnabled(True) # <<< HABILITA o botão
        else:
            self.siren_status_label.setText("DESATIVADA")
            # Estilo para DESATIVADA (Vermelho)
            self.siren_status_label.setStyleSheet("font-size: 14px; font-weight: bold; color: white; background-color: #dc3545; padding: 2px 5px; border-radius: 3px; border: none;") # Adicionado border: none
            self.deactivate_siren_btn.setEnabled(False) # <<< DESABILITA o botão

    def deactivate_siren_clicked(self):
        """Chamado quando o botão 'Desligar Sirene' é clicado."""
        # --- Lógica para Modo Cliente ---
        if self.is_client_only:
            if not self.remote_server_address: return
            api_url = f"{self.remote_server_address}/api/siren/deactivate" # Endpoint hipotético
            self.logger.info(f"Enviando requisição para {api_url}")
            try:
                response = self.api_session.post(api_url, timeout=5)
                response.raise_for_status()
                self.logger.info("Comando para desligar sirene enviado ao servidor.")
                # A UI será atualizada pelo _fetch_remote_stats
            except requests.exceptions.RequestException as e:
                self.logger.error(f"Erro ao enviar comando para desligar sirene: {e}")
                QMessageBox.warning(self, "Erro de API", f"Não foi possível enviar comando ao servidor:\n{e}")
            return # Fim da lógica do cliente

        # --- Lógica Original para Modo Servidor ---
        if self.model and self.siren_active: # Verifica se sirene está ativa localmente
            self.logger.info("Solicitando desativação da sirene...")
            self.model.deactivate_siren()
            # A UI será atualizada no próximo ciclo de `update_display` quando o modelo enviar o novo status
        else:
            self.logger.warning("Tentativa de desativar sirene quando não ativa ou modelo indisponível.")
    def create_status_bar(self):
        status_bar = QStatusBar()
        self.setStatusBar(status_bar)
        # Criar o QLabel ANTES de adicioná-lo
        # <<< NOVO: Adicionar label permanente à direita >>>
        self.system_indicator_label = QLabel("Segurança: <font color='#00FF00'>ATIVADA</font> | Desenvolvido por Victor Silva")
        status_bar.addPermanentWidget(self.system_indicator_label)
        # <<< FIM NOVO >>>
        self.status_label = QLabel("Status: Aguardando vídeo")
        status_bar.addWidget(self.status_label)

    def update_conf_threshold(self):
        self.conf_threshold = self.conf_slider.value() / 100.0
        updated_conf = self.model.update_conf(self.conf_threshold)
        self.conf_label.setText(f"Confiança: {updated_conf:.2f}")
        print(f"Interface - Confiança atualizada: {updated_conf:.2f}")

    def update_iou_threshold(self):
        self.iou_threshold = self.iou_slider.value() / 100.0
        updated_iou = self.model.update_iou(self.iou_threshold)
        self.iou_label.setText(f"IOU: {updated_iou:.2f}")
        print(f"Interface - IOU atualizado: {updated_iou:.2f}")

    def update_frame(self):
        if self.cap and self.is_video_active:
            ret, frame = self.cap.read()
            if ret:
                self.current_frame_pos += 1
                self.current_frame = frame
                self.model.add_frame(frame)
                
                # Atualiza progresso
                progress = (self.current_frame_pos / self.total_frames) * 100
                self.status_label.setText(f"Progresso: {progress:.1f}%")
                
            elif self.current_frame_pos >= self.total_frames:
                print("Vídeo finalizado naturalmente")
                self.stop_video_processing()
            else:
                print(f"Erro na leitura do frame: {self.current_frame_pos}/{self.total_frames}")
                self.stop_video_processing()

    def stop_video_processing(self):
        # No modo cliente, isso deve parar a thread do stream
        if self.is_client_only:
            self._stop_client_stream()
            return
        print("Parando processamento de vídeo...")
        # self.timer.stop() # Já removido
        # self.fps_timer.stop() # Removido
        self.is_video_active = False
        self.processing_active = False
        self.model.stop_processing()
        if self.cap:
            self.cap.release()
            self.cap = None
        self.status_label.setText("Status: Vídeo finalizado")
        self.update_default_message() # Mostra mensagem padrão
        
        # Pergunta se quer salvar o vídeo processado
        # self.ask_save_video() # Desativado por enquanto para simplificar

    def _stop_client_stream(self):
        """Para a thread de stream e o timer de stats no modo cliente."""
        self.logger.info("Parando stream e polling de stats do cliente...")
        if self.stream_thread:
            self.stream_thread.stop()
            self.stream_thread.wait() # Espera a thread terminar
            self.stream_thread = None
        if self.stats_poll_timer:
            self.stats_poll_timer.stop()
            self.stats_poll_timer = None
        if self.reconnect_timer and self.reconnect_timer.isActive(): # <<< Parar timer de reconexão
            self.reconnect_timer.stop()
        self.is_reconnecting = False # <<< Resetar flag
        self.is_video_active = False # Marcar como inativo
        self.update_default_message("Desconectado")
        self.status_label.setText("Status: Desconectado")
        
    def on_video_finished(self):
        # Garante que seja executado na thread principal
        QTimer.singleShot(0, self.ask_save_video)
        
    def ask_save_video(self):
        reply = QMessageBox.question(
            self,
            'Salvar Vídeo',
            'O processamento terminou. Deseja salvar o vídeo processado?',
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes
        )
        
        if reply == QMessageBox.Yes:
            self.save_processed_video()
            
    def save_processed_video(self):
        try:
            if not self.model.processed_frames:
                self.logger.error("Nenhum frame processado disponível")
                QMessageBox.warning(self, "Erro", "Não há frames processados para salvar")
                return
                
            # Cria diretório padrão se não existir
            os.makedirs(self.default_save_path, exist_ok=True)
            
            default_name = os.path.join(self.default_save_path, 
                                      f"video_detectado_{int(time.time())}.mp4")
            
            file_name, _ = QFileDialog.getSaveFileName(
                self,
                "Salvar Vídeo Processado",
                default_name,
                "Vídeos (*.mp4)"
            )
            
            if file_name:
                if self.model.save_processed_video(file_name):
                    self.statusBar().showMessage(f"Vídeo salvo em: {file_name}")
                else:
                    QMessageBox.warning(self, "Erro", "Não foi possível salvar o vídeo")
        except Exception as e:
            self.logger.error(f"Erro ao salvar vídeo: {str(e)}")
            QMessageBox.warning(self, "Erro", f"Erro ao salvar vídeo: {str(e)}")

    def start_video(self):
        """Inicia o processamento a partir de um arquivo de vídeo."""
        if self.is_client_only:
            self.logger.warning("Seleção de arquivo local desabilitada no modo cliente.")
            return

        if not self.check_permission('change_source'):
            return

        file_name, _ = QFileDialog.getOpenFileName( # type: ignore
            self, "Selecionar Vídeo", "", "Vídeos (*.mp4 *.avi *.mkv)"
        )
        if file_name:
            self._load_and_start_source("video", file_path=file_name)

    def _load_and_start_source(self, source_type, file_path=None, camera_id=None, stream_url=None):
        """Lógica centralizada para carregar e iniciar uma fonte de vídeo."""
        if self.is_client_only:
            self.logger.error("Tentativa de iniciar fonte local no modo cliente.")
            return

        if not self.model:
            self.logger.error("Modelo não carregado. Não é possível iniciar a fonte de vídeo.")
            QMessageBox.critical(self, "Erro", "O modelo de IA não está carregado.")
            return

        # Parar processamento anterior, se houver
        self.stop_video_processing()

        # Resetar estado do modelo e contadores
        self.model.reset_state()
        self.current_frame_pos = 0
        self.total_frames = 0 # Resetar total de frames

        # Tentar carregar a nova fonte no modelo
        success = False
        if source_type == "video" and file_path:
            success = self.model.load_video(file_path)
            # Acessar o atributo 'total_frames' diretamente
            if success: self.total_frames = self.model.total_frames # Obter total de frames
        elif source_type == "camera" and camera_id is not None:
            success = self.model.load_camera(camera_id)
        elif source_type == "stream" and stream_url:
            success = self.model.load_stream(stream_url)

        if success:
            # Acessar o atributo 'video_source' do objeto self.model
            self.cap = self.model.video_source # Obter o objeto de captura do modelo
            if self.cap and self.cap.isOpened():
                self.is_video_active = True
                self.processing_active = True # Marcar como processando
                self.model.start_processing() # Inicia a thread de processamento do modelo
                # self.timer.start(int(1000 / self.settings['VIDEO_PARAMS']['default_fps'])) # Timer removido
                self.status_label.setText(f"Status: Processando {source_type}")
                self.logger.info(f"Fonte '{source_type}' iniciada com sucesso.")
                self.update_default_message(clear=True) # Limpa mensagem padrão
            else:
                self.logger.error(f"Falha ao obter ou abrir o objeto de captura para '{source_type}'.")
                QMessageBox.warning(self, "Erro", f"Não foi possível iniciar a fonte: {source_type}")
                self.stop_video_processing() # Garante que tudo está parado
        else:
            QMessageBox.warning(self, "Erro", f"Não foi possível carregar a fonte: {source_type}")
            self.stop_video_processing() # Garante que tudo está parado

    def check_permission(self, action):
        """Verifica se o usuário atual tem permissão para a ação."""
        # No modo cliente, a UI já deve ter habilitado/desabilitado o botão
        # baseado no login. A verificação final é feita pela API do servidor.
        # Portanto, se for cliente, permitimos que a chamada prossiga.
        if self.is_client_only:
            self.logger.debug(f"check_permission: Modo cliente, permitindo ação '{action}' prosseguir para chamada API.")
            return True # Permite que show_settings/etc continuem

        # Simplificado: Apenas admin pode mudar fonte ou abrir settings
        # TODO: Implementar sistema de permissões mais granular se necessário
        is_admin = self.current_user and self.current_user.get('is_admin', False)

        if action in ['change_source', 'show_settings'] and not is_admin:
            self.logger.warning(f"check_permission: Acesso negado para '{action}' (usuário não admin no modo servidor).")
            QMessageBox.warning(self, "Acesso Negado",
                              "Apenas administradores podem realizar esta ação.")
            return False
        return True

    def toggle_video(self):
        """Alternar entre play/pause"""
        # --- Lógica para Modo Cliente ---
        if self.is_client_only:
            if self.server_is_paused:
                # Se o servidor está pausado, tentar retomar
                if self.send_pause_resume_request('resume'):
                    # Não mudamos o botão aqui, esperamos a confirmação via /api/stats
                    pass
            else:
                # Se o servidor está rodando, tentar pausar
                if self.send_pause_resume_request('pause'):
                    # Não mudamos o botão aqui, esperamos a confirmação via /api/stats
                    pass
            return # Fim da lógica do cliente

        # --- Lógica Original para Modo Servidor ---
        self.is_paused = not self.is_paused # Estado local de pausa
        if self.is_paused:
            self.play_pause_btn.setText("▶️ Reproduzir") # Atualiza botão localmente
            if self.model: self.model.pause_processing()
            self.log_to_console("Fonte pausada (local)")
        else:
            self.play_pause_btn.setText("⏸️ Pausar") # Atualiza botão localmente
            if self.model: self.model.resume_processing()
            self.log_to_console("Fonte reproduzindo (local)")
            if 'processamento' in self.status_labels:
                self.status_labels['processamento'].setText("Processamento: Ativo")
            self.log_to_console("Fonte reproduzindo")

    def log_to_console(self, message):
        """Atualizado para usar logging"""
        self.logger.info(message)
        
    def update_status(self, stats):
        """Atualiza as informações de status"""
        if not stats: # Se stats for None ou vazio
            # Limpar ou mostrar N/A no modo cliente se a conexão falhar
            if self.is_client_only:
                for key, label in self.status_labels.items():
                    if label and not sip.isdeleted(label): label.setText("N/A")
                self.status_label.setText("Status: Erro de conexão")
            return
        try:
            # Mapeia os valores diretamente dos stats do modelo
            for key, label in self.status_labels.items():
                if label and not sip.isdeleted(label):
                    value = stats.get(key, 0) # Usar 0 como padrão para contadores
                    
                    # Formatação específica para diferentes tipos de valores
                    if isinstance(value, float):
                        if key in ['fps', 'conf', 'iou']:
                            text = f"{value:.2f}" # Apenas o valor no card
                        else:
                            text = f"{int(value)}"
                    else:
                        text = f"{value}" # Apenas o valor
                        
                    label.setText(text)
                    
            # --- Atualizar botão Pause/Resume no modo cliente ---
            if self.is_client_only:
                server_processing_state = stats.get('processamento', 'N/A')
                self.server_is_paused = (server_processing_state == 'Pausado')
                if self.server_is_paused:
                    self.play_pause_btn.setText("▶️ Retomar")
                else:
                    self.play_pause_btn.setText("⏸️ Pausar")
            # ----------------------------------------------------
            if 'progresso' in stats and not self.is_client_only:
                self.status_label.setText(f"Progresso: {stats['progresso']}")
            if 'siren_active' in stats:
                QTimer.singleShot(0, lambda: self.update_siren_status(stats['siren_active']))
        except Exception as e:
            print(f"Erro ao atualizar status: {str(e)}")
            self.log_to_console(f"Erro de atualização: {str(e)}")

    def save_image(self):
        if self.current_frame is not None:
            file_name = QFileDialog.getSaveFileName(self, 
                "Salvar Imagem", 
                "captura.jpg",
                "Imagens (*.jpg *.png)"
            )[0]
            if file_name:
                cv2.imwrite(file_name, self.current_frame)
                self.statusBar().showMessage(f"Imagem salva em: {file_name}")

    def export_report(self):
        if not hasattr(self, 'report_dialog'):
            self.report_dialog = QDialog(self)
            self.report_dialog.setWindowTitle("Exportar Relatório")
            layout = QVBoxLayout()

            # Campos do relatório
            form_layout = QFormLayout()
            self.report_name = QLineEdit()
            self.report_description = QTextEdit()
            form_layout.addRow("Nome:", self.report_name)
            form_layout.addRow("Descrição:", self.report_description)
            
            # Botão exportar
            export_btn = QPushButton("Exportar")
            export_btn.clicked.connect(self.generate_report)
            
            layout.addLayout(form_layout)
            layout.addWidget(export_btn)
            self.report_dialog.setLayout(layout)

        self.report_dialog.show()

    def generate_report(self):
        # Implementação básica de geração de relatório
        report_data = {
            "nome": self.report_name.text(),
            "descricao": self.report_description.toPlainText(),
            # Usar timestamp UTC para o relatório, formatado para exibição local se necessário
            "data": convert_utc_to_local_display(get_current_utc_timestamp()) or get_current_utc_timestamp().isoformat()
        }
        
        file_name = QFileDialog.getSaveFileName(self,
            "Salvar Relatório",
            "relatorio.txt",
            "Texto (*.txt)"
        )[0]
        
        if file_name:
            with open(file_name, 'w', encoding='utf-8') as f:
                for key, value in report_data.items():
                    f.write(f"{key}: {value}\n")
            self.statusBar().showMessage(f"Relatório salvo em: {file_name}")
            self.report_dialog.close()

    def show_settings(self):
        """Verificar permissão antes de abrir configurações"""
        # --- Lógica para Modo Cliente ---
        self.logger.debug("show_settings: Botão clicado.") # Log inicial
        if self.is_client_only:
            if not self.check_permission('show_settings'):
                 self.logger.warning("show_settings: Permissão negada por check_permission (cliente - inesperado).")
                 return
            self.logger.info("show_settings: Chamando fetch_and_show_remote_settings...")
            self.fetch_and_show_remote_settings()
            return # Fim da lógica do cliente

        # --- Lógica para Modo Servidor ---
        if not self.check_permission('show_settings'):
            return
        try:
            # Reutilizar a lógica de criação do diálogo que já existe
            self._create_and_show_local_settings_dialog()
        except Exception as e:
            self.logger.error(f"Erro ao abrir configurações locais: {str(e)}")
            QMessageBox.warning(self, "Erro", f"Erro ao abrir configurações locais: {str(e)}")

    def fetch_and_show_remote_settings(self):
        """Busca configurações do servidor e abre o diálogo (Modo Cliente)."""
        if not self.remote_server_address:
            self.logger.error("fetch_and_show_remote_settings: Endereço do servidor não configurado.")
            return
        api_url = f"{self.remote_server_address}/api/settings"
        self.logger.info(f"Buscando configurações remotas de {api_url}")

        try:
            # <<< CRIPTO: Aceitar octet-stream e descriptografar >>>
            headers = {'Accept': 'application/octet-stream'}
            response = self.api_session.get(api_url, headers=headers, timeout=5)
            response.raise_for_status()

            encrypted_data = response.content
            if not self.security:
                 self.logger.error("SecurityManager não disponível para descriptografar configurações.")
                 QMessageBox.critical(self, "Erro Interno", "Criptografia não disponível.")
                 return

            decrypted_data = self.security.decrypt_data(encrypted_data)
            if decrypted_data is None:
                 self.logger.error("Falha ao descriptografar configurações remotas.")
                 QMessageBox.warning(self, "Erro de Comunicação", "Não foi possível ler as configurações do servidor (erro de criptografia).")
                 return

            remote_settings = json.loads(decrypted_data.decode('utf-8'))
            self.logger.info("Configurações remotas descriptografadas com sucesso.")

            # Agora, criar e popular o diálogo com os dados remotos
            self._create_and_show_remote_settings_dialog(remote_settings)

        except requests.exceptions.RequestException as e:
            self.logger.error(f"Erro ao buscar configurações remotas: {e}", exc_info=True)
            status_code = e.response.status_code if e.response is not None else "N/A"
            error_detail = str(e)
            if e.response is not None:
                try: error_detail = e.response.json().get('message', str(e))
                except ValueError: error_detail = e.response.text[:200]

# <<< NOVO: Tratar especificamente o erro 409 de login duplicado >>>
            if status_code == 409: # Conflito - Login Duplicado
                QMessageBox.warning(self, "Login Duplicado", 
                                  f"Não foi possível fazer login:\n{error_detail}")
            elif status_code == 401 or status_code == 403:                 QMessageBox.critical(self, "Erro de Permissão", f"Acesso negado pelo servidor ao buscar configurações (Erro {status_code}).")
            else:
                 QMessageBox.critical(self, "Erro de API", f"Erro ao buscar configurações do servidor (Erro {status_code}):\n{error_detail}")

    def _create_and_show_local_settings_dialog(self):
        """Cria e mostra o diálogo de configurações usando os settings locais."""
        self._create_and_show_settings_dialog(self.settings, is_remote=False)

    def _create_and_show_remote_settings_dialog(self, remote_settings_data):
        """Cria e mostra o diálogo de configurações usando dados remotos."""
        self._create_and_show_settings_dialog(remote_settings_data, is_remote=True)

    def _create_and_show_settings_dialog(self, settings_data, is_remote):
        settings_dialog = QDialog(self)
        settings_dialog.setWindowTitle("Configurações")
        layout = QVBoxLayout()

        # Criar widget de abas
        tab_widget = QTabWidget()

        # Tab de configurações básicas
        basic_tab = QWidget()
        basic_layout = QVBoxLayout()

        # Grupo de configurações de vídeo
        video_group = QGroupBox("Configurações de Vídeo")
        video_layout = QFormLayout()

        resolution_combo = QComboBox()
        resolution_combo.addItems(settings_data.get('VIDEO_PARAMS', {}).get('resolutions', {}).keys())
        resolution_combo.setCurrentText(settings_data.get('VIDEO_PARAMS', {}).get('default_resolution', ''))

        fps_combo = QComboBox()
        fps_combo.addItems([str(fps) for fps in settings_data.get('VIDEO_PARAMS', {}).get('fps_options', [])])
        fps_combo.setCurrentText(str(settings_data.get('VIDEO_PARAMS', {}).get('default_fps', 30))) # <<< Usar settings_data

        video_layout.addRow("Resolução:", resolution_combo)
        video_layout.addRow("FPS:", fps_combo)
        video_group.setLayout(video_layout)
        basic_layout.addWidget(video_group)

        # Grupo de configurações básicas de IA
        ai_group = QGroupBox("Configurações de IA")
        ai_layout = QFormLayout()

        conf_spin = QDoubleSpinBox()
        conf_spin.setRange(0.01, 1.0)
        conf_spin.setSingleStep(0.05)
        conf_spin.setValue(settings_data.get('AI_PARAMS', {}).get('conf_default', 0.5))

        iou_spin = QDoubleSpinBox()
        iou_spin.setRange(0.01, 1.0)
        iou_spin.setSingleStep(0.05) # <<< CORREÇÃO: Faltava esta linha
        iou_spin.setValue(settings_data.get('AI_PARAMS', {}).get('iou_default', 0.5)) # <<< Usar settings_data

        ai_layout.addRow("Confidence:", conf_spin)
        ai_layout.addRow("IOU:", iou_spin)
        ai_group.setLayout(ai_layout)
        basic_layout.addWidget(ai_group)

        basic_tab.setLayout(basic_layout)

        # Tab de configurações avançadas
        advanced_tab = QWidget()
        advanced_layout = QVBoxLayout()

        advanced_group = QGroupBox("Configurações Avançadas de IA")
        advanced_form = QFormLayout()

        frame_skip_spin = QSpinBox()
        frame_skip_spin.setRange(1, 30)
        frame_skip_spin.setValue(settings_data.get('AI_PARAMS', {}).get('advanced', {}).get('frame_skip', 1))

        batch_size_spin = QSpinBox()
        batch_size_spin.setRange(1, 32)
        batch_size_spin.setValue(settings_data.get('AI_PARAMS', {}).get('advanced', {}).get('batch_size', 1))

        det_threshold_spin = QSpinBox()
        det_threshold_spin.setRange(1, 10)
        det_threshold_spin.setValue(settings_data.get('AI_PARAMS', {}).get('advanced', {}).get('detection_threshold', 3))

        nms_spin = QDoubleSpinBox()
        nms_spin.setRange(0.1, 1.0)
        nms_spin.setSingleStep(0.05)
        nms_spin.setValue(settings_data.get('AI_PARAMS', {}).get('advanced', {}).get('nms_threshold', 0.5))

        max_det_spin = QSpinBox()
        max_det_spin.setRange(100, 1000)
        max_det_spin.setValue(settings_data.get('AI_PARAMS', {}).get('advanced', {}).get('max_det', 300))

        agnostic_check = QCheckBox()
        agnostic_check.setChecked(settings_data.get('AI_PARAMS', {}).get('advanced', {}).get('agnostic_nms', False))

        advanced_form.addRow("Frame Skip (1/N):", frame_skip_spin)
        advanced_form.addRow("Batch Size:", batch_size_spin)
        # Corrigir nome da label
        advanced_form.addRow("Detection Threshold:", det_threshold_spin)
        advanced_form.addRow("NMS Threshold:", nms_spin)
        advanced_form.addRow("Max Detections:", max_det_spin)
        advanced_form.addRow("NMS Agnóstico:", agnostic_check)

        advanced_group.setLayout(advanced_form)
        advanced_layout.addWidget(advanced_group)

            # Adicionar grupo de fonte de vídeo nas configurações avançadas
        source_group = QGroupBox("Fonte de Vídeo")
        source_layout = QVBoxLayout()

        # Tipo de fonte
        source_combo = QComboBox()
        source_combo.addItems(["video", "camera", "stream"]) # Tipos fixos por enquanto
        source_combo.setCurrentText(settings_data.get('AI_PARAMS', {}).get('advanced', {}).get('video_source', {}).get('type', 'camera'))

        # ID da câmera
        camera_spin = QSpinBox()
        camera_spin.setRange(0, 10)
        camera_spin.setValue(settings_data.get('AI_PARAMS', {}).get('advanced', {}).get('video_source', {}).get('camera_id', 0))

        # URL do stream
        stream_input = QLineEdit()
        stream_input.setText(settings_data.get('AI_PARAMS', {}).get('advanced', {}).get('video_source', {}).get('stream_url', ''))

        source_layout.addWidget(QLabel("Tipo de Fonte:"))
        source_layout.addWidget(source_combo)
        source_layout.addWidget(QLabel("ID da Câmera:"))
        source_layout.addWidget(camera_spin)
        source_layout.addWidget(QLabel("URL do Stream:"))
        source_layout.addWidget(stream_input)

        source_group.setLayout(source_layout)
        advanced_layout.addWidget(source_group)

        advanced_tab.setLayout(advanced_layout)

        # Adicionar tabs ao widget
        tab_widget.addTab(basic_tab, "Configurações Básicas")
        tab_widget.addTab(advanced_tab, "Configurações Avançadas")
        layout.addWidget(tab_widget)

        # Botões
        button_box = QDialogButtonBox(
            QDialogButtonBox.Save | QDialogButtonBox.Cancel # Usar Save
        )

            # Coletar dados dos widgets
        def collect_settings_data():
                        # <<< NOVO: Tratamento de erro para FPS >>>
            try:
                fps_value = int(fps_combo.currentText())
            except ValueError:
                self.logger.warning(f"Valor inválido ou vazio no FPS combo: '{fps_combo.currentText()}'. Usando 30 como padrão.")
                fps_value = 30 # Valor padrão seguro
            return {
                    'VIDEO_PARAMS': {
                        'default_resolution': resolution_combo.currentText(),
                        'default_fps': fps_value # <<< Usar valor tratado
                        # Manter outras chaves de VIDEO_PARAMS se existirem
                    },
                    'AI_PARAMS': {
                        'conf_default': conf_spin.value(),
                        'iou_default': iou_spin.value(),
                        'advanced': {
                            'frame_skip': frame_skip_spin.value(),
                            'batch_size': batch_size_spin.value(),
                            'detection_threshold': det_threshold_spin.value(),
                            'nms_threshold': nms_spin.value(),
                            'max_det': max_det_spin.value(),
                            'agnostic_nms': agnostic_check.isChecked(),
                            'video_source': {
                                'type': source_combo.currentText(),
                                'camera_id': camera_spin.value(),
                                'stream_url': stream_input.text()
                            }
                        }
                        # Manter outras seções de alto nível (COLORS, UI_PARAMS, etc.)
                    }
                }

        # --- Conectar o botão Save ---
        if is_remote:
            # Conectar ao método de envio remoto
            button_box.accepted.connect(lambda: self.send_remote_settings_update(settings_dialog, collect_settings_data()))
        else:
            # Conectar ao método de salvamento local
            button_box.accepted.connect(lambda: self.save_local_settings(settings_dialog, collect_settings_data()))

        # --- Conectar o botão Cancel ---
        button_box.rejected.connect(settings_dialog.reject)

        layout.addWidget(button_box)
        settings_dialog.setLayout(layout)
        settings_dialog.exec_()

    def save_local_settings(self, dialog, collected_data):
        """Salva as configurações localmente (Modo Servidor)."""
        # O método save_settings do SettingsManager espera o dicionário completo
        # Precisamos mesclar os dados coletados com os settings atuais
        # para não perder outras seções (COLORS, UI_PARAMS, etc.)
        current_full_settings = self.settings_manager.get_all()
        # Atualiza apenas as seções VIDEO_PARAMS e AI_PARAMS
        current_full_settings.update(collected_data)

        if self.settings_manager.save_settings(current_full_settings):
            dialog.accept()
            QMessageBox.information(self, "Sucesso", "Configurações locais salvas com sucesso!")
            # O watcher cuidará de aplicar as mudanças
        else:
            QMessageBox.warning(self, "Erro", "Falha ao salvar configurações locais.")

    def send_remote_settings_update(self, dialog, collected_data):
        """Envia as configurações atualizadas para o servidor (Modo Cliente)."""
        if not self.remote_server_address: return
        api_url = f"{self.remote_server_address}/api/settings"
        self.logger.info(f"Enviando configurações atualizadas para {api_url}")

        # Precisamos enviar a estrutura completa que o servidor espera.
        # O ideal seria buscar as configs atuais do servidor, mesclar as mudanças
        # e enviar de volta. Por simplicidade, vamos enviar apenas as seções
        # que o diálogo modificou, assumindo que o servidor sabe mesclar.
        # ATENÇÃO: Isso pode sobrescrever outras configs se o servidor não mesclar!
        payload = collected_data # Envia apenas VIDEO_PARAMS e AI_PARAMS
        try:
            # <<< CRIPTO: Criptografar payload >>>
            encrypted_payload = self._encrypt_payload(payload)
            if encrypted_payload is None:
                QMessageBox.critical(self, "Erro Interno", "Falha ao criptografar dados para envio.")
                return
            headers = {'Content-Type': 'application/octet-stream'}
            # <<< FIM CRIPTO >>>

            # Enviar dados criptografados
            # <<< CORRIGIDO: Usar 'data=encrypted_payload' e passar 'headers' >>>
            response = self.api_session.post(api_url, data=encrypted_payload, headers=headers, timeout=10)
            response.raise_for_status()
            response_data = response.json()
            if response_data.get("message"): # Servidor retorna 'message' em sucesso/erro
                self.logger.info(f"Resposta do servidor ao salvar configs: {response_data['message']}")
                QMessageBox.information(self, "Configurações Remotas", response_data['message'])
                dialog.accept() # Fecha o diálogo se o servidor aceitou
            else: # Caso inesperado
                 QMessageBox.warning(self, "Resposta Inválida", "O servidor respondeu de forma inesperada.")

        except requests.exceptions.RequestException as e:
            self.logger.error(f"Erro ao enviar configurações remotas: {e}", exc_info=True)
            status_code = e.response.status_code if e.response is not None else "N/A"
            error_detail = str(e)
            if e.response is not None:
                try: error_detail = e.response.json().get('message', str(e))
                except ValueError: error_detail = e.response.text[:200]

# <<< NOVO: Tratar especificamente o erro 409 de login duplicado >>>
            if status_code == 409: # Conflito - Login Duplicado
                QMessageBox.warning(self, "Login Duplicado", 
                                  f"Não foi possível fazer login:\n{error_detail}")
            elif status_code == 401 or status_code == 403:                 QMessageBox.critical(self, "Erro de Permissão", f"Acesso negado pelo servidor ao salvar configurações (Erro {status_code}).")
            else:
                 QMessageBox.critical(self, "Erro de API", f"Erro ao enviar configurações para o servidor (Erro {status_code}):\n{error_detail}")

    # Renomeado para evitar conflito
    def save_settings_legacy(self, dialog, new_settings):
        try:
            # Cria uma cópia profunda das configurações atuais para modificação
            # Usamos get_all() para garantir que temos a estrutura completa
            updated_settings_data = self.settings_manager.get_all().copy()

            # Atualizar configurações básicas
            if 'VIDEO_PARAMS' in updated_settings_data:
                updated_settings_data['VIDEO_PARAMS']['default_resolution'] = new_settings['basic']['resolution']
                updated_settings_data['VIDEO_PARAMS']['default_fps'] = new_settings['basic']['fps']
            if 'AI_PARAMS' in updated_settings_data:
                updated_settings_data['AI_PARAMS']['conf_default'] = new_settings['basic']['conf']
                updated_settings_data['AI_PARAMS']['iou_default'] = new_settings['basic']['iou']

            # Atualizar configurações avançadas
            if 'AI_PARAMS' in updated_settings_data and 'advanced' in updated_settings_data['AI_PARAMS']:
                 # Atualiza apenas as chaves presentes em new_settings['advanced']
                 for key, value in new_settings['advanced'].items():
                     if key != 'video_source': # Trata video_source separadamente
                         updated_settings_data['AI_PARAMS']['advanced'][key] = value
                 # Atualiza video_source
                 if 'video_source' in new_settings['advanced']:
                     updated_settings_data['AI_PARAMS']['advanced']['video_source'].update(new_settings['advanced']['video_source'])

            # Salvar usando o settings_manager
            # A função save_settings agora retorna True/False
            if self.settings_manager.save_settings(updated_settings_data):
                # O file watcher detectará a mudança e chamará handle_settings_file_changed
                # que por sua vez chamará apply_settings_changes.
                # Não precisamos aplicar as mudanças diretamente aqui.
                dialog.accept()
                QMessageBox.information(self, "Sucesso", "Configurações salvas com sucesso!")
            else:
                raise Exception("Erro ao salvar no arquivo de configurações")

        except Exception as e:
            QMessageBox.warning(self, "Erro", f"Erro ao salvar configurações: {str(e)}")
            self.logger.error(f"Erro detalhado ao salvar configurações: {e}", exc_info=True)

    def handle_settings_file_changed(self, path):
        """Chamado quando o QFileSystemWatcher detecta uma mudança."""
        settings_file_path = str(self.settings_manager.settings_path)
        if path == settings_file_path:
            self.logger.info(f"Detectada alteração em {path}. Aguardando para recarregar...")
            # Usar singleShot para evitar múltiplos reloads rápidos e dar tempo ao arquivo ser escrito
            QTimer.singleShot(500, self._process_settings_update)

    def _process_settings_update(self):
        """Recarrega e aplica as configurações."""
        self.logger.info("Processando atualização de configurações...")
        settings_file_path = str(self.settings_manager.settings_path)
        # Readicionar o path ao watcher, pois alguns sistemas/editores removem o watch ao salvar
        self.settings_watcher.addPath(settings_file_path)

        old_settings = self.settings.copy() # Guardar configurações antigas para comparação
        new_settings = self.settings_manager.reload_settings()

        if new_settings is None:
            self.logger.error("Falha ao recarregar configurações. Mantendo configurações atuais.")
            # Restaurar watcher caso o reload falhe
            if not self.settings_watcher.files():
                 self.settings_watcher.addPath(settings_file_path)
            return

        # Comparar e aplicar apenas as mudanças necessárias
        self.apply_settings_changes(new_settings, old_settings)

    def apply_settings_changes(self, new_settings, old_settings):
        """Aplica as mudanças detectadas entre as configurações antigas e novas."""
        self.logger.info("Aplicando mudanças de configuração...")
        self.settings = new_settings # Atualiza a referência interna principal

        # 1. Atualizar Parâmetros de IA (Conf, IOU, Avançados) - Podem ser feitos sem reiniciar vídeo
        if new_settings.get('AI_PARAMS') != old_settings.get('AI_PARAMS'):
            self.logger.info("Detectadas mudanças nos parâmetros de IA.")
            self.conf_threshold = new_settings.get('AI_PARAMS', {}).get('conf_default', self.conf_threshold)
            self.iou_threshold = new_settings.get('AI_PARAMS', {}).get('iou_default', self.iou_threshold)

            # Atualizar UI (Sliders e Labels)
            self.conf_slider.setValue(int(self.conf_threshold * 100))
            self.iou_slider.setValue(int(self.iou_threshold * 100))
            self.conf_label.setText(f"Confiança: {self.conf_threshold:.2f}")
            self.iou_label.setText(f"IOU: {self.iou_threshold:.2f}")

            if self.model:
                self.model.update_conf(self.conf_threshold)
                self.model.update_iou(self.iou_threshold)
                # Verificar se configurações avançadas mudaram e aplicar se possível
                new_advanced = new_settings.get('AI_PARAMS', {}).get('advanced', {})
                old_advanced = old_settings.get('AI_PARAMS', {}).get('advanced', {})
                if new_advanced != old_advanced:
                     self.logger.info("Aplicando configurações avançadas de IA.")
                     # Assumindo que o modelo tem um método para isso
                     if hasattr(self.model, 'update_advanced_settings'):
                         self.model.update_advanced_settings(new_advanced)
                     else:
                         self.logger.warning("Modelo não possui método 'update_advanced_settings'.")
            else:
                 self.logger.warning("Modelo não carregado, parâmetros de IA atualizados na interface, mas não no modelo.")

        # 2. Atualizar Fonte de Vídeo (Requer reiniciar o stream/câmera/vídeo)
        new_source_config = new_settings.get('AI_PARAMS', {}).get('advanced', {}).get('video_source', {})
        old_source_config = old_settings.get('AI_PARAMS', {}).get('advanced', {}).get('video_source', {})
        if new_source_config != old_source_config:
            self.logger.info("Detectada mudança na fonte de vídeo. Reiniciando a fonte...")
            source_type = new_source_config.get('type')
            camera_id = new_source_config.get('camera_id')
            stream_url = new_source_config.get('stream_url')
            # Chamar a função centralizada para carregar e iniciar
            # (Presume que o usuário não quer carregar um ARQUIVO remotamente, apenas mudar tipo/id/url)
            if source_type == "camera":
                 self._load_and_start_source("camera", camera_id=camera_id)
            elif source_type == "stream":
                 self._load_and_start_source("stream", stream_url=stream_url)
            # Nota: Iniciar um 'video' remotamente sem um QFileDialog é problemático.
            # Poderia ser adicionado se o path do vídeo estivesse na config.

        # 3. Atualizar Tema/UI (se houver mudanças relevantes)
        if new_settings.get('COLORS') != old_settings.get('COLORS'):
             self.logger.info("Detectada mudança nas cores. Reaplicando tema.")
             self.setup_theme() # Reaplica o stylesheet

        self.logger.info("Mudanças de configuração aplicadas.")

    def closeEvent(self, event):
        """Cleanup ao fechar janela"""
        if self.is_client_only:
            self._stop_client_stream() # Garante que a thread e o timer parem
            event.accept()
            return
        self.processing_active = False
        if hasattr(self, 'timer'):
            self.timer.stop()
        # if hasattr(self, 'frame_check_timer'): # Timer removido
        #     self.frame_check_timer.stop()
        if hasattr(self, 'settings_watcher'):
             # Parar de monitorar o arquivo
             self.settings_watcher.removePaths(self.settings_watcher.files())
        # if hasattr(self, 'fps_timer'): # Removido
        #     self.fps_timer.stop() # Removido
        self.model.stop_processing()
        if self.cap:
            self.cap.release()
        event.accept()

    def update_display(self, data):
        """Atualiza a imagem e as estatísticas na UI (Modo Servidor)."""
        if self.is_client_only:
            # No modo cliente, este slot é chamado pelo model.set_callback,
            # mas o modelo não existe. O frame vem de _handle_remote_frame.
            # As stats vêm de _fetch_remote_stats.
            return

        try:
            if self.is_paused:
                if self.frozen_frame is not None and hasattr(self, 'video_label'):
                    self.video_label.setPixmap(self.frozen_frame)
                return

            # --- Lógica existente para modo servidor ---
            processed_frame_bgr = data.get('frame')
            if processed_frame_bgr is not None:
                # Exibe o frame
                self._display_frame_on_label(processed_frame_bgr)

                # Atualizar o frame compartilhado para o stream MJPEG (protegido por lock)
                if self.frame_container is not None and self.frame_lock is not None:
                    with self.frame_lock:
                        self.frame_container[0] = processed_frame_bgr.copy()

            # Atualizar estatísticas
            current_stats = data.get('stats')
            if current_stats:
                self.update_status(current_stats)
                # Atualizar o dicionário compartilhado de forma segura
                if self.shared_stats is not None and self.stats_lock is not None:
                    with self.stats_lock:
                        self.shared_stats.clear()
                        self.shared_stats.update(current_stats)

            # Atualizar status da sirene se a informação estiver presente
            if 'siren_active' in data:
                QTimer.singleShot(0, lambda: self.update_siren_status(data['siren_active']))

        except Exception as e:
            self.logger.error(f"Erro ao atualizar display (Servidor): {str(e)}", exc_info=True)

    def _display_frame_on_label(self, frame_bgr):
        """Auxiliar para converter e exibir o frame no QLabel correto (Main ou FullScreen)."""
        if frame_bgr is None or frame_bgr.size == 0: return
        
        # Determinar qual label usar
        target_label = self.video_label
        if hasattr(self, 'fs_dialog') and self.fs_dialog and self.fs_dialog.isVisible():
            target_label = self.fs_dialog.video_label

        if sip.isdeleted(target_label): return

        try:
            h, w, ch = frame_bgr.shape
            bytes_per_line = ch * w
            # Usar Format_BGR888 diretamente se disponível (PyQt5 suporta)
            q_img = QImage(frame_bgr.data, w, h, bytes_per_line, QImage.Format_BGR888)
            
            # Redimensionar mantendo aspect ratio baseado no tamanho atual da label
            label_w = target_label.width()
            label_h = target_label.height()
            
            if label_w > 0 and label_h > 0:
                pixmap = QPixmap.fromImage(q_img)
                target_label.setPixmap(pixmap.scaled(label_w, label_h, Qt.KeepAspectRatio, Qt.SmoothTransformation))
                self.is_video_active = True
        except Exception as e:
            self.logger.error(f"Erro ao exibir frame: {e}")

    @pyqtSlot(np.ndarray)
    def _handle_remote_frame(self, frame_bgr):
        """Slot para receber e exibir frames da thread do stream (Modo Cliente)."""
        if not self.is_client_only or self.is_paused: # Ignorar se não for cliente ou estiver pausado
            self.logger.debug("_handle_remote_frame: Ignorando frame (não cliente ou pausado).")
            return
        self._display_frame_on_label(frame_bgr)

    @pyqtSlot(str)
    def _handle_stream_error(self, error_message):
        """Slot para lidar com erros da thread do stream (Modo Cliente)."""
        # Só entra em modo reconexão se já não estiver nele
        if not self.is_reconnecting:
            self.logger.error(f"Erro no Stream Remoto: {error_message}")
            self._enter_reconnecting_mode("Erro na conexão do stream de vídeo.") # <<< Entrar em modo reconexão
        else:
            # Se já está reconectando, apenas loga o erro do stream sem mudar estado
            self.logger.debug(f"Erro no Stream Remoto (durante reconexão): {error_message}")


    def _fetch_remote_stats(self):
        """Busca estatísticas do servidor remoto (Modo Cliente)."""
        if not self.is_client_only or not self.remote_server_address or (self.current_user and self.current_user.get('is_guest', False)):
            return

        stats_url = f"{self.remote_server_address}/api/stats"
        try:
            # <<< USA self.api_session em vez de requests.get >>>
            response = self.api_session.get(stats_url, timeout=0.5) # Timeout curto
            # <<< CRIPTO: Aceitar octet-stream e descriptografar >>>
            headers = {'Accept': 'application/octet-stream'}
            response = self.api_session.get(stats_url, headers=headers, timeout=0.5) # Timeout curto
            response.raise_for_status() # Levanta exceção para erros HTTP (4xx, 5xx)

            encrypted_data = response.content
            if not self.security:
                 self.logger.error("SecurityManager não disponível para descriptografar stats.")
                 self._enter_reconnecting_mode("Erro interno: Criptografia não disponível.")
                 return
            decrypted_data = self.security.decrypt_data(encrypted_data)
            if decrypted_data is None:
                 self.logger.error("Falha ao descriptografar estatísticas recebidas do servidor.")
                 self._enter_reconnecting_mode("Erro de comunicação: Falha na descriptografia dos dados.")
                 return
            stats_data = json.loads(decrypted_data.decode('utf-8'))

            # --- SUCESSO! Sair do modo de reconexão se necessário ---
            if self.is_reconnecting:
                self._exit_reconnecting_mode()
            # ---------------------------------------------------------

            self.update_status(stats_data) # Atualiza a UI com os novos stats
            self.status_label.setText("Status: Conectado") # Atualiza status bar
            self.update_connection_status(True) # <<< NOVO: Atualiza indicador visual

        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
            # Se for o primeiro erro, loga como ERROR e entra em reconexão
            # Se já estiver reconectando, loga como DEBUG
            log_level = logging.DEBUG if self.is_reconnecting else logging.ERROR
            self.logger.log(log_level, f"Erro de conexão/timeout ao buscar stats: {e}")
            self.update_connection_status(False) # <<< NOVO: Atualiza indicador visual
            if not self.is_reconnecting:
                self._enter_reconnecting_mode(f"Erro ao buscar stats: {e}")

        except requests.exceptions.HTTPError as e:
            # Erros como 401 Unauthorized, 403 Forbidden, 404 Not Found, 5xx Server Error
            log_level = logging.WARNING # Usar WARNING para erros HTTP
            self.logger.log(log_level, f"Erro HTTP ao buscar stats: {e}")

            # --- MODIFICAÇÃO: Lidar com 401/403 durante a reconexão SEM PARAR ---
            # <<< MODIFICADO: Tentar re-autenticar em 401/403 durante reconexão >>>
            if self.is_reconnecting and e.response.status_code in [401, 403]:
                self.logger.warning("Sessão inválida durante reconexão (401/403). Tentando re-autenticar...")
                self.status_label.setText("Status: Re-autenticando...")
                if self.last_username and self.last_password:
                    # Tenta re-autenticar. Se falhar, continua no loop de reconexão.
                    # Se tiver sucesso, a próxima tentativa de _fetch_remote_stats deve funcionar.
                    self.authenticate_with_server_api(self.last_username, self.last_password)
                    # Não saia do modo de reconexão aqui, espere a próxima tentativa de stats ter sucesso.
                    # Apenas loga e atualiza o status. O timer continua.
                else:
                    self.logger.error("Não foi possível re-autenticar: credenciais não armazenadas.")
                    # Neste caso, o loop de 401/403 continuará. Talvez parar a reconexão?
                    # Por enquanto, vamos deixar continuar, mas logamos o erro.
                # NÃO paramos o timer nem saímos do modo de reconexão aqui.
            elif e.response.status_code in [401, 403]: # Se não estava reconectando, loga como WARNING
                self.logger.warning("Erro de autenticação/autorização ao buscar stats. Verifique o login.")
            elif not self.is_reconnecting: # Para outros erros HTTP (5xx), entrar em reconexão
                 self._enter_reconnecting_mode(f"Erro HTTP {e.response.status_code} ao buscar stats.")

        except json.JSONDecodeError as e:
            # Este erro agora só deve ocorrer se os dados *descriptografados* forem inválidos
            self.logger.error(f"Erro ao decodificar JSON das estatísticas descriptografadas: {e}")
            if not self.is_reconnecting:
                self._enter_reconnecting_mode("Dados de estatísticas corrompidos recebidos do servidor.")

        except Exception as e: # Outros erros inesperados
            self.logger.error(f"Erro inesperado ao buscar stats: {e}", exc_info=True)
            if not self.is_reconnecting:
                self._enter_reconnecting_mode(f"Erro inesperado ao buscar stats: {e}")

    def _attempt_reconnection(self):
        """Chamado pelo reconnect_timer para tentar reconectar."""
        self.logger.debug("Tentando reconectar ao servidor...") # Mudar para DEBUG
        # A maneira mais simples de verificar é tentar buscar os stats
        self._fetch_remote_stats()
        # Se _fetch_remote_stats for bem-sucedido, ele chamará _exit_reconnecting_mode
        # Se falhar, ele manterá o estado is_reconnecting e o timer continuará
    def update_connection_status(self, is_connected):
        """Atualiza visualmente o indicador de conexão no cabeçalho."""
        if not hasattr(self, 'conn_status_label'): return
        
        if is_connected:
            self.conn_status_label.setText("● SERVER: CONNECTED")
            self.conn_status_label.setStyleSheet(f"color: {self.colors['accent']}; font-weight: bold; border: 1px solid {self.colors['border']}; padding: 8px 15px; border-radius: 20px; background: {self.colors['bg_main']};")
        else:
            self.conn_status_label.setText("○ SERVER: OFFLINE")
            self.conn_status_label.setStyleSheet(f"color: {self.colors['danger']}; font-weight: bold; border: 1px solid {self.colors['danger']}; padding: 8px 15px; border-radius: 20px; background: {self.colors['bg_main']};")

    def _enter_reconnecting_mode(self, reason=""):
        """Ativa o modo de reconexão."""
        if self.is_reconnecting: return # Já está no modo
        
        # Loga a entrada no modo como WARNING (é um estado anormal)
        self.logger.warning(f"Entrando em modo de reconexão. Razão: {reason}")
        self.is_reconnecting = True
        self.is_video_active = False # Para vídeo

        # Parar timers/threads normais
        if self.stats_poll_timer: self.stats_poll_timer.stop()
        if self.stream_thread:
            self.stream_thread.stop()
            # Não esperar aqui para não bloquear a UI
            # self.stream_thread.wait()
            self.stream_thread = None

        # Atualizar UI
        self.update_default_message("Tentando reconectar ao servidor...")
        self.status_label.setText("Status: Reconectando...")
        self.update_status(None) # Limpar stats

        # Iniciar timer de reconexão
        if not self.reconnect_timer.isActive():
            self.reconnect_timer.start(self.reconnect_interval)

    def _exit_reconnecting_mode(self):
        """Desativa o modo de reconexão e retoma a operação normal."""
        if not self.is_reconnecting: return # Já está no modo normal

        self.logger.info("Reconexão com o servidor bem-sucedida.")
        self.is_reconnecting = False

        # Parar timer de reconexão
        if self.reconnect_timer.isActive():
            self.reconnect_timer.stop()

        # <<< NOVO: Mostrar mensagem de espera na área do vídeo >>>
        self.update_default_message("Esperando processamento do servidor...")

        # Reiniciar polling de stats e stream de vídeo
        if self.stats_poll_timer and not self.stats_poll_timer.isActive():
            self.stats_poll_timer.start(1000)
        if self.remote_server_address and not self.stream_thread:
            stream_url = f"{self.remote_server_address}/video_feed"
            self.logger.info(f"Reiniciando thread de captura do stream: {stream_url}")
            self.stream_thread = StreamClientThread(stream_url, self)
            self.stream_thread.new_frame_signal.connect(self._handle_remote_frame)
            self.stream_thread.connection_error_signal.connect(self._handle_stream_error)
            self.stream_thread.start()
    def _format_info_text(self, stats):
        """Formata o texto de informações"""
        return f"""
            <div style='font-family: Roboto Mono, monospace; font-size: 12px;'>
            <p><b>Status Diversos:</b></p>
            <p>Sistema: {'Online' if self.processing_active else 'Standby'}</p>
            <p>Memória GPU: {self.get_gpu_memory()}%</p>
            <p>Tempo de Execução: {self.get_execution_time()}</p>
            <p>Taxa de Processamento: {stats.get('fps', 0):.1f} FPS</p>
            <p>Últimas Detecções:</p>
            <p>- Normais: {stats['lata_normals']}</p>
            <p>- Invertidas: {stats['lata_invertidas']}</p>
            <p>- Tombadas: {stats['lata_tombada']}</p>
            </div>
        """

    def get_gpu_memory(self):
        """Uso de GPU não é mais monitorado via Torch (Backend OpenVINO)."""
        return 0

    def get_execution_time(self):
        """Retorna o tempo de execução desde o início do processamento"""
        if not hasattr(self, 'start_time'):
            self.start_time = time.time()
        elapsed = time.time() - self.start_time
        return time.strftime('%H:%M:%S', time.gmtime(elapsed))

    # Código da câmera comentado para referência futura
    """
    def start_camera(self):
        if not self.is_camera_active:
            self.cap = cv2.VideoCapture(0)
            if self.cap.isOpened():
                self.is_camera_active = True
                self.timer.start(30)
                self.status_label.setText("Status: Câmera Ativa")
    """

    def create_detection_controls(self):
        """Cria grupo de controles de detecção com sliders de confiança e IOU"""
        group = QGroupBox("Parâmetros de Detecção")
        layout = QVBoxLayout()

        # Slider de Confiança
        conf_container = QWidget()
        conf_layout = QHBoxLayout(conf_container)
        self.conf_label = QLabel(f"Confiança: {self.conf_threshold:.2f}")
        self.conf_slider = QSlider(Qt.Horizontal)
        self.conf_slider.setMinimum(0)
        self.conf_slider.setMaximum(100)
        self.conf_slider.setValue(int(self.conf_threshold * 100))
        self.conf_slider.valueChanged.connect(self.update_conf_threshold)
        
        conf_layout.addWidget(self.conf_label)
        conf_layout.addWidget(self.conf_slider)

        # Slider de IOU
        iou_container = QWidget()
        iou_layout = QHBoxLayout(iou_container)
        self.iou_label = QLabel(f"IOU: {self.iou_threshold:.2f}")
        self.iou_slider = QSlider(Qt.Horizontal)
        self.iou_slider.setMinimum(0)
        self.iou_slider.setMaximum(100)
        self.iou_slider.setValue(int(self.iou_threshold * 100))
        self.iou_slider.valueChanged.connect(self.update_iou_threshold)
        
        iou_layout.addWidget(self.iou_label)
        iou_layout.addWidget(self.iou_slider)

        # Aplicar estilo aos containers
        for container in [conf_container, iou_container]:
            container.setStyleSheet(f"""
                QWidget {{
                    background-color: {self.colors['bg_main']};
                    border: 1px solid {self.colors['border']};
                    border-radius: 8px;
                    padding: 8px;
                }}
                QLabel {{
                    color: {self.colors['text_muted']};
                    font-weight: 700;
                    font-size: 11px;
                    background: transparent;
                    border: none;
                }}
                QSlider::groove:horizontal {{
                    background: {self.colors['bg_card']};
                    height: 6px;
                    border-radius: 3px;
                }}
                QSlider::handle:horizontal {{
                    background: {self.colors['primary']};
                    border: none;
                    width: 14px;
                    height: 14px;
                    margin: -4px 0;
                    border-radius: 7px;
                }}
                QSlider::handle:horizontal:hover {{
                    background: {self.colors['accent']};
                }}
            """)

        layout.addWidget(conf_container)
        layout.addWidget(iou_container)
        group.setLayout(layout)
        return group

    def hide_guest_restricted_controls(self):
        """Esconde os widgets que não devem ser visíveis para convidados."""
        if hasattr(self, 'detection_controls_group'):
            self.detection_controls_group.setVisible(False)

    def append_log_message(self, message):
        """Slot para adicionar mensagens de log ao console na thread principal."""
        if sip.isdeleted(self.console): return # Segurança extra
        cursor = self.console.textCursor()
        cursor.movePosition(cursor.End)
        cursor.insertText(message)
        self.console.setTextCursor(cursor)
        self.console.ensureCursorVisible()
    def update_source_config(self, source_type):
        """Atualiza configurações baseado no tipo de fonte"""
        # Limpa layout atual
        while self.source_config_layout.count():
            child = self.source_config_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()  
        if source_type == "camera":
            # Configuração de webcam
            camera_layout = QFormLayout()
            self.camera_combo = QComboBox()
            available_cameras = self.get_available_cameras()
            self.camera_combo.addItems([f"Câmera {i}" for i in range(len(available_cameras))])
            camera_layout.addRow("Selecionar câmera:", self.camera_combo)
            self.source_config_layout.addLayout(camera_layout)
            
        elif source_type == "stream":
            # Configuração de stream
            stream_layout = QFormLayout()
            self.stream_url = QLineEdit()
            self.stream_url.setText(self.settings['AI_PARAMS']['advanced']['video_source']['stream_url'])
            stream_layout.addRow("URL do Stream:", self.stream_url)
            
            connect_btn = QPushButton("Conectar")
            connect_btn.clicked.connect(lambda: self.start_stream(self.stream_url.text()))
            self.source_config_layout.addLayout(stream_layout)
            self.source_config_layout.addWidget(connect_btn)

    def get_available_cameras(self):
        """Retorna lista de câmeras disponíveis"""
        cameras = []
        for i in range(10):  # Testa as primeiras 10 câmeras
            cap = cv2.VideoCapture(i)
            if cap.isOpened():
                cameras.append(i)
                cap.release()
        return cameras

    def start_camera(self):
        """Verificar permissão antes de iniciar câmera"""
        if self.is_client_only:
            self.logger.warning("Seleção de câmera local desabilitada no modo cliente.")
            return

        if not self.check_permission('change_source'):
            return
            
        selected_camera = self.camera_combo.currentIndex() if hasattr(self, 'camera_combo') else 0
        self.model.change_source("camera", camera_id=selected_camera)
        self.update_source_config("camera")

    def start_stream(self, url=None):
        """Verificar permissão antes de iniciar stream"""
        if self.is_client_only:
            self.logger.warning("Seleção de stream local desabilitada no modo cliente.")
            return

        if not self.check_permission('change_source'):
            return
            
        # No modo cliente, esta função não deve ser chamada diretamente pelos botões.
        if self.is_client_only:
             self.logger.warning("start_stream chamada incorretamente no modo cliente.")
             return
        if url:
            self._load_and_start_source("stream", stream_url=url)
        # self.update_source_config("stream") # update_source_config não é mais necessário aqui

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, 'video_label') and self.frozen_frame:
            # Redimensionar frame congelado quando janela for redimensionada
            video_size = self.video_label.size()
            scaled_pixmap = self.frozen_frame.scaled(
                video_size,
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )
            self.video_label.setPixmap(scaled_pixmap)

    def update_default_message(self, message=None, clear=False):
        """Atualiza mensagem padrão quando não há vídeo"""
        if not hasattr(self, 'video_label') or sip.isdeleted(self.video_label):
            return # Evita erro se label não existir

        self.is_video_active = False # Assume que não há vídeo ativo ao mostrar msg padrão
        if clear:
            self.video_label.setText("") # Limpa o texto
            self.video_label.setStyleSheet("QLabel { background-color: #2d2d2d; border: 2px solid #2d2d2d; border-radius: 8px; }") # Estilo normal
        elif not self.is_video_active:
            if message:
                self.video_label.setText(f"""
                    <div style='text-align: center; color: #666; font-size: 24px;'>
                        <p>{message}</p>
                    </div>
                """) # type: ignore
            elif not self.is_client_only: # Mensagem padrão só no modo servidor/completo
                self.video_label.setText("""
                    <div style='text-align: center; color: #666; font-size: 24px;'>
                        <p>VisionAlign</p>
                        <p style='font-size: 18px;'>Desenvolvido por Victor Silva</p>
                    </div>
                """)

            else: # Mensagem padrão para o cliente
                 self.video_label.setText("""
                    <div style='text-align: center; color: #666; font-size: 24px;'>
                        <p>VisionAlign Cliente</p>
                        <p style='font-size: 18px;'>Aguardando conexão com o servidor...</p>
                    </div>
                """)
            self.video_label.setStyleSheet("""
                QLabel {
                    border: 2px solid #2d2d2d;
                    border-radius: 8px;
                    background-color: #1a1a1a;
                    padding: 20px;
                }
            """)

    def _request_and_save_frame(self):
        """Solicita um frame ao servidor, baixa e salva descriptografado."""
        if not self.is_client_only or not self.remote_server_address:
            QMessageBox.warning(self, "Ação Indisponível", "Esta função está disponível apenas no modo cliente.")
            return

        api_url = f"{self.remote_server_address}/api/extract_frame"
        self.logger.info(f"Solicitando extração de frame de {api_url}")

        try:
            # Usar POST conforme definido no servidor
            response = self.api_session.post(api_url, timeout=15) # Timeout maior para download
            response.raise_for_status()
        except requests.exceptions.ConnectionError as e:
            self.logger.error(f"Erro de conexão ao solicitar frame: {e}")
            self.update_connection_status(False)
            QMessageBox.critical(self, "Erro de Conexão", 
                               "Não foi possível conectar ao servidor para extrair o frame.\nVerifique se o servidor está ativo.")
            return
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Erro na requisição de frame: {e}")
            QMessageBox.warning(self, "Falha na Requisição", f"Ocorreu um erro ao solicitar o frame:\n{e}")
            return

            # Verificar se a resposta é do tipo esperado (criptografado)
            if response.headers.get('Content-Type') != 'application/octet-stream':
                self.logger.error(f"Resposta inesperada do servidor ao extrair frame: Content-Type={response.headers.get('Content-Type')}")
                QMessageBox.warning(self, "Erro", "O servidor enviou uma resposta inesperada.")
                return

            encrypted_data = response.content
            if not encrypted_data:
                self.logger.warning("Servidor enviou resposta vazia ao extrair frame.")
                QMessageBox.information(self, "Info", "Nenhum frame disponível no servidor no momento.")
                return

            # Descriptografar
            if not self.security:
                self.logger.error("SecurityManager não disponível para descriptografar frame.")
                QMessageBox.critical(self, "Erro Interno", "Criptografia não disponível.")
                return
            decrypted_data = self.security.decrypt_data(encrypted_data)
            if decrypted_data is None:
                self.logger.error("Falha ao descriptografar o frame baixado.")
                QMessageBox.warning(self, "Erro", "Não foi possível descriptografar o frame baixado.")
                return

            # Obter nome do arquivo sugerido (removendo .enc)
            content_disposition = response.headers.get('Content-Disposition', '')
            filename_enc = content_disposition.split('filename=')[-1].strip('"')
            default_filename = filename_enc.replace('.enc', '') if filename_enc.endswith('.enc') else f"frame_capturado_{int(time.time())}.jpg"

            # Pedir local para salvar
            save_path, _ = QFileDialog.getSaveFileName(self, "Salvar Frame Capturado", default_filename, "Imagens JPEG (*.jpg)")

            if save_path:
                with open(save_path, "wb") as f:
                    f.write(decrypted_data)
                self.logger.info(f"Frame descriptografado e salvo em: {save_path}")
                QMessageBox.information(self, "Sucesso", f"Frame salvo com sucesso em:\n{save_path}")

        except requests.exceptions.RequestException as e:
            self.logger.error(f"Erro ao solicitar/baixar frame: {e}", exc_info=True)
            QMessageBox.critical(self, "Erro de Rede", f"Erro ao comunicar com o servidor para extrair frame:\n{e}")
        except Exception as e:
            self.logger.error(f"Erro inesperado ao processar frame extraído: {e}", exc_info=True)
            QMessageBox.critical(self, "Erro Inesperado", f"Ocorreu um erro ao processar o frame:\n{e}")

    def toggle_video_full_screen(self):
        """Alterna o vídeo para modo tela cheia em uma nova janela dedicada."""
        if not hasattr(self, 'fs_dialog') or self.fs_dialog is None:
            self.logger.info("Entrando em modo Full Screen (Vídeo)")
            self.fs_dialog = FullScreenVideoDialog(self)
            self.fs_dialog.finished.connect(self._on_fs_closed)
            self.fs_dialog.show()
        else:
            self.fs_dialog.accept()

    def _on_fs_closed(self):
        self.logger.info("Saindo de modo Full Screen (Vídeo)")
        self.fs_dialog = None

    def _update_class_filters(self):
        """Atualiza a lista de classes ocultas e sincroniza com o servidor/modelo."""
        excluded = []
        if hasattr(self, 'filter_btns'):
            for internal_name, btn in self.filter_btns.items():
                if not btn.isChecked():
                    excluded.append(internal_name)
        
        self.excluded_classes = excluded
        self.logger.info(f"Filtros alterados. Excluindo: {excluded}")
        
        # Se estiver em modo cliente, enviar para o servidor
        if self.is_client_only:
            try:
                url = f"{self.remote_server_address}/api/set_stream_filters"
                from threading import Thread
                def send_req():
                    try:
                        self.api_session.post(url, json={"excluded_classes": excluded}, timeout=2)
                    except: pass
                Thread(target=send_req).start()
            except Exception as e:
                self.logger.error(f"Falha ao enviar filtros: {e}")
        else:
            if self.model:
                self.model.set_excluded_classes(excluded)

    def toggle_fullscreen(self):
        """Alterna entre o modo janela e tela cheia."""
        if self.isFullScreen():
            self.showNormal()
            self.fullscreen_btn.setText("📺 Tela Cheia")
        else:
            self.showFullScreen()
            self.fullscreen_btn.setText("🪟 Sair da Tela Cheia")
            
    def keyPressEvent(self, event):
        """Atalhos de teclado globais."""
        if event.key() == Qt.Key_F11:
            self.toggle_fullscreen()
        else:
            super().keyPressEvent(event)