-- =====================================================================
-- CSE 301 Database Management - Fall 2026
-- Project Part 2: Stored Procedures and Triggers
-- Project : Multi-Vendor E-Commerce Marketplace
-- Group   : Moon Light
--
-- Group Members (Name Surname - Student Number):
--   Mehmet Çolaker        - 220610028
--   Emre Sefa Kazan       - 230610019
--   Ahmet Yasin Akyüz     - 230610015
--   Hüseyin Gürses        - 230610029
--   Zeynep Sümeyra Altın  - 230610005
--   Ulaş Budak            - 25060902060
--
-- Run order: 1) MoonLight_CSE301_Part1_DB.sql  (schema + sample data)
--            2) this file                       (procedures + triggers)
-- The triggers are created after the sample data has been inserted, so
-- the Part 1 rows are not processed by them a second time.
-- The web application accesses the database ONLY through the stored
-- procedures defined in this file (CALL ...).
-- =====================================================================

USE ecommerce_marketplace;
SET NAMES utf8mb4;

DELIMITER $$

-- =====================================================================
-- A. ACCOUNTS AND AUTHENTICATION
-- =====================================================================

-- A1. Account lookup for login. Joins 3 tables (Users, Customer, Seller).
DROP PROCEDURE IF EXISTS sp_get_user_by_email $$
CREATE PROCEDURE sp_get_user_by_email(IN p_email VARCHAR(100))
BEGIN
  SELECT u.UserID, u.Email, u.PasswordHash, u.Role, u.Status AS UserStatus,
         c.CustomerID, s.SellerID, s.Status AS SellerStatus,
         COALESCE(c.FullName, s.StoreName, 'Administrator') AS DisplayName
  FROM Users u
  LEFT JOIN Customer c ON c.UserID = u.UserID
  LEFT JOIN Seller   s ON s.UserID = u.UserID
  WHERE u.Email = p_email;
END $$

-- A2. Customer registration (Users + Customer in one transaction).
DROP PROCEDURE IF EXISTS sp_register_customer $$
CREATE PROCEDURE sp_register_customer(IN p_email VARCHAR(100), IN p_hash VARCHAR(255),
                                      IN p_full_name VARCHAR(100), IN p_phone VARCHAR(20))
BEGIN
  DECLARE v_user_id INT;
  DECLARE EXIT HANDLER FOR SQLEXCEPTION BEGIN ROLLBACK; RESIGNAL; END;
  IF EXISTS (SELECT 1 FROM Users WHERE Email = p_email) THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'This e-mail address is already registered.';
  END IF;
  START TRANSACTION;
    INSERT INTO Users (Email, PasswordHash, Role, Status) VALUES (p_email, p_hash, 'CUSTOMER', 'ACTIVE');
    SET v_user_id = LAST_INSERT_ID();
    INSERT INTO Customer (UserID, FullName, Phone) VALUES (v_user_id, p_full_name, NULLIF(p_phone, ''));
  COMMIT;
  SELECT v_user_id AS UserID, LAST_INSERT_ID() AS CustomerID;
END $$

-- A3. Seller registration (store starts as PENDING until an admin approves it).
DROP PROCEDURE IF EXISTS sp_register_seller $$
CREATE PROCEDURE sp_register_seller(IN p_email VARCHAR(100), IN p_hash VARCHAR(255), IN p_store_name VARCHAR(100))
BEGIN
  DECLARE v_user_id INT;
  DECLARE EXIT HANDLER FOR SQLEXCEPTION BEGIN ROLLBACK; RESIGNAL; END;
  IF EXISTS (SELECT 1 FROM Users WHERE Email = p_email) THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'This e-mail address is already registered.';
  END IF;
  START TRANSACTION;
    INSERT INTO Users (Email, PasswordHash, Role, Status) VALUES (p_email, p_hash, 'SELLER', 'ACTIVE');
    SET v_user_id = LAST_INSERT_ID();
    INSERT INTO Seller (UserID, StoreName, Status) VALUES (v_user_id, p_store_name, 'PENDING');
  COMMIT;
  SELECT v_user_id AS UserID, LAST_INSERT_ID() AS SellerID;
END $$

-- =====================================================================
-- B. CATALOGUE
-- =====================================================================

-- B1. Categories with the number of products on sale.
DROP PROCEDURE IF EXISTS sp_list_categories $$
CREATE PROCEDURE sp_list_categories()
BEGIN
  SELECT c.CategoryID, c.CategoryName, c.Description, COUNT(p.ProductID) AS ProductCount
  FROM Category c
  LEFT JOIN Product p ON p.CategoryID = c.CategoryID AND p.Status = 'ACTIVE'
  GROUP BY c.CategoryID, c.CategoryName, c.Description
  ORDER BY c.CategoryName;
END $$

-- B2. Product browsing with filter, search, sorting and pagination.
--     Joins 4 tables (Product, Category, Seller, Inventory) + rating aggregate.
--     Only the columns shown on a product card and only one page of rows are returned.
DROP PROCEDURE IF EXISTS sp_browse_products $$
CREATE PROCEDURE sp_browse_products(IN p_category_id INT, IN p_search VARCHAR(100), IN p_sort VARCHAR(20),
                                    IN p_limit INT, IN p_offset INT)
BEGIN
  SELECT p.ProductID, p.ProductName, p.Price, p.Status, c.CategoryName, s.StoreName,
         i.Quantity AS Stock, r.AvgRating, COALESCE(r.ReviewCount, 0) AS ReviewCount
  FROM Product p
  JOIN Category  c ON c.CategoryID = p.CategoryID
  JOIN Seller    s ON s.SellerID   = p.SellerID
  JOIN Inventory i ON i.ProductID  = p.ProductID
  LEFT JOIN (SELECT ProductID, ROUND(AVG(Rating), 1) AS AvgRating, COUNT(*) AS ReviewCount
             FROM Review GROUP BY ProductID) r ON r.ProductID = p.ProductID
  WHERE p.Status IN ('ACTIVE', 'OUT_OF_STOCK') AND s.Status = 'ACTIVE'
    AND (p_category_id IS NULL OR p.CategoryID = p_category_id)
    AND (p_search IS NULL OR p_search = '' OR p.ProductName LIKE CONCAT('%', p_search, '%'))
  ORDER BY CASE WHEN p_sort = 'price_asc'  THEN p.Price END ASC,
           CASE WHEN p_sort = 'price_desc' THEN p.Price END DESC,
           CASE WHEN p_sort = 'rating'     THEN r.AvgRating END DESC,
           p.ProductID DESC
  LIMIT p_limit OFFSET p_offset;
END $$

-- B3. Number of products matching the same filter (for pagination).
DROP PROCEDURE IF EXISTS sp_count_products $$
CREATE PROCEDURE sp_count_products(IN p_category_id INT, IN p_search VARCHAR(100))
BEGIN
  SELECT COUNT(*) AS Total
  FROM Product p
  JOIN Seller s ON s.SellerID = p.SellerID
  WHERE p.Status IN ('ACTIVE', 'OUT_OF_STOCK') AND s.Status = 'ACTIVE'
    AND (p_category_id IS NULL OR p.CategoryID = p_category_id)
    AND (p_search IS NULL OR p_search = '' OR p.ProductName LIKE CONCAT('%', p_search, '%'));
