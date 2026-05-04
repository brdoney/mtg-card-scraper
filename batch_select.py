#!/usr/bin/env python3
import asyncio
import argparse
import pathlib
import re
import webbrowser

from main import CardDetails
from scraping import Product
from search import search_card
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container
from textual.widgets import DataTable, Footer, Header, Label
from textual.reactive import reactive
from textual.fuzzy import FuzzySearch


def filter_data(data: list[Product], search_text: str) -> list[Product]:
    fuzzy = FuzzySearch()
    fuzzy_lookup = {p: fuzzy.match(search_text, p.name)[0] for p in data}
    filtered = [p for p in data if fuzzy_lookup[p] > 0.1]
    filtered.sort(key=lambda p: (fuzzy_lookup[p], -p.price), reverse=True)
    return filtered


class BatchSelectApp(App):
    CSS_PATH = "mtg-search.tcss"
    BINDINGS = [
        Binding("s", "skip_card", "Skip/Start", show=True),
        Binding("q", "quit", "Quit", show=True),
    ]

    cards: list[str]
    output_file: pathlib.Path
    current_index: reactive[int] = reactive(0)
    current_results: reactive[list[Product]] = reactive([])
    started: reactive[bool] = reactive(False)
    search_task: asyncio.Task[tuple[list[Product], pathlib.Path]] | None = None

    prompt_label: Label
    status_label: Label

    def __init__(self, cards: list[str], output_file: pathlib.Path, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.cards = cards
        self.output_file = output_file

    def compose(self) -> ComposeResult:
        yield Header()
        with Container(id="batch-container"):
            self.prompt_label = Label("", id="prompt")
            yield self.prompt_label
            self.status_label = Label("", id="status")
            yield self.status_label
            yield DataTable(id="result-table", cursor_type="row", zebra_stripes=True)
            yield CardDetails(id="card-details")
            yield Label(
                "Use Up/Down to highlight, Enter to select, S to skip, Q to quit",
                id="instructions",
            )
        yield Footer()

    async def on_mount(self) -> None:
        self.prompt_label.update("Press S to start processing cards")
        self.status_label.update("Ready")
        # Clear any existing details until a row is highlighted
        self.query_one(CardDetails).data = None

    async def load_next_card(self) -> None:
        if self.current_index >= len(self.cards):
            self.status_label.update("All cards processed. Press q to exit.")
            self.query_one(DataTable).clear(columns=True)
            self.query_one(CardDetails).data = None
            return

        card = self.cards[self.current_index]
        self.prompt_label.update(
            f"[{self.current_index + 1}/{len(self.cards)}] Searching: {card}"
        )
        self.status_label.update("Loading search results...")

        self.query_one(DataTable).clear(columns=True)
        self.query_one(CardDetails).data = None

        self.search_task = asyncio.create_task(search_card(card))

        try:
            data, _ = await self.search_task
        except asyncio.CancelledError:
            self.status_label.update("Search canceled")
            self.search_task = None
            return
        finally:
            self.search_task = None

        results = filter_data(data, card)

        if not results:
            self.status_label.update("No results, skipped.")
            self._append_line(card, "<no-match>")
            self.current_index += 1
            await asyncio.sleep(1)
            await self.load_next_card()
            return

        self.current_results = results
        table = self.query_one(DataTable)
        table.clear(columns=True)
        table.add_columns("name", "attributes", "store", "stock", "price")

        for p in results:
            table.add_row(
                p.name, p.attributes, p.store, str(p.stock), f"${p.price:.2f}"
            )

        self.status_label.update("Select one result with Enter or press S to skip.")
        table.focus()

    def _append_line(self, original_line: str, url: str) -> None:
        self.output_file.parent.mkdir(parents=True, exist_ok=True)
        with self.output_file.open("a", encoding="utf-8") as f:
            f.write(f"{original_line.strip()} - {url}\n")

    def action_skip_card(self) -> None:
        if not self.started:
            self.started = True
            self.status_label.update("Started. Searching first card...")
            self.call_later(self.load_next_card)
            return

        if self.current_index < len(self.cards):
            card = self.cards[self.current_index]
            self._append_line(card, "<skipped>")
            self.current_index += 1
            self.call_later(self.load_next_card)

    async def action_quit(self) -> None:
        if self.search_task is not None and not self.search_task.done():
            self.search_task.cancel()
            self.status_label.update("Cancelling search...")
        await super().action_quit()

    async def on_data_table_row_selected(self, _msg: DataTable.RowSelected) -> None:
        if self.current_index >= len(self.cards):
            return

        selected_row = self.query_one(DataTable).cursor_row
        if selected_row is None:
            return

        product = self.current_results[selected_row]
        card = self.cards[self.current_index]

        webbrowser.open(product.dest, autoraise=False)
        self._append_line(card, product.dest)

        self.current_index += 1
        await self.load_next_card()

    async def on_data_table_row_highlighted(
        self, _msg: DataTable.RowHighlighted
    ) -> None:
        row = self.query_one(DataTable).cursor_row
        if row is None or row >= len(self.current_results):
            self.query_one(CardDetails).data = None
            return
        product = self.current_results[row]
        self.status_label.update(
            f"Highlighted: {product.name} @ {product.store} ${product.price:.2f}"
        )
        self.query_one(CardDetails).data = product


def parse_input_file(path: pathlib.Path) -> list[str]:
    num_regex = re.compile(r"^\d+\s+(.+)")
    with path.open("r", encoding="utf-8") as f:
        lines: list[str] = []
        for line in f:
            line = line.strip()

            # Skip empty lines
            if not line:
                continue

            # Strip leading number (e.g. 1 Forest)
            if m := num_regex.match(line):
                card_name = m.group(1)
                lines.append(card_name)
            else:
                lines.append(line)
    return lines


def main() -> None:
    parser = argparse.ArgumentParser(description="Batch MTG card selection UI")
    parser.add_argument("input_file", type=pathlib.Path, help="Input card list file")
    parser.add_argument(
        "output_file",
        type=pathlib.Path,
        nargs="?",
        default=pathlib.Path("selected-output.txt"),
        help="Output file to write selections",
    )
    args = parser.parse_args()

    cards = parse_input_file(args.input_file)
    if not cards:
        print("No cards found in input file")
        return

    app = BatchSelectApp(cards, args.output_file)
    app.run()


if __name__ == "__main__":
    main()
