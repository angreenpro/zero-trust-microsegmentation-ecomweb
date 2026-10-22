# Zero Trust Micro-segmentation Demo

Đồ án nghiên cứu **Zero Trust Architecture (ZTA)** và **Micro-segmentation** trên một ứng dụng web bán hàng 3 lớp. Hệ thống dùng **mTLS** giữa các phân vùng và một **AI node** giám sát traffic để phát hiện, chặn tấn công **Lateral Movement** trong vòng dưới 3 giây.

## Mục tiêu

- Thiết kế mô hình mạng 4 phân vùng cô lập (Docker + Open vSwitch).
- Xác thực hai chiều **mTLS 1.3** giữa Web ↔ App ↔ DB bằng Root CA nội bộ.
- Giám sát thụ động qua cổng **OVS SPAN**, phân loại traffic bằng ML (Random Forest / Isolation Forest).
- Phản hồi khép kín: AI phát hiện → gọi API → `iptables DROP` IP tấn công.
- Đo độ trễ/throughput của web khi bật mTLS và SPAN.

## Kiến trúc

```
[Browser] ──HTTPS──▶ [Seg 1: Nginx Web   10.0.1.10]
                              │ mTLS
                              ▼
                     [Seg 2: Flask API   10.0.2.10]
                              │ mTLS
                              ▼
                     [Seg 3: PostgreSQL  10.0.3.10]

[Seg 4: AI Node 10.0.4.10] ◀── SPAN (passive) ── OVS br0
        │
        └── isolate command (iptables DROP)
```

| Phân vùng | Vai trò | Công nghệ |
|---|---|---|
| Seg 1 | Web server / DMZ | Nginx, HTML/CSS/JS thuần |
| Seg 2 | App server | Python, Flask, SQLAlchemy, JWT, bcrypt |
| Seg 3 | Database | PostgreSQL (SSL `verify-full`) |
| Seg 4 | AI & Security | NFStream, Scikit-learn, Scapy, Flask (host isolation) |

## Tính năng web bán hàng

- **Khách hàng**: xem/lọc/tìm sản phẩm, giỏ hàng, đặt hàng, thanh toán giả lập, đăng ký/đăng nhập, lịch sử đơn.
- **Admin**: dashboard thống kê, CRUD sản phẩm, quản lý đơn hàng và người dùng.

## Cài đặt nhanh

```bash
python -m venv venv
venv\Scripts\activate        # Windows
pip install -r requirements.txt
```
