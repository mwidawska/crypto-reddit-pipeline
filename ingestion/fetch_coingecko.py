import requests
from dotenv import load_dotenv
import snowflake.connector
import os
import json
from datetime import datetime, timezone, timedelta


load_dotenv()

COIN_ID = "bitcoin"
# OHLC API only stores daily records for the past 30 days.
OHLC_MAX_DAYS = 30

# --------------------------------------------------------------------------------
# Connect to Snowflake
# --------------------------------------------------------------------------------


def connect_to_snowflake():
    """
    Establishes a connection to the Snowflake data warehouse using credentials
    stored in environment variables.
    """
    return snowflake.connector.connect(
        account=os.getenv("SNOWFLAKE_ACCOUNT_ID"),
        user=os.getenv("SNOWFLAKE_USER"),
        password=os.getenv("SNOWFLAKE_PASSWORD"),
        database="CRYPTO_PIPELINE",
        schema="RAW",
        warehouse="COMPUTE_WH"
    )


# --------------------------------------------------------------------------------
# Fetch data from API
# --------------------------------------------------------------------------------

def get_market_chart(coin_id: str, number_of_days: int) -> list:
    """
    Fetches daily market data (price, market cap, volume) for a given coin from the CoinGecko 
    market chart API and returns one record per day.

    CoinGecko returns three lists (prices, market_caps, total_volumes) each containing [timestamp_ms, value] pairs.
    This function zips them together into one record per day using the shared index.

    CoinGecko represents the daily close as the 00:00:00 UTC timestamp of the following day. 
    This function filters for midnight timestamps only and shifts the date back by one day so each record is stored under the correct date.
    """

    url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart"
    headers = {"x-cg-demo-api-key": os.getenv("COINGECKO_API_KEY")}
    params = {
        "vs_currency": "usd",
        "days": number_of_days,
        "interval": "daily",
        "precision": 2
    }

    response = requests.get(url, params=params, headers=headers)

    response.raise_for_status()

    market_data = response.json()

    records = []

    prices = market_data["prices"]
    market_caps = market_data["market_caps"]
    total_volumes = market_data["total_volumes"]

    created_at = datetime.now(timezone.utc).isoformat()

    for loop in range(len(prices)):
        timestamp = prices[loop][0]
        system_date = datetime.fromtimestamp(
            timestamp / 1000, tz=timezone.utc)
        if system_date.hour == 0 and system_date.minute == 0:
            price_date = (system_date - timedelta(days=1)
                          ).strftime("%Y-%m-%d")
            records.append(
                {"coin_id": coin_id,
                 "price_date": price_date,
                 "price_usd": prices[loop][1],
                 "market_cap_usd": market_caps[loop][1],
                 "total_volume_usd": total_volumes[loop][1],
                 "created_at": created_at}
            )
    return records


def get_ohlc(coin_id: str, number_of_days: int) -> list:
    """
    Fetches daily OHLC (Open, High, Low, Close) price data for a given coin from the CoinGecko API and returns one record per day.

    CoinGecko returns candles at 4-hour intervals. The daily closing price is represented by the candle timestamped at 00:00:00 UTC of the NEXT day.
    For example, the candle at 2026-04-26 00:00:00 is the close of 2026-04-25. This function filters for midnight candles only and shifts the date back
    by one day so each record reflects the correct calendar date.
    """

    url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/ohlc"
    headers = {"x-cg-demo-api-key": os.getenv("COINGECKO_API_KEY")}
    params = {
        "vs_currency": "usd",
        "days": number_of_days,
        "precision": 2
    }

    response = requests.get(url, params=params, headers=headers)

    response.raise_for_status()

    ohlc = response.json()

    records = []

    created_at = datetime.now(timezone.utc).isoformat()

    for d in range(len(ohlc)):
        timestamp = ohlc[d][0]
        ohlc_date = datetime.fromtimestamp(
            timestamp / 1000, tz=timezone.utc)
        if ohlc_date.hour == 0 and ohlc_date.minute == 0:
            # CoinGecko represents the daily close as the 00:00:00 candle of the following day.
            # Subtracting one day maps it back to the correct calendar date.
            price_date = (ohlc_date - timedelta(days=1)).strftime("%Y-%m-%d")
            records.append(
                {"coin_id": coin_id,
                 "price_date": price_date,
                 "open_price": ohlc[d][1],
                 "high_price": ohlc[d][2],
                 "low_price": ohlc[d][3],
                 "close_price": ohlc[d][4],
                 "created_at": created_at}
            )

    return records


