import requests
from dotenv import load_dotenv
import snowflake.connector
import os
import json
from datetime import datetime, timezone, timedelta


load_dotenv()


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


def get_market_chart(coin_id: str, number_of_days: int) -> list:
    """
    Fetches daily market data (price, market cap, volume) for a given coin
    from the CoinGecko market chart API and returns one record per day.

    CoinGecko returns three parallel lists — prices, market_caps, total_volumes —
    each containing [timestamp_ms, value] pairs at matching indices.
    This function zips them together into one record per day using the shared index.

    Args:
        coin_id (str):        CoinGecko coin slug, e.g. "bitcoin"
        number_of_days (int): Number of past days to fetch, e.g. 90

    Returns:
        list[dict]: One record per day, each containing:
            - coin_id          (str)   : CoinGecko coin slug
            - price_date       (str)   : Date in YYYY-MM-DD format
            - price_usd        (float) : Daily closing price in USD
            - market_cap_usd   (float) : Market capitalisation in USD
            - total_volume_usd (float) : Total trading volume in USD
            - created_at       (str)   : UTC timestamp of when this record was fetched

    API docs:
        https://docs.coingecko.com/reference/coins-id-market-chart
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

    market_data = response.json()

    records = []

    prices = market_data["prices"]
    market_caps = market_data["market_caps"]
    total_volumes = market_data["total_volumes"]

    for loop, d in enumerate(market_data):
        timestamp = prices[loop][0]
        price_date = datetime.fromtimestamp(
            timestamp / 1000, tz=timezone.utc).strftime("%Y-%m-%d")
        created_at = datetime.now(timezone.utc).isoformat()
        records.append(
            {"coin_id": coin_id,
             "price_date": price_date,
             "price_usd": prices[loop][1],
             "market_cap_usd": market_caps[loop][1],
             "total_volume_usd": total_volumes[loop][1],
             "created_at": created_at}
        )

    print(records)
    return records


def get_ohlc(coin_id: str, number_of_days: int) -> list:
    """
    Fetches daily OHLC (Open, High, Low, Close) price data for a given coin from the CoinGecko API and returns one record per day.

    CoinGecko returns candles at 4-hour intervals. The daily closing price is represented by the candle timestamped at 00:00:00 UTC of the NEXT day.
    For example, the candle at 2026-04-26 00:00:00 is the close of 2026-04-25. This function filters for midnight candles only and shifts the date back
    by one day so each record reflects the correct calendar date.

    Args:
        coin_id (str):              CoinGecko coin slug, e.g. "bitcoin"
        number_of_days (int):       Number of past days to fetch, e.g. 90

    Returns:
        list[dict]: One record per day, each containing:
            - coin_id     (str)   : CoinGecko coin slug
            - price_date  (str)   : Date in YYYY-MM-DD format
            - open_price  (float) : Opening price in USD
            - high_price  (float) : Highest price of the day in USD
            - low_price   (float) : Lowest price of the day in USD
            - close_price (float) : Closing price in USD
            - created_at  (str)   : UTC timestamp of when this record was fetched

    API docs:
        https://docs.coingecko.com/reference/coins-id-ohlc
    """

    url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/ohlc"
    headers = {"x-cg-demo-api-key": os.getenv("COINGECKO_API_KEY")}
    params = {
        "vs_currency": "usd",
        "days": number_of_days,
        "precision": 2
    }

    response = requests.get(url, params=params, headers=headers)

    ohlc = response.json()

    records = []

    for d in range(len(ohlc)):
        timestamp = ohlc[d][0]
        ohlc_date = datetime.fromtimestamp(
            timestamp / 1000, tz=timezone.utc)
        created_at = datetime.now(timezone.utc).isoformat()
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


if __name__ == "__main__":
    get_market_chart("bitcoin", 30)
    get_ohlc("bitcoin", 30)
