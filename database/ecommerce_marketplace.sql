-- CSE301 Multi-Vendor E-Commerce Marketplace
CREATE DATABASE IF NOT EXISTS ecommerce_marketplace;
USE ecommerce_marketplace;

CREATE TABLE `Users` (
  `UserID` INT NOT NULL AUTO_INCREMENT,
  `Email` VARCHAR(100) NOT NULL,
  `PasswordHash` VARCHAR(255) NOT NULL,
  `Role` ENUM('CUSTOMER','SELLER','ADMIN') NOT NULL,
  `Status` VARCHAR(20) NOT NULL,
  PRIMARY KEY (`UserID`),
  UNIQUE (`Email`)
) ENGINE=InnoDB;

CREATE TABLE `Customer` (
  `CustomerID` INT NOT NULL AUTO_INCREMENT,
  `UserID` INT NOT NULL,
  `FullName` VARCHAR(100) NOT NULL,
  `Phone` VARCHAR(20),
  PRIMARY KEY (`CustomerID`),
  UNIQUE (`UserID`),
  CONSTRAINT `fk_customer_userid` FOREIGN KEY (`UserID`) REFERENCES `Users` (`UserID`)
) ENGINE=InnoDB;

CREATE TABLE `Seller` (
  `SellerID` INT NOT NULL AUTO_INCREMENT,
  `UserID` INT NOT NULL,
  `StoreName` VARCHAR(100) NOT NULL,
  `Status` VARCHAR(20) NOT NULL,
  PRIMARY KEY (`SellerID`),
  UNIQUE (`UserID`),
  CONSTRAINT `fk_seller_userid` FOREIGN KEY (`UserID`) REFERENCES `Users` (`UserID`)
) ENGINE=InnoDB;

CREATE TABLE `Category` (
  `CategoryID` INT NOT NULL AUTO_INCREMENT,
  `CategoryName` VARCHAR(100) NOT NULL,
  `Description` TEXT,
  PRIMARY KEY (`CategoryID`)
) ENGINE=InnoDB;

CREATE TABLE `Product` (
  `ProductID` INT NOT NULL AUTO_INCREMENT,
  `SellerID` INT NOT NULL,
  `CategoryID` INT NOT NULL,
  `ProductName` VARCHAR(150) NOT NULL,
  `Price` DECIMAL(10,2) NOT NULL,
  `Status` VARCHAR(20) NOT NULL,
  PRIMARY KEY (`ProductID`),
  CONSTRAINT `fk_product_sellerid` FOREIGN KEY (`SellerID`) REFERENCES `Seller` (`SellerID`),
  CONSTRAINT `fk_product_categoryid` FOREIGN KEY (`CategoryID`) REFERENCES `Category` (`CategoryID`),
  CONSTRAINT chk_product_price CHECK (Price > 0)
) ENGINE=InnoDB;

CREATE TABLE `Inventory` (
  `ProductID` INT NOT NULL,
  `Quantity` INT NOT NULL,
  `LastUpdated` DATETIME,
  PRIMARY KEY (`ProductID`),
  CONSTRAINT `fk_inventory_productid` FOREIGN KEY (`ProductID`) REFERENCES `Product` (`ProductID`),
  CONSTRAINT chk_inventory_quantity CHECK (Quantity >= 0)
) ENGINE=InnoDB;

CREATE TABLE `Address` (
  `AddressID` INT NOT NULL AUTO_INCREMENT,
  `CustomerID` INT NOT NULL,
  `City` VARCHAR(100) NOT NULL,
  `District` VARCHAR(100) NOT NULL,
  `AddressLine` VARCHAR(255) NOT NULL,
  PRIMARY KEY (`AddressID`),
  CONSTRAINT `fk_address_customerid` FOREIGN KEY (`CustomerID`) REFERENCES `Customer` (`CustomerID`)
) ENGINE=InnoDB;

CREATE TABLE `Cart` (
  `CartID` INT NOT NULL AUTO_INCREMENT,
  `CustomerID` INT NOT NULL,
  `CreatedAt` DATETIME NOT NULL,
  PRIMARY KEY (`CartID`),
  UNIQUE (`CustomerID`),
  CONSTRAINT `fk_cart_customerid` FOREIGN KEY (`CustomerID`) REFERENCES `Customer` (`CustomerID`)
) ENGINE=InnoDB;

CREATE TABLE `CartItem` (
  `CartID` INT NOT NULL,
  `ProductID` INT NOT NULL,
  `Quantity` INT NOT NULL,
  PRIMARY KEY (`CartID`, `ProductID`),
  CONSTRAINT `fk_cartitem_cartid` FOREIGN KEY (`CartID`) REFERENCES `Cart` (`CartID`),
  CONSTRAINT `fk_cartitem_productid` FOREIGN KEY (`ProductID`) REFERENCES `Product` (`ProductID`),
  CONSTRAINT chk_cartitem_quantity CHECK (Quantity > 0)
) ENGINE=InnoDB;

