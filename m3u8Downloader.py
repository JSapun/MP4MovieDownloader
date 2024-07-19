
from getMovieIds import *
from logger import Logger
from getMovieIds import MovieInfoScraper

import re
import csv
import argparse
import requests
from cryptography.fernet import Fernet
import os
import traceback

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
class FFMPEGInvalidInput(Exception):
	pass
class NoMoviesSaved(Exception):
	pass


class m3u8Finder(object):
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
		return self.driver.requests

	def clear_network(self):
		del self.driver.requests

	def parse_network_masters(self, master_list, res):
		index = 0
		cnt = 0
		dumb = []
		for i in range(len(master_list)):
			if master_list[i].response is not None and master_list[
				i].response.headers.get_content_type() == 'application/vnd.apple.mpegurl':
				if "/master.m3u8" in master_list[i].url or "/index.m3u8" in master_list[i].url:
					index = i  # Get last m3u8 one, indicating valid
					cnt += 1
					dumb.append(master_list[i].url)
		if cnt != 1:
			log.debug("Found more or less than 1 m3u8 link?? Going to ignore")


		xhr_list = ['font/woff', 'image/jpg', 'image/png', 'image/gif', 'text/vtt', 'text/css', 'text/javascript',
				'video/mp2t', 'application/vnd.apple.mpegurl']

		sub_master_list = [x for x in master_list[index:] if (
					x.response is not None and x.response.headers.get_content_type() in xhr_list)]  # Get xhr requests
		sub_content_type = [x.response.headers.get_content_type() for x in sub_master_list]  # Get xhr requests

		if master_list[index].response.status_code == 200:  # confirm good
			if sum([1 if any(ext in x.url for ext in ["/360.m3u8", "/720.m3u8", "/1080.m3u8", "/master.m3u8"]) else 0
				  for x in sub_master_list]) == 2:
				# Way 1 -- master.m3u8
				log.debug("Found m3u8 -- way 1")
				return master_list[index].url.replace("master", res), res, 1
			elif sum([0 if x == 'video/mp2t' else 1 for x in
				    sub_content_type[-5:]]) == 0:  # Way 2 or 3 --> master.m3u8 --> .ts
				if "/index.m3u8" in master_list[index].url:  # way 2, for simplicity, only 720
					log.debug("Found m3u8 -- way 2 (index.m3u8 .ts)")
					return master_list[index].url, "720", 2
				else:  # way 3
					log.debug("Found m3u8 -- way 3 (master.m3u8 .ts)")
					return master_list[index].url, "720", 3  # this method only supports 720
			else:
				log.debug("RIP --> could not figure out m3u8 method")
				log.debug(index)
				log.debug(master_list[index])
				log.debug(sum([1 if any(ext in x.url for ext in ["/360.m3u8", "/720.m3u8", "/1080.m3u8", "/master.m3u8"]) else 0
				  for x in sub_master_list]))
				return "", "", 0
		else:
			log.debug("RIP --> Not good m3u8 status code")
			return "", "", 0

	def find_num_episodes(self):
		# self.wait.until(EC.element_to_be_clickable((By.XPATH, "//button[@class='btn btn-dark m-1 ms-0 episode']"))).click()
		return len(self.driver.find_elements(By.XPATH, "//button[@class='btn btn-dark m-1 ms-0 episode']")) + 1

	def click_episode(self, ep):
		try:
			self.wait.until(EC.element_to_be_clickable((By.XPATH, "//button[@id='ep-{}']".format(ep)))).click()
		except:
			print("Could not click next episode")
			exit(1)

	def get_name(self, url):
		return re.findall(r'.*/film/(.*)-\d+/', url)[0]

