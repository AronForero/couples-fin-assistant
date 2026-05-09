import time
import logging
from fastapi import HTTPException, Request
import jwt
from config import JWT_SECRET

logger = logging.getLogger(__name__)

ALGORITHM = "HS256"
TOKEN_EXPIRY_DAYS = 30


def create_token(user: str) -> str:
    payload = {
        "sub": user,
        "iat": int(time.time()),
        "exp": int(time.time()) + TOKEN_EXPIRY_DAYS * 86400,
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=ALGORITHM)


def verify_token(token: str) -> dict:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expirado")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Token inválido")


def get_current_user(request: Request) -> str:
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Falta token de autorización")
    token = auth[7:]
    payload = verify_token(token)
    user = payload.get("sub")
    if user not in {"Aru", "Mon"}:
        raise HTTPException(status_code=401, detail="Usuario no válido")
    return user
