"""
run_scenarios.py - Chạy tự động 4 kịch bản kiểm thử Zero Trust / Micro-segmentation.

Yêu cầu: cụm docker-compose đang chạy (nginx-gateway tại http://localhost:8086).
Chỉ dùng thư viện chuẩn của Python trên máy host; các phép thử bên trong
container được chạy qua `docker exec -i <container> python -`.

    python tests/run_scenarios.py            # chạy KB1 -> KB4
    python tests/run_scenarios.py --skip-kb4 # bỏ qua KB4 (không ngắt mạng catalog)
Kết quả in ra màn hình và lưu vào tests/results/report_<thời gian>.md
"""
import base64
import datetime
import hashlib
import hmac
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

sys.stdout.reconfigure(encoding="utf-8")

BASE = os.getenv("BASE_URL", "http://localhost:8086")
RESULTS = []  # (kịch bản, mô tả, kỳ vọng, thực tế, PASS/FAIL)


# ----------------------------------------------------------------------
# Tiện ích
# ----------------------------------------------------------------------
def http(method, path, body=None, headers=None, timeout=15):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")
    except Exception as e:  # timeout, connection refused...
        return 0, f"{type(e).__name__}: {e}"


def docker(*args, stdin=None, timeout=60):
    p = subprocess.run(["docker", *args], input=stdin, capture_output=True,
                       text=True, encoding="utf-8", errors="replace", timeout=timeout)
    return p.returncode, (p.stdout + p.stderr).strip()


def in_container(container, script, *args):
    """Chạy một đoạn Python bên trong container (đóng vai kẻ tấn công đã chiếm shell)."""
    _, out = docker("exec", "-i", container, "python", "-", *args, stdin=script)
    return out.strip()


def record(kb, desc, expected, actual, ok):
    status = "PASS" if ok else "FAIL"
    RESULTS.append((kb, desc, expected, actual, status))
    icon = "✅" if ok else "❌"
    print(f"  {icon} [{status}] {desc}\n       kỳ vọng : {expected}\n       thực tế : {actual}")


def short(text, n=160):
    text = " ".join(str(text).split())
    return text if len(text) <= n else text[:n] + "..."


def b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def forge_jwt(payload, secret=None, alg="HS256"):
    header = b64url(json.dumps({"alg": alg, "typ": "JWT"}).encode())
    body = b64url(json.dumps(payload).encode())
    if alg == "none":
        return f"{header}.{body}."
    sig = hmac.new(secret.encode(), f"{header}.{body}".encode(), hashlib.sha256).digest()
    return f"{header}.{body}.{b64url(sig)}"


TCP_PROBE = r'''
import socket, sys
host, port = sys.argv[1], int(sys.argv[2])
try:
    ip = socket.gethostbyname(host)
except Exception as e:
    print("DNS_FAIL", type(e).__name__, e); sys.exit(0)
s = socket.socket(); s.settimeout(3)
try:
    s.connect((ip, port)); print("CONNECTED", ip)
except Exception as e:
    print("BLOCKED", ip, type(e).__name__, e)
'''

SQL_PROBE = r'''
import os, sys, mysql.connector
c = mysql.connector.connect(host=os.environ["DB_HOST"], user=os.environ["DB_USER"],
                            password=os.environ["DB_PASSWORD"], database=os.environ["DB_NAME"])
cur = c.cursor()
try:
    cur.execute(sys.argv[1])
    if cur.with_rows:
        print("OK", cur.fetchall()[:3])
    else:
        print("OK rowcount=%d" % cur.rowcount)
    c.rollback()   # không để lại thay đổi
except mysql.connector.Error as e:
    print("DENIED", e.errno, e.msg)
'''

PORT_SCAN = r'''
import socket, sys, time
target = sys.argv[1]
ports = [21, 22, 23, 25, 53, 80, 110, 143, 443, 3306, 5432, 6379, 8001, 8002, 8003, 8080, 9200, 27017]
t0 = time.time(); opened = []
for p in ports:
    s = socket.socket(); s.settimeout(0.5)
    if s.connect_ex((target, p)) == 0:
        opened.append(p)
    s.close()
print("SCANNED=%d OPEN=%s ELAPSED_MS=%d" % (len(ports), opened, (time.time() - t0) * 1000))
'''


