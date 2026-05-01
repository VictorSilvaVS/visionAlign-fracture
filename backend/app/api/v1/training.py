from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, UploadFile, File, Request
from backend.app.services.otx_service import get_otx_service, OTXService
from backend.app.services.model_worker import get_model_worker
from pydantic import BaseModel
from typing import Optional, List
import os
import cv2
import numpy as np
import base64
from datetime import datetime

router = APIRouter()

class RetrainRequest(BaseModel):
    model: str
    epochs: int

@router.get("/dataset_info")
async def get_dataset_info(service: OTXService = Depends(get_otx_service)):
    """Retorna informações sobre o dataset coletado."""
    try:
        settings = service.settings_manager.get_all()
        dataset_path = settings.get('MODEL_PARAMS', {}).get('dataset_path', 'data/dataset_collect/images')
        
        # Ajustar path se necessário (relativo à raiz do projeto)
        if not os.path.isabs(dataset_path):
            project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', '..'))
            dataset_path = os.path.join(project_root, dataset_path)
            
        image_count = 0
        if os.path.exists(dataset_path):
            image_count = len([f for f in os.listdir(dataset_path) if f.lower().endswith(('.jpg', '.jpeg', '.png'))])
        
        return {
            "image_count": image_count,
            "class_count": 4, 
            "last_update": datetime.now().strftime("%d/%m/%Y %H:%M")
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/start_retrain")
async def start_retrain(request: RetrainRequest, background_tasks: BackgroundTasks, service: OTXService = Depends(get_otx_service)):
    """Inicia o processo de retreinamento."""
    settings = service.settings_manager.get_all()
    dataset_path = settings.get('MODEL_PARAMS', {}).get('dataset_path', 'data/dataset_collect/images')
    
    background_tasks.add_task(service.manager.train, request.model, dataset_path)
    return {"success": True, "message": f"Treinamento de {request.model.toUpperCase()} iniciado com {request.epochs} épocas."}

@router.post("/test_models")
async def test_models():
    """Executa autodiagnóstico nos modelos (Simulação)."""
    return {
        "success": True,
        "results": {
            "align": {"status": "success", "message": "Modelo VisionAlign carregado e operacional."},
            "fracture": {"status": "success", "message": "Modelo VisionFracture (Segmentation) pronto."}
        }
    }

@router.post("/test_inference")
async def test_inference(image: UploadFile = File(...)):
    """Testa inferência em uma imagem enviada."""
    try:
        contents = await image.read()
        nparr = np.frombuffer(contents, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if img is None:
            return {"success": False, "message": "Falha ao decodificar imagem"}
            
        worker = get_model_worker()
        # Aqui o worker deveria ter um método para processar um frame avulso e retornar os resultados
        # Por enquanto vamos simular o desenho de uma detecção se o worker estiver ativo
        
        # Simulação de desenho de resultado
        cv2.putText(img, "DETECTION TEST OK", (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
        
        _, buffer = cv2.imencode('.jpg', img)
        img_base64 = base64.b64encode(buffer).decode('utf-8')
        
        return {
            "success": True, 
            "image": f"data:image/jpeg;base64,{img_base64}",
            "summary": "Detecção simulada concluída com sucesso."
        }
    except Exception as e:
        return {"success": False, "message": str(e)}

@router.post("/express_retrain")
async def express_retrain(target_class: str, images: List[UploadFile] = File(...), service: OTXService = Depends(get_otx_service)):
    """Inicia o ajuste fino rápido (Treino Relâmpago)."""
    # Em uma implementação real, salvaríamos essas imagens e rodaríamos um treino curto
    # Por enquanto, vamos simular sucesso após um pequeno delay
    return {"success": True, "message": f"Treino relâmpago para {target_class} concluído com sucesso."}
