import httpx
from fastapi import FastAPI
from pydantic import BaseModel
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from typing import Dict, Any, List
import asyncio
import time
from dotenv import dotenv_values
import os

app = FastAPI()
scheduler = AsyncIOScheduler()
config = dotenv_values(".env")

API_KEY = config["API_KEY"]
OPENSEA_API_URL = "https://api.opensea.io/api/v2/listings/collection/{collection_slug}/all?limit=30"
OPENSEA_API_ASSET_URL = "https://api.opensea.io/api/v1/assets?token_ids={token_id}&collection_slug={collection_slug}&include_orders=false"
OPENSEA_API_COL_STAT = "https://api.opensea.io/api/v1/collection/{collection_slug}/stats"

# Replace with your specific NFT collection slugs
collections = [
    # "nakamigos",
    # "goblintownwtf",
    # "vibers-2",
    # "brozo",
    # "sandbox",
    # "y00ts",
]

offers_data = {slug: [] for slug in collections}
stat_data = {slug: [] for slug in collections}


class Offer(BaseModel):
    id: str
    currency: str
    price: float
    order_hash: str
    image_url: str

async def fetch_stats(collection_slug):
    headers = {
        "accept": "application/json",
        "X-API-KEY": API_KEY
    }
    return_data = {}
    async with httpx.AsyncClient() as client:
        retry_count = 0
        while retry_count < 3:
            try:
                response = await client.get(OPENSEA_API_COL_STAT.format(collection_slug=collection_slug), headers=headers)
                response.raise_for_status()  # raise an exception if the response has an HTTP error status code
                data = response.json()
                return_data["floor_price"] = data["stats"]["floor_price"]
                return_data["one_day_volume"] = data["stats"]["one_day_volume"]
                break  # break out of the loop if the request succeeds
            except (httpx.TimeoutException, httpx.HTTPError, httpx.RequestError):
                # catch exceptions that indicate a temporary failure (e.g. network error, server error)
                if retry_count == 2:
                    raise  # raise the exception if we've reached the maximum number of retries
                retry_count += 1
                time.sleep(2)  # wait 2 seconds before the next attempt

    return return_data

async def fetch_asset_image_url(collection_slug: str, token_id: str):
    headers = {
        "X-API-KEY": API_KEY
    }
    async with httpx.AsyncClient() as client:
        for attempt in range(5):
            print(collection_slug)
            print(token_id)
            print(attempt)
            try:
                response = await client.get(OPENSEA_API_ASSET_URL.format(collection_slug=collection_slug, token_id=token_id), headers=headers)
                data = response.json()
                # print(data["assets"][0]["image_thumbnail_url"])
                # print(data["assets"][0])

                if response.status_code == 200 and "image_thumbnail_url" in data["assets"][0]:
                    return data["assets"][0]["image_thumbnail_url"]
            except httpx.RequestError:
                pass  # Ignore request errors and retry

            await asyncio.sleep(1)  # Add a delay between retries

    return ""  # Return an empty string if all attempts fail

async def fetch_offers(collection_slug):
    headers = {
        "accept": "application/json",
        "X-API-KEY": API_KEY
    }
    async with httpx.AsyncClient() as client:
        retry_count = 0
        while retry_count < 3:
            try:
                response = await client.get(OPENSEA_API_URL.format(collection_slug=collection_slug), headers=headers)
                response.raise_for_status()  # raise an exception if the response has an HTTP error status code
                data = response.json()
                break  # break out of the loop if the request succeeds
            except (httpx.TimeoutException, httpx.HTTPError, httpx.RequestError):
                # catch exceptions that indicate a temporary failure (e.g. network error, server error)
                if retry_count == 2:
                    raise  # raise the exception if we've reached the maximum number of retries
                retry_count += 1
                time.sleep(2)  # wait 2 seconds before the next attempt


    offers = []
    for order in data["listings"]:
        try:
            token_id = order["protocol_data"]["parameters"]["offer"][0]["identifierOrCriteria"]
            image_url = "" # await fetch_asset_image_url(collection_slug, token_id)
            offer = Offer(
                id=token_id,
                currency=order["price"]["current"]["currency"],
                price=float(order["price"]["current"]["value"]) / 1e18,
                order_hash=order["order_hash"],
                image_url=image_url,
            )

            offers.append(offer)
        except (TypeError, KeyError, ValueError):
            pass  # Ignore orders with data type mismatches or missing fields

    return offers


async def update_offers_data():
    global offers_data
    for slug in collections:
        offers_data[slug] = await fetch_offers(slug)


@scheduler.scheduled_job("interval", seconds=6000)  # Adjust the interval as needed
async def scheduled_fetch():
    await update_offers_data()


@app.on_event("startup")
async def on_startup():
    scheduler.start()
    #await update_offers_data()


@app.on_event("shutdown")
async def on_shutdown():
    scheduler.shutdown()


@app.get("/offers/{collection_slug}", response_model=List[Dict[str, Any]])
async def get_offers(collection_slug: str):
    if collection_slug not in offers_data:
        offers = await fetch_offers(collection_slug)
        if not offers:
            return [{"error": "Collection not found"}]
        offers_data[collection_slug] = offers
    return [offer.dict() for offer in offers_data[collection_slug]]

@app.get("/stats/{collection_slug}", response_model=Dict[str, Any])
async def get_stats(collection_slug: str):
    if collection_slug not in stat_data:
        stat = await fetch_stats(collection_slug)
        if not stat:
            return [{"error": "Collection not found"}]
        stat_data[collection_slug] = stat
    return stat_data[collection_slug]

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("nft_server:app", host="0.0.0.0", port=8000)
