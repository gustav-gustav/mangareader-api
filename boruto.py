from decorators import ResponseTimer
from bs4 import BeautifulSoup
import argparse
import requests
import shutil
import glob
import os
import sys

class Scraper:
    def __init__(self):
        self.base_url = 'https://www.mangareader.net/boruto-naruto-next-generations/'
        self.base_path = os.path.join(os.getcwd(), 'Boruto')

        parser = argparse.ArgumentParser()
        parser.add_argument('--debug', '-d', dest='debug', default=False, action='store_true', help='display information of get requests')
        parser.add_argument('--no-download', '-n', dest='download', default=True, action='store_false',help='weather or not to download')
        args = parser.parse_args()

        self.debug = args.debug
        self.write_to_file = args.download
        self.current_chapter = self.get_last_chapter()
        self.current_page = self.get_last_page()
        if self.debug:
            requests.get = ResponseTimer(requests.get)
        self.mkdir()
        self.main()

    def mkdir(self):
        self.directory = os.path.join(
            self.base_path, f'Chapter {self.current_chapter}')

        if not os.path.isdir(self.directory):
            if not self.debug:
                print(f"Creating directory {self.directory}")
            os.mkdir(self.directory)
        self.check()

    def get_last_chapter(self):
        paths = glob.glob(os.path.join(self.base_path, '*/'))
        chapter_list = []
        for chapter in paths:
            chapter_dir = chapter.split(os.path.sep)[-2]
            chapter_number = chapter_dir.strip('Chapter ')
            chapter_list.append(int(chapter_number))
        return max(chapter_list)

    def get_last_page(self):
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

    def check(self):
        try:
            with requests.get(self.current_endpoint) as response:
                if response.ok:
                    soup = BeautifulSoup(response.text, 'html.parser')
                    pages_in_chapter = soup.findAll('div', {'id': 'selectpage'})[0].text
                    self.all_episodes_in_chapter = int(pages_in_chapter[(len(pages_in_chapter)-2):])
                else:
                    response.raise_for_status()
        except IndexError:
            print('No new chapters yet, check again at 20th of every month')
            sys.exit()

    @property
    def current_endpoint(self):
        return f'{self.base_url}{self.current_chapter}/{self.current_page}'

    def main(self):
        while True:
            try:
                with requests.get(self.current_endpoint) as response:
                    if response.ok:
                        soup = BeautifulSoup(response.text, 'html.parser')
                        image_url = soup.findAll("div", attrs={"id": "imgholder"})[0].img["src"]
                        response = requests.get(image_url, stream=True)
                        photo = f'Boruto.ch{self.current_chapter}.p{str(self.current_page).zfill(3)}.jpg'
                        photo_path = os.path.join(self.base_path, self.directory, photo)
                        if not os.path.isfile(photo_path):
                            if self.write_to_file:
                                with open(photo_path, 'wb') as out_file:
                                    if not self.debug:
                                        print(f'Downloading {photo} at {self.directory}')
                                    shutil.copyfileobj(response.raw, out_file)

                        if self.current_page == self.all_episodes_in_chapter:
                            self.current_chapter += 1
                            self.current_page = 1
                            self.mkdir()
                        else:
                            self.current_page += 1

                    else:
                        raise response.raise_for_status()

            except KeyboardInterrupt:
                break

            except IndexError as e:
                print(f'Last chapter released is {self.current_chapter - 1}')
                break

            except Exception as e:
                print(e)
                break



if __name__ == '__main__':
    Scraper()
