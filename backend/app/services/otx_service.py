import logging
from training.otx_manager import OTXManager
from interface.configuracoes.settings import Settings

class OTXService:
    _instance = None
    
    def __init__(self):
        self.settings_manager = Settings()
        self.logger = logging.getLogger("VisionAlign.OTXService")
        self.manager = OTXManager(self.settings_manager, logger=self.logger)
        
    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

def get_otx_service():
    return OTXService.get_instance()
