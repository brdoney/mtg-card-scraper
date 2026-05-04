#!/usr/bin/env python3
import asyncio
import argparse
import pathlib
import re

from tcgplayer import find_tcgplayer_price


def parse_no_match_lines(path: pathlib.Path) -> list[str]:
    """Extract card names from lines ending with ' - <no-match>'"""
    card_regex = re.compile(r"^\d*\s?(.+) - <(?:no-match)|(?:skipped)>")
    card_names = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if m := card_regex.match(line):
                card_name = m.group(1)
            else:
                continue
            card_names.append(card_name)
    return card_names


async def main() -> None:
    parser = argparse.ArgumentParser(description="Calculate total TCGPlayer price for <no-match> cards")
    parser.add_argument("input_file", type=pathlib.Path, help="Input file with batch select output")
    args = parser.parse_args()

    card_names = parse_no_match_lines(args.input_file)
    if not card_names:
        print("No <no-match> or <skipped> cards found in input file")
        return

    total_price = 0.0
    for card in card_names:
        price = await find_tcgplayer_price(card)
        if price is not None:
            print(f"{card}: ${price:.2f}")
            total_price += price
        else:
            print(f"{card}: No price found")

    print(f"\nTotal price: ${total_price:.2f}")


if __name__ == "__main__":
    asyncio.run(main())
