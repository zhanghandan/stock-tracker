"""
JWT Token 工具
"""
import os
import time
import jwt

JWT_SECRET = os.getenv("JWT_SECRET", "stock-tracker-secret-change-me")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_SECONDS = 7 * 24 * 3600  # 7天


def create_token(phone: str, user_id: int) -> str:
    """生成JWT token"""
    payload = {
        "phone": phone,
        "user_id": user_id,
        "iat": int(time.time()),
        "exp": int(time.time()) + JWT_EXPIRE_SECONDS,
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def verify_token(token: str) -> dict | None:
    """验证JWT token，返回payload或None"""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None
