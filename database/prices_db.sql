CREATE DATABASE IF NOT EXISTS price_collection;
USE price_collection;

CREATE TABLE `price` (
  `ID` bigint NOT NULL AUTO_INCREMENT,
  `Product` varchar(255) NOT NULL,
  `Date` date NOT NULL,
  `Seller` varchar(255) NOT NULL,
  `Price` decimal(10,2) NOT NULL,
  PRIMARY KEY (`ID`),
  UNIQUE KEY `uq_product_date_seller` (`Product`,`Date`,`Seller`)
) ENGINE=InnoDB AUTO_INCREMENT=4 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
