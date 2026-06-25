import re
import urllib.parse
from typing import Any, NamedTuple, cast
from urllib.parse import urlparse, urlunparse

import aiohttp
from bs4 import BeautifulSoup

# A browser-like UA; TCGplayer's storefront edge rejects the default client UA.
_BROWSER_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)


class Product(NamedTuple):
    name: str
    attributes: str
    store: str
    stock: int
    price: float
    description: str
    img_medium_src: str
    img_src: str
    dest: str

    def from_dict(d: dict[str, Any]) -> "Product":
        return Product(**d)

    def rich_text(self, tcgplayer_price: float | None = None) -> str:
        """Convert the product to a description using markup from the Rich library, with an optional TCGPlayer price."""
        tcgplayer_label = (
            f" -- TCGPlayer: ${tcgplayer_price:.02f}"
            if tcgplayer_price is not None
            else ""
        )
        return f"[b cyan]{self.name}[/b cyan]\n{self.attributes}\n[i]{self.store}[/i]\nQty: {self.stock}\n[b]${self.price:.02f}[/b]{tcgplayer_label}\n[gray]{self.description}[/gray]"


async def scrape_products(
    store_name: str,
    link_template: str,
    search_string: str | None = None,
    output: bool = True,
) -> list[Product]:
    base_link = urlparse(link_template)._replace(
        path="", params="", query="", fragment=""
    )

    page_number = 1
    products: list[Product] = []
    has_products = True

    includes_search_string = True
    search_string = search_string.lower() if search_string is not None else None

    session = aiohttp.ClientSession()

    while has_products and includes_search_string:
        if output:
            print(f"  Page {page_number}...")
        link = link_template.format(page=page_number)

        async with session.get(link) as res:
            soup = BeautifulSoup(await res.text(), "html.parser")

        if soup.select("p.no-product"):
            break

        # Get the first container so we don't look at any extra items at the bottom of the page
        container = soup.select_one("ul.products")
        assert container is not None

        if search_string is not None:
            includes_search_string = False

        has_products = False
        for product in container.select("li.product"):
            has_products = True
            img_tag = product.find("img")
            name_tag = product.find("h4")
            desc_tag = product.select_one("span.variant-short-info.variant-description")
            stock_tag = product.select_one("span.variant-short-info.variant-qty")
            price_tag = product.select_one("span.regular.price")

            assert img_tag is not None
            assert name_tag is not None
            assert desc_tag is not None
            assert stock_tag is not None
            assert price_tag is not None

            dest_tag = name_tag.parent
            assert dest_tag is not None

            img_medium_src = img_tag["src"]
            full_name = name_tag.text.strip()
            desc = desc_tag.text

            if "out of stock" in stock_tag.text.lower():
                continue

            stock = int(stock_tag.text.split()[0])
            price = float(price_tag.text[1:])
            dest = cast(str, urlunparse(base_link._replace(path=dest_tag["href"])))

            assert stock > 0 and isinstance(img_medium_src, str)

            img_src = img_medium_src.replace("medium/", "")

            if search_string is not None and search_string in full_name.lower():
                includes_search_string = True

            # For the crystal commerce, card names look like:
            # Traveling Chocobo - Foil - Borderless  <-- everything "-" and after is optional!
            # Esper Origins // Summon: Esper Maduin - Foil  <-- Card w/ transformation
            # Swamp (0301) - Foil  <-- Card that's repeated a bunch of times
            parts = full_name.split(" - ", 1)
            name, rest = (
                (parts[0].strip(), parts[1].strip())
                if len(parts) > 1
                else (full_name, "")
            )

            # img_src

            products.append(
                Product(
                    name=name,
                    attributes=rest,
                    store=store_name,
                    stock=stock,
                    price=price,
                    description=desc,
                    img_medium_src=img_medium_src,
                    img_src=img_src,
                    dest=dest,
                )
            )

        page_number += 1

    await session.close()

    return products


async def scrape_forge_api(
    store_name: str,
    api_url: str,
    search_string: str,
    output: bool = True,
) -> list[Product]:
    """Scrape Forge Games & Hobbies, which serves a JS storefront backed by a
    JSON POS-search API instead of Crystal Commerce's paginated HTML.

    `api_url` is the base endpoint (e.g. .../api/inventory-api.php); the query
    string is built here. Each catalog item can carry several condition rows
    (NM/LP/...) at different prices, so we emit one Product per in-stock
    condition, mirroring how the site's own front-end flattens results.
    """
    base = urlparse(api_url)._replace(path="", params="", query="", fragment="")

    query = urllib.parse.urlencode(
        {
            "action": "pos_search",
            "q": search_string,
            "limit": 200,
            "game": "mtg",
        }
    )
    link = f"{api_url}?{query}"

    if output:
        print(f"  Querying {store_name} API...")

    async with aiohttp.ClientSession() as session:
        async with session.get(link) as res:
            data = await res.json()

    if not (data and data.get("ok") and isinstance(data.get("items"), list)):
        return []

    products: list[Product] = []
    for item in data["items"]:
        # This tool only deals in singles; skip sealed/accessories rows.
        if item.get("category") not in (None, "singles"):
            continue

        full_name = (item.get("name") or "").strip()
        if not full_name:
            continue

        # Match the Crystal Commerce convention: everything after the first
        # " - " is treatment/foil/variant info.
        parts = full_name.split(" - ", 1)
        name, rest = (
            (parts[0].strip(), parts[1].strip())
            if len(parts) > 1
            else (full_name, "")
        )

        card_set = item.get("set") or ""
        image = item.get("image_url") or ""
        # Link back to the storefront search for this card (no per-card pages).
        dest = cast(
            str,
            urlunparse(
                base._replace(
                    path="/store",
                    query=urllib.parse.urlencode(
                        {"game": "mtg", "type": "singles", "q": name}
                    ),
                )
            ),
        )

        for cond in item.get("conditions", []):
            qty = int(cond.get("qty") or 0)
            if qty <= 0:
                continue

            # Prefer the listed price; fall back to market price like the site.
            price = float(cond.get("price") or 0)
            if price <= 0:
                market = float(cond.get("market_price_market") or 0)
                low = float(cond.get("market_price_low") or 0)
                price = min(market, low) if market > 0 and low > 0 else (low or market)

            condition = cond.get("condition") or ""
            description = f"{card_set} · {condition}".strip(" ·") if card_set or condition else ""

            products.append(
                Product(
                    name=name,
                    attributes=rest,
                    store=store_name,
                    stock=qty,
                    price=price,
                    description=description,
                    img_medium_src=image,
                    img_src=image,
                    dest=dest,
                )
            )

    return products


