-----------------------------------------------------------------
-- Run this script once to set up the Snowflake environment.
-- Fill in passwords before running.
-----------------------------------------------------------------

-----------------------------------------------------------------
-- Database and schemas
-----------------------------------------------------------------
CREATE WAREHOUSE IF NOT EXISTS COMPUTE_WH;
USE WAREHOUSE COMPUTE_WH;

CREATE DATABASE IF NOT EXISTS CRYPTO_PIPELINE;

CREATE SCHEMA IF NOT EXISTS CRYPTO_PIPELINE.RAW;
CREATE SCHEMA IF NOT EXISTS CRYPTO_PIPELINE.DEV;

USE DATABASE CRYPTO_PIPELINE;
USE SCHEMA RAW;



---------------------------------------------------------
-- Create tables
---------------------------------------------------------

-- Raw tables
CREATE TABLE IF NOT EXISTS CRYPTO_PIPELINE.RAW.COINGECKO_OHLC (
    coin_id      VARCHAR,
    price_date   DATE,
    open_price   FLOAT,
    high_price   FLOAT,
    low_price    FLOAT,
    close_price  FLOAT,
    created_at   TIMESTAMP_TZ
);

CREATE TABLE IF NOT EXISTS CRYPTO_PIPELINE.RAW.COINGECKO_MARKET_CHART (
    coin_id          VARCHAR,
    price_date       DATE,
    price_usd        FLOAT,
    market_cap_usd   FLOAT,
    total_volume_usd FLOAT,
    created_at       TIMESTAMP_TZ
);



-----------------------------------------------------------------
-- Role + user for Python ingestion
-----------------------------------------------------------------
USE ROLE ACCOUNTADMIN;

CREATE ROLE IF NOT EXISTS CRYPTO_LOADER;
GRANT ROLE CRYPTO_LOADER TO ROLE ACCOUNTADMIN;


CREATE USER IF NOT EXISTS python_loader
    LOGIN_NAME = 'python_loader'
    PASSWORD = '<<password>>'
    DEFAULT_ROLE = CRYPTO_LOADER
    DEFAULT_WAREHOUSE = 'COMPUTE_WH'
    DEFAULT_NAMESPACE = 'CRYPTO_PIPELINE.RAW'
    COMMENT = 'Used by Python ingestion scripts';

GRANT ROLE CRYPTO_LOADER TO USER python_loader;
GRANT USAGE  ON WAREHOUSE COMPUTE_WH TO ROLE CRYPTO_LOADER;
GRANT USAGE  ON DATABASE  CRYPTO_PIPELINE TO ROLE CRYPTO_LOADER;
GRANT USAGE  ON SCHEMA CRYPTO_PIPELINE.RAW TO ROLE CRYPTO_LOADER;
GRANT CREATE TABLE ON SCHEMA CRYPTO_PIPELINE.RAW TO ROLE CRYPTO_LOADER;
GRANT INSERT, SELECT ON FUTURE TABLES IN SCHEMA CRYPTO_PIPELINE.RAW TO ROLE CRYPTO_LOADER;