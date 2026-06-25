#!/usr/bin/env python3

import asyncio
import itertools
import json
import sys
import urllib.parse
from pathlib import Path

from scraping import (
    Product,
    scrape_forge_api,
    scrape_products,
    scrape_tcgplayer_pro,
)

search_link_formats = {
    # "forge": "https://theforgecville.crystalcommerce.com/products/search?q={search_text}&page={page}&c=8",
    "endg": "https://shop.theendgames.co/products/search?q={search_text}&page={page}&c=8",
}

# Stores backed by a JSON POS-search API rather than Crystal Commerce HTML.
api_link_formats = {
    "forgenew": "https://forgegamesandhobbies.com/api/inventory-api.php",
}

# TCGplayer Pro storefronts (*.tcgplayerpro.com), keyed to their base URL.
tcg_pro_link_formats = {
    "lifelink": "https://lifelinkgames.tcgplayerpro.com",
}

# All store names that get searched, for display purposes.
store_names = (
    list(search_link_formats) + list(api_link_formats) + list(tcg_pro_link_formats)
)


async def _scrape_store(store_link_info: tuple[str, str], text: str) -> list[Product]:
    store, search_link_format = store_link_info
    text_encoded = urllib.parse.quote_plus(text)
    link_format = search_link_format.format(search_text=text_encoded, page="{page}")
    return await scrape_products(store, link_format, text, False)


async def search_card(text: str) -> tuple[list[Product], Path]:
    text_encoded = urllib.parse.quote_plus(text)

    futures = [_scrape_store(item, text) for item in search_link_formats.items()]
    futures += [
        scrape_forge_api(store, api_url, text, False)
        for store, api_url in api_link_formats.items()
    ]
    futures += [
        scrape_tcgplayer_pro(store, base_url, text, False)
        for store, base_url in tcg_pro_link_formats.items()
    ]

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
