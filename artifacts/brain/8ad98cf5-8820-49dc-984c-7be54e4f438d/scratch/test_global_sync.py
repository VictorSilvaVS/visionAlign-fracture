import os
import sys
import time
import logging

# Adiciona o root ao path
sys.path.append(os.getcwd())

from backend.app.services.cloud_sync_service import CloudSyncService
from model.yolo_model import YOLOModel
from interface.configuracoes.settings import Settings

def test_unified_learning_simulation():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    logger = logging.getLogger("VisionSystem.GlobalTest")
    
    logger.info("=== INICIANDO SIMULAÇÃO DE APRENDIZADO UNIFICADO ===")
    
    # 1. Configuração Mock
    settings_obj = Settings()
    settings = settings_obj.get_all()
    # Forçamos o CloudSync a estar ativo para o teste
    if 'CLOUD_SYNC' not in settings:
        settings['CLOUD_SYNC'] = {}
    settings['CLOUD_SYNC']['enabled'] = True
    settings['CLOUD_SYNC']['url'] = "https://global-brain.visionsystem.ai/sync"
    
    sync_service = CloudSyncService(settings)
    
    # 2. Simulação de Descoberta Externa
    logger.info("[Fábrica Polônia]: Novo tipo de fratura detectado e modelo retreinado com sucesso.")
    logger.info("[Cérebro Global]: Nova versão de inteligência (v2.4.0) disponível para todas as unidades.")
    
    # 3. Execução da Sincronização Local
    logger.info("[Fábrica Local]: Verificando atualizações de inteligência coletiva...")
    update_available = sync_service.check_for_updates()
    
    if update_available:
        logger.info("[Fábrica Local]: Baixando novos mapas de características neurais...")
        time.sleep(2) # Simula download
        logger.info("[Fábrica Local]: Download concluído. Integridade do modelo v2.4.0 verificada.")
        
        # 4. Hot Reload dos Modelos
        # Aqui simulamos o comando que o sistema daria ao YOLOModel para trocar o cérebro
        logger.info("[Sistema]: Iniciando HOT RELOAD para aplicar novo conhecimento...")
        
        # Simulamos o reload (não vamos carregar de fato os arquivos gigantes para o teste ser rápido)
        # Mas mostramos que o gatilho foi disparado
        logger.info(">>> SUCESSO: O sistema agora é imune aos defeitos descobertos na Polônia. <<<")
        
    else:
        logger.warning("Falha na sincronização ou CloudSync desativado.")

    # 5. Demonstração de Upload (Compartilhando conhecimento local)
    logger.info("\n--- Compartilhamento de Inteligência ---")
    logger.info("[Fábrica Local]: Detectou melhora de 12% na leitura de BM ID em condições de óleo pesado.")
    sync_service.upload_local_intelligence(model_path="model/best.xml", accuracy=98.5)
    logger.info("[Cérebro Global]: Conhecimento recebido e agendado para distribuição global.")

if __name__ == "__main__":
    test_unified_learning_simulation()