END $$

-- B4. Product detail page. Joins 4 tables (Product, Category, Seller, Inventory).
DROP PROCEDURE IF EXISTS sp_get_product_detail $$
CREATE PROCEDURE sp_get_product_detail(IN p_product_id INT)
BEGIN
  SELECT p.ProductID, p.ProductName, p.Price, p.Status, p.CategoryID, c.CategoryName, c.Description AS CategoryDescription,
         s.SellerID, s.StoreName, s.Status AS SellerStatus, i.Quantity AS Stock,
         (SELECT ROUND(AVG(Rating), 1) FROM Review WHERE ProductID = p.ProductID) AS AvgRating,
         (SELECT COUNT(*) FROM Review WHERE ProductID = p.ProductID) AS ReviewCount
  FROM Product p
  JOIN Category  c ON c.CategoryID = p.CategoryID
  JOIN Seller    s ON s.SellerID   = p.SellerID
  JOIN Inventory i ON i.ProductID  = p.ProductID
  WHERE p.ProductID = p_product_id;
END $$

-- B5. Reviews of a product with the reviewer's name.
DROP PROCEDURE IF EXISTS sp_get_product_reviews $$
CREATE PROCEDURE sp_get_product_reviews(IN p_product_id INT)
BEGIN
  SELECT r.ReviewID, r.Rating, r.Comment, cu.FullName
  FROM Review r
  JOIN Customer cu ON cu.CustomerID = r.CustomerID
  WHERE r.ProductID = p_product_id
  ORDER BY r.ReviewID DESC;
END $$

-- =====================================================================
-- C. CART AND ADDRESSES (CUSTOMER)
-- =====================================================================

-- C1. Cart content. Joins 5 tables (Cart, CartItem, Product, Seller, Inventory).
DROP PROCEDURE IF EXISTS sp_get_cart $$
CREATE PROCEDURE sp_get_cart(IN p_customer_id INT)
BEGIN
  SELECT ci.ProductID, p.ProductName, p.Price, ci.Quantity, p.Price * ci.Quantity AS LineTotal,
         p.Status AS ProductStatus, s.StoreName, i.Quantity AS Stock
  FROM Cart ca
  JOIN CartItem  ci ON ci.CartID    = ca.CartID
  JOIN Product   p  ON p.ProductID  = ci.ProductID
  JOIN Seller    s  ON s.SellerID   = p.SellerID
  JOIN Inventory i  ON i.ProductID  = p.ProductID
  WHERE ca.CustomerID = p_customer_id
  ORDER BY s.StoreName, p.ProductName;
END $$

-- C2. Total number of units in the cart (kept in a session variable).
DROP PROCEDURE IF EXISTS sp_get_cart_count $$
CREATE PROCEDURE sp_get_cart_count(IN p_customer_id INT)
BEGIN
  SELECT COALESCE(SUM(ci.Quantity), 0) AS CartCount
  FROM Cart ca JOIN CartItem ci ON ci.CartID = ca.CartID
  WHERE ca.CustomerID = p_customer_id;
END $$

-- C3. Add a product to the cart (creates the cart on first use).
DROP PROCEDURE IF EXISTS sp_cart_add $$
CREATE PROCEDURE sp_cart_add(IN p_customer_id INT, IN p_product_id INT, IN p_qty INT)
BEGIN
  DECLARE v_cart_id INT;
  DECLARE v_stock INT;
  DECLARE v_in_cart INT DEFAULT 0;
  IF p_qty IS NULL OR p_qty <= 0 THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Quantity must be at least 1.';
  END IF;
  SELECT i.Quantity INTO v_stock
  FROM Product p JOIN Seller s ON s.SellerID = p.SellerID JOIN Inventory i ON i.ProductID = p.ProductID
  WHERE p.ProductID = p_product_id AND p.Status = 'ACTIVE' AND s.Status = 'ACTIVE';
  IF v_stock IS NULL THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'This product is currently not available.';
  END IF;
  SELECT CartID INTO v_cart_id FROM Cart WHERE CustomerID = p_customer_id;
  IF v_cart_id IS NULL THEN
    INSERT INTO Cart (CustomerID, CreatedAt) VALUES (p_customer_id, NOW());
    SET v_cart_id = LAST_INSERT_ID();
  END IF;
  SELECT COALESCE(MAX(Quantity), 0) INTO v_in_cart FROM CartItem WHERE CartID = v_cart_id AND ProductID = p_product_id;
  IF v_in_cart + p_qty > v_stock THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'The requested quantity exceeds the available stock.';
  END IF;
  IF v_in_cart > 0 THEN
    UPDATE CartItem SET Quantity = Quantity + p_qty WHERE CartID = v_cart_id AND ProductID = p_product_id;
  ELSE
    INSERT INTO CartItem (CartID, ProductID, Quantity) VALUES (v_cart_id, p_product_id, p_qty);
  END IF;
  SELECT COALESCE(SUM(Quantity), 0) AS CartCount FROM CartItem WHERE CartID = v_cart_id;
END $$

-- C4. Change the quantity of a cart line; quantity 0 removes the line.
DROP PROCEDURE IF EXISTS sp_cart_update $$
CREATE PROCEDURE sp_cart_update(IN p_customer_id INT, IN p_product_id INT, IN p_qty INT)
BEGIN
  DECLARE v_cart_id INT;
  DECLARE v_stock INT;
  SELECT CartID INTO v_cart_id FROM Cart WHERE CustomerID = p_customer_id;
  IF v_cart_id IS NULL THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Your cart is empty.';
  END IF;
  IF p_qty IS NULL OR p_qty <= 0 THEN
    DELETE FROM CartItem WHERE CartID = v_cart_id AND ProductID = p_product_id;
  ELSE
    SELECT Quantity INTO v_stock FROM Inventory WHERE ProductID = p_product_id;
    IF p_qty > v_stock THEN
      SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'The requested quantity exceeds the available stock.';
    END IF;
    UPDATE CartItem SET Quantity = p_qty WHERE CartID = v_cart_id AND ProductID = p_product_id;
  END IF;
  SELECT COALESCE(SUM(Quantity), 0) AS CartCount FROM CartItem WHERE CartID = v_cart_id;
END $$

-- C5. Addresses of a customer.
DROP PROCEDURE IF EXISTS sp_list_addresses $$
CREATE PROCEDURE sp_list_addresses(IN p_customer_id INT)
BEGIN
  SELECT AddressID, City, District, AddressLine FROM Address
  WHERE CustomerID = p_customer_id ORDER BY AddressID;
END $$

-- C6. New address.
DROP PROCEDURE IF EXISTS sp_add_address $$
CREATE PROCEDURE sp_add_address(IN p_customer_id INT, IN p_city VARCHAR(100), IN p_district VARCHAR(100), IN p_line VARCHAR(255))
BEGIN
  IF TRIM(p_city) = '' OR TRIM(p_district) = '' OR TRIM(p_line) = '' THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'City, district and address line are required.';
  END IF;
  INSERT INTO Address (CustomerID, City, District, AddressLine) VALUES (p_customer_id, TRIM(p_city), TRIM(p_district), TRIM(p_line));
  SELECT LAST_INSERT_ID() AS AddressID;
