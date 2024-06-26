
import re
import requests
from bs4 import BeautifulSoup, SoupStrainer
import pandas as pd
import warnings
from bs4 import GuessedAtParserWarning
warnings.filterwarnings('ignore')


def find_pages_to_parse(url):
	response = requests.get(url).text
	soup = BeautifulSoup(response, "html.parser")
	movie_xmls = soup.findAll("loc")
	movie_xmls = [x.text for x in movie_xmls]
	return movie_xmls

def retrieve_links(xml_pages):
	film_urls = []
	for xml in xml_pages:
		response = requests.get(xml).text
		soup = BeautifulSoup(response, "html.parser")
		film_urls += [x.text for x in soup.findAll("loc")]
	return film_urls

def parse_urls(film_urls):
	names = []
	ids = []
	seasons = []
	cnt = 0
	for x in film_urls:
		try:
			id = int(x.split('/')[-2].split('-')[-1])
			name = x.split('/')[-2].split('-')[:-1]
			if "season" in name: # film is a show
				name = " ".join(name[:-2])
				season = name[-1]
			else:
				name = " ".join(name)
				season = None
			ids.append(id)
			names.append(name)
			seasons.append(season)
		except:
			cnt += 1
			continue
	#print("Missed "+str(cnt)+" film(s)")

	return names, ids, seasons


def getMovieIds():
	base = "https://ww4.fmovies.co/sitemap.xml"

	xmls = find_pages_to_parse(base)
	urls = retrieve_links(xmls)
	ids, names, seasons = parse_urls(urls)

	df = pd.DataFrame([names, ids, seasons, urls]).T
	df.columns = ['name', 'id', 'season', 'url']

	df_prev = pd.read_csv('./movieIds.csv')
	df.to_csv("./movieIds.csv", index=False)

	return "Added {} film(s) to index".format(len(df) - len(df_prev))