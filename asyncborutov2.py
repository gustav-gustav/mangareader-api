from decorators import ResponseTimer
from urllib.parse import urlparse
from bs4 import BeautifulSoup
from time import strftime, perf_counter
import argparse
import requests
import shutil
import glob
import os
import sys
import json

from aiohttp import ClientSession
import asyncio
import aiofiles


class Test:
    def __init__(self):
        self.base_url = 'https://www.mangareader.net/naruto'
        self.base_path = os.path.join(os.getcwd(), 'Naruto')

        parser = argparse.ArgumentParser()
        parser.add_argument('--debug', '-d', dest='debug', default=False,
                            action='store_true', help='display information of get requests')
        parser.add_argument('--no-download', '-n', dest='download', default=True,
                            action='store_false', help='weather or not to download')
        args = parser.parse_args()

        self.debug = args.debug
        self.write_to_file = args.download
        self.initial = self.last_chapter
        self.runtime_pages = 0
        self.current_chapter = self.initial
        self.current_page = self.last_page
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:74.0) Gecko/20100101 Firefox/74.0'}
        if self.debug:
            requests.get = ResponseTimer(requests.get)
        # creating asyncio event loop
        try:
            self.start = perf_counter()
            self.loop = asyncio.get_event_loop()
            self.loop.run_until_complete(self.main())
        except Exception as e:
            print(e)
        finally:
            print(
                f"Total duration of requests of {self.runtime_pages} pages from Chapter {self.initial} to {self.last_chapter}: {(perf_counter() - self.start):.2f} seconds")
    @property
    def end_chapter(self):
        with requests.get(self.base_url) as response:
            soup = BeautifulSoup(response.text, 'html.parser')
            last_a = soup.findAll('ul')[2].findAll('a')[0]['href']
            return int(last_a.split('/')[-1])

    @property
    def last_chapter(self):
        paths = glob.glob(os.path.join(self.base_path, '*/'))
        chapter_list = []
        if paths:
            for chapter in paths:
                chapter_dir = chapter.split(os.path.sep)[-2]
                chapter_number = chapter_dir.strip('Chapter ')
                chapter_list.append(int(chapter_number))
            return max(chapter_list)
        else:
            return 1

    @property
    def last_page(self):
        path = os.path.join(
            self.base_path, f'Chapter {self.current_chapter}', "*.jpg")
        paths = glob.glob(path)
        image_list = []
        if paths:
            for image in paths:
                image_file = image.split(os.path.sep)[-1]
                image_name = os.path.splitext(image_file)[0]
                image_number = int(image_name[(len(image_name) - 2):])
                image_list.append(image_number)
            return max(image_list)
        else:
            return 1

    async def main(self):
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:74.0) Gecko/20100101 Firefox/74.0'}
        fetch_tasks = []
        sema_count = 10
        self.sema = asyncio.Semaphore(sema_count)
        async with ClientSession(headers=headers) as session:
            for endpoint in (f"{self.base_url}/{chapter}/1" for chapter in range(self.initial, self.end_chapter + 1)):
                fetch_tasks.append(self.fetch(session, endpoint,))
            download_tasks = await asyncio.gather(*fetch_tasks)
            for task in download_tasks:
                await asyncio.gather(*task)

    async def fetch(self, session, url):
        start = perf_counter()
        async with self.sema:
            async with session.get(url) as response:
                self.printer(response.status, response.url.path, start)
                chapter = int(os.path.splitext(url)[0].split('/')[-2])
                if response.status == 200:
                    soup = BeautifulSoup(await response.text(), 'html.parser')
                    pages_in_chapter = soup.findAll('div', {'id': 'selectpage'})[0].text
                    await asyncio.sleep(0.25)
                    total_pages = int(pages_in_chapter[(len(pages_in_chapter)-2):])
                    tasks = []
                    initial = 1
                    if chapter == self.initial:
                        last = self.last_page
                        if last == total_pages:
                            tasks.append(asyncio.sleep(0))
                    else:
                        for endpoint in (f"{self.base_url}/{chapter}/{page}" for page in range(initial, total_pages + 1)):
                            tasks.append(self.download(session, endpoint))
                    return tasks
                else:
                    response.raise_for_status()

    async def download(self, session, url):
        '''Makes async http requests and parses it with bs4
        Download's the image that the first endpoint matched'''
        async with self.sema:
            try:
                start = perf_counter()
                async with session.get(url) as response:
                    self.printer(response.status, response.url.path, start)
                    page_number = os.path.splitext(url)[0].split('/')[-1]
                    chapter = os.path.splitext(url)[0].split('/')[-2]
                    directory = f"Chapter {chapter}"
                    await self.mkdir(chapter)

                    html = await response.text()
                    soup = BeautifulSoup(html, 'html.parser')
                    img_url = soup.findAll("div", attrs={"id": "imgholder"})[
                        0].img["src"]
                    await asyncio.sleep(0.25)
                    start = perf_counter()
                    async with session.get(img_url) as response:
                        self.printer(response.status, response.url.path, start)
                        photo = f'Boruto.ch{chapter}.p{page_number.zfill(3)}.jpg'
                        photo_path = os.path.join(self.base_path, directory, photo)
                        async with aiofiles.open(photo_path, 'wb') as aiof:
                            await aiof.write(await response.read())
                            await aiof.close()
            except Exception as e:
                print(e)
                await self.download(session, url)
                # sys.exit()

    async def mkdir(self, chapter):
        '''Checks if there is a directory for the current chapter.
        If not, creates it.'''
        directory = os.path.join(self.base_path, f'Chapter {chapter}')
        if not os.path.isdir(directory):
            if not self.debug:
                print(f"Creating directory {directory}")
            os.mkdir(directory)

    def printer(self, status, url_path, start):
        print(f"{strftime('[%d/%m/%Y %H:%M:%S]')} {status}@{url_path!r} finished in {(perf_counter() - start):.2f}")

if __name__ == "__main__":
    Test()