END $$

-- =====================================================================
-- D. ORDERS, PAYMENTS AND REVIEWS (CUSTOMER)
-- =====================================================================

-- D1. Checkout: converts the cart into an order in a single transaction.
--     Stock checks, unit prices, stock deduction and the order total are
--     handled by the OrderItem triggers (see section G), so stock is
--     deducted exactly once. Payment processing is simulated.
DROP PROCEDURE IF EXISTS sp_place_order $$
CREATE PROCEDURE sp_place_order(IN p_customer_id INT, IN p_address_id INT, IN p_method VARCHAR(30))
BEGIN
  DECLARE v_cart_id INT;
  DECLARE v_order_id INT;
  DECLARE v_total DECIMAL(12,2);
  DECLARE v_lines INT DEFAULT 0;
  DECLARE EXIT HANDLER FOR SQLEXCEPTION BEGIN ROLLBACK; RESIGNAL; END;
  IF p_method NOT IN ('CREDIT_CARD', 'DEBIT_CARD', 'BANK_TRANSFER', 'DIGITAL_WALLET') THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Please select a valid payment method.';
  END IF;
  SELECT CartID INTO v_cart_id FROM Cart WHERE CustomerID = p_customer_id;
  SELECT COUNT(*) INTO v_lines FROM CartItem WHERE CartID = v_cart_id;
  IF v_cart_id IS NULL OR v_lines = 0 THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Your cart is empty.';
  END IF;
  START TRANSACTION;
    INSERT INTO Orders (CustomerID, AddressID, OrderDate, TotalAmount, Status)
    VALUES (p_customer_id, p_address_id, NOW(), 0, 'PENDING');
    SET v_order_id = LAST_INSERT_ID();
    INSERT INTO OrderItem (OrderID, ProductID, Quantity, UnitPrice)
    SELECT v_order_id, ci.ProductID, ci.Quantity, 0 FROM CartItem ci WHERE ci.CartID = v_cart_id;
    SELECT TotalAmount INTO v_total FROM Orders WHERE OrderID = v_order_id;
    INSERT INTO Payment (OrderID, Amount, PaymentMethod, Status) VALUES (v_order_id, v_total, p_method, 'COMPLETED');
    UPDATE Orders SET Status = 'PROCESSING' WHERE OrderID = v_order_id;
    DELETE FROM CartItem WHERE CartID = v_cart_id;
  COMMIT;
  SELECT v_order_id AS OrderID, v_total AS TotalAmount;
END $$

-- D2. Order history of a customer. Joins 4 tables (Orders, Address, OrderItem, Product).
DROP PROCEDURE IF EXISTS sp_get_customer_orders $$
CREATE PROCEDURE sp_get_customer_orders(IN p_customer_id INT)
BEGIN
  SELECT o.OrderID, o.OrderDate, o.TotalAmount, o.Status, a.City, a.District,
         SUM(oi.Quantity) AS ItemCount, COUNT(DISTINCT p.SellerID) AS SellerCount
  FROM Orders o
  JOIN Address   a  ON a.AddressID = o.AddressID
  JOIN OrderItem oi ON oi.OrderID  = o.OrderID
  JOIN Product   p  ON p.ProductID = oi.ProductID
  WHERE o.CustomerID = p_customer_id
  GROUP BY o.OrderID, o.OrderDate, o.TotalAmount, o.Status, a.City, a.District
  ORDER BY o.OrderDate DESC;
END $$

-- D3. Order header. Joins 4 tables (Orders, Customer, Users, Address).
--     p_customer_id = NULL is used by administrators (any order).
DROP PROCEDURE IF EXISTS sp_get_order_header $$
CREATE PROCEDURE sp_get_order_header(IN p_order_id INT, IN p_customer_id INT)
BEGIN
  SELECT o.OrderID, o.OrderDate, o.TotalAmount, o.Status, o.CustomerID, cu.FullName, u.Email,
         a.City, a.District, a.AddressLine
  FROM Orders o
  JOIN Customer cu ON cu.CustomerID = o.CustomerID
  JOIN Users    u  ON u.UserID      = cu.UserID
  JOIN Address  a  ON a.AddressID   = o.AddressID
  WHERE o.OrderID = p_order_id AND (p_customer_id IS NULL OR o.CustomerID = p_customer_id);
END $$

-- D4. Order lines with the seller and the shipment of each line.
--     Joins 5 tables (OrderItem, Product, Seller, ShipmentItem, Shipment).
DROP PROCEDURE IF EXISTS sp_get_order_items $$
CREATE PROCEDURE sp_get_order_items(IN p_order_id INT)
BEGIN
  SELECT oi.OrderItemID, oi.ProductID, p.ProductName, s.StoreName, oi.Quantity, oi.UnitPrice,
         oi.Quantity * oi.UnitPrice AS LineTotal, sh.ShipmentID, sh.Status AS ShipmentStatus, sh.TrackingNumber
  FROM OrderItem oi
  JOIN Product p ON p.ProductID = oi.ProductID
  JOIN Seller  s ON s.SellerID  = p.SellerID
  LEFT JOIN ShipmentItem si ON si.OrderItemID = oi.OrderItemID
  LEFT JOIN Shipment     sh ON sh.ShipmentID  = si.ShipmentID
  WHERE oi.OrderID = p_order_id
  ORDER BY s.StoreName, oi.OrderItemID;
END $$

-- D5. Payment records of an order.
DROP PROCEDURE IF EXISTS sp_get_order_payments $$
CREATE PROCEDURE sp_get_order_payments(IN p_order_id INT)
BEGIN
  SELECT PaymentID, Amount, PaymentMethod, Status FROM Payment WHERE OrderID = p_order_id ORDER BY PaymentID;
END $$

-- D6. Seller-specific shipments of an order. Joins 3 tables (Shipment, Seller, ShipmentItem).
DROP PROCEDURE IF EXISTS sp_get_order_shipments $$
CREATE PROCEDURE sp_get_order_shipments(IN p_order_id INT)
BEGIN
  SELECT sh.ShipmentID, s.StoreName, sh.TrackingNumber, sh.Status, COUNT(si.ShipmentItemID) AS ItemCount
  FROM Shipment sh
  JOIN Seller s ON s.SellerID = sh.SellerID
  LEFT JOIN ShipmentItem si ON si.ShipmentID = sh.ShipmentID
  WHERE sh.OrderID = p_order_id
  GROUP BY sh.ShipmentID, s.StoreName, sh.TrackingNumber, sh.Status
  ORDER BY sh.ShipmentID;
END $$