class m3u8Downloader(object):
	def __init__(self, debug=False):
		self.debug = debug

	def __enter__(self):
		return self

	def __exit__(self, exc_type, exc_value, tb):
		return True

	def load_csv(self, key):
		try:
			with open('movieIds.csv', 'rb') as enc_file:
				encrypted = enc_file.read()
				decrypted = key.decrypt(encrypted)
				ids = decrypted.decode('utf-8').splitlines(keepends=False)[1:]
				ids = [x.split(',') for x in ids]
		except:
			log.error("Could not find movieIds.txt file")
			exit(1)
		return pd.DataFrame(ids, columns=['name', 'season', 'year', 'id', 'url'])

	def args_logic(self):
		return None

	def __parse_input_file__(self, input):
		if len(input) > 1:
			input = [x[0] for x in input]
		data = []
		year = []
		show = []
		for s in input:
			if '-' in s:  # year
				s = s.split('-')
				year.append(s[1][1:])  # remove additional space and add year
				s = s[0][:-1]
			else:
				year.append(None)
			if 'season' in s and s[-1].isdigit():  # show
				s = s.split(' ')
				show.append(int(float(s[-1])))
				s = " ".join(s[:-2])
			else:
				show.append(None)
			data.append(s)  # Data
		return data, show, year

	def __parse_input_film__(self, n, y):
		name = n.split(' ')
		if "season" in n and n[-1].isdigit():  # film is a show
			season = int(float(name[-1].lstrip('0')))  # remove leading 0s
			name = " ".join(name[:-2])
			date = y
		else:
			name = " ".join(name)
			season = None
			date = y
		return [name], [season], [date]

	def __clean_movie_input__(self, file, n, y):
		if file is None:
			# Check if film or movie, then parse
			names, seasons, dates = self.__parse_input_film__(n, y)

		else: # Open file
			try:
				with open(file, newline='\n') as f: # Try to read file
					reader = csv.reader(f)
					d = list(reader)
					names, seasons, dates = self.__parse_input_file__(d)
					# define year y here, and season
			except:
				log.print('Could not open file '+str(file))
				exit(1)

		new_n = []
		new_d = []
		new_s = []
		for i in range(len(names)):
			if not re.match(r"[\w\s-]+$", names[i]):
				log.print("Bad film input: "+names[i])
				continue
			if dates[i] is not None:
				if not (len(dates[i]) == 4 and int(dates[i]) > 1800 and int(dates[i]) < 2100):
					log.print("Bad year input: "+dates[i])
					continue
			if not (seasons[i] is None or seasons[i] > 0):
				log.print("Bad season input: " + seasons[i])
				continue
			new_n.append(names[i].lower())
			new_d.append(dates[i])
			new_s.append(seasons[i])

		return new_n, new_d, new_s

	def get_urls_from_input(self, df_ids, file, names, years):

		data, year_list, season_list = self.__clean_movie_input__(file, names, years) # Input

		new_data = []
		for i in range(len(data)):
			if season_list[i] is not None: # Save time by checking only movie or show list
				df = df_ids[df_ids.season != '']
				df.season = [int(float(x)) for x in df.season] # Convert to int for easier comparision
				df = df[df.season == season_list[i]]
				vocab = "show"
			else:
				df = df_ids[df_ids.season == ''] # None values represented by ''
				vocab = "movie"
			sub_df = df[df.name == data[i]]
			if len(sub_df) == 0:  # No films found
				print("Could not find {}: '{}'".format(vocab, data[i]))
			elif len(sub_df) == 1:  # One film:
				if year_list[i] is None:  # Found 1, no year flag
					new_data.append(sub_df.url.values[0])
				else:  # Found 1 with year flag
					if sub_df.year.values[0] == year_list[i]:  # Correct year
						new_data.append(sub_df.url.values[0])
					else:  # Incorrect year
						print("{}: '{}' found, try again with the correct year".format(vocab, data[i]))
			else:  # Multiple films
				if year_list[i] is None:  # Found multiple, no year flag
					print("{} {}s found with the same name: '{}', try again using the year flag".format(
						len(sub_df), vocab, data[i]))
				else:  # Found multiple with year flag
					sub_df = sub_df[sub_df.year == year_list[i]]
					if len(sub_df) > 0:  # Found film
						new_data.append(sub_df.url.values[0])
					else:  # Multiple films
						print("Multiple {}s found: '{}', try again with the correct year.".format(vocab,
																		  data[i]))
		return new_data, [False if x is None else True for x in season_list] # return boolean for saving

	def get_m3u8_links(self, m3u8Finder, data, show_list, res):
		"""
		This function tries to find the m3u8 links. Note, for shows, we will need to retrieve links for all episodes
		in a season. Returning a list of (list of strings/strings).
		"""
		if res is None:
			res = "1080"
		try:
			m3u8_out = []
			name_list = []
			res_list = []
			with m3u8Finder(debug=self.debug) as m3u8Finder2:
				print()  # Formatting for output :)
				for i in range(len(data)):
					url = data[i]

					m3u8Finder2.load_page(url)
					sleep(2)
					m3u8Finder2.press_play_button()
					m3u8Finder2.close_popup()

					m3u8 = []
					way = 0
					if show_list[i]:  # Show episode retrieval
						del_req = m3u8Finder2.network()  # Clear requests
						episodes = m3u8Finder2.find_num_episodes()
						for ep in range(1, episodes + 1):  # Iterate through episodes and get m3u8 links
							m3u8Finder2.load_page(url)
							sleep(2)
							m3u8Finder2.press_play_button()
							try:
								m3u8Finder2.close_popup()  # in case
							except:
								pass
							if ep != episodes:  # Do not need to repress if last episode, default loading
								del_req = m3u8Finder2.network()  # Clear requests
								m3u8Finder2.click_episode(ep)
								del_req = m3u8Finder2.network()  # Clear requests
							sleep(10)
							master_list = m3u8Finder2.network()
							try:
								m3u8_temp, resolution, way = m3u8Finder2.parse_network_masters(master_list,res)
							except:
								print("idk why")
							if len(m3u8_temp) == 0:
								m3u8 = []  # Just don't bother saving any episodes if one fails
								break
							m3u8.append(m3u8_temp)

					else:  # Single movie retrieval
						sleep(12)
						master_list = m3u8Finder2.network()
						m3u8, resolution, way = m3u8Finder2.parse_network_masters(master_list, res)
					if len(m3u8) == 0:
						log.print("\tCould not save: " + m3u8Finder2.get_name(url))
					else:
						m3u8_out.append(m3u8)
						name_list.append(m3u8Finder2.get_name(url) + "-" + resolution)
						res_list.append(resolution)

			if len(m3u8_out) == 0:
				raise NoMoviesSaved
			else:
				return m3u8_out, name_list, res_list # return a list of lists/str,
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
			updated_name_list = []
			b = 0
			for i in range(len(m3u8s)):
				index = m3u8s[i]
				name = name_list[i]
				if isinstance(index, list): # show
					temp_list = []
					temp_list.append(name)
					new_path_dir = os.path.join(dir,name)
					os.makedirs(new_path_dir) # Create sub-directory for season
					for k in range(len(index)):
						response = requests.get(index[k])
						if "404 Not Found" in response.content.decode('utf-8'):
							log.error("Invalid resolution, try inputting a lower value: "+name)
							break
						out_dir = Path(str(os.path.join(new_path_dir, name)+"-ep"+str(k+1)+'.m3u8'))
						open(out_dir, "wb").write(response.content)
						b += int(out_dir.stat().st_size)
						temp_list.append(name+"-ep"+str(k+1))
					updated_name_list.append(temp_list)
				else:
					response = requests.get(index)
					if "404 Not Found" in response.content.decode('utf-8'):
						log.error("Invalid resolution, try inputting a lower value: "+name)
						continue
					out_dir = Path(str(os.path.join(dir, name)+'.m3u8'))
					open(out_dir, "wb").write(response.content)
					b += int(out_dir.stat().st_size)
					updated_name_list.append(name)
			if len(os.listdir(dir)) == 0:
				raise EmptyDirectory
			return updated_name_list, b
		except EmptyDirectory:
			log.error("Could not download any m3u8 links")
			exit(1)
		except Exception as e:
			log.debug(e)
			log.error("Unexpected error when downloading m3u8 links")
			exit(1)

	def __convert_single__(self, name, dir):
		old_file = str(os.path.join(dir, name) + '.m3u8')
		new_file = str(os.path.join(dir, name) + '_2.mp4')
		command = ('ffmpeg.exe -protocol_whitelist file,http,https,tcp,tls,crypto -i '
			     + old_file + ' -c copy -bsf:a aac_adtstoasc ' + new_file)
		log.debug(command)
		try:
			if os.path.exists(new_file):  # Delete before converting in case
				os.remove(new_file)
			proc = subprocess.run(command, shell=True, stderr=subprocess.PIPE, stdout=subprocess.DEVNULL)
			os.remove(old_file)
			if 'HTTP error 403 Forbidden' in proc.stderr.decode('utf-8'):
				raise HTTPError403
			elif 'Invalid data found when processing input' in proc.stderr.decode('utf-8'):
				raise FFMPEGInvalidInput
			os.rename(new_file, str(os.path.join(dir, name) + '.mp4'))
			log.print("\tConverted: " + name + ".mp4")

		except HttpError403:
			log.error("Failed to convert: " + name)
			log.debug("HTTP error 403 Forbidden --> bad m3u8 link, check site network")
		except FFMPEGInvalidInput:
			log.error("Failed to convert: " + name)#+". Possible causes: invalid resolution input, incorrect stream parsing")
			log.debug("Bad m3u8 link --> check network site, caused by different m3u8 streaming methods (index.ts)")
		except subprocess.CalledProcessError:
			log.error("Could not convert: " + name)
		except FileNotFoundError:
			log.error("Could not find file? " + name)
		except Exception as e:
			log.debug(e)
			log.error("Unexpected error when converting m3u8 files")

	def convert_to_mp4(self, name_list, dir):
		if len(name_list) == 0:
			log.error("No films to convert")
			exit(1)
		for x in name_list:
			if isinstance(x, list):  # show
				for y in x[1:]:
					new_path_dir = os.path.join(dir, x[0])
					self.__convert_single__(y, new_path_dir)
			else:
				self.__convert_single__(x, dir)




