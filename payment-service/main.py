"""
payment-service (Cổng 8004) - Zone 5: Deep Internal Payment / PCI-DSS Zone
- Cô lập hoàn toàn khỏi cổng biên (nginx-gateway), catalog-service và auth-service.
- Chỉ nhận kết nối Đông-Tây (East-West) duy nhất từ order-service qua mạng order_payment_net.
- Áp dụng Xác thực Kép (Dual Zero-Trust Verification):
    1. Định danh dịch vụ gọi (Header X-Service-Key) chỉ order-service nắm giữ.
    2. Định danh người dùng cuối (Header Authorization: Bearer <JWT>).
- Dùng tài khoản MySQL payment_user (Least Privilege):
    + SELECT, INSERT trên bảng payments.
    + SELECT (id, user_id, total_price, status) và chỉ được UPDATE (status) trên bảng orders.
    + Hoàn toàn không đọc được bảng users hay products, không sửa được cột total_price.
"""
import os
import time
import uuid
import mysql.connector
import jwt
from fastapi import FastAPI, HTTPException, Header
from pydantic import BaseModel
from typing import Optional

app = FastAPI(title="payment-service")

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "mysql-db"),
    "port": int(os.getenv("DB_PORT", "3306")),
    "user": os.getenv("DB_USER", "payment_user"),
    "password": os.getenv("DB_PASSWORD", "Payment#Lab2026"),
    "database": os.getenv("DB_NAME", "ecommerce"),
    "charset": "utf8mb4",
    "use_unicode": True,
}

JWT_SECRET = os.getenv("JWT_SECRET", "zta-lab-super-secret-change-me")
JWT_ALGORITHM = "HS256"
INTERNAL_SERVICE_KEY = os.getenv("INTERNAL_SERVICE_KEY", "zta-internal-order-to-payment-key-2026")


def get_connection():
    return mysql.connector.connect(**DB_CONFIG)


def verify_dual_identity(
    authorization: Optional[str] = Header(None),
    x_service_key: Optional[str] = Header(None),
):
    """
    *** CÀI CẮM CHO ZERO TRUST ĐÔNG-TÂY (EAST-WEST DUAL VERIFICATION) ***
    1. Kiểm tra X-Service-Key để xác nhận gói tin đến từ order-service hợp lệ.
    2. Kiểm tra JWT của người dùng để chống giả mạo định danh hoặc thanh toán chéo (IDOR).
    """
    if not x_service_key or x_service_key != INTERNAL_SERVICE_KEY:
        raise HTTPException(
            status_code=403,
            detail="Từ chối truy cập Đông-Tây: Thiếu hoặc sai X-Service-Key nội bộ",
        )

    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Thiếu hoặc sai định dạng header Authorization (User JWT)",
        )
    token = authorization.split(" ", 1)[1]
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token người dùng đã hết hạn")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Token người dùng không hợp lệ")
    return payload


def mask_card(card_number: Optional[str], method: str) -> str:
    if method == "cod":
        return "COD-CASH"
    if method == "vietqr":
        return "VIETQR-NAPAS"
    digits = "".join(ch for ch in (card_number or "4111222233334242") if ch.isdigit())
    last4 = digits[-4:] if len(digits) >= 4 else "4242"
    return f"****-****-****-{last4}"


class ChargeRequest(BaseModel):
    order_id: int
    amount: float
    payment_method: str = "credit_card"
    card_number: Optional[str] = "4111222233334242"


@app.get("/health")
def health():
    return {"status": "ok", "service": "payment-service", "zone": "pci-dss-deep-internal"}


@app.post("/api/payments/charge")
def charge_order(
    req: ChargeRequest,
    authorization: Optional[str] = Header(None),
    x_service_key: Optional[str] = Header(None),
):
    payload = verify_dual_identity(authorization, x_service_key)
    user_id = payload["user_id"]

    method = req.payment_method if req.payment_method in ("credit_card", "vietqr", "cod") else "credit_card"
    card_masked = mask_card(req.card_number, method)

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        conn.start_transaction()

        # Chỉ đọc các cột mà payment_user được cấp quyền trên bảng orders
        cursor.execute(
            "SELECT id, user_id, total_price, status FROM orders WHERE id = %s FOR UPDATE",
            (req.order_id,),
        )
        order = cursor.fetchone()
        if not order:
            raise HTTPException(status_code=404, detail=f"Đơn hàng #{req.order_id} không tồn tại")

        if int(order["user_id"]) != int(user_id):
            raise HTTPException(
                status_code=403,
                detail="Vi phạm Zero Trust (IDOR): Không thể thanh toán đơn hàng của người dùng khác",
            )

        if order["status"] == "paid":
            raise HTTPException(status_code=400, detail=f"Đơn hàng #{req.order_id} đã được thanh toán trước đó")

        expected_amount = float(order["total_price"])
        if abs(expected_amount - float(req.amount)) > 0.01:
            raise HTTPException(
                status_code=400,
                detail=f"Số tiền thanh toán ({req.amount}) không khớp với tổng đơn hàng ({expected_amount})",
            )

        tx_ref = f"TX-{int(time.time())}-{req.order_id}-{uuid.uuid4().hex[:6].upper()}"

        cursor.execute(
            """
            INSERT INTO payments (order_id, user_id, amount, payment_method, card_masked, transaction_ref, status)
            VALUES (%s, %s, %s, %s, %s, %s, 'success')
            """,
            (req.order_id, user_id, expected_amount, method, card_masked, tx_ref),
        )
        payment_id = cursor.lastrowid

        # payment_user chỉ có quyền UPDATE(status) trên bảng orders
        cursor.execute(
            "UPDATE orders SET status = 'paid' WHERE id = %s",
            (req.order_id,),
        )

        conn.commit()
        return {
            "payment_id": payment_id,
            "order_id": req.order_id,
            "amount": expected_amount,
            "payment_method": method,
            "card_masked": card_masked,
            "transaction_ref": tx_ref,
            "status": "success",
        }
    except HTTPException:
        conn.rollback()
        raise
    except mysql.connector.Error as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Lỗi cơ sở dữ liệu tại payment-service: {e}")
    finally:
        cursor.close()
        conn.close()


@app.get("/api/payments/order/{order_id}")
def get_payment_by_order(
    order_id: int,
    authorization: Optional[str] = Header(None),
    x_service_key: Optional[str] = Header(None),
):
    payload = verify_dual_identity(authorization, x_service_key)
    user_id = payload["user_id"]

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute(
            """
            SELECT id, order_id, user_id, amount, payment_method, card_masked, transaction_ref, status, created_at
            FROM payments
            WHERE order_id = %s AND user_id = %s
            ORDER BY id DESC LIMIT 1
            """,
            (order_id, user_id),
        )
        payment = cursor.fetchone()
        if not payment:
            raise HTTPException(status_code=404, detail="Không tìm thấy giao dịch thanh toán")
        return {"payment": payment}
    finally:
        cursor.close()
        conn.close()

