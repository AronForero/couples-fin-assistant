import time
import logging
import bcrypt
from fastapi import HTTPException, Request
import jwt
from config import JWT_SECRET
import database

logger = logging.getLogger(__name__)

ALGORITHM = "HS256"
TOKEN_EXPIRY_DAYS = 30


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())


def create_token(user_id: int) -> str:
    payload = {
        "sub": str(user_id),
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


def get_current_user(request: Request) -> dict:
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Falta token de autorización")
    token = auth[7:]
    payload = verify_token(token)
    sub = payload.get("sub")

    if sub is not None:
        try:
            sub = int(sub)
        except (ValueError, TypeError):
            pass

    if isinstance(sub, int):
        user = database.get_user_by_id(sub)
    elif isinstance(sub, str):
        user = database.get_user_by_display_name(sub)
    else:
        user = None

    if not user:
        raise HTTPException(status_code=401, detail="Usuario no válido")
    return user
