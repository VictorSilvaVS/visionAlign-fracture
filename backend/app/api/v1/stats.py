from fastapi import APIRouter, Depends
from typing import Any
from backend.app.services.model_worker import get_model_worker

router = APIRouter()

@router.get("/")
async def get_stats(worker=Depends(get_model_worker)) -> Any:
    """
    Retorna as estatísticas em tempo real do processamento de IA.
    """
    model = worker.get_model()
    stats = model.detection_stats.copy()
    
    return {
        "status": "Operacional" if model.processing else "Parado",
        "fps": round(model.fps, 1),
        "detections": {
            "normal": stats.get('lata_normal', 0),
            "inverted": stats.get('lata_invertida', 0),
            "fallen": stats.get('lata_tombada', 0),
            "fracture": stats.get('fracture', 0)
        },
        "system_info": {
            "model_version": model.settings.get('MODEL_PARAMS', {}).get('model_version', '1.0'),
            "device": "CPU (OpenVINO)"
        }
    }
