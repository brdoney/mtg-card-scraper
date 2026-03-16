# MTG Card Scraper

Search for Magic the Gathering cards at local game shops, compare prices, and more. Currently supports any game shop with a Crystal Commerce website.

## Terminal

While any terminal will work, only the [kitty](https://github.com/kovidgoyal/kitty) terminal will show card preview images at the moment.

## Setup

To install the Python dependencies:

```
$ pip install -r requirements.txt
```

## Run

For the TUI (which is probably what you want):

```
$ python main.py
```

Most of the files should be consumable as standalone library files though.

## Developing

I', using [Textual](https://textual.textualize.io) to write the TUI. But because textual takes over the terminal to display the UI, you won't see any print statements you add while developing. To see those and other Textual-defined debug messages while running the app, I run `textual console --exclude EVENT` in one terminal and `textual run --dev main.py` in another.