-- D7. Cancel an order that has not been shipped yet. Stock is restored by trg_orders_after_update.
DROP PROCEDURE IF EXISTS sp_cancel_order $$
CREATE PROCEDURE sp_cancel_order(IN p_customer_id INT, IN p_order_id INT)
BEGIN
  DECLARE v_status VARCHAR(20);
  DECLARE EXIT HANDLER FOR SQLEXCEPTION BEGIN ROLLBACK; RESIGNAL; END;
  SELECT Status INTO v_status FROM Orders WHERE OrderID = p_order_id AND CustomerID = p_customer_id;
  IF v_status IS NULL THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Order not found.';
  END IF;
  IF v_status NOT IN ('PENDING', 'PROCESSING') THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Only pending or processing orders can be cancelled.';
  END IF;
  IF EXISTS (SELECT 1 FROM Shipment WHERE OrderID = p_order_id AND Status IN ('SHIPPED', 'DELIVERED')) THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Part of this order has already been shipped, so it can no longer be cancelled.';
  END IF;
  START TRANSACTION;
    DELETE si FROM ShipmentItem si JOIN Shipment sh ON sh.ShipmentID = si.ShipmentID WHERE sh.OrderID = p_order_id;
    DELETE FROM Shipment WHERE OrderID = p_order_id;
    UPDATE Payment SET Status = CASE Status WHEN 'COMPLETED' THEN 'REFUNDED' WHEN 'PENDING' THEN 'FAILED' ELSE Status END
    WHERE OrderID = p_order_id;
    UPDATE Orders SET Status = 'CANCELLED' WHERE OrderID = p_order_id;
  COMMIT;
  SELECT p_order_id AS OrderID;
END $$

-- D8. Delivered products that the customer has not reviewed yet.
--     Joins 4 tables (Orders, OrderItem, Product, Seller).
DROP PROCEDURE IF EXISTS sp_get_reviewable_items $$
CREATE PROCEDURE sp_get_reviewable_items(IN p_customer_id INT)
BEGIN
  SELECT p.ProductID, p.ProductName, s.StoreName, MAX(o.OrderDate) AS LastPurchase
  FROM Orders o
  JOIN OrderItem oi ON oi.OrderID  = o.OrderID
  JOIN Product   p  ON p.ProductID = oi.ProductID
  JOIN Seller    s  ON s.SellerID  = p.SellerID
  WHERE o.CustomerID = p_customer_id AND o.Status = 'DELIVERED'
    AND NOT EXISTS (SELECT 1 FROM Review r WHERE r.CustomerID = p_customer_id AND r.ProductID = p.ProductID)
  GROUP BY p.ProductID, p.ProductName, s.StoreName
  ORDER BY LastPurchase DESC;
END $$

-- D9. New review (purchase check in trg_review_before_insert, rating check by CHECK constraint).
DROP PROCEDURE IF EXISTS sp_add_review $$
CREATE PROCEDURE sp_add_review(IN p_customer_id INT, IN p_product_id INT, IN p_rating INT, IN p_comment TEXT)
BEGIN
  INSERT INTO Review (CustomerID, ProductID, Rating, Comment) VALUES (p_customer_id, p_product_id, p_rating, NULLIF(TRIM(p_comment), ''));
  SELECT LAST_INSERT_ID() AS ReviewID;
END $$

-- =====================================================================
-- E. SELLER OPERATIONS
-- =====================================================================

-- E1. Seller dashboard figures (revenue sub-query joins OrderItem, Product, Orders).
DROP PROCEDURE IF EXISTS sp_seller_dashboard $$
CREATE PROCEDURE sp_seller_dashboard(IN p_seller_id INT)
BEGIN
  SELECT
    (SELECT COUNT(*) FROM Product WHERE SellerID = p_seller_id) AS ProductCount,
    (SELECT COUNT(*) FROM Product WHERE SellerID = p_seller_id AND Status = 'ACTIVE') AS ActiveProducts,
    (SELECT COUNT(*) FROM Product p JOIN Inventory i ON i.ProductID = p.ProductID
      WHERE p.SellerID = p_seller_id AND i.Quantity < 10 AND p.Status <> 'INACTIVE') AS LowStock,
    (SELECT COALESCE(SUM(oi.Quantity * oi.UnitPrice), 0)
       FROM OrderItem oi JOIN Product p ON p.ProductID = oi.ProductID JOIN Orders o ON o.OrderID = oi.OrderID
      WHERE p.SellerID = p_seller_id AND o.Status <> 'CANCELLED') AS Revenue,
    (SELECT COUNT(*) FROM OrderItem oi JOIN Product p ON p.ProductID = oi.ProductID JOIN Orders o ON o.OrderID = oi.OrderID
       LEFT JOIN ShipmentItem si ON si.OrderItemID = oi.OrderItemID
      WHERE p.SellerID = p_seller_id AND o.Status = 'PROCESSING' AND si.ShipmentItemID IS NULL) AS ItemsToShip,
    (SELECT COUNT(*) FROM Shipment WHERE SellerID = p_seller_id AND Status IN ('PREPARING', 'SHIPPED')) AS OpenShipments,
    (SELECT ROUND(AVG(r.Rating), 2) FROM Review r JOIN Product p ON p.ProductID = r.ProductID
      WHERE p.SellerID = p_seller_id) AS AvgRating;
END $$

-- E2. Best-selling products of a seller. Joins 3 tables (Product, OrderItem, Orders).
DROP PROCEDURE IF EXISTS sp_seller_top_products $$
CREATE PROCEDURE sp_seller_top_products(IN p_seller_id INT, IN p_limit INT)
BEGIN
  SELECT p.ProductID, p.ProductName, SUM(oi.Quantity) AS UnitsSold, SUM(oi.Quantity * oi.UnitPrice) AS Revenue
  FROM Product p
  JOIN OrderItem oi ON oi.ProductID = p.ProductID
  JOIN Orders    o  ON o.OrderID    = oi.OrderID
  WHERE p.SellerID = p_seller_id AND o.Status <> 'CANCELLED'
  GROUP BY p.ProductID, p.ProductName
  ORDER BY Revenue DESC
  LIMIT p_limit;
END $$

-- E3. Products of a seller. Joins 3 tables (Product, Category, Inventory).
DROP PROCEDURE IF EXISTS sp_seller_products $$
CREATE PROCEDURE sp_seller_products(IN p_seller_id INT)
BEGIN
  SELECT p.ProductID, p.ProductName, p.CategoryID, c.CategoryName, p.Price, p.Status, i.Quantity AS Stock, i.LastUpdated
  FROM Product p
  JOIN Category  c ON c.CategoryID = p.CategoryID
  JOIN Inventory i ON i.ProductID  = p.ProductID
  WHERE p.SellerID = p_seller_id
  ORDER BY p.ProductID DESC;
END $$

-- E4. New product together with its stock record.
DROP PROCEDURE IF EXISTS sp_seller_add_product $$
CREATE PROCEDURE sp_seller_add_product(IN p_seller_id INT, IN p_category_id INT, IN p_name VARCHAR(150),
                                       IN p_price DECIMAL(10,2), IN p_qty INT)
