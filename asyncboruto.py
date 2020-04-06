"""Asynchronously get links embedded in multiple pages' HMTL."""
from aiohttp import ClientSession
import asyncio
import aiofiles

from urllib.parse import urlparse
from bs4 import BeautifulSoup
import logging
import sys

logging.basicConfig(level=logging.DEBUG,
                    format="%(name)s: %(message)s",
                    stream=sys.stderr)

log = logging.getLogger("main")

async def main():
    chapter = 42
    total_pages = 10
    base_url = 'https://www.mangareader.net/boruto-naruto-next-generations/'
    all_endpoints = (f'{base_url}{chapter}/{page + 1}' for page in range(total_pages))

    download_tasks = []
    tasks = []
    headers = {
        'User-Agent': 'Mozilla/5.0 (X11; Linux i686) AppleWebKit/537.17 (KHTML, like Gecko) Chrome/24.0.1312.27 Safari/537.17'
    }
    async with ClientSession(headers=headers) as session:
        for endpoint in all_endpoints:
            tasks.append(fetch(session, endpoint))
        htmls = await asyncio.gather(*tasks)
        for html in htmls:
            soup = BeautifulSoup(html, 'html.parser')
            img_url = soup.findAll("div", attrs={"id": "imgholder"})[0].img["src"]
            download_tasks.append(download(session, img_url))
        await asyncio.gather(*download_tasks)

async def fetch(session, url):
    async with session.get(url) as response:
        return await response.text()

async def download(session, url):
    async with session.get(url) as response:
        path = urlparse(url).path.replace('/', '_')
        async with aiofiles.open(path, 'wb') as aiof:
            await aiof.write(await response.read())
            await aiof.close()


if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
