from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    PROJECT_NAME: str = "VisionAlign"
    API_V1_STR: str = "/api/v1"
    SECRET_KEY: str = "sua-chave-secreta-aqui" # Em produção, use uma variável de ambiente
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 8  # 8 dias
    
    # Configurações do Banco de Dados
    DATABASE_PATH: str = "data/users.db"
    
    # Configurações de Segurança
    KEY_FILE: str = "config/server_security.key"
    
    class Config:
        case_sensitive = True
        env_file = ".env"

settings = Settings()
