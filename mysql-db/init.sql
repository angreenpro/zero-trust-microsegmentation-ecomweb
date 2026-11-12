-- =====================================================================
-- init.sql - Data Zone (MySQL) cho lab Micro-segmentation / ZTA
-- Chạy tự động lần đầu khi container mysql-db khởi tạo volume trống.
-- =====================================================================

SET CHARACTER SET utf8mb4;
SET NAMES utf8mb4 COLLATE utf8mb4_unicode_ci;

CREATE DATABASE IF NOT EXISTS ecommerce
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE ecommerce;

-- ---------------------------------------------------------------------
-- 1. BẢNG DỮ LIỆU
-- ---------------------------------------------------------------------

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

CREATE TABLE coupons (
  id              INT UNSIGNED  NOT NULL AUTO_INCREMENT,
  code            VARCHAR(30)   NOT NULL,
  description     VARCHAR(150)  NOT NULL,
  discount_type   ENUM('percent','fixed') NOT NULL DEFAULT 'percent',
  discount_value  DECIMAL(12,2) NOT NULL,
  max_discount    DECIMAL(12,2) NULL,
  min_order_value DECIMAL(14,2) NOT NULL DEFAULT 0,
  usage_limit     INT UNSIGNED  NOT NULL DEFAULT 100,
  used_count      INT UNSIGNED  NOT NULL DEFAULT 0,
  active          TINYINT(1)    NOT NULL DEFAULT 1,
  PRIMARY KEY (id),
  UNIQUE KEY uq_coupons_code (code),
  CONSTRAINT chk_coupons_val CHECK (discount_value >= 0),
  CONSTRAINT chk_coupons_usage CHECK (used_count <= usage_limit)
) ENGINE=InnoDB;

CREATE TABLE orders (
  id              INT UNSIGNED  NOT NULL AUTO_INCREMENT,
  user_id         INT UNSIGNED  NOT NULL,
  coupon_code     VARCHAR(30)   NULL,
  discount_amount DECIMAL(14,2) NOT NULL DEFAULT 0,
  total_price     DECIMAL(14,2) NOT NULL DEFAULT 0,
  status          ENUM('pending','paid','shipped','cancelled') NOT NULL DEFAULT 'pending',
  created_at      TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_orders_user (user_id),
  CONSTRAINT fk_orders_user FOREIGN KEY (user_id) REFERENCES users (id)
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
  CONSTRAINT fk_items_order   FOREIGN KEY (order_id)   REFERENCES orders (id)   ON DELETE CASCADE,
  CONSTRAINT fk_items_product FOREIGN KEY (product_id) REFERENCES products (id),
  CONSTRAINT chk_items_qty CHECK (quantity > 0)
) ENGINE=InnoDB;

CREATE TABLE payments (
  id              INT UNSIGNED  NOT NULL AUTO_INCREMENT,
  order_id        INT UNSIGNED  NOT NULL,
  user_id         INT UNSIGNED  NOT NULL,
  amount          DECIMAL(14,2) NOT NULL,
  payment_method  ENUM('credit_card','vietqr','cod') NOT NULL DEFAULT 'credit_card',
  card_masked     VARCHAR(30)   NULL,
  transaction_ref VARCHAR(64)   NOT NULL,
  status          ENUM('success','failed','refunded') NOT NULL DEFAULT 'success',
  created_at      TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uq_payments_tx (transaction_ref),
  KEY idx_payments_order (order_id),
  CONSTRAINT fk_payments_order FOREIGN KEY (order_id) REFERENCES orders (id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- 2. DỮ LIỆU MẪU
-- ---------------------------------------------------------------------

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

INSERT INTO coupons (code, description, discount_type, discount_value, max_discount, min_order_value, usage_limit, used_count, active) VALUES
  ('ZTA10',    'Giảm 10% tối đa 1.000.000đ cho đơn từ 500.000đ',   'percent', 10.00,      1000000.00,   500000.00, 100, 0, 1),
  ('ZTA500K',  'Giảm trực tiếp 500.000đ cho đơn từ 3.000.000đ',    'fixed',   500000.00,  500000.00,   3000000.00,  50, 0, 1),
  ('VIP20',    'Giảm 20% tối đa 2.500.000đ cho đơn từ 10.000.000đ','percent', 20.00,      2500000.00, 10000000.00,  20, 0, 1),
  ('EXPIRED0', 'Mã khuyến mãi đã hết hiệu lực (dùng để test)',     'percent', 50.00,      5000000.00,        0.00,  10, 0, 0);

-- ---------------------------------------------------------------------
-- 3. TÀI KHOẢN DB THEO NGUYÊN TẮC LEAST PRIVILEGE (4 Microservices = 4 DB Users)
-- ---------------------------------------------------------------------

-- (1) catalog-service: CHỈ ĐỌC bảng products. Không thấy users, orders, coupons, payments.
CREATE USER 'catalog_user'@'%' IDENTIFIED BY 'Catalog#Lab2026';
GRANT SELECT ON ecommerce.products TO 'catalog_user'@'%';

-- (2) order-service:
--     - Đọc/ghi orders, order_items.
--     - Đọc products và chỉ UPDATE được cột stock (không sửa được price).
--     - Đọc coupons và chỉ UPDATE được cột used_count (không sửa được discount_value hay active).
--     - KHÔNG có quyền truy cập bảng payments hay users.
CREATE USER 'order_user'@'%' IDENTIFIED BY 'Order#Lab2026';
GRANT SELECT, INSERT, UPDATE, DELETE ON ecommerce.orders      TO 'order_user'@'%';
GRANT SELECT, INSERT, UPDATE, DELETE ON ecommerce.order_items TO 'order_user'@'%';
GRANT SELECT ON ecommerce.products TO 'order_user'@'%';
GRANT UPDATE (stock) ON ecommerce.products TO 'order_user'@'%';
GRANT SELECT ON ecommerce.coupons TO 'order_user'@'%';
GRANT UPDATE (used_count) ON ecommerce.coupons TO 'order_user'@'%';

-- (3) payment-service:
--     - Đọc/ghi giao dịch trên bảng payments.
--     - Chỉ đọc các cột cần thiết của bảng orders và CHỈ UPDATE được cột status (không sửa được total_price).
--     - KHÔNG có quyền truy cập bảng users, products, coupons, order_items.
CREATE USER 'payment_user'@'%' IDENTIFIED BY 'Payment#Lab2026';
GRANT SELECT, INSERT ON ecommerce.payments TO 'payment_user'@'%';
GRANT SELECT (id, user_id, coupon_code, discount_amount, total_price, status) ON ecommerce.orders TO 'payment_user'@'%';
GRANT UPDATE (status) ON ecommerce.orders TO 'payment_user'@'%';

-- (4) auth-service: chỉ đọc/thêm trên bảng users.
CREATE USER 'auth_user'@'%' IDENTIFIED BY 'Auth#Lab2026';
GRANT SELECT, INSERT ON ecommerce.users TO 'auth_user'@'%';

FLUSH PRIVILEGES;
