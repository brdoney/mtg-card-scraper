from textual.fuzzy import FuzzySearch
from rich.pretty import pprint
from typing import Any
import asyncio
import aiohttp

_PRICE_CACHE: dict[str, float] = {}


async def _search_card_tcgplayer(name: str) -> dict[str, Any]:
    """
    Search for a particular card name on TCGPlayer.

    NOTE: Uses the public API (that the website uses), which has no stability
    guarantees but doesn't require authentication.
    """
    async with aiohttp.ClientSession() as session:
        async with session.post(
            "https://mp-search-api.tcgplayer.com/v1/search/request",
            params={"q": name},
            json={
                "algorithm": "sales_dismax",
                "from": 0,
                "size": 24,
                "filters": {"term": {"productLineName": ["magic"]}},
                "range": {},
                "match": {},
                "listingSearch": {
                    "context": {"cart": {}},
                    "filters": {
                        "term": {"sellerStatus": "Live", "channelId": 0},
                        "range": {"quantity": {"gte": 1}},
                        "exclude": {"channelExclusion": 0},
                    },
                },
                "context": {
                    "cart": {},
                    "shippingCountry": "US",
                    "userProfile": {"priceAffinity": 215},
                },
                "settings": {"useFuzzySearch": True, "didYouMean": {}},
                "sort": {},
            },
            headers={
                "User-Agent": "Mozilla/5.0",
                "Accept": "application/json",
            },
        ) as res:
            res.raise_for_status()
            return await res.json()


def _find_match(name: str, search_results: dict[str, Any]) -> dict[str, Any] | None:
    """Find the closest match to a given card name in the TCGPlayer search results."""
    cards = search_results["results"][0]["results"]
    fuzzy = FuzzySearch(case_sensitive=False)

    best_score = 0
    best_card = None
    for card in cards:
        card_name = card["productUrlName"]
        score = fuzzy.match(name, card_name)[0]
        if score > best_score:
            best_score = score
            best_card = card

    return best_card


async def find_tcgplayer_price(name: str) -> float | None:
    """
    Get the price for a particular card on TCGPlayer. Uses median price
    field (rather than "market" price field, which is really the TCGPlayer
    Direct price), since it's usually significantly closer to actual market.
    """
    if name in _PRICE_CACHE:
        return _PRICE_CACHE[name]

    res = await _search_card_tcgplayer(name)
    print(res)
    card = _find_match(name, res)
    if card is not None:
        price = card["medianPrice"]
        _PRICE_CACHE[name] = price
        return price
    return None


# curl 'https://mp-search-api.tcgplayer.com/v1/search/request?q=aerith,+last+ancient&isList=false&mpfev=4622' \
# --data-raw '{"algorithm":"sales_dismax","from":0,"size":24,"filters":{"term":{"productLineName":["magic"]},"range":{},"match":{}},"listingSearch":{"context":{"cart":{}},"filters":{"term":{"sellerStatus":"Live","channelId":0},"range":{"quantity":{"gte":1}},"exclude":{"channelExclusion":0}}},"context":{"cart":{},"shippingCountry":"US","userProfile":{"priceAffinity":215}},"settings":{"useFuzzySearch":true,"didYouMean":{}},"sort":{}}'
# {
#   "algorithm": "sales_dismax",
#   "from": 0,
#   "size": 24,
#   "filters": {
#     "term": {
#       "productLineName": [
#         "magic"
#       ]
#     },
#     "range": {},
#     "match": {}
#   },
#   "listingSearch": {
#     "context": {
#       "cart": {}
#     },
#     "filters": {
#       "term": {
#         "sellerStatus": "Live",
#         "channelId": 0
#       },
#       "range": {
#         "quantity": {
#           "gte": 1
#         }
#       },
#       "exclude": {
#         "channelExclusion": 0
#       }
#     }
#   },
#   "context": {
#     "cart": {},
#     "shippingCountry": "US",
#     "userProfile": {
#       "priceAffinity": 215
#     }
#   },
#   "settings": {
#     "useFuzzySearch": true,
#     "didYouMean": {}
#   },
#   "sort": {}
# }


async def main():
    pprint(await find_tcgplayer_price("Aerith"))


if __name__ == "__main__":
    asyncio.run(main())