def login(username="customer1", password="Customer@123"):
    st, body = http("POST", "/api/auth/login", {"username": username, "password": password})
    token = None
    if st == 200:
        token = json.loads(body).get("access_token")
    return st, body, token


# ----------------------------------------------------------------------
# KB0: Kiểm tra hệ thống sẵn sàng
# ----------------------------------------------------------------------
def kb0():
    print("\n=== KB0: Kiểm tra hệ thống (baseline) ===")
    st, _ = http("GET", "/")
    record("KB0", "Trang web qua nginx-gateway", "200", st, st == 200)
    st, body = http("GET", "/api/products")
    n = len(json.loads(body).get("products", [])) if st == 200 else 0
    record("KB0", "GET /api/products (catalog-service)", "200, có sản phẩm", f"{st}, {n} sản phẩm", st == 200 and n > 0)
    st, body, token = login()
    record("KB0", "Đăng nhập customer1 (auth-service)", "200 + JWT", f"{st}, token={'có' if token else 'không'}", bool(token))
    return token


# ----------------------------------------------------------------------
# KB1: SQL Injection tại catalog-service + Least Privilege ở DB
# ----------------------------------------------------------------------
def kb1():
    print("\n=== KB1: SQL Injection tại Breach Point (catalog-service) ===")

    def search(q):
        st, body = http("GET", "/api/products/search?q=" + urllib.parse.quote(q))
        try:
            rows = json.loads(body).get("products", [])
        except Exception:
            rows = None
        return st, body, rows

    st, _, rows = search("Laptop")
    record("KB1", "Tìm kiếm hợp lệ q='Laptop'", "200, 1 kết quả", f"{st}, {len(rows or [])} kết quả", st == 200 and len(rows or []) == 1)

    st, _, rows = search("' OR '1'='1")
    record("KB1", "SQLi tautology q=\"' OR '1'='1\"", "200, trả về TẤT CẢ sản phẩm (lỗ hổng tồn tại)",
           f"{st}, {len(rows or [])} kết quả", st == 200 and len(rows or []) >= 10)

    st, _, rows = search("' UNION SELECT 1,current_user(),0,0,@@version-- ")
    leaked = rows[0] if rows else None
    record("KB1", "SQLi UNION đọc danh tính DB", "Lộ user DB = catalog_user (chứng minh khai thác được)",
           f"{st}, {short(leaked)}", st == 200 and leaked and "catalog_user" in str(leaked))

    st, _, rows = search("' UNION SELECT 1,table_name,0,0,table_schema FROM information_schema.tables WHERE table_schema='ecommerce'-- ")
    tables = sorted({r.get("name") for r in rows or []} - {None})
    tables = [t for t in tables if t in ("users", "products", "orders", "order_items")]
    record("KB1", "SQLi liệt kê bảng qua information_schema", "Chỉ thấy bảng 'products' (users/orders bị ẩn)",
           f"{st}, bảng nhìn thấy = {tables}", st == 200 and tables == ["products"])

    st, body, rows = search("' UNION SELECT id,username,password_hash,1,role FROM users-- ")
    record("KB1", "SQLi UNION đánh cắp bảng users", "Bị từ chối (HTTP 500), KHÔNG lộ username/password_hash",
           f"{st}, {short(body, 80)}", st != 200 and "password" not in body and "admin" not in body)

    _, logs = docker("logs", "--tail", "60", "catalog-service")
    denied = [l for l in logs.splitlines() if "1142" in l]
    record("KB1", "Log catalog-service ghi nhận MySQL từ chối", "Lỗi 1142 SELECT command denied ... table 'users'",
           short(denied[-1]) if denied else "không thấy lỗi 1142", bool(denied))


