# interface/configuracoes/settings.py
import json
from pathlib import Path
import logging
import os  # Necessário para os.replace

logger = logging.getLogger("VisionAlign." + __name__)


class Settings:
    DEFAULT_SETTINGS = {
        'MODEL_PARAMS': {
            'model_path': 'model/visionalign_v11s.pt',
            'model_version': 'v11s',
            'model_type': 'yolov8'
        },
        'AI_PARAMS': {
            'conf_default': 0.5,
            'iou_default': 0.45,
            'max_queue_size': 30,
            'advanced': {
                'frame_skip': 2,
                'batch_size': 1,
                'detection_threshold': 3,
                'nms_threshold': 0.45,
                'max_det': 300,
                'agnostic_nms': False,
                'video_source': {
                    'type': 'stream',
                    'stream_url': 'rtsp://admin:VisionAlign123%4010.81.50.64:554/cam/realmonitor?channel=1&subtype=0'
                },
                'dataset_collection': {
                    'enabled': True,
                    'save_on_event': True,
                    'save_interval': 10,
                    'distrust_range': [0.3, 0.6],
                    'retention_days': 30
                }
            }
        },
        'VIDEO_PARAMS': {
            'save_path': 'output/videos',
            'default_resolution': '1280x720',
            'default_fps': 30,
            'resolutions': {
                '1280x720': {'width': 1280, 'height': 720},
                '1920x1080': {'width': 1920, 'height': 1080},
                '640x480': {'width': 640, 'height': 480}
            },
            'fps_options': [15, 30, 60]
        },
        'UI_PARAMS': {
            'update_interval': 30,
            'max_log_lines': 1000,
            'font_size': 12,
            'default_theme': 'dark'
        },
        'COLORS': {
            'background': '#1a1a1a',
            'text': '#ffffff',
            'widget_bg': '#2d2d2d',
            'border': '#3d3d3d',
            'interface_primary': '#0066cc',
            'interface_hover': '#0077ee',
            'detection': {
                'lata_normal': (0, 255, 0),  # Verde
                'lata_invertida': (0, 0, 255),  # Vermelho
                'lata_tombada': (255, 165, 0)  # Laranja
            },
            'success': '#00cc00',
            'warning': '#ffcc00',
            'error': '#cc0000'
        },
        # Nova seção para configuração do cliente/servidor
        'SERVER_CONFIG': {
            'remote_host': '127.0.0.1',  # IP ou hostname do servidor principal
            'remote_port': 7586  # Porta do servidor principal
        }
    }

    def __init__(self):
        self.logger = logging.getLogger("VisionAlign.Settings")
        self.settings_path = Path(__file__).parent / 'settings.json'
        self.settings = self._load_settings_from_file()

    def _load_settings_from_file(self, path=None):
        """Carrega configurações com validação"""
        file_path = path or self.settings_path
        try:
            if file_path.exists():
                with open(file_path, 'r', encoding='utf-8') as f:
                    settings = json.load(f)
                if self.validate_settings(settings):
                    return settings
                self.logger.warning("Configurações inválidas, usando padrão")
            return self.save_default_settings()
        except Exception as e:
            self.logger.error(f"Erro ao carregar configurações: {e}")
            return self.save_default_settings()

    def reload_settings(self):
        """Recarrega as configurações do arquivo JSON e atualiza o estado interno."""
        self.logger.info(f"Recarregando configurações de {self.settings_path}")
        # Usar _load_settings_from_file que já tem a lógica de fallback e validação
        new_settings = self._load_settings_from_file(self.settings_path)
        if new_settings:
            # Valida as novas configurações antes de aplicá-las
            if self.validate_settings(new_settings):
                self.settings = new_settings
                self.logger.info("Configurações recarregadas e validadas com sucesso.")  # Usar self.logger
                return self.settings
            else:
                self.logger.error("Falha ao recarregar: Novas configurações são inválidas.")
                return None  # Indica falha na validação
        return None  # Indica falha no carregamento

    def validate_settings(self, settings):
        """Validação detalhada das configurações"""
        try:
            required_sections = ['MODEL_PARAMS', 'AI_PARAMS', 'VIDEO_PARAMS', 'UI_PARAMS', 'COLORS',
                                 'SERVER_CONFIG']  # Adicionado SERVER_CONFIG

            # Verificar seções principais
            if not all(section in settings for section in required_sections):
                return False

            # Validar MODEL_PARAMS
            model_params = settings.get('MODEL_PARAMS', {})
            if not model_params.get('model_path'):
                return False

            # Validar AI_PARAMS
            ai_params = settings.get('AI_PARAMS', {})
            if not isinstance(ai_params.get('conf_default'), (int, float)):
                return False
            if not isinstance(ai_params.get('iou_default'), (int, float)):
                return False

            # Validar SERVER_CONFIG
            server_config = settings.get('SERVER_CONFIG', {})
            if not isinstance(server_config.get('remote_host'), str) or not server_config.get('remote_host'):
                return False
            if not isinstance(server_config.get('remote_port'), int):
                return False

            # Mais validações específicas podem ser adicionadas aqui

            return True

        except Exception as e:
            self.logger.error(f"Erro na validação de configurações: {e}")
            return False

    def save_default_settings(self):
        """Salva e retorna configurações padrão"""
        try:
            self.settings_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.settings_path, 'w', encoding='utf-8') as f:
                json.dump(self.DEFAULT_SETTINGS, f, indent=4)
            return self.DEFAULT_SETTINGS
        except Exception as e:
            self.logger.error(f"Erro ao salvar configurações padrão: {e}")
            return self.DEFAULT_SETTINGS

    def get_all(self):
        """Retorna todas as configurações"""
        return self.settings

    def save_settings(self, settings_to_save):
        """Salva o dicionário de configurações fornecido no arquivo JSON."""
        if not self.validate_settings(settings_to_save):
            self.logger.error("Tentativa de salvar configurações inválidas. Abortando.")
            return False

        try:
            # Escreve em um arquivo temporário primeiro
            temp_file_path = self.settings_path.with_suffix('.json.tmp')
            with open(temp_file_path, 'w', encoding='utf-8') as f:
                json.dump(settings_to_save, f, indent=4, ensure_ascii=False)

            # Renomeia atomicamente (melhor para evitar corrupção)
            os.replace(temp_file_path, self.settings_path)

            # Atualiza o estado interno APÓS salvar com sucesso
            self.settings = settings_to_save
            self.logger.info(f"Configurações salvas com sucesso em {self.settings_path}")
            return True
        except Exception as e:
            self.logger.error(f"Erro ao salvar configurações: {e}")
            # Tenta remover o arquivo temporário se existir
            if 'temp_file_path' in locals() and temp_file_path.exists():  # Verificar se temp_file_path foi definido
                try:
                    temp_file_path.unlink()
                except OSError:
                    pass
            return False

    def update_advanced_ai_params(self, new_params):
        """Atualiza parâmetros avançados de IA"""
        try:
            self.settings['AI_PARAMS']['advanced'].update(new_params)
            return self.save_settings()
        except (KeyError, TypeError):  # Adicionar TypeError para o caso de self.settings['AI_PARAMS'] não ser um dict
            self.logger.error("Seção 'AI_PARAMS' ou 'advanced' não encontrada.")
            return False
        except Exception as e:  # Captura outras exceções de save_settings
            self.logger.error(f"Erro ao atualizar parâmetros avançados: {e}")
            return False

    def get_setting(self, section, key, default=None):
        """Obtém uma configuração específica com valor padrão"""
        try:
            return self.settings[section][key]
        except (KeyError, TypeError):
            return default

    def update_setting(self, section, key, value):
        """Atualiza uma configuração específica"""
        try:
            if section not in self.settings:
                self.settings[section] = {}
            self.settings[section][key] = value
            return self.save_settings(self.settings)  # Passar o self.settings atualizado para save_settings
        except Exception as e:
            self.logger.error(f"Erro ao atualizar configuração: {e}")
            return False
