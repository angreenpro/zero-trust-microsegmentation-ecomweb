"""
catalog-service (Cổng 8002) - Ngày 2
Application Zone 1 (public-facing) - vùng rủi ro bị tấn công cao trong lab ZTA.
Dùng tài khoản MySQL catalog_user: CHỈ có quyền SELECT trên bảng products.
"""
import os
import mysql.connector
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="catalog-service")

# Nginx (Ngày 5) sẽ là điểm vào duy nhất; CORS mở ở đây chỉ để tiện test trực tiếp.
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "mysql-db"),
    "port": int(os.getenv("DB_PORT", "3306")),
    "user": os.getenv("DB_USER", "catalog_user"),
    "password": os.getenv("DB_PASSWORD", "Catalog#Lab2026"),
    "database": os.getenv("DB_NAME", "ecommerce"),
}


def get_connection():
    return mysql.connector.connect(**DB_CONFIG)


@app.get("/health")
def health():
    return {"status": "ok", "service": "catalog-service"}


@app.get("/api/products")
def list_products():
    """Lấy toàn bộ sản phẩm từ MySQL."""
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id, name, price, stock, image_url FROM products")
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return {"products": rows}


@app.get("/api/products/search")
def search_products(q: str = ""):
    """
    Tìm sản phẩm theo tên.

    *** CÀI CẮM CHO ZTA (Ngày 7) ***
    Câu lệnh dưới đây CỐ Ý nối chuỗi trực tiếp q vào SQL, tạo lỗ hổng
    SQL Injection. Đây là "cửa ngõ" để đóng vai hacker chiếm quyền container
    catalog-service trong bài lab Micro-segmentation / Lateral Movement.
    KHÔNG dùng mẫu này cho bất kỳ hệ thống thật nào ngoài bài lab.
    Bản vá an toàn (dùng tham số hóa) được để bên dưới dạng comment.
    """
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    query = f"SELECT id, name, price, stock, image_url FROM products WHERE name LIKE '%{q}%'"
    cursor.execute(query)

    # Bản vá an toàn (dùng khi báo cáo xong phần khai thác ở Ngày 7):
    # cursor.execute(
    #     "SELECT id, name, price, stock, image_url FROM products WHERE name LIKE %s",
    #     (f"%{q}%",),
    # )

    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return {"products": rows, "query": q}
