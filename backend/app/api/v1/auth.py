from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from typing import Any
from backend.app.db.session import get_db
from backend.app.core import security
from datetime import timedelta
from backend.app.core.config import settings

router = APIRouter()

@router.post("/login")
async def login(form_data: OAuth2PasswordRequestForm = Depends(), db=Depends(get_db)) -> Any:
    """
    OAuth2 compatible token login, get an access token for future requests
    """
    user = db.verify_user(form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuário ou senha incorretos",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    return {
        "access_token": security.create_access_token(
            user['username'], expires_delta=access_token_expires
        ),
        "token_type": "bearer",
        "user_info": {
            "username": user['username'],
            "role": "admin" if user['is_admin'] else "user",
            "first_name": user.get('first_name'),
            "last_name": user.get('last_name')
        }
    }

@router.post("/register")
async def register() -> Any:
    # Placeholder
    return {"message": "Endpoint de registro em construção"}