if __name__ == '__main__':
	if len(sys.argv) > 1:
		parser = argparse.ArgumentParser(description='M3U8-->MP4 Movie Scraper')
		group1 = parser.add_mutually_exclusive_group(required=False)
		group1.add_argument('-t', '--txt', type=str, help='path to txt file of all desired movie names by line')
		group1.add_argument('-f', '--film', type=str, help='film name in quotes (movie or show)')
		parser.add_argument('-u', '--update', action='store_true', help='update film registry for newer films',
					  required=False)
		parser.add_argument('-o', '--out', type=str, help='path to output directory for mp4', default="Output",
					  required=False)
		parser.add_argument('-r', '--res', type=str, help='video resolution (360, 720, or 1080)', default="1080",
					  required=False)
		parser.add_argument('-y', '--year', type=str, help='year of film', required=False)
		parser.set_defaults(debug=False)  # Change to True to see more print statements
		args = parser.parse_args()

		if not args.update and not (args.txt or args.film):
			parser.error("-u or --txt or --film is required")
			exit(1)
	else:
		print("Error: no arguments passed")
		""" GUI -->
		print("Welcome to the M3U8-->MP4 Movie Scraper")
		show_bool = input("Do you want to download a tv-show? (y/n)")

		advanced_opt = input("Do you want advanced options? (y/n)")
		if advanced_opt:
			if input("Would you like to download multiple films with a text file? (y/n)"):
				txt_fil = None
			else:
				if show_bool:
					film = input("Enter your desired show: ")
				else:
					film = input("Enter your desired movie: ")

			update_bool = input("Would you like to update the movie registry? (y/n)")
			out_bool = input("Would you like to specify an output directory" (y/n)
			res_bool = input("Would you like to specify an output resolution? (y/n)")

		manual_input()
		"""
		exit(1)

	try: # To prevent users from seeing PATH statements when failing
		log = Logger(args.debug)
		m3u8Downloader = m3u8Downloader(False)  # Change to True to see selenium browser
		key_binary = b's3WrX9o-kU42GxYfimhDcryvCUEcT3WDd4h9qTtwzjE='
		key_fernet = Fernet(key_binary)
		df = m3u8Downloader.load_csv(key_fernet)


		if args.update == True: # For updating the movie id registry
			log.print("Updating registry (~0.25 minutes)")
			start = time.time()
			try:
				movie_info = MovieInfoScraper(df, key_fernet, args.debug)
				log.print(movie_info.getInfo())
				df = m3u8Downloader.load_csv(key_fernet) # Reload csv
			except RegistryUpdateError:
				log.error("Failed to update registry")
			log.timer(start)


		# 1.) Read, clean and cross-reference movie names to obtain links
		urls, show_list = m3u8Downloader.get_urls_from_input(df, args.txt, args.film, args.year)

		
		# 2.) Find m3u8 links for each movie using selenium wire
		log.print("Retrieving m3u8 links (~ "+str(round(len(urls)*0.4,2))+" minutes)...")
		start = time.time()
		m3u8_out, name_list, res_list = m3u8Downloader.get_m3u8_links(m3u8Finder, urls, show_list, args.res)
		log.debug(str(len(urls))+" m3u8 films found")
		log.timer(start)


		# 3.) Handle output directory
		output_dir = m3u8Downloader.get_output_dir(args.out) # Should handle "C:/user/..../..." or "../movies_folder/" or default


		# 4.) Download each m3u8 file by accessing the m3u8 links
		log.print("Downloading m3u8 files (~ "+str(round(len(m3u8_out)*0.1,2))+" minutes)...")
		start = time.time()
		name_list, m3u8_bytes = m3u8Downloader.download_m3u8_links(m3u8_out, name_list, output_dir)
		log.debug(str(len(m3u8_out))+" m3u8 links downloaded")
		log.timer(start)


		# 5.) Using the m3u8 files, convert to mp4 using ffmpeg
		"""if max(way_list)==1: # 2.5 mins for 1.5 hrs conversion
			log.print("Beginning conversion now (~ "+str(round(m3u8_bytes * (2.5/610000) , 1))+" minutes)...")
		elif max(way_list)==2 or max(way_list)==3: # 2.8 mins for 0.75 hr conversion
			log.print("Beginning conversion now (~ " + str(round(m3u8_bytes / 747, 1)) + " minutes)...")"""
		if "1080" in res_list: # 12 mins for 4.5 hr conversion -- IDK
			log.print("Beginning conversion now (~ " + str(round(m3u8_bytes * (1/132000), 1)) + " minutes)...")
		else: # 6 mins for 1.5 hrs conversion
			log.print("Beginning conversion now (~ " + str(round(m3u8_bytes * (1/79000), 1)) + " minutes)...")
		start = time.time()
		m3u8Downloader.convert_to_mp4(name_list, output_dir)
		log.timer(start)
		log.debug(str(m3u8_bytes)+" total bytes converted")


		log.print("Done!")
		exit(0)
	except Exception as e:
		if args.debug:
			print(traceback.format_exc())
		else:
			print(colored("Error during execution, please download the most up to date script.", 'red'))
		exit(1)


# python .\m3u8Downloader.py --File "movies.txt"

# python setup.py build

