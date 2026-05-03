import sys
import os
import threading
import time
import logging
from openvino.runtime import Core  # Para info de hardware
from threading import RLock  # **OTIMIZAÇÃO: RLock para melhor concorrência no Xeon Gold**
from collections import defaultdict
from typing import Dict, Any, Optional

# Adiciona o root ao path
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from interface.configuracoes.settings import Settings
from utils.logger_config import setup_logging 
from utils.database import Database
from utils.security import SecurityManager
from utils.server import run_server
from model.yolo_model import YOLOModel
from utils.timezone_utils import get_current_utc_timestamp
from utils.clp_communication import CLPCommunication
from utils.email_utils import set_email_config

# --- Globais ---
stats_lock = RLock()
frame_lock = RLock()
db_log_lock = RLock()

frame_container = [None]
system_start_time = get_current_utc_timestamp().timestamp()

last_logged_db_counts = {'lata_normal': 0, 'lata_invertida': 0, 'lata_tombada': 0, 'fracture': 0}
current_stats = {
    'lata_normal': 0,
    'lata_invertida': 0,
    'lata_tombada': 0,
    'fracture': 0,
    'fps': 0.0,
    'processamento': 'Iniciando',
    'memoria': 'N/A',
    'progresso': "0/0"
}

class ModelManager:
    """Gerencia o modelo YOLO e suas operações."""
    
    def __init__(self, settings: Dict[str, Any], logger: logging.Logger):
        self.settings = settings
        self.logger = logger
        self.model = None
        
    def initialize(self) -> Optional[YOLOModel]:
        """Inicializa e configura o modelo YOLO."""
        try:
            self._log_hardware_info()
            self.model = YOLOModel(
                None,
                self.settings.copy()
            )
            
            self.model.set_callback(model_update_callback)
            self._setup_video_source()
            
            return self.model
            
        except Exception as e:
            self.logger.error(f"Erro ao inicializar modelo: {e}", exc_info=True)
            raise

    def _log_hardware_info(self):
        try:
            core = Core()
            devices = core.available_devices
            self.logger.info(f"OpenVINO Runtime disponível. Dispositivos detectados: {devices}")
            for device in devices:
                full_name = core.get_property(device, "FULL_DEVICE_NAME")
                self.logger.info(f"Dispositivo OpenVINO: {device} ({full_name})")
        except Exception as e:
            self.logger.warning(f"Não foi possível obter detalhes do hardware OpenVINO: {e}")

    def _setup_video_source(self) -> bool:
        video_config = self.settings.get('AI_PARAMS', {}).get('advanced', {}).get('video_source', {})
        source_type = video_config.get('type', 'stream')
        
        source_loaders = {
            'stream': self._load_stream_source,
            'camera': self._load_camera_source,
            'video': self._load_video_source
        }
        
        loader = source_loaders.get(source_type)
        if not loader:
            self.logger.warning(f"Tipo de fonte '{source_type}' não suportado.")
            return False
            
        return loader(video_config)

    def _load_stream_source(self, config: Dict[str, Any]) -> bool:
        stream_url = config.get('stream_url')
        if not stream_url:
            self.logger.error("URL de stream não configurada.")
            return False
        self.logger.info(f"Carregando stream: {stream_url}")
        return self.model.load_stream(stream_url)

    def _load_camera_source(self, config: Dict[str, Any]) -> bool:
        camera_id = config.get('camera_id', 0)
        self.logger.info(f"Carregando câmera ID: {camera_id}")
        return self.model.load_camera(int(camera_id))

    def _load_video_source(self, config: Dict[str, Any]) -> bool:
        video_path = config.get('default_video_path')
        if not video_path or not os.path.exists(video_path):
            self.logger.warning(f"Vídeo não encontrado: {video_path}")
            return False
        self.logger.info(f"Carregando vídeo: {video_path}")
        return self.model.load_video(video_path)

# --- Callbacks ---