CREATE TABLE `Orders` (
  `OrderID` INT NOT NULL AUTO_INCREMENT,
  `CustomerID` INT NOT NULL,
  `AddressID` INT NOT NULL,
  `OrderDate` DATETIME NOT NULL,
  `TotalAmount` DECIMAL(12,2) NOT NULL,
  `Status` VARCHAR(20) NOT NULL,
  PRIMARY KEY (`OrderID`),
  CONSTRAINT `fk_orders_customerid` FOREIGN KEY (`CustomerID`) REFERENCES `Customer` (`CustomerID`),
  CONSTRAINT `fk_orders_addressid` FOREIGN KEY (`AddressID`) REFERENCES `Address` (`AddressID`)
) ENGINE=InnoDB;

CREATE TABLE `OrderItem` (
  `OrderItemID` INT NOT NULL AUTO_INCREMENT,
  `OrderID` INT NOT NULL,
  `ProductID` INT NOT NULL,
  `Quantity` INT NOT NULL,
  `UnitPrice` DECIMAL(10,2) NOT NULL,
  PRIMARY KEY (`OrderItemID`),
  CONSTRAINT `fk_orderitem_orderid` FOREIGN KEY (`OrderID`) REFERENCES `Orders` (`OrderID`),
  CONSTRAINT `fk_orderitem_productid` FOREIGN KEY (`ProductID`) REFERENCES `Product` (`ProductID`),
  CONSTRAINT chk_orderitem_quantity CHECK (Quantity > 0)
) ENGINE=InnoDB;

CREATE TABLE `Payment` (
  `PaymentID` INT NOT NULL AUTO_INCREMENT,
  `OrderID` INT NOT NULL,
  `Amount` DECIMAL(12,2) NOT NULL,
  `PaymentMethod` VARCHAR(30) NOT NULL,
  `Status` VARCHAR(20) NOT NULL,
  PRIMARY KEY (`PaymentID`),
  CONSTRAINT `fk_payment_orderid` FOREIGN KEY (`OrderID`) REFERENCES `Orders` (`OrderID`)
) ENGINE=InnoDB;

CREATE TABLE `Shipment` (
  `ShipmentID` INT NOT NULL AUTO_INCREMENT,
  `OrderID` INT NOT NULL,
  `SellerID` INT NOT NULL,
  `TrackingNumber` VARCHAR(100),
  `Status` VARCHAR(20) NOT NULL,
  PRIMARY KEY (`ShipmentID`),
  CONSTRAINT `fk_shipment_orderid` FOREIGN KEY (`OrderID`) REFERENCES `Orders` (`OrderID`),
  CONSTRAINT `fk_shipment_sellerid` FOREIGN KEY (`SellerID`) REFERENCES `Seller` (`SellerID`)
) ENGINE=InnoDB;

CREATE TABLE `ShipmentItem` (
  `ShipmentItemID` INT NOT NULL AUTO_INCREMENT,
  `ShipmentID` INT NOT NULL,
  `OrderItemID` INT NOT NULL,
  PRIMARY KEY (`ShipmentItemID`),
  UNIQUE (`OrderItemID`),
  CONSTRAINT `fk_shipmentitem_shipmentid` FOREIGN KEY (`ShipmentID`) REFERENCES `Shipment` (`ShipmentID`),
  CONSTRAINT `fk_shipmentitem_orderitemid` FOREIGN KEY (`OrderItemID`) REFERENCES `OrderItem` (`OrderItemID`)
) ENGINE=InnoDB;

CREATE TABLE `Review` (
  `ReviewID` INT NOT NULL AUTO_INCREMENT,
  `CustomerID` INT NOT NULL,
  `ProductID` INT NOT NULL,
  `Rating` INT NOT NULL,
  `Comment` TEXT,
  PRIMARY KEY (`ReviewID`),
  CONSTRAINT `fk_review_customerid` FOREIGN KEY (`CustomerID`) REFERENCES `Customer` (`CustomerID`),
  CONSTRAINT `fk_review_productid` FOREIGN KEY (`ProductID`) REFERENCES `Product` (`ProductID`),
  CONSTRAINT chk_review_rating CHECK (Rating BETWEEN 1 AND 5)
) ENGINE=InnoDB;

-- Cross-table consistency (shipment seller/order match, address ownership, user role profiles) requires additional validation in triggers or application transactions.