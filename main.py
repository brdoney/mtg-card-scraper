import asyncio
import hashlib
import webbrowser
from io import BytesIO
from pathlib import Path
from typing import override

import aiofiles
import aiohttp
import PIL.Image
from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Center, Container, Middle, VerticalGroup
from textual.fuzzy import FuzzySearch
from textual.reactive import reactive
from textual.screen import Screen
from textual.suggester import SuggestFromList
from textual.widgets import DataTable, Footer, Header, Input, Label, ProgressBar
from textual_image.widget import Image

from card_names import update_cache
from scraping import Product
from search import search_card
from tcgplayer import find_tcgplayer_price

IMAGE_CACHE_PATH = Path("~/.cache/mtg-card-images/").expanduser()
IMAGE_CACHE_PATH.mkdir(parents=True, exist_ok=True)


async def _save_image(path: Path, data: bytes) -> None:
    async with aiofiles.open(path, "wb") as f:
        await f.write(data)


async def _get_image(url: str) -> PIL.Image.Image:
    """Get an image, using the cache where possible"""

    md5 = hashlib.md5(url.encode()).hexdigest()
    path = IMAGE_CACHE_PATH / md5

    # Check the cache if we've already downloaded it
    if path.exists():
        # return PIL.Image.open(path)
        return PIL.Image.open(path)

    # Otherwise, download it
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as res:
            data = await res.read()

            # Create a background task to save the image for the future
            asyncio.create_task(_save_image(path, data))

            img = PIL.Image.open(BytesIO(data))
            img.load()

            return img


def filter_data(data: list[Product], search_text: str):
    """
    Use fuzzy search to filter + sort results, since crystal commerce's
    search pulls some unrelated cards (false positives).
    """
    fuzzy = FuzzySearch()
    fuzzy_lookup = {p: fuzzy.match(search_text, p.name)[0] for p in data}
    filtered = [p for p in data if fuzzy_lookup[p] > 0.1]
    filtered.sort(key=lambda p: (fuzzy_lookup[p], -p.price), reverse=True)
    return filtered


class SearchResults(DataTable):
    COLUMNS = {"name", "attributes", "store", "stock", "price", "description"}

    # Adds Emacs (ctrl+p/n/b/f) and Vim (hjkl) cursor movement bindings
    BINDINGS = [
        Binding("up,ctrl+p,k", "cursor_up", "Cursor up", show=False),
        Binding("down,ctrl+n,j", "cursor_down", "Cursor down", show=False),
        Binding("right,ctrl+f,l", "cursor_right", "Cursor right", show=False),
        Binding("left,ctrl+b,h", "cursor_left", "Cursor left", show=False),
    ]

    # The product data from the search
    data: reactive[list[Product]] = reactive([])

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(cursor_type="row", zebra_stripes=True, *args, **kwargs)

    def watch_data(self) -> None:
        self.clear(columns=True)

        if len(self.data) == 0:
            return

        cols = Product._fields
        column_keys = self.add_columns(*zip(cols, cols))
        self.add_rows(self.data)

        for i, col in enumerate(cols):
            if col not in self.COLUMNS:
                self.remove_column(column_keys[i])

    def get_highlighted_product(self) -> Product:
        """Get the product currently highlighted by the cursor"""
        return self.data[self.cursor_row]


class CardDetails(VerticalGroup):
    data: reactive[Product | None] = reactive(None)

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(
            Label(id="card-details-text"),
            Image(id="card-image"),
            *args,
            **kwargs,
        )

    @work(exclusive=True)
    async def load_product(self, product: Product) -> None:
        """
        Load the image and description for a particular product.
        Moved to a worker because the image takes a bit of time and we want it to be exclusive
        since loading an image we're not looking at anymore is pointless.
        """
        img = self.query_one(Image)
        detail_label = self.query_one(Label)

        try:
            img.image = await _get_image(product.img_src)
        except PIL.UnidentifiedImageError:
            pass

        detail_label.update(product.rich_text())

        try:
            price = await find_tcgplayer_price(product.name)
            if price is not None:
                detail_label.update(product.rich_text(price))
        except KeyError:
            pass

    async def watch_data(self, new_data: Product | None) -> None:
        self.query_one(Label).update("")
        self.query_one(Image).image = None

        if new_data is not None:
            self.load_product(new_data)


