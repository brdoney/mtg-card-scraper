from typing import Any, NamedTuple, cast
from urllib.parse import urlparse, urlunparse

import aiohttp
from bs4 import BeautifulSoup


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

    def rich_text(self) -> str:
        return f"[b cyan]{self.name}[/b cyan]\n{self.attributes}\n[i]{self.store}[/i]\nQty: {self.stock}\n[b]${self.price:.02f}[/b]\n[gray]{self.description}[/gray]"


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
