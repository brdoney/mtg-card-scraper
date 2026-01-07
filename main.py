import json
from typing import Any

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import DataTable, Footer, Header


class SearchResult(DataTable):
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

    data: list[dict[str, Any]]

    def __init__(self, file_path: str) -> None:
        with open(file_path) as f:
            self.data = json.load(f)

        super().__init__(cursor_type="row", zebra_stripes=True)

    def on_mount(self) -> None:
        if len(self.data) == 0:
            return

        cols = self.data[0].keys()
        column_keys = self.add_columns(*cols)
        self.add_rows((row.values() for row in self.data))

        for i, col in enumerate(cols):
            if col not in self.COLUMNS:
                self.remove_column(column_keys[i])

    def on_data_table_row_highlighted(self, msg: DataTable.RowHighlighted) -> None:
        print(msg.cursor_row)


class MTGSearchApp(App):
    """TUI to coordinate searching and scraping (instead of using fzf)"""

    COMMAND_PALETTE_BINDING = "ctrl+slash"

    BINDINGS = [
        ("q", "quit", "Quit"),
    ]

    def compose(self) -> ComposeResult:
        yield Header()
        yield SearchResult("./out/search/3141209881939731343.json")
        yield Footer()


MTGSearchApp().run()