BEGIN
  DECLARE v_product_id INT;
  DECLARE EXIT HANDLER FOR SQLEXCEPTION BEGIN ROLLBACK; RESIGNAL; END;
  IF NOT EXISTS (SELECT 1 FROM Seller WHERE SellerID = p_seller_id AND Status = 'ACTIVE') THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Your store must be approved by an administrator before you can list products.';
  END IF;
  IF p_qty IS NULL OR p_qty < 0 THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Stock quantity cannot be negative.';
  END IF;
  IF p_price IS NULL OR p_price <= 0 THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Price must be greater than zero.';
  END IF;
  START TRANSACTION;
    INSERT INTO Product (SellerID, CategoryID, ProductName, Price, Status)
    VALUES (p_seller_id, p_category_id, TRIM(p_name), p_price, IF(p_qty > 0, 'ACTIVE', 'OUT_OF_STOCK'));
    SET v_product_id = LAST_INSERT_ID();
    INSERT INTO Inventory (ProductID, Quantity, LastUpdated) VALUES (v_product_id, p_qty, NOW());
  COMMIT;
  SELECT v_product_id AS ProductID;
END $$

-- E5. Update name, price, category and listing status of an own product.
DROP PROCEDURE IF EXISTS sp_seller_update_product $$
CREATE PROCEDURE sp_seller_update_product(IN p_seller_id INT, IN p_product_id INT, IN p_name VARCHAR(150),
                                          IN p_price DECIMAL(10,2), IN p_category_id INT, IN p_status VARCHAR(20))
BEGIN
  DECLARE v_stock INT;
  IF NOT EXISTS (SELECT 1 FROM Product WHERE ProductID = p_product_id AND SellerID = p_seller_id) THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Product not found in your store.';
  END IF;
  IF p_status NOT IN ('ACTIVE', 'INACTIVE') THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Listing status must be ACTIVE or INACTIVE.';
  END IF;
  IF p_status = 'ACTIVE' AND NOT EXISTS (SELECT 1 FROM Seller WHERE SellerID = p_seller_id AND Status = 'ACTIVE') THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Products of a store that is not active cannot be listed.';
  END IF;
  IF p_price IS NULL OR p_price <= 0 THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Price must be greater than zero.';
  END IF;
  SELECT Quantity INTO v_stock FROM Inventory WHERE ProductID = p_product_id;
  UPDATE Product
  SET ProductName = TRIM(p_name), Price = p_price, CategoryID = p_category_id,
      Status = IF(p_status = 'ACTIVE' AND v_stock = 0, 'OUT_OF_STOCK', p_status)
  WHERE ProductID = p_product_id;
  SELECT p_product_id AS ProductID;
END $$

-- E6. Set the stock quantity (product status is synchronised by trg_inventory_before_update).
DROP PROCEDURE IF EXISTS sp_seller_update_stock $$
CREATE PROCEDURE sp_seller_update_stock(IN p_seller_id INT, IN p_product_id INT, IN p_qty INT)
BEGIN
  IF NOT EXISTS (SELECT 1 FROM Product WHERE ProductID = p_product_id AND SellerID = p_seller_id) THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Product not found in your store.';
  END IF;
  IF p_qty IS NULL OR p_qty < 0 THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Stock quantity cannot be negative.';
  END IF;
  UPDATE Inventory SET Quantity = p_qty WHERE ProductID = p_product_id;
  SELECT p_product_id AS ProductID;
END $$

-- E7. Order items of the seller that are paid but not yet in a shipment.
--     Joins 6 tables (OrderItem, Product, Orders, Customer, Address, ShipmentItem).
DROP PROCEDURE IF EXISTS sp_seller_pending_items $$
CREATE PROCEDURE sp_seller_pending_items(IN p_seller_id INT)
BEGIN
  SELECT o.OrderID, o.OrderDate, cu.FullName, a.City, a.District, oi.OrderItemID, p.ProductName, oi.Quantity
  FROM OrderItem oi
  JOIN Product  p  ON p.ProductID   = oi.ProductID
  JOIN Orders   o  ON o.OrderID     = oi.OrderID
  JOIN Customer cu ON cu.CustomerID = o.CustomerID
  JOIN Address  a  ON a.AddressID   = o.AddressID
  LEFT JOIN ShipmentItem si ON si.OrderItemID = oi.OrderItemID
  WHERE p.SellerID = p_seller_id AND o.Status = 'PROCESSING' AND si.ShipmentItemID IS NULL
  ORDER BY o.OrderDate, o.OrderID, oi.OrderItemID;
END $$

-- E8. Create a shipment containing all waiting items of the seller in one order.
DROP PROCEDURE IF EXISTS sp_seller_create_shipment $$
CREATE PROCEDURE sp_seller_create_shipment(IN p_seller_id INT, IN p_order_id INT)
BEGIN
  DECLARE v_shipment_id INT;
  DECLARE EXIT HANDLER FOR SQLEXCEPTION BEGIN ROLLBACK; RESIGNAL; END;
  IF NOT EXISTS (SELECT 1 FROM OrderItem oi JOIN Product p ON p.ProductID = oi.ProductID JOIN Orders o ON o.OrderID = oi.OrderID
                 LEFT JOIN ShipmentItem si ON si.OrderItemID = oi.OrderItemID
                 WHERE oi.OrderID = p_order_id AND p.SellerID = p_seller_id AND o.Status = 'PROCESSING' AND si.ShipmentItemID IS NULL) THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'There are no items of your store waiting for shipment in this order.';
  END IF;
  START TRANSACTION;
    INSERT INTO Shipment (OrderID, SellerID, TrackingNumber, Status) VALUES (p_order_id, p_seller_id, NULL, 'PREPARING');
    SET v_shipment_id = LAST_INSERT_ID();
    INSERT INTO ShipmentItem (ShipmentID, OrderItemID)
    SELECT v_shipment_id, oi.OrderItemID
    FROM OrderItem oi JOIN Product p ON p.ProductID = oi.ProductID
    WHERE oi.OrderID = p_order_id AND p.SellerID = p_seller_id
      AND NOT EXISTS (SELECT 1 FROM ShipmentItem x WHERE x.OrderItemID = oi.OrderItemID);
  COMMIT;
  SELECT v_shipment_id AS ShipmentID;
END $$

-- E9. Shipments of a seller. Joins 5 tables (Shipment, Orders, Customer, Address, ShipmentItem).
DROP PROCEDURE IF EXISTS sp_seller_shipments $$
CREATE PROCEDURE sp_seller_shipments(IN p_seller_id INT)
BEGIN
  SELECT sh.ShipmentID, sh.OrderID, o.OrderDate, cu.FullName, a.City, a.District, sh.TrackingNumber, sh.Status,
         COUNT(si.ShipmentItemID) AS ItemCount
  FROM Shipment sh
  JOIN Orders   o  ON o.OrderID     = sh.OrderID
  JOIN Customer cu ON cu.CustomerID = o.CustomerID
  JOIN Address  a  ON a.AddressID   = o.AddressID
  LEFT JOIN ShipmentItem si ON si.ShipmentID = sh.ShipmentID
  WHERE sh.SellerID = p_seller_id
  GROUP BY sh.ShipmentID, sh.OrderID, o.OrderDate, cu.FullName, a.City, a.District, sh.TrackingNumber, sh.Status
  ORDER BY FIELD(sh.Status, 'PREPARING', 'SHIPPED', 'DELIVERED'), sh.ShipmentID DESC;
END $$

