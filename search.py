#!/usr/bin/env python3

import asyncio
import itertools
import json
import sys
import urllib.parse
from pathlib import Path

from scraping import Product, scrape_products

search_link_formats = {
    "forge": "https://theforgecville.crystalcommerce.com/products/search?q={search_text}&page={page}&c=8",
    "endg": "https://shop.theendgames.co/products/search?q={search_text}&page={page}&c=8",
}


async def _scrape_store(store_link_info: tuple[str, str], text: str) -> list[Product]:
    store, search_link_format = store_link_info
    text_encoded = urllib.parse.quote_plus(text)
    link_format = search_link_format.format(search_text=text_encoded, page="{page}")
    return await scrape_products(store, link_format, text, False)


async def search_card(text: str) -> tuple[list[Product], Path]:
    text_encoded = urllib.parse.quote_plus(text)

    futures = [_scrape_store(item, text) for item in search_link_formats.items()]

    results = await asyncio.gather(*futures)
    products = list(itertools.chain(*results))

    out = Path("./out/search")
    out.mkdir(exist_ok=True, parents=True)

    dest = out / f"{hash(text_encoded)}.json"
    with dest.open("w") as f:
        data = [p._asdict() for p in products]
        json.dump(data, f, indent=2)

    return products, dest


async def main():
    search_text = sys.argv[1]

    _, dest = await search_card(search_text)

    print(dest)


if __name__ == "__main__":
    asyncio.run(main())