class CardInput(Input):
    BINDINGS = [
        Binding("enter", "submit", "Autocomplete and Submit", show=True),
        Binding("shift+enter", "submit_nocomplete", "Submit", show=True),
    ]

    def accept_completion(self) -> bool:
        # Suggestion takes a bit to update b/c its in a worker thread, so we need to explicitly check against value
        if self.cursor_at_end and self._suggestion and self.value != self._suggestion:
            self.value = self._suggestion
            self.cursor_position = len(self.value)  # type: ignore
            return True
        return False

    @override
    async def action_submit(self) -> None:
        """
        Accept an auto-completion or move the cursor one position to the
        right or handle a submit action if no autocompletion is present.

        Normally triggered by the user pressing Enter. This may also run any validators.
        """
        if not self.accept_completion():
            validation_result = (
                self.validate(self.value) if "submitted" in self.validate_on else None
            )
            self.post_message(self.Submitted(self, self.value, validation_result))

    async def action_submit_nocomplete(self) -> None:
        """Submit action that overrides a check for autocomplete suggestions."""
        self._suggestion = ""
        await self.action_submit()


class SearchView(Container):
    def compose(self) -> ComposeResult:
        yield CardInput(placeholder="Search Cards...")
        with Container(id="results-area"):
            yield SearchResults(id="search-results")
            with Center():
                yield Label("No results found", id="no-results")
        yield CardDetails(id="card-details")

    @work(exclusive=True)
    async def search_for_card(self, search_text: str) -> None:
        search_results = self.query_one(SearchResults)
        card_details = self.query_one(CardDetails)
        no_results = self.query_one("#no-results")

        # Use the card details for the loading bar
        # Multiple (i.e. also the grid) is kind of jarring
        card_details.loading = True

        search_results.data = []
        card_details.data = None

        data, dest = await search_card(search_text)
        data = filter_data(data, search_text)

        search_results.data = data

        has_results = len(data) > 0
        no_results.display = not has_results
        search_results.display = has_results

        card_details.loading = False

    async def on_input_submitted(self, msg: Input.Submitted) -> None:
        # Use the worker to search for the card
        self.search_for_card(msg.value)

    def on_data_table_row_highlighted(self, _msg: DataTable.RowHighlighted) -> None:
        # Show the newly selected card's details in the sidebar
        grid = self.query_one(SearchResults)
        self.query_one(CardDetails).data = grid.get_highlighted_product()

    def on_data_table_row_selected(self, _msg: DataTable.RowSelected) -> None:
        # Open the link when the user presses enter/clicks on a row
        grid = self.query_one(SearchResults)
        selected = grid.get_highlighted_product()
        webbrowser.open(selected.dest)


class CacheProgress(Screen[list[str]]):
    download_size: int
    download_task: asyncio.Task
    progress_queue: asyncio.Queue

    def __init__(
        self,
        download_size: int,
        download_task: asyncio.Task,
        progress_queue: asyncio.Queue,
        *args,
        **kwargs,
    ) -> None:
        self.download_size = download_size
        self.download_task = download_task
        self.progress_queue = progress_queue
        super().__init__(*args, **kwargs)

    def compose(self) -> ComposeResult:
        with Center():
            with Middle():
                yield Label("[b]Updating card autocomplete cache...[/b]")
                yield ProgressBar(total=self.download_size)

    def on_mount(self) -> None:
        self.update_progress()

    @work
    async def update_progress(self) -> None:
        pbar = self.query_one(ProgressBar)

        value: int | list[str]
        while not isinstance((value := await self.progress_queue.get()), list):
            pbar.progress = value

        print("Done!", len(value))

        # Should be done now, but just to make sure
        await self.download_task

        # And we can pop the screen now that we're finished
        self.dismiss(value)


class MTGSearchApp(App):
    """TUI to coordinate searching and scraping (instead of using fzf)"""

    CSS_PATH = "mtg-search.tcss"

    COMMAND_PALETTE_BINDING = "ctrl+slash"

    BINDINGS = [
        Binding("q", "quit", "Quit", show=False),
        Binding("escape", "pop_focus", "Pop focus", show=True),
    ]

    async def action_pop_focus(self) -> None:
        if isinstance(self.focused, Input):
            await self.action_quit()
        else:
            self.query_one(Input).focus()

    def update_autocomplete(self, card_names: list[str] | None) -> None:
        if card_names is not None:
            self.query_one(Input).suggester = SuggestFromList(
                card_names, case_sensitive=False
            )

    @work
    async def check_cache(self) -> None:
        res = await update_cache()
        if isinstance(res, list):
            self.update_autocomplete(res)
            return

        download_size, task, progress_queue = res
        screen = CacheProgress(download_size, task, progress_queue)
        self.push_screen(screen, callback=self.update_autocomplete)

    def on_mount(self) -> None:
        self.check_cache()

    def compose(self) -> ComposeResult:
        yield Header()
        yield SearchView()
        yield Footer()


if __name__ == "__main__":
    MTGSearchApp().run()
