
import socket
from interface.main_window import MainWindow
from utils.security import SecurityManager
from interface.configuracoes.settings import Settings
from PyQt5.QtWidgets import QApplication, QDialog, QMessageBox
from PyQt5.QtCore import QThreadPool
import sys
from utils.logger_config import setup_logging
from utils.database import Database
from interface.dialogs.login_dialog import LoginDialog
from utils.timezone_utils import get_current_utc_timestamp 
import requests 
import os

system_start_time = get_current_utc_timestamp().timestamp()

def initialize_components(logger):
    try:
        settings_manager = Settings()
        settings = settings_manager.get_all()
        
        if not settings_manager.validate_settings(settings):
            raise ValueError("Configurações inválidas ou incompletas")
        database = Database()
        project_root = os.path.dirname(os.path.abspath(__file__))
        config_dir = os.path.join(project_root, "config")
        key_path = os.path.join(config_dir, "server_security.key") 
        logger.info(f"CLIENT: Tentando inicializar SecurityManager com key_file='{key_path}'")
        security = SecurityManager(key_file=key_path) 
        return settings_manager, settings, database, security
    except Exception as e:
        logger.error(f"Erro fatal na inicialização: {str(e)}")
        QMessageBox.critical(None, "Erro Fatal",
                           f"O sistema não pode ser iniciado:\n\n{str(e)}\n\nO aplicativo será encerrado.")
        sys.exit(1)


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("VisionAlign")
    app.setOrganizationName("VisionAlign Inc.")
    app.setOrganizationDomain("visionalign.com")
    global system_start_time 
    system_start_time = get_current_utc_timestamp().timestamp() 
    logger = setup_logging(
        app_type="client",
        console_widget=None
    )
    logger.info("Iniciando VisionAlign (Interface Cliente)")

    settings_manager, settings, database, security = initialize_components(logger) 
    database.create_admin() 
    
    threadpool = QThreadPool.globalInstance() 
    cpu_count = os.cpu_count() or 4
    threadpool.setMaxThreadCount(cpu_count) 
    
    
    default_user = {
        'username': 'guest',
        'role': 'guest', 
        'permissions': ['view'],
        'is_guest': True 
    }
    
    user_info = default_user
    login_dialog = LoginDialog(database)
    result = login_dialog.exec_()
    if result == QDialog.Accepted:
        raw_user_info = login_dialog.user_info 
        if raw_user_info.get('is_guest', False):
            user_info = raw_user_info 
            logger.info(f"Login realizado como visitante. IP: {socket.gethostbyname(socket.gethostname())}")
        else:
            is_admin_flag = raw_user_info.get('is_admin', False)
            normalized_role = 'admin' if is_admin_flag else 'user'
            user_info = raw_user_info.copy() 
            user_info['role'] = normalized_role 
            logger.info(f"Usuário '{user_info['username']}' logado. Role normalizada para: '{user_info['role']}'.")
    else: 
        logger.info("Login cancelado pelo usuário. Encerrando.")
        sys.exit(0) 
    server_host = settings.get('SERVER_CONFIG', {}).get('remote_host', '127.0.0.1')
    server_port = settings.get('SERVER_CONFIG', {}).get('remote_port', 7586)
    server_address = f"http://{server_host}:{server_port}"
    logger.info(f"Aplicação principal configurada para usar servidor em: {server_address}")
    api_session = requests.Session()
    window = MainWindow(
        model=None, 
        security=security,
        settings=settings, 
        user_info=user_info, 
        database=database,
        shared_stats=None, 
        stats_lock=None,
        frame_container=None, 
        frame_lock=None,
        is_client_only=True,
        remote_server_address=server_address,
        api_session=api_session 
    )
    setup_logging(console_widget=window.console, app_type="client") 
    if user_info.get('is_guest', False):
        window.hide_guest_restricted_controls()
    elif not user_info.get('is_guest'):
        username = user_info.get('username')
        password = login_dialog.password_input.text() 
        if not window.authenticate_with_server_api(username, password): 
            
            logger.warning("Autenticação com a API do servidor falhou. Funcionalidades de admin podem não funcionar.")
        window.hide_guest_restricted_controls()
    window.show()

    try:
        return_code = app.exec_()
        logger.info("Encerrando VisionAlign")
        database.close()
        sys.exit(return_code)
    except Exception as e:
        logger.error(f"Erro fatal durante execução: {str(e)}")
        QMessageBox.critical(None, "Erro Fatal",
                           "Ocorreu um erro grave. O aplicativo será encerrado.")
        sys.exit(1)

if __name__ == "__main__":
    main()
