import json
import sys
from multiprocessing import Pool
from pathlib import Path

from scraping import scrape_products

link_templates = {
    # "theforge": "https://theforgecville.crystalcommerce.com/catalog/magic_the_gathering_singles-2025_expansion_sets-final_fantasy/16646?filter_by_stock=in-stock&page={page}&sort_by_price=1",
    # "theendgames": "https://shop.theendgames.co/catalog/magic_singles-2025_magic_sets-final_fantasy/12573?filter_by_stock=in-stock&page={page}&sort_by_price=1",
    # With fixed filters
    "forge": "https://theforgecville.crystalcommerce.com/catalog/magic_the_gathering_singles-2025_expansion_sets-final_fantasy/16646?filter%5B10%5D=&filter%5B11%5D=&filter%5B1259%5D=&filter%5B13%5D=&filter%5B17023%5D=&filter%5B348%5D=&filter%5B349%5D=&filter%5B361%5D=&filter%5B5%5D=&filter%5B6%5D=&filter%5B7%5D=&filter%5B8%5D=&filter%5B9%5D=&filter_by_stock=in-stock&filtered=1&page={page}&sort_by_price=1",
    # "endg": "https://shop.theendgames.co/catalog/magic_singles-2025_magic_sets-final_fantasy/12573?filter%5B10%5D=&filter%5B11%5D=&filter%5B13%5D=&filter%5B20617%5D=&filter%5B20618%5D=&filter%5B20619%5D=&filter%5B20620%5D=&filter%5B20621%5D=&filter%5B20622%5D=&filter%5B355%5D=&filter%5B356%5D=&filter%5B372%5D=&filter%5B373%5D=&filter%5B5%5D=&filter%5B6%5D=&filter%5B7%5D=&filter%5B8%5D=&filter%5B9%5D=&filter_by_stock=in-stock&filtered=1&page={page}&sort_by_price=1",
}

# Just to be safe
SCRAPE = True
if not SCRAPE:
    sys.exit(0)


def _scrape_catalog(store_link_info: tuple[str, str]) -> None:
    store, link_template = store_link_info
    products = [p._asdict() for p in scrape_products(store, link_template)]
    with (out_dir / f"{store}.json").open("w") as f:
        json.dump(products, f, indent=2)


if __name__ == "__main__":
    out_dir = Path("./out")
    out_dir.mkdir(exist_ok=True)

    with Pool(len(link_templates)) as pool:
        pool.map(_scrape_catalog, link_templates.items())