def model_update_callback(data: Dict[str, Any]):
    logger = logging.getLogger("VisionAlign.Callback")
    
    with frame_lock:
        if (frame := data.get('frame')) is not None:
            frame_container[0] = frame
    
    with stats_lock:
        new_stats = data.get('stats', {})
        # Atualiza contagens acumuladas
        for can_type in ['lata_normal', 'lata_invertida', 'lata_tombada', 'fracture']:
            if can_type in new_stats:
                current_stats[can_type] = new_stats[can_type]
        
        current_stats['fps'] = new_stats.get('fps', 0.0)
        current_stats['processamento'] = new_stats.get('processamento', 'Ativo')

# --- Background Tasks ---

def log_stats_to_db_periodically(interval_seconds: int, db_path: str = None):
    logger = logging.getLogger("VisionAlign.DBLogger")
    logger.info(f"Iniciando logger periódico (intervalo: {interval_seconds}s)")
    
    db = None
    try:
        while True:
            time.sleep(interval_seconds)
            # Lógica de cálculo de deltas
            with stats_lock, db_log_lock:
                deltas = {
                    'normal_count': max(0, current_stats['lata_normal'] - last_logged_db_counts['lata_normal']),
                    'inverted_count': max(0, current_stats['lata_invertida'] - last_logged_db_counts['lata_invertida']),
                    'fallen_count': max(0, current_stats['lata_tombada'] - last_logged_db_counts['lata_tombada']),
                    'fracture_count': max(0, current_stats['fracture'] - last_logged_db_counts['fracture'])
                }
                # Atualiza último log
                for k in last_logged_db_counts:
                    last_logged_db_counts[k] = current_stats[k]

            if any(v > 0 for v in deltas.values()):
                if db is None: 
                    db = Database(db_path=db_path)
                db.log_detection_counts(**deltas)
                logger.debug(f"Deltas logados: {deltas}")
                
                # **NOVO: Registrar alertas APENAS para detecções anormais**
                timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
                
                # Alerta para Latas Invertidas
                if deltas['inverted_count'] > 0:
                    db.log_alert(
                        timestamp=timestamp,
                        alert_type="inverted",
                        lata_id="--",
                        details=f"{deltas['inverted_count']} lata(s) invertida(s) detectada(s)"
                    )
                
                # Alerta para Latas Tombadas
                if deltas['fallen_count'] > 0:
                    db.log_alert(
                        timestamp=timestamp,
                        alert_type="fallen",
                        lata_id="--",
                        details=f"{deltas['fallen_count']} lata(s) tombada(s) detectada(s)"
                    )
                
                # Alerta para Fraturas (se houver)
                if deltas['fracture_count'] > 0:
                    db.log_alert(
                        timestamp=timestamp,
                        alert_type="fracture",
                        lata_id="--",
                        details=f"{deltas['fracture_count']} fratura(s) detectada(s) (contagem agregada)"
                    )
                
    except Exception as e:
        logger.error(f"Erro no logger periódico: {e}")
    finally:
        if db: db.close()

def cleanup_old_files_task(settings_manager):
    """Apaga arquivos mais antigos que o período de retenção (1 dia a 1 ano)."""
    logger = logging.getLogger("VisionAlign.CleanupTask")
    logger.info("Task de limpeza de arquivos iniciada.")
    
    while True:
        try:
            settings = settings_manager.get_all()
            collection = settings.get('AI_PARAMS', {}).get('dataset_collection', {})
            retention_days = int(collection.get('retention_days', 30))
            retention_days = max(1, min(365, retention_days))
            
            now = time.time()
            max_age_seconds = retention_days * 24 * 3600
            project_root = os.path.dirname(os.path.abspath(__file__))
            target_dirs = [
                os.path.join(project_root, "data", "alerts"),
                os.path.join(project_root, "data", "dataset_collect", "images")
            ]
            
            deleted_count = 0
            for directory in target_dirs:
                if not os.path.exists(directory):
                    continue
                
                for filename in os.listdir(directory):
                    file_path = os.path.join(directory, filename)
                    if os.path.isfile(file_path):
                        file_age = now - os.path.getmtime(file_path)
                        if file_age > max_age_seconds:
                            try:
                                os.remove(file_path)
                                deleted_count += 1
                            except Exception as e:
                                logger.error(f"Erro ao remover {file_path}: {e}")
            
            if deleted_count > 0:
                logger.info(f"Limpeza concluída. {deleted_count} arquivos antigos removidos (Retenção: {retention_days} dias).")
            else:
                logger.debug("Nenhum arquivo antigo para remover.")
                
        except Exception as e:
            logger.error(f"Erro na task de limpeza: {e}")
        time.sleep(86400)