# ----------------------------------------------------------------------
# KB2: Lateral Movement từ catalog-service (đã bị chiếm quyền)
# ----------------------------------------------------------------------
def kb2():
    print("\n=== KB2: Lateral Movement & Egress từ catalog-service ===")
    cases = [
        ("order-service", 8003, "DNS_FAIL", "Gọi order-service theo tên (DNS)"),
        ("auth-service", 8001, "DNS_FAIL", "Gọi auth-service theo tên (DNS)"),
        ("172.28.3.10", 8003, "BLOCKED", "Gọi thẳng IP order-service (pep_order_net)"),
        ("172.28.13.10", 8003, "BLOCKED", "Gọi thẳng IP order-service (db_order_net)"),
        ("172.28.1.10", 8001, "BLOCKED", "Gọi thẳng IP auth-service (pep_auth_net)"),
        ("172.28.13.20", 3306, "BLOCKED", "Pivot qua IP mysql-db ở nhánh order (db_order_net)"),
        ("1.1.1.1", 80, "BLOCKED", "Kết nối ra Internet (egress / reverse shell)"),
        ("mysql-db", 3306, "CONNECTED", "Đối chứng: catalog -> mysql-db (luồng hợp lệ)"),
    ]
    for host, port, expect, desc in cases:
        out = in_container("catalog-service", TCP_PROBE, host, str(port))
        record("KB2", f"{desc} [{host}:{port}]", expect, short(out), out.startswith(expect))


# ----------------------------------------------------------------------
# KB3: JWT tại order-service + phân quyền mức cột ở DB
# ----------------------------------------------------------------------
def kb3(token):
    print("\n=== KB3: Xác thực JWT (order-service) & Column-level privilege ===")
    order = {"items": [{"product_id": 5, "quantity": 1}]}
    fake_payload = {"user_id": 1, "username": "admin", "role": "admin", "exp": int(time.time()) + 3600}
    cases = [
        ("Đặt hàng KHÔNG có JWT", None),
        ("Đặt hàng với chuỗi token rác", "abc.def.ghi"),
        ("Đặt hàng với JWT alg=none (bỏ chữ ký)", forge_jwt(fake_payload, alg="none")),
        ("Đặt hàng với JWT ký bằng secret của hacker", forge_jwt(fake_payload, secret="hacker-secret")),
        ("Đặt hàng với JWT đã hết hạn", forge_jwt({**fake_payload, "exp": int(time.time()) - 60},
                                                     secret="zta-lab-super-secret-change-me")),
    ]
    for desc, tok in cases:
        headers = {"Authorization": f"Bearer {tok}"} if tok else {}
        st, body = http("POST", "/api/orders", order, headers)
        record("KB3", desc, "401 Unauthorized", f"{st}, {short(body, 70)}", st == 401)

    if token:
        st, body = http("POST", "/api/orders", order, {"Authorization": f"Bearer {token}"})
        record("KB3", "Đối chứng: đặt hàng với JWT hợp lệ", "200 + order_id", f"{st}, {short(body, 70)}", st == 200)
        st, body = http("GET", "/api/orders/my-orders", headers={"Authorization": f"Bearer {token}"})
        record("KB3", "Đối chứng: xem đơn hàng của tôi", "200", f"{st}, {short(body, 70)}", st == 200)

    sql_cases = [
        ("order-service", "UPDATE products SET price = 0 WHERE id = 1", "DENIED 1143", "order_user sửa GIÁ sản phẩm"),
        ("order-service", "SELECT username, password_hash FROM users", "DENIED 1142", "order_user đọc bảng users"),
        ("order-service", "UPDATE products SET stock = stock WHERE id = 1", "OK", "Đối chứng: order_user sửa cột stock"),
        ("catalog-service", "UPDATE products SET price = 0 WHERE id = 1", "DENIED 1142", "catalog_user sửa bảng products"),
        ("catalog-service", "DELETE FROM orders", "DENIED 1142", "catalog_user xóa bảng orders"),
    ]
    for container, sql, expect, desc in sql_cases:
        out = in_container(container, SQL_PROBE, sql)
        record("KB3", desc, expect, short(out), out.startswith(expect))


