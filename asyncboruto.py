from decorators import ResponseTimer
from urllib.parse import urlparse
from bs4 import BeautifulSoup
from time import strftime
import argparse
import requests
import shutil
import glob
import os
import sys

from aiohttp import ClientSession
import asyncio
import aiofiles


class Scraper:
    'Async implementation for downloading multiple images concurrently'
    def __init__(self):
        self.base_url = 'https://www.mangareader.net/boruto-naruto-next-generations/'
        self.base_path = os.path.join(os.getcwd(), 'Boruto')

        parser = argparse.ArgumentParser()
        parser.add_argument('--debug', '-d', dest='debug', default=False,
                            action='store_true', help='display information of get requests')
        parser.add_argument('--no-download', '-n', dest='download', default=True,
                            action='store_false', help='weather or not to download')
        args = parser.parse_args()

        self.debug = args.debug
        self.write_to_file = args.download
        self.current_chapter = self.last_chapter
        self.current_page = self.last_page
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:74.0) Gecko/20100101 Firefox/74.0'}
        if self.debug:
            requests.get = ResponseTimer(requests.get)
        self.mkdir()
        # creating asyncio event loop
        self.loop = asyncio.get_event_loop()
        self.loop.run_until_complete(self.main())

    async def main(self):
        while True:
            try:
                all_endpoints = (f'{self.current_chapter_endpoint}{page}' for page in range(
                    self.current_page, self.total_pages + 1))
                tasks = []
                async with ClientSession(headers=self.headers) as session:
                    for endpoint in all_endpoints:
                        tasks.append(self.fetch(session, endpoint))
                    await asyncio.gather(*tasks)

                self.reset()
            except Exception as e:
                print(e)
                break

    async def fetch(self, session, url):
        async with session.get(url) as response:
            if self.debug:
                print(f"{strftime('[%d/%m/%Y %H:%M:%S]')} {response.status}@{response.url.path!r}")
            page_number = os.path.splitext(url)[0].split('/')[-1]
            html = await response.text()
            soup = BeautifulSoup(html, 'html.parser')
            img_url = soup.findAll("div", attrs={"id": "imgholder"})[
                0].img["src"]
            async with session.get(img_url) as response:
                print(f"{strftime('[%d/%m/%Y %H:%M:%S]')} {response.status}@{response.url.path!r}")
                photo = f'Boruto.ch{self.current_chapter}.p{page_number.zfill(3)}.jpg'
                photo_path = os.path.join(
                    self.base_path, self.directory, photo)
                if not self.debug:
                    print(f'Creating {photo_path}')
                async with aiofiles.open(photo_path, 'wb') as aiof:
                    await aiof.write(await response.read())
                    await aiof.close()

    @property
    def current_chapter_endpoint(self):
        return f'{self.base_url}{self.current_chapter}/'

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

    def reset(self):
        self.current_chapter += 1
        self.current_page = 1
        self.mkdir()

    def mkdir(self):
        self.directory = os.path.join(
            self.base_path, f'Chapter {self.current_chapter}')

        if not os.path.isdir(self.directory):
            if not self.debug:
                print(f"Creating directory {self.directory}")
            os.mkdir(self.directory)
        self.check()

    def check(self):
        try:
            with requests.get(f"{self.current_chapter_endpoint}{self.last_page}") as response:
                if response.ok:
                    soup = BeautifulSoup(response.text, 'html.parser')
                    pages_in_chapter = soup.findAll(
                        'div', {'id': 'selectpage'})[0].text
                    self.total_pages = int(
                        pages_in_chapter[(len(pages_in_chapter)-2):])
                    if self.current_page == self.total_pages:
                        self.reset()
                else:
                    response.raise_for_status()
        except IndexError:
            print('No new chapters yet, check again at 20th of every month')
            sys.exit()


if __name__ == '__main__':
    Scraper()