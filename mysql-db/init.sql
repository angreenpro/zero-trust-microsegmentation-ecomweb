-- =====================================================================
-- init.sql - NGÀY 1: Data Zone (MySQL) cho lab Micro-segmentation / ZTA
-- Chạy tự động lần đầu khi container mysql-db khởi tạo volume trống.
-- =====================================================================

SET NAMES utf8mb4;

CREATE DATABASE IF NOT EXISTS ecommerce
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE ecommerce;

-- ---------------------------------------------------------------------
-- 1. BẢNG
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

CREATE TABLE orders (
  id          INT UNSIGNED  NOT NULL AUTO_INCREMENT,
  user_id     INT UNSIGNED  NOT NULL,
  total_price DECIMAL(14,2) NOT NULL DEFAULT 0,
  status      ENUM('pending','paid','shipped','cancelled') NOT NULL DEFAULT 'pending',
  created_at  TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,
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

-- ---------------------------------------------------------------------
-- 2. DỮ LIỆU MẪU
-- ---------------------------------------------------------------------

-- Mật khẩu (CHỈ DÙNG TRONG LAB):  admin / Admin@123   |   customer1 / Customer@123
-- Hash bcrypt cost 12 (tiền tố $2y$ tương thích thư viện bcrypt / passlib của Python).
INSERT INTO users (username, password_hash, role) VALUES
  ('admin',      '$2y$12$SO6Zas4mWVUH.pbHXZI7UetwuL02JrHZy67kenyTdAnuAGlo0tFAy', 'admin'),
  ('customer1',  '$2y$12$b31q7rKmePStwyPTFFdq..6X.22k5fhUYnW0bQxVgL7a4Yn8KgyMe', 'customer');

INSERT INTO products (name, price, stock, image_url) VALUES
  ('Laptop Dell Inspiron 15',        15990000.00, 25, 'https://placehold.co/400x300?text=Laptop'),
  ('Điện thoại Samsung Galaxy A55',   9490000.00, 40, 'https://placehold.co/400x300?text=Phone'),
  ('Tai nghe Bluetooth Sony WH-1000', 6290000.00, 60, 'https://placehold.co/400x300?text=Headphone'),
  ('Bàn phím cơ Keychron K2',         1890000.00, 80, 'https://placehold.co/400x300?text=Keyboard'),
  ('Chuột không dây Logitech MX',     1590000.00, 100,'https://placehold.co/400x300?text=Mouse'),
  ('Màn hình LG UltraGear 27"',       5790000.00, 30, 'https://placehold.co/400x300?text=Monitor'),
  ('Ổ cứng SSD Samsung 980 1TB',      2190000.00, 70, 'https://placehold.co/400x300?text=SSD'),
  ('Webcam Logitech C920',            1490000.00, 55, 'https://placehold.co/400x300?text=Webcam'),
  ('Loa Bluetooth JBL Flip 6',        2790000.00, 45, 'https://placehold.co/400x300?text=Speaker'),
  ('Router WiFi TP-Link AX55',        1390000.00, 65, 'https://placehold.co/400x300?text=Router');

-- ---------------------------------------------------------------------
-- 3. TÀI KHOẢN DB THEO NGUYÊN TẮC LEAST PRIVILEGE (cài cắm cho ZTA)
--    Mỗi microservice dùng đúng 1 tài khoản, chỉ có quyền tối thiểu.
--    Host '%' vì ở giai đoạn Baseline các container nằm chung mạng phẳng;
--    sang Ngày 7 sẽ siết lại theo IP/subnet + cô lập mạng.
--    Mật khẩu dưới đây chỉ là mật khẩu lab, hãy đổi nếu đưa ra ngoài.
-- ---------------------------------------------------------------------

-- catalog-service: CHỈ ĐỌC bảng products. Đây là điểm xâm nhập giả định (Breach Point),
-- nên nếu bị chiếm quyền, kẻ tấn công không đọc được users / orders.
CREATE USER 'catalog_user'@'%' IDENTIFIED BY 'Catalog#Lab2026';
GRANT SELECT ON ecommerce.products TO 'catalog_user'@'%';

-- order-service: đọc/ghi orders, order_items; đọc products và chỉ được sửa cột stock.
-- UPDATE(stock) ở mức cột => không sửa được price/name. SELECT ... FOR UPDATE cần SELECT + UPDATE.
CREATE USER 'order_user'@'%' IDENTIFIED BY 'Order#Lab2026';
GRANT SELECT, INSERT, UPDATE, DELETE ON ecommerce.orders      TO 'order_user'@'%';
GRANT SELECT, INSERT, UPDATE, DELETE ON ecommerce.order_items TO 'order_user'@'%';
GRANT SELECT ON ecommerce.products TO 'order_user'@'%';
GRANT UPDATE (stock) ON ecommerce.products TO 'order_user'@'%';

-- auth-service: đọc users để đăng nhập, thêm user mới để đăng ký. Không đụng tới products/orders.
-- (Ngoài 2 user trong tài liệu: Ngày 3 auth-service cần quyền riêng trên bảng users.)
CREATE USER 'auth_user'@'%' IDENTIFIED BY 'Auth#Lab2026';
GRANT SELECT, INSERT ON ecommerce.users TO 'auth_user'@'%';

FLUSH PRIVILEGES;