# ----------------------------------------------------------------------
# KB4: Port scan -> phát hiện -> cô lập catalog-service -> kiểm tra tính liên tục
# (Phần phát hiện dùng luật ngưỡng đơn giản, thay chỗ cho AI Node sẽ xây sau)
# ----------------------------------------------------------------------
def kb4(token):
    print("\n=== KB4: Port scan -> Phát hiện -> Cô lập catalog-service ===")
    _, raw = docker("inspect", "-f", "{{json .NetworkSettings.Networks}}", "catalog-service")
    nets = {name: cfg.get("IPAMConfig", {}).get("IPv4Address") or cfg.get("IPAddress")
            for name, cfg in json.loads(raw).items()}

    out = in_container("catalog-service", PORT_SCAN, "172.28.12.20")
    scanned = int(out.split("SCANNED=")[1].split()[0]) if "SCANNED=" in out else 0
    record("KB4", "Attacker quét cổng mysql-db từ catalog-service", "Quét được nhiều cổng trong vài giây", short(out), scanned > 0)

    threshold = 10
    detected = scanned >= threshold
    record("KB4", f"Phát hiện (luật: >= {threshold} cổng đích khác nhau / cửa sổ)", "Gắn cờ tấn công",
           f"{scanned} cổng -> {'ATTACK' if detected else 'normal'}", detected)
    if not detected:
        return

    t0 = time.perf_counter()
    for net in nets:
        docker("network", "disconnect", net, "catalog-service")
    iso_ms = (time.perf_counter() - t0) * 1000
    _, raw2 = docker("inspect", "-f", "{{json .NetworkSettings.Networks}}", "catalog-service")
    remaining = list(json.loads(raw2).keys())
    record("KB4", "Cô lập: ngắt toàn bộ mạng của catalog-service", "Không còn network nào",
           f"còn lại={remaining}, thời gian={iso_ms:.0f} ms", remaining == [])

    try:
        st, body = http("GET", "/api/products", timeout=20)
        record("KB4", "Web: danh mục sản phẩm (vùng bị cô lập)", "Lỗi 502/504 (chỉ vùng này ngừng)", f"{st}, {short(body, 60)}", st in (0, 502, 504))
        st, _, tok = login()
        record("KB4", "Web: đăng nhập (auth-service) khi catalog bị cô lập", "200", st, st == 200)
        tok = tok or token
        st, body = http("POST", "/api/orders", {"items": [{"product_id": 2, "quantity": 1}]}, {"Authorization": f"Bearer {tok}"})
        record("KB4", "Web: thanh toán (order-service) khi catalog bị cô lập", "200", f"{st}, {short(body, 60)}", st == 200)
        st, _ = http("GET", "/api/orders/my-orders", headers={"Authorization": f"Bearer {tok}"})
        record("KB4", "Web: xem đơn hàng khi catalog bị cô lập", "200", st, st == 200)
    finally:
        for net, ip in nets.items():
            args = ["network", "connect"] + (["--ip", ip] if ip else []) + [net, "catalog-service"]
            docker(*args)
        time.sleep(2)
        st, _ = http("GET", "/api/products")
        record("KB4", "Khôi phục: nối lại mạng catalog-service", "200", st, st == 200)


# ----------------------------------------------------------------------
def write_report():
    os.makedirs(os.path.join(os.path.dirname(__file__), "results"), exist_ok=True)
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(os.path.dirname(__file__), "results", f"report_{stamp}.md")
    passed = sum(1 for r in RESULTS if r[4] == "PASS")
    with open(path, "w", encoding="utf-8") as f:
        f.write(f"# Kết quả kiểm thử Zero Trust - {stamp}\n\n")
        f.write(f"**Tổng: {passed}/{len(RESULTS)} PASS** — Base URL: `{BASE}`\n\n")
        f.write("| KB | Phép thử | Kỳ vọng | Thực tế | Kết quả |\n|---|---|---|---|---|\n")
        for kb, desc, exp, act, st in RESULTS:
            act = str(act).replace("|", "\\|")
            f.write(f"| {kb} | {desc} | {exp} | `{act}` | {'✅' if st == 'PASS' else '❌'} {st} |\n")
    return path, passed


def main():
    args = {a.lower() for a in sys.argv[1:]}
    selected = args & {"kb0", "kb1", "kb2", "kb3", "kb4"}

    token = kb0()
    if not selected or "kb1" in selected:
        kb1()
    if not selected or "kb2" in selected:
        kb2()
    if not selected or "kb3" in selected:
        kb3(token)
    if (not selected and "--skip-kb4" not in args) or "kb4" in selected:
        kb4(token)
    path, passed = write_report()
    print(f"\n===== TỔNG KẾT: {passed}/{len(RESULTS)} PASS =====")
    print(f"Báo cáo: {path}")
    sys.exit(0 if passed == len(RESULTS) else 1)


if __name__ == "__main__":
    main()