# --- Main Server Logic ---

def main_server():
    model = None
    database = None
    clp = None
    
    log_file = os.path.join(project_root, "server.log")
    logger = setup_logging(
        app_type="server",
        logger_name="VisionAlignServer",
        level=logging.INFO,
        specific_log_filename=log_file
    )
    
    logger.info("Iniciando VisionAlign Server")
    
    try:
        # Components
        settings_manager = Settings()
        settings = settings_manager.get_all()
        db_path = settings.get('SYSTEM_CONFIG', {}).get('paths', {}).get('database')
        database = Database(db_path=db_path)
        # Security
        sec_key_path = settings.get('SYSTEM_CONFIG', {}).get('paths', {}).get('security_key')
        security_manager = SecurityManager(key_file=sec_key_path)

        # Email
        email_config = settings.get('EMAIL_CONFIG', {})
        set_email_config(email_config)
        model_manager = ModelManager(settings, logger)
        model = model_manager.initialize()
        
        if model:
            model.start_processing()
            logger.info("Modelo iniciado com sucesso.")
        clp_config = settings.get('CLP_CONFIG', {})
        if clp_config.get('enabled', False):
            try:
                clp = CLPCommunication(ip=clp_config.get('ip'), slot=clp_config.get('slot', 0))
                if clp.connect():
                    clp.start_heartbeat(
                        tag=clp_config.get('heartbeat_tag'), 
                        interval=clp_config.get('heartbeat_interval')
                    )
                    logger.info("Comunicação com CLP e Heartbeat iniciados.")
                else:
                    logger.warning("Falha na conexão inicial com CLP. O Heartbeat tentará reconectar em background.")
                    clp.start_heartbeat(
                        tag=clp_config.get('heartbeat_tag'), 
                        interval=clp_config.get('heartbeat_interval')
                    )
            except Exception as e:
                logger.error(f"Erro ao inicializar CLP: {e}")
        flask_thread = threading.Thread(
            target=run_server,
            args=(settings_manager, logger, current_stats, stats_lock, 
                  frame_container, frame_lock, system_start_time, 
                  model, security_manager),
            daemon=True
        )
        flask_thread.start()

        # DB Logger
        db_interval = settings.get('SYSTEM_CONFIG', {}).get('logging', {}).get('db_log_interval', 60)
        db_thread = threading.Thread(
            target=log_stats_to_db_periodically,
            args=(db_interval, db_path),
            daemon=True
        )
        db_thread.start()
        """snapshot injection"""
        cleanup_thread = threading.Thread(
            target=cleanup_old_files_task,
            args=(settings_manager,),
            daemon=True
        )
        cleanup_thread.start()

        # Loop infinito principal
        main_loop_sleep = settings.get('SYSTEM_CONFIG', {}).get('monitoring', {}).get('main_loop_sleep', 0.1)
        while True:
            time.sleep(main_loop_sleep)
            logger.debug("Servidor ativo e monitorando...")

    except KeyboardInterrupt:
        logger.info("Encerrando por comando do usuário (Ctrl+C).")
    except Exception as e:
        logger.critical(f"Erro fatal: {e}", exc_info=True)
    finally:
        # Cleanup Seguro
        logger.info("Iniciando limpeza de recursos...")
        if model:
            model.stop_processing()
        if clp:
            clp.close()
        if database:
            database.close()
        logger.info("Servidor finalizado.")

if __name__ == "__main__":
    main_server()  