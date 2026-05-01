from fastapi import FastAPI, Depends, HTTPException, status, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from typing import List
import logging
import os
import sys
from pathlib import Path

# Adicionar o diretório raiz ao path para importar módulos existentes
BASE_DIR = Path(__file__).parent.parent.parent
sys.path.append(str(BASE_DIR))

from backend.app.api.v1 import auth, stats, video, settings as settings_router, training
from backend.app.core.config import settings
from backend.app.services.model_worker import get_model_worker

app = FastAPI(
    title="VisionAlign API",
    description="API Industrial para o Sistema de Inspeção VisionAlign",
    version="2.0.0",
)

# Configuração de Caminhos da Interface
TEMPLATES_DIR = BASE_DIR / "interface" / "flask" / "templates"
STATIC_DIR = BASE_DIR / "interface" / "flask" / "static"

# Montar arquivos estáticos
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# Configurar Templates
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
templates.env.auto_reload = True

@app.on_event("startup")
async def startup_event():
    setup_sse_logging()
    worker = get_model_worker()
    source_type = worker.settings.get('VIDEO_PARAMS', {}).get('source_type', 'stream')
    source_param = worker.settings.get('VIDEO_PARAMS', {}).get('source_param', '')
    worker.start(source_type=source_type, source_param=source_param)

@app.on_event("shutdown")
async def shutdown_event():
    worker = get_model_worker()
    worker.stop()

# Configuração de CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Inclusão dos roteadores
app.include_router(auth.router, prefix="/api/v1/auth", tags=["Autenticação"])
app.include_router(stats.router, prefix="/api/v1/stats", tags=["Estatísticas"])
app.include_router(video.router, prefix="/api/v1/video", tags=["Vídeo"])
app.include_router(settings_router.router, prefix="/api/v1/settings", tags=["Configurações"])
app.include_router(training.router, prefix="/api/v1/training", tags=["Treinamento AI"])

@app.get("/console_stream")
async def console_stream():
    """Stream de logs para o console de treinamento (SSE)."""
    async def log_generator():
        queue = asyncio.Queue()
        sse_handler.add_queue(queue)
        try:
            while True:
                log_line = await queue.get()
                yield f"data: {log_line}\n\n"
        except asyncio.CancelledError:
            sse_handler.remove_queue(queue)

    return StreamingResponse(log_generator(), media_type="text/event-stream")

# Rotas de Interface (Frontend)
@app.get("/", response_class=HTMLResponse, name="index")
async def index(request: Request):
    return templates.TemplateResponse("index.html", {
        "request": request, 
        "current_user": {"username": "Operador", "role": "admin", "is_authenticated": True},
        "now": lambda: __import__('datetime').datetime.now()
    })

@app.get("/login", response_class=HTMLResponse, name="login_page")
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request, "error": None, "last_username": None, "duplicate_session_info": None})

@app.get("/logout", response_class=HTMLResponse, name="logout")
async def logout(request: Request):
    return templates.TemplateResponse("login.html", {"request": request, "error": None, "last_username": None, "duplicate_session_info": None})

@app.get("/forgot-password", response_class=HTMLResponse, name="forgot_password")
async def forgot_password(request: Request):
    return templates.TemplateResponse("login.html", {"request": request, "error": "Recuperação de senha não implementada.", "last_username": None, "duplicate_session_info": None})

@app.post("/api/register", name="api_register")
async def api_register(request: Request):
    return {"success": False, "message": "Registro desativado nesta versão de migração."}

@app.get("/analytics", response_class=HTMLResponse, name="analytics_page")
async def analytics_page(request: Request):
    return templates.TemplateResponse("analytics.html", {
        "request": request, 
        "current_user": {"username": "Operador", "role": "admin", "is_authenticated": True},
        "now": lambda: __import__('datetime').datetime.now()
    })

@app.get("/settings", response_class=HTMLResponse, name="settings_page")
async def settings_page(request: Request):
    return templates.TemplateResponse("settings.html", {
        "request": request, 
        "current_user": {"username": "Operador", "role": "admin", "is_authenticated": True},
        "now": lambda: __import__('datetime').datetime.now()
    })

@app.get("/users", response_class=HTMLResponse, name="users")
async def users(request: Request):
    return templates.TemplateResponse("users.html", {
        "request": request, 
        "current_user": {"username": "Operador", "role": "admin", "is_authenticated": True},
        "now": lambda: __import__('datetime').datetime.now()
    })

@app.get("/retrain", response_class=HTMLResponse, name="retrain_page")
async def retrain_page(request: Request):
    return templates.TemplateResponse("retrain.html", {
        "request": request, 
        "current_user": {"username": "Operador", "role": "admin", "is_authenticated": True},
        "now": lambda: __import__('datetime').datetime.now()
    })

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
