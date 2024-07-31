
from logger import Logger

import re
import requests
from bs4 import BeautifulSoup, SoupStrainer
from lxml import etree
from tqdm import tqdm
import collections
import pandas as pd
from bs4 import GuessedAtParserWarning
import warnings
warnings.filterwarnings('ignore')

"""
Created by: https://github.com/JSapun/. This code is released under the MIT license. 
"""

exclusion_list = ["https://ww4.fmovies.co/film/24-season-9-live-another-day-9296/",
			"https://ww4.fmovies.co/film/the-man-in-the-high-castle-4-100150-c/"] # Weird url formats, just ignore
base = "https://ww4.fmovies.co/sitemap.xml"


class Film404Error(Exception):
	pass
class InvalidYearError(Exception):
	pass

class RegistryUpdateError(Exception):
	pass


class MovieInfoScraper(object):
	def __init__(self, old_df, fernet, debug):
		self.old_df = old_df
		self.key = fernet
		self.debug = debug
		self.log = Logger(debug)

	def __enter__(self):
		return self

	def __exit__(self, exc_type, exc_value, tb):
		return True

	def __find_pages_to_parse__(self, url):
		response = requests.get(url).text
		soup = BeautifulSoup(response, "html.parser")
		movie_xmls = soup.findAll("loc")
		movie_xmls = [x.text for x in movie_xmls]
		return movie_xmls

	def __retrieve_links__(self, xml_pages):
		film_urls = []
		for xml in xml_pages:
			response = requests.get(xml).text
			soup = BeautifulSoup(response, "html.parser")
			film_urls += [x.text for x in soup.findAll("loc")]
		return film_urls

	def __get_new_urls__(self, urls):
		if self.old_df.empty:
			return urls
		df_urls = list(self.old_df.url)
		urls = [x for x in urls if x not in exclusion_list]
		need_urls = []
		for x in urls:
			x = x.replace('--', '-')
			if x not in df_urls:
				need_urls.append(x)  # Create list of new urls, used for getting other info faster
		return need_urls

	def __parse_urls__(self, film_urls):
		names = []
		ids = []
		seasons = []
		new_film_list = []

		for x in film_urls:
			if x in exclusion_list:
				continue
			try:
				id = int(x.split('/')[-2].split('-')[-1])
				name = x.split('/')[-2].split('-')[:-1]
				if "season" in name and name[-1].isdigit():  # film is a show
					season = name[-1].lstrip('0') # remove leading 0s
					name = " ".join(name[:-2])
				else:
					name = " ".join(name)
					season = None
				ids.append(id)
				names.append(name)
				seasons.append(season)
				new_film_list.append(x)
			except:
				self.log.debug("Failed to parse movie url:"+x)

		return ids, names, seasons, new_film_list

	def __get_other_info__(self, urls3):
		years = []  # Only thing we want now
		for url in tqdm(urls3, disable=self.debug):
			try:
				val = None
				response = requests.get(url).text
				if "https://ww4.fmovies.co/404.html" in response:
					raise Film404Error
				htmlparser = etree.HTMLParser()
				tree = etree.fromstring(response, htmlparser)
				r = tree.xpath('//p[@class="mb-1"]//a')  # year xpath
				y = int(r[-1].text)  # Last item in info is film year
				if not (y > 1800 and y < 2100):  # Valid year boundaries
					raise InvalidYearError
				years.append(y)

			except Film404Error:
				self.log.debug("This film has been removed: "+url)
				years.append(0)
			except InvalidYearError:
				self.log.debug("Invalid year boundries for url: "+url)
				years.append(1)
			except:
				self.log.debug("Something else went wrong: " + url)
				years.append(-1)
		return years

	def __save_file__(self, ids, names, seasons, years, urls):
		df = pd.DataFrame([names, seasons, years, ids, urls]).T
		df.columns = ['name', 'season', 'year', 'id', 'url']
		if self.old_df.empty:
			df_comb = df
		else:
			df_comb = pd.concat([self.old_df, df])
		df_comb.to_csv("./movieIds.csv", index=False)

		with open('movieIds.csv', 'rb') as file:  # Encrypt file
			original = file.read()
		encrypted = self.key.encrypt(original)
		with open('movieIds.csv', 'wb') as encrypted_file:
			encrypted_file.write(encrypted)

		return "Added {} more films to the registry. Current index at {}.".format(len(df), len(df_comb))

	def decrypt_save(self): # Functions for debugging
		with open('movieIds.csv', 'rb') as enc_file:
			encrypted = enc_file.read()
			decrypted = self.key.decrypt(encrypted)
		with open('movieIds_debug.csv', 'wb') as enc_file:
			enc_file.write(decrypted)

	def encrypt_save(self):
		with open('movieIds_debug.csv', 'rb') as file:  # Encrypt file
			original = file.read()
			encrypted = self.key.encrypt(original)
		with open('movieIds.csv', 'wb') as encrypted_file:
			encrypted_file.write(encrypted)

	def getInfo(self):  # MAIN
		try:
			xmls = self.__find_pages_to_parse__(base)
			urls = self.__retrieve_links__(xmls)
			new_urls = self.__get_new_urls__(urls)
			ids, names, seasons, valid_urls = self.__parse_urls__(new_urls)
			if len(valid_urls) == 0:
				return "Registry up to date"
			self.log.debug("Retrieving {} links".format(len(valid_urls)))
			years = self.__get_other_info__(valid_urls)

			return self.__save_file__(ids, names, seasons, years, valid_urls)
		except:
			raise RegistryUpdateError