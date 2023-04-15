import httpx
from fastapi import FastAPI
from pydantic import BaseModel
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from typing import Dict, Any, List

app = FastAPI()
scheduler = AsyncIOScheduler()

API_KEY = "4e9eeab87bc94be3a4f054a7b545e27d"
OPENSEA_API_URL = "https://api.opensea.io/api/v2/listings/collection/{collection_slug}/all?limit=10"


# Replace with your specific NFT collection slugs
collections = [
    "nakamigos",
]

offers_data = {slug: [] for slug in collections}


class Offer(BaseModel):
    id: str
    currency: str
    price: float
    order_hash: str


async def fetch_offers(collection_slug):
    headers = {
        "accept": "application/json",
        "X-API-KEY": API_KEY
    }
    async with httpx.AsyncClient() as client:
        response = await client.get(OPENSEA_API_URL.format(collection_slug=collection_slug), headers=headers)
        data = response.json()

    offers = []
    for order in data["listings"]:
        try:
            offer = Offer(
                id=order["protocol_data"]["parameters"]["offer"][0]["identifierOrCriteria"],
                currency=order["price"]["current"]["currency"],
                price=float(order["price"]["current"]["value"]) / 1e18,
                order_hash=order["order_hash"],
            )
            offers.append(offer)
        except (TypeError, KeyError, ValueError):
            pass  # Ignore orders with data type mismatches or missing fields

    return offers


async def update_offers_data():
    global offers_data
    for slug in collections:
        offers_data[slug] = await fetch_offers(slug)


@scheduler.scheduled_job("interval", seconds=600)  # Adjust the interval as needed
async def scheduled_fetch():
    await update_offers_data()


@app.on_event("startup")
async def on_startup():
    scheduler.start()
    await update_offers_data()


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

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("nft_server:app", host="0.0.0.0", port=8000)
