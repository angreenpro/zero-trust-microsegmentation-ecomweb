-- =====================================================================
-- init.sql - Data Zone (MySQL Multi-Schema / Database-per-Service)
-- Kiến trúc Phương pháp 2:
--   1. Database `ecommerce`  : Chứa `users` (Auth) và `products` (Catalog)
--   2. Database `order_db`   : Chứa `orders` và `order_items` (Order Zone)
--   3. Database `payment_db` : Chứa `user_wallets` và `payments` (Payment PCI-DSS Zone)
-- =====================================================================

SET CHARACTER SET utf8mb4;
SET NAMES utf8mb4 COLLATE utf8mb4_unicode_ci;

-- ---------------------------------------------------------------------
-- 1. KHỞI TẠO 3 DATABASE ĐỘC LẬP (MULTI-SCHEMA ISOLATION)
-- ---------------------------------------------------------------------
CREATE DATABASE IF NOT EXISTS ecommerce
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

CREATE DATABASE IF NOT EXISTS order_db
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

CREATE DATABASE IF NOT EXISTS payment_db
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

-- ---------------------------------------------------------------------
-- 2. DATABASE 1: `ecommerce` (Dành cho auth-service & catalog-service)
-- ---------------------------------------------------------------------
USE ecommerce;

CREATE TABLE users (
  id            INT UNSIGNED NOT NULL AUTO_INCREMENT,
  username      VARCHAR(50)  NOT NULL,
  password_hash VARCHAR(255) NOT NULL,              -- bcrypt, KHÔNG lưu mật khẩu thô
  role          ENUM('admin','customer') NOT NULL DEFAULT 'customer',
  PRIMARY KEY (id),
  UNIQUE KEY uq_users_username (username)
) ENGINE=InnoDB;

CREATE TABLE products (
  id        INT UNSIGNED  NOT NULL AUTO_INCREMENT,
  name      VARCHAR(150)  NOT NULL,
  price     DECIMAL(12,2) NOT NULL,
  stock     INT UNSIGNED  NOT NULL DEFAULT 0,       -- UNSIGNED: không cho tồn kho âm
  image_url VARCHAR(255)  NULL,
  PRIMARY KEY (id),
  KEY idx_products_name (name),
  CONSTRAINT chk_products_price CHECK (price >= 0)
) ENGINE=InnoDB;

-- Mật khẩu (CHỈ DÙNG TRONG LAB):  admin / Admin@123   |   customer1 / Customer@123
INSERT INTO users (username, password_hash, role) VALUES
  ('admin',      '$2y$12$SO6Zas4mWVUH.pbHXZI7UetwuL02JrHZy67kenyTdAnuAGlo0tFAy', 'admin'),
  ('customer1',  '$2y$12$b31q7rKmePStwyPTFFdq..6X.22k5fhUYnW0bQxVgL7a4Yn8KgyMe', 'customer');

INSERT INTO products (name, price, stock, image_url) VALUES
  ('Laptop Dell Inspiron 15',        15990000.00, 25, '/images/laptop.jpg'),
  ('Điện thoại Samsung Galaxy A55',   9490000.00, 40, '/images/dienthoai.jpg'),
  ('Tai nghe Bluetooth Sony WH-1000', 6290000.00, 60, '/images/headphone.jpg'),
  ('Bàn phím cơ Keychron K2',         1890000.00, 80, '/images/keyboarf.jpg'),
  ('Chuột không dây Logitech MX',     1590000.00, 100,'/images/chuot.jpg'),
  ('Màn hình LG UltraGear 27"',       5790000.00, 30, '/images/manhinh.jpg'),
  ('Ổ cứng SSD Samsung 980 1TB',      2190000.00, 70, '/images/ssd.jpg'),
  ('Webcam Logitech C920',            1490000.00, 55, '/images/webcam.jpg'),
  ('Loa Bluetooth JBL Flip 6',        2790000.00, 45, '/images/loa.jpg'),
  ('Router WiFi TP-Link AX55',        1390000.00, 65, '/images/router.jpg');

-- ---------------------------------------------------------------------
-- 3. DATABASE 2: `order_db` (Dành riêng cho order-service)
-- ---------------------------------------------------------------------
USE order_db;

CREATE TABLE orders (
  id          INT UNSIGNED  NOT NULL AUTO_INCREMENT,
  user_id     INT UNSIGNED  NOT NULL,
  total_price DECIMAL(14,2) NOT NULL DEFAULT 0,
  status      ENUM('pending','paid','shipped','cancelled') NOT NULL DEFAULT 'pending',
  created_at  TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_orders_user (user_id)
) ENGINE=InnoDB;

