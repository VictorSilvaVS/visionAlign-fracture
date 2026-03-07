import sys
import os

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from model.yolo_model import YOLOModel
from interface.configuracoes.settings import Settings
import logging

def main():
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger("ExportTool")
    
    settings = Settings().get_all()
    model_path = settings.get('MODEL_PARAMS', {}).get('model_path', 'model/visionalign_v11s.pt')
    
    logger.info(f"Carregando modelo de: {model_path}")
    
    try:
        # Initialize cleanly without starting processing
        model = YOLOModel(model_path, settings)
        
        logger.info("Iniciando exportação para ONNX (Otimizado para CPU/Unix)...")
        onnx_path = model.export_to_onnx()
        
        if onnx_path:
            logger.info(f"SUCESSO! Modelo exportado para: {onnx_path}")
            logger.info("A próxima vez que o sistema iniciar, ele usará automaticamente este arquivo .onnx para máxima performance.")
        else:
            logger.info("Exportação retornou None (talvez já exista?).")
            
    except Exception as e:
        logger.error(f"Falha na exportação: {e}")

if __name__ == "__main__":
    main()