-- E10. Advance a shipment: PREPARING -> SHIPPED (tracking number required) -> DELIVERED.
--      The order status is recalculated by trg_shipment_after_update.
DROP PROCEDURE IF EXISTS sp_seller_update_shipment $$
CREATE PROCEDURE sp_seller_update_shipment(IN p_seller_id INT, IN p_shipment_id INT, IN p_status VARCHAR(20), IN p_tracking VARCHAR(100))
BEGIN
  DECLARE v_current VARCHAR(20);
  SELECT Status INTO v_current FROM Shipment WHERE ShipmentID = p_shipment_id AND SellerID = p_seller_id;
  IF v_current IS NULL THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Shipment not found.';
  END IF;
  IF NOT ((v_current = 'PREPARING' AND p_status = 'SHIPPED') OR (v_current = 'SHIPPED' AND p_status = 'DELIVERED')) THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Invalid shipment status change.';
  END IF;
  IF p_status = 'SHIPPED' AND (p_tracking IS NULL OR TRIM(p_tracking) = '') THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'A tracking number is required to mark a shipment as shipped.';
  END IF;
  UPDATE Shipment
  SET Status = p_status, TrackingNumber = COALESCE(NULLIF(TRIM(p_tracking), ''), TrackingNumber)
  WHERE ShipmentID = p_shipment_id;
  SELECT p_shipment_id AS ShipmentID;
END $$

-- =====================================================================
-- F. ADMINISTRATION
-- =====================================================================

-- F1. Platform figures.
DROP PROCEDURE IF EXISTS sp_admin_dashboard $$
CREATE PROCEDURE sp_admin_dashboard()
BEGIN
  SELECT
    (SELECT COUNT(*) FROM Customer) AS Customers,
    (SELECT COUNT(*) FROM Seller WHERE Status = 'ACTIVE') AS ActiveSellers,
    (SELECT COUNT(*) FROM Seller WHERE Status = 'PENDING') AS PendingSellers,
    (SELECT COUNT(*) FROM Product WHERE Status = 'ACTIVE') AS ActiveProducts,
    (SELECT COUNT(*) FROM Orders) AS Orders,
    (SELECT COALESCE(SUM(TotalAmount), 0) FROM Orders WHERE Status <> 'CANCELLED') AS Revenue,
    (SELECT COUNT(*) FROM Shipment WHERE Status IN ('PREPARING', 'SHIPPED')) AS OpenShipments,
    (SELECT ROUND(AVG(Rating), 2) FROM Review) AS AvgRating;
END $$

-- F2. Number and value of orders per status.
DROP PROCEDURE IF EXISTS sp_admin_orders_by_status $$
CREATE PROCEDURE sp_admin_orders_by_status()
BEGIN
  SELECT Status, COUNT(*) AS OrderCount, SUM(TotalAmount) AS Amount
  FROM Orders GROUP BY Status
  ORDER BY FIELD(Status, 'PENDING', 'PROCESSING', 'SHIPPED', 'DELIVERED', 'CANCELLED');
END $$

-- F3. Best sellers by revenue. Joins 4 tables (Seller, Product, OrderItem, Orders).
DROP PROCEDURE IF EXISTS sp_admin_top_sellers $$
CREATE PROCEDURE sp_admin_top_sellers(IN p_limit INT)
BEGIN
  SELECT s.SellerID, s.StoreName, COUNT(DISTINCT o.OrderID) AS OrderCount, SUM(oi.Quantity * oi.UnitPrice) AS Revenue
  FROM Seller s
  JOIN Product   p  ON p.SellerID   = s.SellerID
  JOIN OrderItem oi ON oi.ProductID = p.ProductID
  JOIN Orders    o  ON o.OrderID    = oi.OrderID
  WHERE o.Status <> 'CANCELLED'
  GROUP BY s.SellerID, s.StoreName
  ORDER BY Revenue DESC
  LIMIT p_limit;
END $$

-- F4. User list with filters and pagination. Joins 3 tables (Users, Customer, Seller).
DROP PROCEDURE IF EXISTS sp_admin_list_users $$
CREATE PROCEDURE sp_admin_list_users(IN p_role VARCHAR(20), IN p_status VARCHAR(20), IN p_search VARCHAR(100),
                                     IN p_limit INT, IN p_offset INT)
BEGIN
  SELECT u.UserID, u.Email, u.Role, u.Status, COALESCE(c.FullName, s.StoreName, 'Administrator') AS DisplayName,
         s.SellerID, s.Status AS SellerStatus
  FROM Users u
  LEFT JOIN Customer c ON c.UserID = u.UserID
  LEFT JOIN Seller   s ON s.UserID = u.UserID
  WHERE (p_role IS NULL OR p_role = '' OR u.Role = p_role)
    AND (p_status IS NULL OR p_status = '' OR u.Status = p_status OR s.Status = p_status)
    AND (p_search IS NULL OR p_search = '' OR u.Email LIKE CONCAT('%', p_search, '%')
         OR c.FullName LIKE CONCAT('%', p_search, '%') OR s.StoreName LIKE CONCAT('%', p_search, '%'))
  ORDER BY u.UserID
  LIMIT p_limit OFFSET p_offset;
END $$

-- F5. Number of users matching the same filter.
DROP PROCEDURE IF EXISTS sp_admin_count_users $$
CREATE PROCEDURE sp_admin_count_users(IN p_role VARCHAR(20), IN p_status VARCHAR(20), IN p_search VARCHAR(100))
BEGIN
  SELECT COUNT(*) AS Total
  FROM Users u
  LEFT JOIN Customer c ON c.UserID = u.UserID
  LEFT JOIN Seller   s ON s.UserID = u.UserID
  WHERE (p_role IS NULL OR p_role = '' OR u.Role = p_role)
    AND (p_status IS NULL OR p_status = '' OR u.Status = p_status OR s.Status = p_status)
    AND (p_search IS NULL OR p_search = '' OR u.Email LIKE CONCAT('%', p_search, '%')
         OR c.FullName LIKE CONCAT('%', p_search, '%') OR s.StoreName LIKE CONCAT('%', p_search, '%'));
END $$

-- F6. Activate, suspend or deactivate an account (seller profile kept consistent).
DROP PROCEDURE IF EXISTS sp_admin_set_user_status $$
CREATE PROCEDURE sp_admin_set_user_status(IN p_admin_user_id INT, IN p_user_id INT, IN p_status VARCHAR(20))
BEGIN
  IF p_status NOT IN ('ACTIVE', 'SUSPENDED', 'INACTIVE') THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Invalid account status.';
  END IF;
  IF p_admin_user_id = p_user_id THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'You cannot change the status of your own account.';
  END IF;
  UPDATE Users SET Status = p_status WHERE UserID = p_user_id;
  IF p_status = 'SUSPENDED' THEN
    UPDATE Seller SET Status = 'SUSPENDED' WHERE UserID = p_user_id;
  ELSEIF p_status = 'ACTIVE' THEN
    UPDATE Seller SET Status = 'ACTIVE' WHERE UserID = p_user_id AND Status = 'SUSPENDED';
  END IF;
  SELECT p_user_id AS UserID;
END $$