CREATE TABLE order_items (
  id         INT UNSIGNED  NOT NULL AUTO_INCREMENT,
  order_id   INT UNSIGNED  NOT NULL,
  product_id INT UNSIGNED  NOT NULL,
  quantity   INT UNSIGNED  NOT NULL,
  unit_price DECIMAL(12,2) NOT NULL,                -- chốt giá tại thời điểm mua
  PRIMARY KEY (id),
  KEY idx_items_order (order_id),
  KEY idx_items_product (product_id),
  CONSTRAINT fk_items_order FOREIGN KEY (order_id) REFERENCES orders (id) ON DELETE CASCADE,
  CONSTRAINT chk_items_qty CHECK (quantity > 0)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- 4. DATABASE 3: `payment_db` (Dành riêng cho payment-service - PCI-DSS Zone)
-- ---------------------------------------------------------------------
USE payment_db;

CREATE TABLE user_wallets (
  id           INT UNSIGNED  NOT NULL AUTO_INCREMENT,
  user_id      INT UNSIGNED  NOT NULL,
  balance      DECIMAL(15,2) NOT NULL DEFAULT 0,   -- Số dư khả dụng (không âm)
  credit_limit DECIMAL(15,2) NOT NULL DEFAULT 0,   -- Hạn mức tín dụng được cấp
  card_holder  VARCHAR(100)  NOT NULL,
  card_masked  VARCHAR(30)   NOT NULL DEFAULT '****-****-****-4242',
  bank_name    VARCHAR(80)   NOT NULL DEFAULT 'Vietcombank Digibank',
  status       ENUM('active','locked') NOT NULL DEFAULT 'active',
  updated_at   TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uq_wallets_user (user_id),
  CONSTRAINT chk_wallets_balance CHECK (balance >= 0)
) ENGINE=InnoDB;

CREATE TABLE payments (
  id              INT UNSIGNED  NOT NULL AUTO_INCREMENT,
  order_id        INT UNSIGNED  NOT NULL,
  user_id         INT UNSIGNED  NOT NULL,
  amount          DECIMAL(14,2) NOT NULL,
  balance_after   DECIMAL(15,2) NULL,
  payment_method  ENUM('credit_card','vietqr','cod') NOT NULL DEFAULT 'credit_card',
  card_masked     VARCHAR(30)   NULL,
  transaction_ref VARCHAR(64)   NOT NULL,
  status          ENUM('success','failed','refunded') NOT NULL DEFAULT 'success',
  created_at      TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uq_payments_tx (transaction_ref),
  KEY idx_payments_order (order_id)
) ENGINE=InnoDB;

-- Dữ liệu Ví & Thẻ thanh toán mẫu cho các user (Trong payment_db)
INSERT INTO user_wallets (user_id, balance, credit_limit, card_holder, card_masked, bank_name, status) VALUES
  (1, 500000000.00, 1000000000.00, 'TRAN AN ADMIN',       '****-****-****-9999', 'Techcombank Priority', 'active'),
  (2, 100000000.00,  200000000.00, 'NGUYEN VAN CUSTOMER', '****-****-****-4242', 'Vietcombank Digibank', 'active');

-- ---------------------------------------------------------------------
-- 5. TÀI KHOẢN DB THEO NGUYÊN TẮC LEAST PRIVILEGE (4 Microservices = 4 DB Users)
-- ---------------------------------------------------------------------

-- (1) catalog-service: CHỈ ĐỌC bảng ecommerce.products.
--     Không thấy ecommerce.users, order_db.*, hay payment_db.*.
CREATE USER 'catalog_user'@'%' IDENTIFIED BY 'Catalog#Lab2026';
GRANT SELECT ON ecommerce.products TO 'catalog_user'@'%';

-- (2) order-service (kết nối vào order_db):
--     - Toàn quyền CRUD trên order_db.orders và order_db.order_items.
--     - Đọc ecommerce.products và chỉ UPDATE được cột stock (không sửa được price).
--     - KHÔNG có quyền truy cập payment_db.* (payments, user_wallets) hay ecommerce.users.
CREATE USER 'order_user'@'%' IDENTIFIED BY 'Order#Lab2026';
GRANT SELECT, INSERT, UPDATE, DELETE ON order_db.orders      TO 'order_user'@'%';
GRANT SELECT, INSERT, UPDATE, DELETE ON order_db.order_items TO 'order_user'@'%';
GRANT SELECT ON ecommerce.products TO 'order_user'@'%';
GRANT UPDATE (stock) ON ecommerce.products TO 'order_user'@'%';

-- (3) payment-service (kết nối vào payment_db):
--     - Đọc/ghi giao dịch trên bảng payment_db.payments.
--     - Đọc bảng payment_db.user_wallets và CHỈ UPDATE được cột balance (không sửa được credit_limit hay status).
--     - Chỉ đọc các cột cần thiết của order_db.orders và CHỈ UPDATE được cột status (không sửa được total_price).
--     - KHÔNG có quyền truy cập ecommerce.* (users, products) hay order_db.order_items.
CREATE USER 'payment_user'@'%' IDENTIFIED BY 'Payment#Lab2026';
GRANT SELECT, INSERT ON payment_db.payments TO 'payment_user'@'%';
GRANT SELECT ON payment_db.user_wallets TO 'payment_user'@'%';
GRANT UPDATE (balance) ON payment_db.user_wallets TO 'payment_user'@'%';
GRANT SELECT (id, user_id, total_price, status) ON order_db.orders TO 'payment_user'@'%';
GRANT UPDATE (status) ON order_db.orders TO 'payment_user'@'%';

-- (4) auth-service: chỉ đọc/thêm trên bảng ecommerce.users.
CREATE USER 'auth_user'@'%' IDENTIFIED BY 'Auth#Lab2026';
GRANT SELECT, INSERT ON ecommerce.users TO 'auth_user'@'%';

FLUSH PRIVILEGES;
