import sys
import os

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from interface.configuracoes.settings import Settings
from ultralytics import YOLO
import logging

def main():
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger("ExportTool")
    
    settings = Settings().get_all()
    model_path = settings.get('MODEL_PARAMS', {}).get('model_path', 'model/visionalign_v11s.pt')
    
    logger.info(f"Origem: {model_path}")
    logger.info("Iniciando exportação OpenVINO (Otimizado para Intel Xeon Gold)...")
    
    try:
        model = YOLO(model_path)
        # Exporta com suporte a INT8 para máxima velocidade em Xeon, ou FP16 para precisão/velocidade
        # int8=True quantiza, o que é ótimo para Xeon, mas pode perder precisão levemente.
        # Vamos sugerir o padrão openvino primeiro que já é muito rápido.
        path = model.export(format="openvino", imgsz=640, half=False)  
        
        logger.info(f"SUCESSO! Modelo exportado para: {path}")
        logger.info(f"Pasta criada: {path}")
        logger.info("O sistema detectará automaticamente esta pasta e usará aceleração AVX-512/OpenVINO.")
            
    except Exception as e:
        logger.error(f"Erro na exportação: {e}")
        logger.error("Certifique-se de ter instalado: pip install openvino loguru lapx")

if __name__ == "__main__":
    main()
