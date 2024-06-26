
from getMovieIds import *

import re
import csv
import argparse
import requests
from termcolor import colored
import os
import sys
import time
import pathlib
import subprocess
from sys import exit
from time import sleep
from pathlib import Path
from seleniumwire import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.chrome.options import Options

class HttpError403(Exception):
	pass
class NoMoviesSaved(Exception):
	pass
class EmptyDirectory(Exception):
	pass

class Logger(object):
	def __init__(self, debugger=False):
		self.debugger = debugger
	def print(self, msg):
		print(colored(msg, 'yellow'))

	def debug(self, msg):
		if self.debugger is True:
			print(colored(msg, 'blue'))

	def error(self, msg):
		print(colored(msg, 'red'))
	def timer(self, start):
		self.debug("Completed in: "+str(time.time() - start)+" seconds")

class m3u8Finder():
	def __init__(self, debug=False):
		self.debug = debug
		self.driver = self.get_driver()
		self.wait = WebDriverWait(self.driver, 10)

	def __enter__(self):
		return self

	def __exit__(self, exc_type, exc_value, tb):
		self.driver.quit()
		return True

	def get_driver(self, debug=False):
		chrome_options = Options()

		if not self.debug:
			chrome_options.add_argument("--headless")

		chrome_options.add_argument("--log-level=3")  # Remove console outputs
		chrome_options.add_experimental_option('excludeSwitches', ['enable-logging'])
		chrome_options.add_argument("--disable-notifications")
		driver = webdriver.Chrome(chrome_options=chrome_options)

		if self.debug:
			driver.maximize_window()

		return driver

	def load_page(self, url):
		self.driver.get(url)

	def close_popup(self):
		all = self.driver.window_handles
		current = self.driver.current_window_handle
		self.driver.switch_to.window([w for w in all if w != current][0])
		self.driver.close()
		self.driver.switch_to.window(current)

	def press_play_button(self):
		self.wait.until(EC.element_to_be_clickable((By.XPATH, "//a[@id='play-now']"))).click()

	def network(self):
		master_list = []
		way = 0
		for x in self.driver.requests:
			if "/master.m3u8" in x.url:
				way += 1
				master_list.append(x)

		return master_list, way

	def parse_network_masters(self, master_list, way, res):
		if len(master_list) == 0 or way > 3:
			log.error("Something wrong")
			return None, None
		elif way == 1:
			log.debug("Found m3u8 -- way 1")
			return master_list[0].url.replace("master", res), res
		elif way == 2:
			log.error("Need to implement master.m3u8 --> index.m3u8")
			return None, None
		elif way == 3:
			res = "720"
			log.error("Need to implement master.m3u8 .ts")
			return None, None

	def get_name(self, url):
		return re.findall(r'.*/film/(.*)-\d+/', url)[0]

class m3u8Downloader():
	def __init__(self, debug=False):
		self.debug = debug

	def __enter__(self):
		return self

	def __exit__(self, exc_type, exc_value, tb):
		return True

	def __clean_movie_input__(self, l):
		new_l = []
		for movie in l:
			if re.match(r"[\w\s-]+$", movie[0]):
				new_l.append(movie[0].lower())
			else:
				log.print("Bad input: "+movie[0])
		return new_l

	def get_urls_from_input(self, file, name):
		if file is None:
			data = [[name]]
		else:
			try:
				with open(file, newline='\n') as f:
					reader = csv.reader(f)
					data = list(reader)
			except:
				log.print('Could not open file'+str(file))
				exit(1)
		data = self.__clean_movie_input__(data)

		try:
			with open('./movieIds.csv', 'r', newline='\n') as f:
				reader = csv.reader(f)
				ids = list(reader)
		except:
			log.error("Could not find movieIds.txt file")
			exit(1)

		new_data = []
		for movie in data:
			for index in ids:
				if movie == index[0]:
					new_data.append(index[2])
		if len(new_data) != 0:
			log.print(f"{len(new_data)}/{len(data)} movies were found!")
		else:
			log.error("No movies were found :(, try again with the full title")
			exit(1)

		return new_data

	def get_m3u8_links(self, m3u8Finder, data, res):
		try:
			m3u8_out = []
			name_list = []
			with m3u8Finder(debug=self.debug) as m3u8Finder:
				print() # Formatting for output :)
				for url in data:
					m3u8Finder.load_page(url)
					sleep(2)
					m3u8Finder.press_play_button()
					m3u8Finder.close_popup()
					sleep(10)
					master_list, way = m3u8Finder.network()
					m3u8, resolution = m3u8Finder.parse_network_masters(master_list, way, res)

					if m3u8 is None:
						log.print("\tCould not save: " + m3u8Finder.get_name(url))
					else:
						m3u8_out.append(m3u8)
						name_list.append(m3u8Finder.get_name(url) + "-" + resolution)
			if len(m3u8_out) == 0:
				raise NoMoviesSaved
			else:
				return m3u8_out, name_list
		except NoMoviesSaved:
			log.error("No movies could be saved")
			exit(1)
		except Exception as e:
			log.debug(e)
			log.error("Unexpected error when retrieving m3u8 links")
			exit(1)

	def get_output_dir(self, out):
		out_dir = out
		"""if out is None:
			out_dir = os.path.join(Path().absolute(), out)
		else:
			out_dir = out"""

		if not os.path.exists(out_dir): # Create new directory
			os.makedirs(out_dir)

		# Future: could verify directory itself

		return out_dir

	def download_m3u8_links(self, m3u8s, name_list, dir):
		try:
			b = 0
			for i in range(len(m3u8s)):
				response = requests.get(m3u8s[i])
				out_dir = Path(str(os.path.join(dir, name_list[i])+'.m3u8'))
				open(out_dir, "wb").write(response.content)
				#b += int(Path(dir + name_list[i] + '.m3u8').stat().st_size) # get file sizes
				b += int(out_dir.stat().st_size)
			if len(os.listdir(dir)) == 0:
				raise EmptyDirectory
			return b
		except EmptyDirectory:
			log.error("Could not download any m3u8 links")
			exit(1)
		except Exception as e:
			log.debug(e)
			log.error("Unexpected error when downloading m3u8 links")
			exit(1)

	def convert_to_mp4(self, name_list, dir):
		for x in name_list:
			old_file = str(os.path.join(dir, x)+'.m3u8')
			new_file = str(os.path.join(dir, x) + '_2.mp4')
			command = ('ffmpeg.exe -protocol_whitelist file,http,https,tcp,tls,crypto -i '
				     + old_file + ' -c copy -bsf:a aac_adtstoasc ' + new_file)
			log.debug(command)
			try:
				if os.path.exists(new_file): # Delete before converting in case
					os.remove(new_file)
				proc = subprocess.run(command,shell=True,stderr=subprocess.PIPE,stdout=subprocess.DEVNULL)
				os.remove(old_file)
				if 'HTTP error 403 Forbidden' in proc.stderr.decode('utf-8'):
					raise HTTPError403
				os.rename(new_file, str(os.path.join(dir, x) + '.mp4'))
				log.print("\tConverted: " + x + ".mp4")

			except HttpError403:
				log.error("Failed to convert: "+x)
				log.debug("HTTP error 403 Forbidden --> bad m3u8 link, check site network")
			except subprocess.CalledProcessError:
				log.error("Could not convert: "+x)
			except FileNotFoundError:
				log.error("Could not find file? "+x)
			except Exception as e:
				log.debug(e)
				log.error("Unexpected error when converting m3u8 files")



