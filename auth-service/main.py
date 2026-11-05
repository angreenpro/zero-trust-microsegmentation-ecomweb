"""
auth-service (Cổng 8001) - Ngày 3
Identity Provider của bài lab ZTA: cấp và xác thực JWT. Mọi request nhạy cảm
(ví dụ sang order-service) đều phải mang theo JWT do service này ký.
Dùng tài khoản MySQL auth_user: chỉ SELECT + INSERT trên bảng users.
"""
import os
import datetime
import mysql.connector
import jwt
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from passlib.context import CryptContext

app = FastAPI(title="auth-service")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "mysql-db"),
    "port": int(os.getenv("DB_PORT", "3306")),
    "user": os.getenv("DB_USER", "auth_user"),
    "password": os.getenv("DB_PASSWORD", "Auth#Lab2026"),
    "database": os.getenv("DB_NAME", "ecommerce"),
}

# Trong lab để hardcode theo biến môi trường; thực tế nên dùng secret manager.
JWT_SECRET = os.getenv("JWT_SECRET", "zta-lab-super-secret-change-me")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "60"))

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def get_connection():
    return mysql.connector.connect(**DB_CONFIG)


class LoginRequest(BaseModel):
    username: str
    password: str


@app.get("/health")
def health():
    return {"status": "ok", "service": "auth-service"}


@app.post("/api/auth/login")
def login(req: LoginRequest):
    """Đối chiếu username/password với bảng users, trả về JWT nếu đúng."""
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        "SELECT id, username, password_hash, role FROM users WHERE username = %s",
        (req.username,),
    )
    user = cursor.fetchone()
    cursor.close()
    conn.close()

    if not user or not pwd_context.verify(req.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Sai username hoặc password")

    now = datetime.datetime.now(datetime.timezone.utc)
    payload = {
        "user_id": user["id"],
        "username": user["username"],
        "role": user["role"],
        "iat": now,
        "exp": now + datetime.timedelta(minutes=JWT_EXPIRE_MINUTES),
    }
    token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
    return {"access_token": token, "token_type": "bearer", "role": user["role"]}


@app.get("/api/auth/verify")
def verify(token: str):
    """Xác nhận JWT còn hợp lệ hay không. Các service khác (order-service) gọi
    nội bộ hàm giải mã này bằng cùng JWT_SECRET, không nhất thiết phải gọi qua HTTP."""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return {"valid": True, "payload": payload}
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token đã hết hạn")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Token không hợp lệ")
