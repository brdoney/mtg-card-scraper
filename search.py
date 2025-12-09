#!/usr/bin/env python3

import json
from pathlib import Path
from scraping import scrape_products
import sys
import urllib.parse

search_text = sys.argv[1]
search_text_encoded = urllib.parse.quote_plus(search_text)

search_link_formats = {
    "forge": "https://theforgecville.crystalcommerce.com/products/search?q={search_text}&page={page}&c=8",
    "endg": "https://shop.theendgames.co/products/search?q={search_text}&page={page}&c=8",
}

products = []
for store, search_link_format in search_link_formats.items():
    print(store)
    link_format = search_link_format.format(
        search_text=search_text_encoded, page="{page}"
    )
    products.extend(scrape_products(store, link_format, search_text))

out = Path("./out/search")
out.mkdir(exist_ok=True)

dest = out / f"{hash(search_text_encoded)}.json"
with dest.open("w") as f:
    json.dump([p._asdict() for p in products], f, indent=2)

print(dest)
