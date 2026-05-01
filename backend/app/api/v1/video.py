from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
import cv2
import asyncio
from backend.app.services.model_worker import get_model_worker

router = APIRouter()

@router.get("/feed")
async def video_feed(worker=Depends(get_model_worker)):
    """
    Video streaming route (MJPEG).
    """
    async def frame_generator():
        while True:
            frame = None
            with worker.frame_lock:
                if worker.frame_container[0] is not None:
                    # Fazemos uma cópia para não prender o lock durante a codificação
                    frame = worker.frame_container[0].copy()
            
            if frame is not None:
                # Redimensionar se for muito grande (opcional, para economizar banda)
                h, w = frame.shape[:2]
                if w > 1280:
                    scale = 1280 / w
                    frame = cv2.resize(frame, (1280, int(h * scale)), interpolation=cv2.INTER_AREA)
                
                ret, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
                if ret:
                    yield (b'--frame\r\n'
                           b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')
            
            # Controle de FPS do stream (aprox. 15 FPS)
            await asyncio.sleep(0.06)

    return StreamingResponse(frame_generator(), media_type="multipart/x-mixed-replace; boundary=frame")