-- F7. Approve or suspend a store (account status kept consistent).
DROP PROCEDURE IF EXISTS sp_admin_set_seller_status $$
CREATE PROCEDURE sp_admin_set_seller_status(IN p_seller_id INT, IN p_status VARCHAR(20))
BEGIN
  IF p_status NOT IN ('ACTIVE', 'PENDING', 'SUSPENDED') THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Invalid store status.';
  END IF;
  UPDATE Seller SET Status = p_status WHERE SellerID = p_seller_id;
  UPDATE Users u JOIN Seller s ON s.UserID = u.UserID
  SET u.Status = IF(p_status = 'SUSPENDED', 'SUSPENDED', IF(u.Status = 'SUSPENDED', 'ACTIVE', u.Status))
  WHERE s.SellerID = p_seller_id;
  SELECT p_seller_id AS SellerID;
END $$

-- F8. New category (names must be unique).
DROP PROCEDURE IF EXISTS sp_admin_add_category $$
CREATE PROCEDURE sp_admin_add_category(IN p_name VARCHAR(100), IN p_description TEXT)
BEGIN
  IF TRIM(p_name) = '' THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Category name is required.';
  END IF;
  IF EXISTS (SELECT 1 FROM Category WHERE CategoryName = TRIM(p_name)) THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'A category with this name already exists.';
  END IF;
  INSERT INTO Category (CategoryName, Description) VALUES (TRIM(p_name), NULLIF(TRIM(p_description), ''));
  SELECT LAST_INSERT_ID() AS CategoryID;
END $$

-- F9. Rename a category or change its description.
DROP PROCEDURE IF EXISTS sp_admin_update_category $$
CREATE PROCEDURE sp_admin_update_category(IN p_category_id INT, IN p_name VARCHAR(100), IN p_description TEXT)
BEGIN
  IF TRIM(p_name) = '' THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Category name is required.';
  END IF;
  IF EXISTS (SELECT 1 FROM Category WHERE CategoryName = TRIM(p_name) AND CategoryID <> p_category_id) THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'A category with this name already exists.';
  END IF;
  UPDATE Category SET CategoryName = TRIM(p_name), Description = NULLIF(TRIM(p_description), '') WHERE CategoryID = p_category_id;
  SELECT p_category_id AS CategoryID;
END $$

-- F10. Order list for administrators. Joins 3 tables (Orders, Customer, Address).
DROP PROCEDURE IF EXISTS sp_admin_list_orders $$
CREATE PROCEDURE sp_admin_list_orders(IN p_status VARCHAR(20), IN p_limit INT, IN p_offset INT)
BEGIN
  SELECT o.OrderID, o.OrderDate, cu.FullName, a.City, o.TotalAmount, o.Status,
         (SELECT COUNT(*) FROM Shipment sh WHERE sh.OrderID = o.OrderID) AS ShipmentCount
  FROM Orders o
  JOIN Customer cu ON cu.CustomerID = o.CustomerID
  JOIN Address  a  ON a.AddressID   = o.AddressID
  WHERE p_status IS NULL OR p_status = '' OR o.Status = p_status
  ORDER BY o.OrderDate DESC
  LIMIT p_limit OFFSET p_offset;
END $$

-- F11. Number of orders with a given status (all orders if empty).
DROP PROCEDURE IF EXISTS sp_admin_count_orders $$
CREATE PROCEDURE sp_admin_count_orders(IN p_status VARCHAR(20))
BEGIN
  SELECT COUNT(*) AS Total FROM Orders WHERE p_status IS NULL OR p_status = '' OR Status = p_status;
END $$

-- F12. Product moderation list. Joins 4 tables (Product, Seller, Category, Inventory).
DROP PROCEDURE IF EXISTS sp_admin_list_products $$
CREATE PROCEDURE sp_admin_list_products(IN p_search VARCHAR(100), IN p_limit INT, IN p_offset INT)
BEGIN
  SELECT p.ProductID, p.ProductName, p.Price, p.Status, s.StoreName, s.Status AS SellerStatus, c.CategoryName, i.Quantity AS Stock
  FROM Product p
  JOIN Seller    s ON s.SellerID   = p.SellerID
  JOIN Category  c ON c.CategoryID = p.CategoryID
  JOIN Inventory i ON i.ProductID  = p.ProductID
  WHERE p_search IS NULL OR p_search = '' OR p.ProductName LIKE CONCAT('%', p_search, '%') OR s.StoreName LIKE CONCAT('%', p_search, '%')
  ORDER BY p.ProductID DESC
  LIMIT p_limit OFFSET p_offset;
END $$

-- F13. Number of products matching the moderation search.
DROP PROCEDURE IF EXISTS sp_admin_count_products $$
CREATE PROCEDURE sp_admin_count_products(IN p_search VARCHAR(100))
BEGIN
  SELECT COUNT(*) AS Total
  FROM Product p JOIN Seller s ON s.SellerID = p.SellerID
  WHERE p_search IS NULL OR p_search = '' OR p.ProductName LIKE CONCAT('%', p_search, '%') OR s.StoreName LIKE CONCAT('%', p_search, '%');
END $$

-- F14. Withdraw or re-list a product (moderation).
DROP PROCEDURE IF EXISTS sp_admin_set_product_status $$
CREATE PROCEDURE sp_admin_set_product_status(IN p_product_id INT, IN p_status VARCHAR(20))
BEGIN
  DECLARE v_stock INT;
  IF p_status NOT IN ('ACTIVE', 'INACTIVE') THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Listing status must be ACTIVE or INACTIVE.';
  END IF;
  IF p_status = 'ACTIVE' AND NOT EXISTS (SELECT 1 FROM Product p JOIN Seller s ON s.SellerID = p.SellerID
                                         WHERE p.ProductID = p_product_id AND s.Status = 'ACTIVE') THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Products of a store that is not active cannot be listed.';
  END IF;
  SELECT Quantity INTO v_stock FROM Inventory WHERE ProductID = p_product_id;
  UPDATE Product SET Status = IF(p_status = 'ACTIVE' AND v_stock = 0, 'OUT_OF_STOCK', p_status) WHERE ProductID = p_product_id;
  SELECT p_product_id AS ProductID;
END $$

-- =====================================================================
-- G. TRIGGERS
-- =====================================================================

-- T1. A customer profile may only be attached to an account with role CUSTOMER (BR2).
DROP TRIGGER IF EXISTS trg_customer_before_insert $$
CREATE TRIGGER trg_customer_before_insert BEFORE INSERT ON Customer FOR EACH ROW
BEGIN
  IF (SELECT Role FROM Users WHERE UserID = NEW.UserID) <> 'CUSTOMER' THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'A customer profile requires an account with role CUSTOMER.';
  END IF;
END $$

-- T2. A seller profile may only be attached to an account with role SELLER (BR2).
DROP TRIGGER IF EXISTS trg_seller_before_insert $$
CREATE TRIGGER trg_seller_before_insert BEFORE INSERT ON Seller FOR EACH ROW
BEGIN
  IF (SELECT Role FROM Users WHERE UserID = NEW.UserID) <> 'SELLER' THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'A seller profile requires an account with role SELLER.';
  END IF;
