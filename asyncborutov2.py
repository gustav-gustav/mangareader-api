from urllib.parse import urlparse, urlencode
from time import strftime, perf_counter
from decorators import ResponseTimer
from collections import namedtuple
from bs4 import BeautifulSoup
from fuzzywuzzy import fuzz
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


class Scraper:
    def __init__(self):
        '''Async scraper and parser to download manga chapters from mangareader.net'''
        # https://mangareader.net/actions/search/?q=naruto&limit=100
        self.base_url = 'https://www.mangareader.net/naruto'
        self.base_path = os.path.join(os.getcwd(), 'Naruto')

        parser = argparse.ArgumentParser()
        parser.add_argument('--debug', '-d', dest='debug', default=False,
                            action='store_true', help='display information of get requests')
        parser.add_argument('--no-download', '-n', dest='download', default=True,
                            action='store_false', help='weather or not to download')
        args = parser.parse_args()

        self.match('naruto')
        self.debug = args.debug
        self.write_to_file = args.download
        self.initial = self.last_chapter
        self.runtime_pages = 0
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
            print(f"Total duration of requests of {self.runtime_pages} pages from Chapter {self.initial} to {self.last_chapter}: {(perf_counter() - self.start):.2f} seconds")

    @property
    def end_chapter(self):
        '''Makes a request to self.base_url to get the last chapter available'''
        with requests.get(self.base_url) as response:
            soup = BeautifulSoup(response.text, 'html.parser')
            last_a = soup.findAll('ul')[2].findAll('a')[0]['href']
            return int(last_a.split('/')[-1])

    @property
    def last_chapter(self):
        '''Gets the last chapter created'''
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

    def match(self, string):
        payload = urlencode({"q": string.lower(), "limit": 100})
        with requests.get("https://mangareader.net/actions/search/?", params=payload) as response:
            if response.ok:
                data = response.text.split('\n')
                Fields = namedtuple('Fields', ['Name', 'Image', 'Title', 'Creator', 'Endpoint', 'Index'])
                match_list = []
                for match in data:
                    if match:
                        fields = Fields(*match.split('|'))
                        rating = fuzz.partial_ratio(fields.Name.lower(), string.lower())
                        obj = {'rating': rating, 'obj': fields}
                        match_list.append(obj)
                best_match = max([match['rating'] for match in match_list])
                best_tuple = [match['obj'] for match in match_list if match['rating'] == best_match]
                print(best_tuple)


    async def main(self):
        '''
        In the first part creates tasks from the generator, which yields an endoint in range of
        the last chapter and the end chapter.
        When async.gather(*fetch_tasks) runs, returns a nested list of coroutines for each chapter
        which is called when gathering download_tasks
        '''
        latest_chapter = self.end_chapter
        if self.initial != latest_chapter:
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:74.0) Gecko/20100101 Firefox/74.0'}
            fetch_tasks = []
            sema_count = 10
            self.sema = asyncio.Semaphore(sema_count)
            async with ClientSession(headers=headers) as session:
                for endpoint in (f"{self.base_url}/{chapter}/1" for chapter in range(self.initial,  + 1)):
                    fetch_tasks.append(self.fetch(session, endpoint,))
                download_tasks = await asyncio.gather(*fetch_tasks)
                for task in download_tasks:
                    await asyncio.gather(*task)
        else:
            print('No new chapters yet, check again at 20th of every month')

    async def fetch(self, session, url):
        '''
        Get request @ endpoint created by the generator in self.main, parsing response.text() with BeautifulSoup
        Gets the total_pages for that chapter.
        Returns a list of coroutines to be run in self.main() which will async download all images for each chapter in order of chapters
        '''
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
                    for endpoint in (f"{self.base_url}/{chapter}/{page}" for page in range(1, total_pages + 1)):
                        tasks.append(self.download(session, endpoint))
                    return tasks
                else:
                    response.raise_for_status()

    async def download(self, session, url):
        '''
        Makes async http requests and parses it with BeautifulSoup
        Download's the image that the first endpoint matched.
        If request fails, retries it in the excepion catch
        '''
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
                        self.runtime_pages += 1
            except Exception as e:
                print(e)
                await self.download(session, url)

    async def mkdir(self, chapter):
        '''Checks if there is a directory for the current chapter.
        If not, creates it.'''
        directory = os.path.join(self.base_path, f'Chapter {chapter}')
        if not os.path.isdir(directory):
            if not self.debug:
                print(f"Creating directory {directory}")
            os.mkdir(directory)

    def printer(self, status, url_path, start):
        '''Wraps the async response with usefull debugging stats'''
        print(f"{strftime('[%d/%m/%Y %H:%M:%S]')} {status}@{url_path!r} finished in {(perf_counter() - start):.2f}")

if __name__ == "__main__":
    Scraper()