def _split_tcg_name(full_name: str) -> tuple[str, str]:
    """Split a TCGplayer product name into a base name + attribute string.

    TCGplayer puts treatments in trailing parentheses, e.g.
    "Demonic Tutor (JP Alternate Art) (Foil Etched)" → ("Demonic Tutor",
    "JP Alternate Art - Foil Etched"). The base name is what we fuzzy-match
    the search query against, so it must stay clean.
    """
    groups = re.findall(r"\(([^)]*)\)", full_name)
    base = re.sub(r"\s*\([^)]*\)", "", full_name).strip()
    return base, " - ".join(g.strip() for g in groups)


async def scrape_tcgplayer_pro(
    store_name: str,
    base_url: str,
    search_string: str,
    output: bool = True,
) -> list[Product]:
    """Scrape a TCGplayer Pro storefront (``*.tcgplayerpro.com``).

    These are Vue SPAs backed by two JSON endpoints: ``/api/catalog/search``
    (POST) returns in-stock products with a "lowest price", and
    ``/api/inventory/skus`` returns the per-condition listings (price, qty,
    foil) for a batch of product ids. We emit one Product per in-stock SKU so
    different conditions/finishes show as separate, comparable rows.
    """
    base = urlparse(base_url)._replace(path="", params="", query="", fragment="")
    headers = {
        "User-Agent": _BROWSER_UA,
        "Accept": "application/json, text/plain, */*",
        "Origin": base_url,
        "Referer": base_url + "/",
    }

    payload = {
        "query": search_string,
        "context": {"productLineName": "Magic: The Gathering"},
        "filters": {},
        "from": 0,
        "size": 50,
        "sort": [{"field": "in-stock-price-sort", "order": "desc"}],
    }

    if output:
        print(f"  Querying {store_name} API...")

    async with aiohttp.ClientSession(headers=headers) as session:
        async with session.post(
            base_url + "/api/catalog/search", json=payload
        ) as res:
            data = await res.json()

        items = (data.get("products") or {}).get("items") or []
        by_id = {it["id"]: it for it in items if it.get("id") is not None}
        if not by_id:
            return []

        # Fetch per-SKU listings (condition/qty/price/foil) in id batches.
        ids = list(by_id)
        skus_by_product: dict[int, list[dict]] = {}
        for start in range(0, len(ids), 25):
            batch = ids[start : start + 25]
            id_param = ",".join(str(i) for i in batch)
            async with session.get(
                base_url + "/api/inventory/skus", params={"productIds": id_param}
            ) as res:
                sku_data = await res.json()
            for entry in sku_data or []:
                skus_by_product[entry.get("productId")] = entry.get("skus") or []

    products: list[Product] = []
    for pid, item in by_id.items():
        name, attrs = _split_tcg_name(item.get("name") or "")
        if not name:
            continue

        card_set = item.get("setName") or ""
        image = cast(
            str, urlunparse(("https", "tcgplayer-cdn.tcgplayer.com", f"/product/{pid}_200w.jpg", "", "", ""))
        )
        # Rebuild the storefront product URL the same way the site does.
        dest = cast(
            str,
            urlunparse(
                base._replace(
                    path="/".join(
                        [
                            "/catalog",
                            item.get("productLineUrlName") or "magic",
                            item.get("setUrlName") or "",
                            item.get("productUrlName") or "",
                            str(pid),
                        ]
                    )
                )
            ),
        )

        for sku in skus_by_product.get(pid, []):
            qty = int(sku.get("quantity") or 0)
            if qty <= 0:
                continue
            price = float(sku.get("price") or 0)
            condition = sku.get("conditionName") or ""

            sku_attrs = attrs
            if sku.get("isFoil") and "foil" not in attrs.lower():
                sku_attrs = f"{attrs} - Foil".strip(" -") if attrs else "Foil"

            language = sku.get("languageName") or ""
            desc_bits = [b for b in (card_set, condition, language if language and language != "English" else "") if b]
            description = " · ".join(desc_bits)

            products.append(
                Product(
                    name=name,
                    attributes=sku_attrs,
                    store=store_name,
                    stock=qty,
                    price=price,
                    description=description,
                    img_medium_src=image,
                    img_src=image,
                    dest=dest,
                )
            )

    return products
