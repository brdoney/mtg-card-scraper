import asyncio
import hashlib
import webbrowser
from io import BytesIO
from pathlib import Path

import aiofiles
import aiohttp
import PIL.Image
from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, VerticalGroup
from textual.reactive import reactive
from textual.widgets import DataTable, Footer, Header, Input, Label
from textual_image.widget import Image

from scraping import Product
from search import search_card

IMAGE_CACHE_PATH = Path("~/.cache/mtg-card-images/").expanduser()
IMAGE_CACHE_PATH.mkdir(parents=True, exist_ok=True)


async def save_image(path: Path, data: bytes) -> None:
    async with aiofiles.open(path, "wb") as f:
        await f.write(data)


async def get_image_path(url: str) -> PIL.Image.Image:
    md5 = hashlib.md5(url.encode()).hexdigest()
    path = IMAGE_CACHE_PATH / md5

    # Check the cache if we've already downloaded it
    if path.exists():
        # return PIL.Image.open(path)
        return PIL.Image.open(path)

    print("Downloading")
    # Otherwise, download it
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as res:
            data = await res.read()

            # Create a background task to save the image for the future
            asyncio.create_task(save_image(path, data))

            img = PIL.Image.open(BytesIO(data))
            img.load()

            return img

    # fname="$HOME/.cache/mtg-card-images/$(echo "$url" | md5sum | cut -d" " -f1).png";


class SearchResults(DataTable):
    COLUMNS = {"name", "attributes", "store", "stock", "price", "description"}

    BINDINGS = [
        Binding("enter", "select_cursor", "Select", show=False),
        Binding("up", "cursor_up", "Cursor up", show=False),
        Binding("ctrl+p", "cursor_up", "Cursor up", show=False),
        Binding("k", "cursor_up", "Cursor up", show=False),
        Binding("down", "cursor_down", "Cursor down", show=False),
        Binding("ctrl+n", "cursor_down", "Cursor down", show=False),
        Binding("j", "cursor_down", "Cursor down", show=False),
        Binding("right", "cursor_right", "Cursor right", show=False),
        Binding("ctrl+f", "cursor_right", "Cursor right", show=False),
        Binding("l", "cursor_right", "Cursor right", show=False),
        Binding("left", "cursor_left", "Cursor left", show=False),
        Binding("ctrl+b", "cursor_left", "Cursor left", show=False),
        Binding("h", "cursor_left", "Cursor left", show=False),
        Binding("pageup", "page_up", "Page up", show=False),
        Binding("pagedown", "page_down", "Page down", show=False),
        Binding("ctrl+home", "scroll_top", "Top", show=False),
        Binding("ctrl+end", "scroll_bottom", "Bottom", show=False),
        Binding("home", "scroll_home", "Home", show=False),
        Binding("end", "scroll_end", "End", show=False),
    ]

    data: reactive[list[Product]] = reactive([])

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(cursor_type="row", zebra_stripes=True, *args, **kwargs)

    def watch_data(self) -> None:
        if len(self.data) == 0:
            return

        self.clear(columns=True)

        cols = Product._fields
        column_keys = self.add_columns(*cols)
        self.add_rows(self.data)

        for i, col in enumerate(cols):
            if col not in self.COLUMNS:
                self.remove_column(column_keys[i])


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
        img = self.query_one(Image)
        img.image = await get_image_path(product.img_src)
        self.query_one(Label).update(product.rich_text())

    async def watch_data(self, new_data: Product | None) -> None:
        if new_data is not None:
            self.load_product(new_data)


class SearchView(Container):
    def __init__(self) -> None:
        super().__init__(
            Input(placeholder="Search Cards..."),
            SearchResults(),
            CardDetails(id="card-details"),
        )

    @work(exclusive=True)
    async def search_for_card(self, search_text: str) -> None:
        print("Searching...")
        data, dest = await search_card(search_text)
        print(f"Finished search... {data}")
        self.query_one(SearchResults).data = data

    async def on_input_submitted(self, msg: Input.Submitted) -> None:
        self.search_for_card(msg.value)

    async def on_data_table_row_highlighted(
        self, _msg: DataTable.RowHighlighted
    ) -> None:
        grid = self.query_one(SearchResults)
        self.query_one(CardDetails).data = grid.data[grid.cursor_row]

    def on_data_table_row_selected(self, _msg: DataTable.RowSelected) -> None:
        grid = self.query_one(SearchResults)
        selected = grid.data[grid.cursor_row]
        webbrowser.open(selected.dest)


class MTGSearchApp(App):
    """TUI to coordinate searching and scraping (instead of using fzf)"""

    CSS_PATH = "mtg-search.tcss"

    COMMAND_PALETTE_BINDING = "ctrl+slash"

    BINDINGS = [
        ("q", "quit", "Quit"),
    ]

    def compose(self) -> ComposeResult:
        yield Header()
        yield SearchView()
        yield Footer()


MTGSearchApp().run()