if __name__ == '__main__':
	parser = argparse.ArgumentParser(description='M3U8-->MP4 Movie Scraper')
	group1 = parser.add_mutually_exclusive_group(required=False)
	group1.add_argument('-t','--txt', type=str, help='path to txt file of all desired movie names by line')
	group1.add_argument('-f','--film', type=str, help='film name in quotes (movie or show)')
	group2 = parser.add_mutually_exclusive_group(required=True)
	group2.add_argument_group(group1)
	group2.add_argument('-u','--update', action='store_true', help='update film registry for newer films')
	parser.add_argument('-o','--out', type=str, help='path to output directory for mp4', default="Output", required=False)
	parser.add_argument('-r','--res', type=str, help='video resolution (360, 720, or 1080)', default="1080", required=False)
	parser.set_defaults(debug=True) # Change to True to see more print statements
	args = parser.parse_args()

	log = Logger(args.debug)
	m3u8Downloader = m3u8Downloader(False)  # Change to True to see selenium browser

	if args.update == True: # For updating the movie id registry
		log.print("Updating registry (~0.2 minutes)")
		start = time.time()
		log.debug(getMovieIds())
		log.timer(start)

	# 1.) Read, clean and cross-reference movie names to obtain links
	urls = m3u8Downloader.get_urls_from_input(args.txt, args.film)


	# 2.) Find m3u8 links for each movie using selenium wire
	log.print("Retrieving m3u8 links (~ "+str(round(len(urls)*0.4,2))+" minutes)...")
	start = time.time()
	m3u8_out, name_list = m3u8Downloader.get_m3u8_links(m3u8Finder, urls, args.res)
	log.debug(str(len(urls))+" m3u8 links found")
	log.timer(start)


	# 3.) Handle output directory
	output_dir = m3u8Downloader.get_output_dir(args.out) # Should handle "C:/user/..../..." or "../movies_folder/" or default


	# 4.) Download each m3u8 file by accessing the m3u8 links
	log.print("Downloading m3u8 files (~ "+str(round(len(m3u8_out)*0.02,2))+" minutes)...")
	start = time.time()
	m3u8_bytes = m3u8Downloader.download_m3u8_links(m3u8_out, name_list, output_dir)
	log.debug(str(len(m3u8_out))+" m3u8 links downloaded")
	log.timer(start)


	# 5.) Using the m3u8 files, convert to mp4 using ffmpeg
	log.print("Beginning conversion now (~ "+str(round((m3u8_bytes / 1000) * (2.25 / 603), 1))+" minutes)...") # 2.5 mins for 1.5 hrs conversion
	start = time.time()
	m3u8Downloader.convert_to_mp4(name_list, output_dir)

	log.timer(start)
	log.debug(str(m3u8_bytes)+" total bytes converted")
	log.print("Done!")
	exit(0)


#python .\m3u8Downloader.py --File "movies.txt"