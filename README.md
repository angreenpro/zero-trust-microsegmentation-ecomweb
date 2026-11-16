# Zero Trust Micro-segmentation Demo

Đề tài nghiên cứu **Zero Trust Architecture (ZTA)** & **Micro-segmentation** trên ứng dụng Web bán hàng kiến trúc **Microservices**. Hệ thống áp dụng **PEP Gateway**, **Least Privilege ở tầng Database**, xác thực **JWT**, kết hợp cô lập 7 phân vùng mạng điểm–tới–điểm (`internal: true`) để chặn tấn công **Lateral Movement** và tự động cô lập vùng bị xâm nhập.

---

## Hướng dẫn Chạy Dự án & Kiểm thử Tự động

### Yêu cầu môi trường
- **Docker Desktop** (trên Windows/macOS) hoặc **Docker Engine** (trên Linux).
- **Python 3.8+** (để chạy script kiểm thử tự động trong thư mục `tests/`).

---

### Khởi động cụm Container bằng Docker Compose

1. Mở ứng dụng **Docker Desktop** và đợi trạng thái góc dưới bên trái báo **Engine running** (màu xanh).
2. Mở Terminal (PowerShell hoặc CMD) tại thư mục gốc của dự án và chạy lệnh:

```powershell
# Khởi tạo và chạy ngầm 5 containers + 7 phân đoạn mạng Micro-segmentation
docker-compose up -d --build
```
*(Nếu máy bạn dùng Docker Compose V2 dạng plugin, có thể gõ `docker compose up -d --build`).*

3. Kiểm tra trạng thái các container (đợi khoảng 15–20 giây lần đầu để `mysql-db` nạp dữ liệu và báo `healthy`):

```powershell
docker ps
```

4. Mở trình duyệt truy cập giao diện Web bán hàng tại:
   **[http://localhost:8086](http://localhost:8086)**
   - **Tài khoản khách hàng**: `customer1` / `Customer@123`
   - **Tài khoản quản trị**: `admin` / `Admin@123`

---

### Các lệnh Quản lý & Khắc phục sự cố thường gặp

- **Khởi động lại toàn bộ và nạp lại Database gốc (`init.sql`) từ đầu**:
  ```powershell
  docker-compose down -v
  docker-compose up -d --build
  ```
- **Xem log của một service cụ thể (ví dụ xem lỗi MySQL chặn SQLi ở `catalog-service`)**:
  ```powershell
  docker logs --tail 50 catalog-service
  ```
- **Tắt hệ thống khi không sử dụng**:
  ```powershell
  docker-compose down
  ```
