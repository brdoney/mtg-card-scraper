#!/usr/bin/env python3

import itertools
import json
import sys
import urllib.parse
from multiprocessing import Pool
from pathlib import Path
from typing import Any

from scraping import scrape_products

search_text = sys.argv[1]
search_text_encoded = urllib.parse.quote_plus(search_text)

search_link_formats = {
    "forge": "https://theforgecville.crystalcommerce.com/products/search?q={search_text}&page={page}&c=8",
    "endg": "https://shop.theendgames.co/products/search?q={search_text}&page={page}&c=8",
}


def _scrape_store(store_link_info: tuple[str, str]) -> list[dict[str, Any]]:
    store, search_link_format = store_link_info
    link_format = search_link_format.format(
        search_text=search_text_encoded, page="{page}"
    )
    return [
        p._asdict() for p in scrape_products(store, link_format, search_text, False)
    ]


if __name__ == "__main__":
    with Pool(len(search_link_formats)) as pool:
        items = pool.map(_scrape_store, search_link_formats.items())
        products = list(itertools.chain(*items))

    out = Path("./out/search")
    out.mkdir(exist_ok=True)

    dest = out / f"{hash(search_text_encoded)}.json"
    with dest.open("w") as f:
        json.dump(products, f, indent=2)

    print(dest)
