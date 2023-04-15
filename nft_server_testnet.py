import httpx
from fastapi import FastAPI
from pydantic import BaseModel
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from typing import Dict, Any, List

app = FastAPI()
scheduler = AsyncIOScheduler()

# for testnet
OPENSEA_API_URL = "https://testnets-api.opensea.io/api/v1/assets?order_direction=desc&offset=0&limit=20&collection={collection_slug}&include_orders=true"

# Replace with your specific NFT collection slugs
collections = [
    "boredapeyachtclubgoerli",
    # "beanz-collection-goelri",
]

offers_data = {slug: [] for slug in collections}


class Offer(BaseModel):
    id: int
    price: float
    link: str


async def fetch_offers(collection_slug):
    async with httpx.AsyncClient() as client:
        response = await client.get(OPENSEA_API_URL.format(collection_slug=collection_slug))
        data = response.json()

    offers = []
    for asset in data["assets"]:
        if asset["seaport_sell_orders"]:
            try:
                offer = Offer(
                    id=int(asset["id"]),
                    price=float(asset["seaport_sell_orders"][0]["current_price"]) / 1e18,
                    link=asset["permalink"],
                )
                offers.append(offer)
            except (TypeError, KeyError, ValueError):
                pass  # Ignore assets with data type mismatches or missing fields

    return offers


async def update_offers_data():
    global offers_data
    for slug in collections:
        offers_data[slug] = await fetch_offers(slug)


@scheduler.scheduled_job("interval", seconds=60)  # Adjust the interval as needed
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