# --------------------------------------------------------------------------------
# Insert data into Snowflake tables
# --------------------------------------------------------------------------------

def insert_market_chart(cursor, records):
    """   
    Inserts market chart records into RAW.COINGECKO_MARKET_CHART.

    Args:
        cursor:           Active Snowflake cursor.
        records (list):   Output of get_market_chart().
    """
    sql = """
    INSERT INTO RAW.COINGECKO_MARKET_CHART (coin_id, price_date, price_usd, market_cap_usd, total_volume_usd, created_at)
    VALUES (%(coin_id)s, %(price_date)s, %(price_usd)s, %(market_cap_usd)s, %(total_volume_usd)s, %(created_at)s)
    """
    cursor.executemany(sql, records)


def insert_ohlc(cursor, records):
    """   
    Inserts OHLC records into RAW.COINGECKO_OHLC.

    Args:
        cursor:           Active Snowflake cursor.
        records (list):   Output of get_ohlc().
    """
    sql = """
    INSERT INTO RAW.COINGECKO_OHLC (coin_id, price_date, open_price, high_price, low_price, close_price, created_at)
    VALUES (%(coin_id)s, %(price_date)s, %(open_price)s, %(high_price)s, %(low_price)s, %(close_price)s, %(created_at)s)
    """
    cursor.executemany(sql, records)


def load_to_snowflake(coin_id, days=OHLC_MAX_DAYS):
    """
    Fetches market chart and OHLC data for the given number of days
    and inserts both into Snowflake RAW tables in a single transaction.
    """

    market_chart_records = get_market_chart(coin_id, days)
    ohlc_records = get_ohlc(coin_id, days)

    conn = connect_to_snowflake()

    try:

        with conn.cursor() as cursor:
            insert_market_chart(cursor, market_chart_records)
            insert_ohlc(cursor, ohlc_records)
        conn.commit()

    except Exception as e:
        conn.rollback()
        print("Loading data failed:", e)
        raise

    finally:
        conn.close()


# --------------------------------------------------------------------------------
# Helper - counting number of missing records in a Snowflake table
# --------------------------------------------------------------------------------

def count_missing_records():
    """
    Checks the most recent date in RAW.COINGECKO_MARKET_CHART and returns
    the number of days between that date and yesterday — i.e. how many
    daily records are missing and need to be fetched.
    """

    conn = connect_to_snowflake()

    try:
        with conn.cursor() as cursor:
            cursor.execute("""SELECT price_date
                                FROM RAW.COINGECKO_MARKET_CHART
                                ORDER BY price_date DESC
                                LIMIT 1""")
            result = cursor.fetchone()
            if result is None:
                print(
                    f"Snowflake table is empty. Fetching {OHLC_MAX_DAYS} days of history.")
                return OHLC_MAX_DAYS
            else:
                last_date = result[0]
                yesterday = (datetime.now(timezone.utc) -
                             timedelta(days=1)).date()
                missing_records = (yesterday - last_date).days
                return missing_records

    except Exception as e:
        print("Failed to retrieve last record date from Snowflake:", e)
        raise

    finally:
        conn.close()


# --------------------------------------------------------------------------------
# Run final script to add missing records
# --------------------------------------------------------------------------------

if __name__ == "__main__":

    days = count_missing_records()

    if days <= OHLC_MAX_DAYS:
        load_to_snowflake(COIN_ID, days=days)
    else:
        print(
            f"Warning: {days} days missing but API limit is {OHLC_MAX_DAYS} days. Some historical data will have gaps.")
        load_to_snowflake(COIN_ID, days=OHLC_MAX_DAYS)
