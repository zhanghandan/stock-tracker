"""
FastAPI 鉴权依赖
"""
from fastapi import HTTPException, Request, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from backend.auth.jwt_utils import verify_token

security = HTTPBearer(auto_error=False)


async def get_current_user(request: Request):
    """获取当前登录用户，未登录则返回None"""
    token = request.cookies.get("token")
    if not token:
        # 尝试从 Authorization header 获取
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]

    if not token:
        return None

    payload = verify_token(token)
    if payload:
        return {"phone": payload["phone"], "user_id": payload["user_id"]}

    return None


async def require_auth(user=Depends(get_current_user)):
    """要求必须登录，否则返回401"""
    if user is None:
        raise HTTPException(status_code=401, detail="请先登录")
    return user
