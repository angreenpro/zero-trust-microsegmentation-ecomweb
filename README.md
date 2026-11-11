# Zero Trust Micro-segmentation Demo

Đề tài nghiên cứu **Zero Trust Architecture (ZTA)** & **Micro-segmentation** trên ứng dụng Web bán hàng kiến trúc **Microservices**. Hệ thống áp dụng **PEP Gateway**, **Least Privilege ở tầng Database**, xác thực **JWT**, kết hợp cô lập 7 phân vùng mạng điểm–tới–điểm (`internal: true`) để chặn tấn công **Lateral Movement** và tự động cô lập vùng bị xâm nhập.

---

## Hướng dẫn Chạy Dự án & Kiểm thử Tự động

### Yêu cầu môi trường
- **Docker Desktop** (trên Windows/macOS) hoặc **Docker Engine** (trên Linux).
- **Python 3.8+** (để chạy script kiểm thử tự động trong thư mục `tests/`).

---

### Bước 1: Khởi động cụm Container bằng Docker Compose

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

### Bước 2: Chạy Bộ Kịch bản Kiểm thử Bảo mật Zero Trust (`tests/`)

Dự án đi kèm bộ kiểm thử tự động gồm **37 phép thử** chia làm 5 giai đoạn (`KB0` $\to$ `KB4`). Bạn có thể chạy bằng **1 trong 3 cách** dưới đây:

#### Cách A: Chạy bằng Script tự động trên Windows PowerShell (Khuyên dùng)
Script [tests/run_tests.ps1](tests/run_tests.ps1) sẽ tự động kiểm tra Docker, tự bật container nếu chưa chạy, đợi Database sẵn sàng rồi thực thi kiểm thử:

```powershell
# Chạy toàn bộ từ KB0 -> KB4
.\tests\run_tests.ps1

# Hoặc nếu PowerShell trên máy bạn chặn quyền chạy file .ps1, hãy dùng lệnh:
powershell -ExecutionPolicy Bypass -File .\tests\run_tests.ps1
```

Khi thuyết trình demo từng phần, bạn có thể chạy lẻ từng kịch bản:
```powershell
.\tests\run_tests.ps1 kb1          # Chỉ chạy Kịch bản 1: SQL Injection & DB Least Privilege
.\tests\run_tests.ps1 kb2          # Chỉ chạy Kịch bản 2: Chặn Lateral Movement & Internet
.\tests\run_tests.ps1 kb3          # Chỉ chạy Kịch bản 3: Xác thực JWT & Phân quyền mức cột
.\tests\run_tests.ps1 kb4          # Chỉ chạy Kịch bản 4: Port Scan -> Cô lập động -> Khôi phục
.\tests\run_tests.ps1 --skip-kb4   # Chạy KB0 -> KB3 (không ngắt mạng catalog-service)
```

#### Cách B: Chạy trực tiếp bằng lệnh Python (Trên mọi Hệ điều hành)
Khi cụm Docker đã bật sẵn, bạn có thể gọi trực tiếp file [tests/run_scenarios.py](tests/run_scenarios.py) (không cần cài thêm thư viện ngoài):

```powershell
# Chạy toàn bộ 4 kịch bản
python tests/run_scenarios.py

# Chạy riêng từng kịch bản
python tests/run_scenarios.py kb1
python tests/run_scenarios.py kb2
python tests/run_scenarios.py kb3
python tests/run_scenarios.py kb4
```
*(Nếu muốn cài thêm các gói hỗ trợ kiểm thử mở rộng: `pip install -r tests/requirements.txt`).*

#### Cách C: Chạy trên Linux / WSL2 / Git Bash
```bash
bash tests/run_tests.sh
```

---

### Bước 3: Xem Báo cáo Kết quả Kiểm thử

Sau mỗi lần chạy kiểm thử, ngoài kết quả `[PASS]` / `[FAIL]` hiển thị trực tiếp trên màn hình Terminal, hệ thống tự động xuất một file báo cáo bảng Markdown chi tiết tại:
- `tests/results/report_<YYYYMMDD_HHMMSS>.md`

---

### Bước 4: Các lệnh Quản lý & Khắc phục sự cố thường gặp

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
