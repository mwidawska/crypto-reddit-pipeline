import requests
from dotenv import load_dotenv
import snowflake.connector
import os
import json


def connect_to_snowflake():
    return snowflake.connector.connect(
        account=os.getenv("SNOWFLAKE_ACCOUNT_ID"),
        user=os.getenv("SNOWFLAKE_USER"),
        password=os.getenv("SNOWFLAKE_PASSWORD"),
        database="CRYPTO_PIPELINE",
        schema="RAW",
        warehouse="COMPUTE_WH"
    )


def get_market_chart(coin_id, number_of_days):

    url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart"

    load_dotenv()
    headers = {"x-cg-demo-api-key": os.getenv("COINGECKO_API_KEY")}

    params = {
        "vs_currency": "usd",
        "days": number_of_days,
        "interval": "daily"
    }

    response = requests.get(url, params=params, headers=headers)

    data = response.json()

    prices = data["prices"]
    market_caps = data["market_caps"]
    total_volumes = data["total_volumes"]


if __name__ == "__main__":
    get_market_chart("bitcoin", 90)
