"""
order-service (Cổng 8003) - Application Zone 4
- Kết nối tới database riêng `order_db` (chứa bảng `orders` và `order_items`).
- Được cấp quyền đọc `ecommerce.products` và chỉ UPDATE được cột `stock` (không sửa được `price`).
- Hoàn toàn không có quyền truy cập vào `payment_db` (`user_wallets`, `payments`) hay `ecommerce.users`.
- Khi tạo đơn hàng:
  1. Lưu đơn vào `order_db.orders` ở trạng thái 'pending' và trừ tồn kho (`ecommerce.products.stock`).
  2. Gọi Đông-Tây (East-West) sang `payment-service` (Zone 5 - PCI-DSS) qua mạng riêng
     `order_payment_net` kèm Xác thực Kép (User JWT + X-Service-Key) để xử lý thanh toán.
"""
import json
import os
import urllib.error
import urllib.request
import mysql.connector
import jwt
from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional

app = FastAPI(title="order-service")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "mysql-db"),
    "port": int(os.getenv("DB_PORT", "3306")),
    "user": os.getenv("DB_USER", "order_user"),
    "password": os.getenv("DB_PASSWORD", "Order#Lab2026"),
    "database": os.getenv("DB_NAME", "order_db"),
    "charset": "utf8mb4",
    "use_unicode": True,
}

JWT_SECRET = os.getenv("JWT_SECRET", "zta-lab-super-secret-change-me")
JWT_ALGORITHM = "HS256"
PAYMENT_SERVICE_URL = os.getenv("PAYMENT_SERVICE_URL", "http://payment-service:8004")
INTERNAL_SERVICE_KEY = os.getenv("INTERNAL_SERVICE_KEY", "zta-internal-order-to-payment-key-2026")


def get_connection():
    return mysql.connector.connect(**DB_CONFIG)


def require_user(authorization: Optional[str] = Header(None)):
    """
    *** CÀI CẮM CHO ZTA ***
    Middleware kiểm tra header Authorization: Bearer <JWT>.
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


def call_payment_service(path: str, method: str, authorization: str, body: Optional[dict] = None) -> dict:
    """Gọi Đông-Tây sang payment-service qua phân đoạn mạng riêng order_payment_net."""
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(
        f"{PAYMENT_SERVICE_URL}{path}",
        data=data,
        method=method,
        headers={
            "Content-Type": "application/json",
            "Authorization": authorization,
            "X-Service-Key": INTERNAL_SERVICE_KEY,
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", "replace")
        try:
            detail = json.loads(err_body).get("detail", err_body)
        except Exception:
            detail = err_body
        raise HTTPException(status_code=e.code, detail=f"Payment Service từ chối: {detail}")
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Không thể kết nối tới payment-service: {e}")


class OrderItemIn(BaseModel):
    product_id: int
    quantity: int


class OrderIn(BaseModel):
    items: List[OrderItemIn]
    payment_method: str = "credit_card"
    card_number: Optional[str] = "4111222233334242"


@app.get("/health")
def health():
    return {"status": "ok", "service": "order-service", "database": DB_CONFIG["database"]}


@app.post("/api/orders")
def create_order(order: OrderIn, authorization: Optional[str] = Header(None)):
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
            cursor.execute(
                "SELECT id, price, stock FROM ecommerce.products WHERE id = %s FOR UPDATE",
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

        # Bước 1: Tạo đơn ở trạng thái 'pending' trong order_db.orders
        cursor.execute(
            """
            INSERT INTO orders (user_id, total_price, status)
            VALUES (%s, %s, 'pending')
            """,
            (user_id, total_price),
        )
        order_id = cursor.lastrowid

        for product_id, quantity, unit_price in checked_items:
            cursor.execute(
                "INSERT INTO order_items (order_id, product_id, quantity, unit_price) VALUES (%s, %s, %s, %s)",
                (order_id, product_id, quantity, unit_price),
            )
            cursor.execute(
                "UPDATE ecommerce.products SET stock = stock - %s WHERE id = %s",
                (quantity, product_id),
            )

        conn.commit()
    except HTTPException:
        conn.rollback()
        raise
    except mysql.connector.Error as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Lỗi cơ sở dữ liệu: {e}")
    finally:
        cursor.close()
        conn.close()

    # Bước 2: Gọi Đông-Tây sang payment-service qua mạng cô lập order_payment_net
    payment_info = call_payment_service(
        path="/api/payments/charge",
        method="POST",
        authorization=authorization,
        body={
            "order_id": order_id,
            "amount": total_price,
            "payment_method": order.payment_method,
            "card_number": order.card_number,
        },
    )

    return {
        "order_id": order_id,
        "total_price": total_price,
        "status": "paid",
        "payment": payment_info,
    }


@app.get("/api/orders/my-orders")
def my_orders(authorization: Optional[str] = Header(None)):
    payload = require_user(authorization)
    user_id = payload["user_id"]

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute(
            """
            SELECT id, total_price, status, created_at
            FROM orders
            WHERE user_id = %s
            ORDER BY created_at DESC
            """,
            (user_id,),
        )
        orders = cursor.fetchall()
        return {"orders": orders}
    finally:
        cursor.close()
        conn.close()


@app.get("/api/orders/wallet")
def get_user_wallet(authorization: Optional[str] = Header(None)):
    """Truy vấn thông tin Ví & Thẻ của người dùng từ payment-service (payment_db) qua luồng Đông-Tây."""
    require_user(authorization)
    return call_payment_service(
        path="/api/payments/wallet",
        method="GET",
        authorization=authorization,
    )


@app.get("/api/orders/{order_id}/payment")
def get_order_payment(order_id: int, authorization: Optional[str] = Header(None)):
    """Tra cứu biên lai thanh toán từ payment-service (payment_db) qua luồng Đông-Tây."""
    require_user(authorization)
    return call_payment_service(
        path=f"/api/payments/order/{order_id}",
        method="GET",
        authorization=authorization,
    )
