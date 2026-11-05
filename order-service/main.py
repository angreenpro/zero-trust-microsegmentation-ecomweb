"""
order-service (Cổng 8003) - Ngày 4
Application Zone 2 (High-Value Asset) trong lab ZTA: chứa dữ liệu giao dịch
nhạy cảm, cần cô lập nghiêm ngặt. Mọi request bắt buộc có JWT hợp lệ.
Dùng tài khoản MySQL order_user: đọc/ghi orders, order_items; SELECT products
và chỉ UPDATE được cột stock (Least Privilege từ Ngày 1).
"""
import os
import mysql.connector
import jwt
from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List

app = FastAPI(title="order-service")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "mysql-db"),
    "port": int(os.getenv("DB_PORT", "3306")),
    "user": os.getenv("DB_USER", "order_user"),
    "password": os.getenv("DB_PASSWORD", "Order#Lab2026"),
    "database": os.getenv("DB_NAME", "ecommerce"),
}

# PHẢI giống hệt JWT_SECRET của auth-service, vì order-service tự giải mã JWT
# chứ không gọi sang auth-service (giảm phụ thuộc Đông-Tây không cần thiết).
JWT_SECRET = os.getenv("JWT_SECRET", "zta-lab-super-secret-change-me")
JWT_ALGORITHM = "HS256"


def get_connection():
    return mysql.connector.connect(**DB_CONFIG)


def require_user(authorization: str = Header(None)):
    """
    *** CÀI CẮM CHO ZTA ***
    Middleware kiểm tra header Authorization: Bearer <JWT>. Trong Zero Trust,
    địa chỉ IP nguồn (kể cả từ container nội bộ cùng mạng) không được tin
    tưởng tuyệt đối - mọi request đều phải mang định danh hợp lệ.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Thiếu hoặc sai định dạng header Authorization")
    token = authorization.split(" ", 1)[1]
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token đã hết hạn")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Token không hợp lệ")
    return payload


class OrderItemIn(BaseModel):
    product_id: int
    quantity: int


class OrderIn(BaseModel):
    items: List[OrderItemIn]


@app.get("/health")
def health():
    return {"status": "ok", "service": "order-service"}


@app.post("/api/orders")
def create_order(order: OrderIn, authorization: str = Header(None)):
    payload = require_user(authorization)
    user_id = payload["user_id"]

    if not order.items:
        raise HTTPException(status_code=400, detail="Đơn hàng không có sản phẩm")

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        conn.start_transaction()

        total_price = 0.0
        checked_items = []
        for item in order.items:
            # Khóa dòng để tránh 2 request cùng lúc trừ tồn kho chồng nhau (race condition)
            cursor.execute(
                "SELECT id, price, stock FROM products WHERE id = %s FOR UPDATE",
                (item.product_id,),
            )
            product = cursor.fetchone()
            if not product:
                raise HTTPException(status_code=404, detail=f"Sản phẩm id={item.product_id} không tồn tại")
            if product["stock"] < item.quantity:
                raise HTTPException(
                    status_code=400,
                    detail=f"Sản phẩm id={item.product_id} không đủ tồn kho (còn {product['stock']})",
                )
            unit_price = float(product["price"])
            total_price += unit_price * item.quantity
            checked_items.append((item.product_id, item.quantity, unit_price))

        cursor.execute(
            "INSERT INTO orders (user_id, total_price, status) VALUES (%s, %s, 'paid')",
            (user_id, total_price),
        )
        order_id = cursor.lastrowid

        for product_id, quantity, unit_price in checked_items:
            cursor.execute(
                "INSERT INTO order_items (order_id, product_id, quantity, unit_price) VALUES (%s, %s, %s, %s)",
                (order_id, product_id, quantity, unit_price),
            )
            cursor.execute(
                "UPDATE products SET stock = stock - %s WHERE id = %s",
                (quantity, product_id),
            )

        conn.commit()
        return {"order_id": order_id, "total_price": total_price, "status": "paid"}

    except HTTPException:
        conn.rollback()
        raise
    except mysql.connector.Error as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Lỗi cơ sở dữ liệu: {e}")
    finally:
        cursor.close()
        conn.close()


@app.get("/api/orders/my-orders")
def my_orders(authorization: str = Header(None)):
    payload = require_user(authorization)
    user_id = payload["user_id"]

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        "SELECT id, total_price, status, created_at FROM orders WHERE user_id = %s ORDER BY created_at DESC",
        (user_id,),
    )
    orders = cursor.fetchall()
    cursor.close()
    conn.close()
    return {"orders": orders}
