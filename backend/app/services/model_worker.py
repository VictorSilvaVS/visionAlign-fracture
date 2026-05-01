import os
import sys
import logging
from threading import Lock

# Adicionar o diretório raiz ao path para importar módulos existentes
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))

from model.yolo_model import YOLOModel
from interface.configuracoes.settings import Settings

logger = logging.getLogger("VisionAlign.ModelWorker")

class ModelWorker:
    _instance = None
    _lock = Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(ModelWorker, cls).__new__(cls)
                cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        
        try:
            self.settings_manager = Settings()
            self.settings = self.settings_manager.get_all()
            
            # Containers para compartilhamento de frames (Thread-Safe)
            self.frame_container = [None]
            self.frame_lock = Lock()

            # Inicializar o modelo
            self.model = YOLOModel(
                model_path=None,
                settings=self.settings,
                shared_frame_container=self.frame_container,
                shared_frame_lock=self.frame_lock
            )

            # Configurar callback para atualizar o container de frames
            def frame_update_callback(data):
                with self.frame_lock:
                    self.frame_container[0] = data.get('frame')

            self.model.set_callback(frame_update_callback)
            
            self._initialized = True
            logger.info("ModelWorker inicializado com sucesso.")
        except Exception as e:
            logger.error(f"Falha ao inicializar ModelWorker: {e}")
            raise

    def get_model(self):
        return self.model

    def start(self, source_type='stream', source_param=None):
        """Inicia o processamento do modelo."""
        if source_type == 'stream':
            self.model.load_stream(source_param or self.settings['VIDEO_PARAMS']['source_param'])
        elif source_type == 'camera':
            self.model.load_camera(source_param or self.settings['VIDEO_PARAMS']['source_param'])
        
        self.model.start_processing()
        logger.info(f"Processamento do modelo iniciado (Fonte: {source_type}).")

    def stop(self):
        """Para o processamento do modelo."""
        self.model.stop_processing()
        logger.info("Processamento do modelo parado.")

model_worker = ModelWorker()

def get_model_worker():
    return model_worker