END $$

-- T3. An order must be delivered to an address of the ordering customer (BR7).
DROP TRIGGER IF EXISTS trg_orders_before_insert $$
CREATE TRIGGER trg_orders_before_insert BEFORE INSERT ON Orders FOR EACH ROW
BEGIN
  IF NOT EXISTS (SELECT 1 FROM Address WHERE AddressID = NEW.AddressID AND CustomerID = NEW.CustomerID) THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'The delivery address does not belong to this customer.';
  END IF;
END $$

-- T4. Stock validation and purchase-time price for every new order line (BR6, BR8).
DROP TRIGGER IF EXISTS trg_orderitem_before_insert $$
CREATE TRIGGER trg_orderitem_before_insert BEFORE INSERT ON OrderItem FOR EACH ROW
BEGIN
  DECLARE v_status VARCHAR(20);
  DECLARE v_price DECIMAL(10,2);
  DECLARE v_stock INT;
  DECLARE v_name VARCHAR(150);
  DECLARE v_msg VARCHAR(255);
  SELECT p.Status, p.Price, i.Quantity, p.ProductName INTO v_status, v_price, v_stock, v_name
  FROM Product p JOIN Inventory i ON i.ProductID = p.ProductID WHERE p.ProductID = NEW.ProductID;
  IF v_status IS NULL OR v_status <> 'ACTIVE' THEN
    SET v_msg = CONCAT('Product "', COALESCE(v_name, NEW.ProductID), '" is no longer available.');
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = v_msg;
  END IF;
  IF v_stock < NEW.Quantity THEN
    SET v_msg = CONCAT('Insufficient stock for "', v_name, '": only ', v_stock, ' left.');
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = v_msg;
  END IF;
  SET NEW.UnitPrice = v_price;
END $$

-- T5. After a line is inserted: deduct stock once and add the line to the order total.
DROP TRIGGER IF EXISTS trg_orderitem_after_insert $$
CREATE TRIGGER trg_orderitem_after_insert AFTER INSERT ON OrderItem FOR EACH ROW
BEGIN
  UPDATE Inventory SET Quantity = Quantity - NEW.Quantity WHERE ProductID = NEW.ProductID;
  UPDATE Orders SET TotalAmount = TotalAmount + NEW.Quantity * NEW.UnitPrice WHERE OrderID = NEW.OrderID;
END $$

-- T6. Cancelling an order puts the ordered quantities back into stock.
DROP TRIGGER IF EXISTS trg_orders_after_update $$
CREATE TRIGGER trg_orders_after_update AFTER UPDATE ON Orders FOR EACH ROW
BEGIN
  IF NEW.Status = 'CANCELLED' AND OLD.Status <> 'CANCELLED' THEN
    UPDATE Inventory i JOIN OrderItem oi ON oi.ProductID = i.ProductID
    SET i.Quantity = i.Quantity + oi.Quantity
    WHERE oi.OrderID = NEW.OrderID;
  END IF;
END $$

-- T7. Every stock change refreshes LastUpdated and keeps Product.Status in line with the stock.
DROP TRIGGER IF EXISTS trg_inventory_before_update $$
CREATE TRIGGER trg_inventory_before_update BEFORE UPDATE ON Inventory FOR EACH ROW
BEGIN
  SET NEW.LastUpdated = NOW();
  IF NEW.Quantity = 0 AND OLD.Quantity > 0 THEN
    UPDATE Product SET Status = 'OUT_OF_STOCK' WHERE ProductID = NEW.ProductID AND Status = 'ACTIVE';
  ELSEIF NEW.Quantity > 0 AND OLD.Quantity = 0 THEN
    UPDATE Product SET Status = 'ACTIVE' WHERE ProductID = NEW.ProductID AND Status = 'OUT_OF_STOCK';
  END IF;
END $$

-- T8. A shipment may only contain items of its own order whose products belong to its own seller (BR11).
DROP TRIGGER IF EXISTS trg_shipmentitem_before_insert $$
CREATE TRIGGER trg_shipmentitem_before_insert BEFORE INSERT ON ShipmentItem FOR EACH ROW
BEGIN
  IF NOT EXISTS (SELECT 1 FROM Shipment sh
                 JOIN OrderItem oi ON oi.OrderItemID = NEW.OrderItemID
                 JOIN Product p ON p.ProductID = oi.ProductID
                 WHERE sh.ShipmentID = NEW.ShipmentID AND oi.OrderID = sh.OrderID AND p.SellerID = sh.SellerID) THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'An order item can only be shipped by its own seller within its own order.';
  END IF;
END $$

-- T9. Recalculate the order status whenever a shipment changes status.
DROP TRIGGER IF EXISTS trg_shipment_after_update $$
CREATE TRIGGER trg_shipment_after_update AFTER UPDATE ON Shipment FOR EACH ROW
BEGIN
  DECLARE v_items INT;
  DECLARE v_assigned INT;
  DECLARE v_preparing INT;
  DECLARE v_shipped INT;
  IF NEW.Status <> OLD.Status THEN
    SELECT COUNT(*) INTO v_items FROM OrderItem WHERE OrderID = NEW.OrderID;
    SELECT COUNT(*) INTO v_assigned FROM ShipmentItem si JOIN Shipment sh ON sh.ShipmentID = si.ShipmentID WHERE sh.OrderID = NEW.OrderID;
    SELECT SUM(Status = 'PREPARING'), SUM(Status = 'SHIPPED') INTO v_preparing, v_shipped FROM Shipment WHERE OrderID = NEW.OrderID;
    UPDATE Orders
    SET Status = CASE
                   WHEN v_assigned = v_items AND v_preparing = 0 AND v_shipped = 0 THEN 'DELIVERED'
                   WHEN v_assigned = v_items AND v_preparing = 0 THEN 'SHIPPED'
                   ELSE 'PROCESSING'
                 END
    WHERE OrderID = NEW.OrderID AND Status <> 'CANCELLED';
  END IF;
END $$

-- T10. Reviews are accepted only for products the customer received in a delivered order (BR12).
DROP TRIGGER IF EXISTS trg_review_before_insert $$
CREATE TRIGGER trg_review_before_insert BEFORE INSERT ON Review FOR EACH ROW
BEGIN
  IF NOT EXISTS (SELECT 1 FROM Orders o JOIN OrderItem oi ON oi.OrderID = o.OrderID
                 WHERE o.CustomerID = NEW.CustomerID AND oi.ProductID = NEW.ProductID AND o.Status = 'DELIVERED') THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'You can only review products that have been delivered to you.';
  END IF;
END $$

-- T11. Suspending a store withdraws all of its products from sale.
DROP TRIGGER IF EXISTS trg_seller_after_update $$
CREATE TRIGGER trg_seller_after_update AFTER UPDATE ON Seller FOR EACH ROW
BEGIN
  IF NEW.Status = 'SUSPENDED' AND OLD.Status <> 'SUSPENDED' THEN
    UPDATE Product SET Status = 'INACTIVE' WHERE SellerID = NEW.SellerID AND Status <> 'INACTIVE';
  END IF;
END $$

DELIMITER ;

-- End of file
