from datetime import datetime
import asyncio
import pickle
from pathlib import Path
from typing import Any

import aiofiles
import aiohttp
import ijson

CACHE_PATH = Path("~/.cache/mtg-card-images/").expanduser()
CACHE_PATH.mkdir(parents=True, exist_ok=True)
CARD_BULK_PATH = CACHE_PATH / "cards.json"
CARD_NAME_PATH = CACHE_PATH / "card-names.json"


def extract_names() -> list[str]:
    names = []
    with open(CARD_BULK_PATH, "rb") as f:
        # for each object in the top-level array, read the "name" property
        for name in ijson.items(f, "item.name"):
            names.append(name)
    return names


async def load_names() -> list[str]:
    async with aiofiles.open(CARD_NAME_PATH, "rb") as f:
        content = await f.read()
    return pickle.loads(content)


async def download_card_data(download_uri: str, progress_queue: asyncio.Queue) -> None:
    async with aiohttp.ClientSession() as session:
        async with session.get(download_uri) as res:
            res.raise_for_status()

            bytes_downloaded = 0
            chunk_size = 8192
            async with aiofiles.open(CARD_BULK_PATH, "wb") as f:
                async for chunk in res.content.iter_chunked(chunk_size):
                    bytes_downloaded += chunk_size
                    progress_queue.put_nowait(bytes_downloaded)
                    await f.write(chunk)

    names = extract_names()
    print("Putting names in")
    progress_queue.put_nowait(names)
    progress_queue.shutdown()

    # Now that the bulk data is saved, extract just the names
    pickle_dump = pickle.dumps(names)
    async with aiofiles.open(CARD_NAME_PATH, "wb") as f:
        await f.write(pickle_dump)


async def update_cache() -> tuple[int, asyncio.Task, asyncio.Queue] | list[str]:
    async with aiohttp.ClientSession() as session:
        async with session.get("https://api.scryfall.com/bulk-data") as res:
            res.raise_for_status()
            data: dict[str, Any] = await res.json()

    sources: list[dict[str, Any]] = data["data"]
    source: dict[str, Any] | None = None
    for source in sources:
        # Keep going until we find the default cards source
        if source["name"] == "Oracle Cards":
            break

    if source is None:
        raise RuntimeError("Could not find default card bulk object from scryfall")

    download_uri = source["download_uri"]
    size = source["size"]
    last_updated = source["updated_at"]
    last_updated_datetime = datetime.fromisoformat(last_updated)

    # Check if the file is up to date, if it exists
    if CARD_BULK_PATH.exists():
        modification_time = CARD_BULK_PATH.stat().st_mtime
        local_timezone = datetime.now().astimezone().tzinfo
        modification_datetime = datetime.fromtimestamp(
            modification_time, tz=local_timezone
        )
        print(modification_time, modification_datetime)
        if last_updated_datetime < modification_datetime:
            # It's up to date, so return
            return await load_names()

    # If it's not up to date, download the file
    progress_queue = asyncio.Queue()
    task = asyncio.create_task(download_card_data(download_uri, progress_queue))

    return size, task, progress_queue
