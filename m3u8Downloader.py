
import re
import csv
import pathlib
from pathlib import Path
import os
import sys
import requests
import argparse
import subprocess
from sys import exit
from time import sleep
from seleniumwire import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.chrome.options import Options


class m3u8Downloader():
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

		chrome_options.add_argument("--log-level=3") # Remove console outputs
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
		final_m3u8 = None
		resolution = None
		for x in self.driver.requests:
			x = x.url
			if "/1080.m3u8" in x:
				final_m3u8 = x
				resolution = "1080"
				break
			elif "/720.m3u8" in x:
				final_m3u8 = x
				resolution = "720"
			elif "/360.m3u8" in x and resolution not in ["720","1080"]:
				final_m3u8 = x
				resolution = "360"

		return final_m3u8, resolution

	def get_name(self, url):
		return re.findall(r'.*/film/(.*)-\d+/', url)[0]

def clean_movie_input(l):
	new_l = []
	for movie in l:
		if re.match(r"[\w\s-]+$", movie[0]):
			new_l.append(movie[0].lower())
		else:
			print("Bad input: "+movie[0])
	return new_l

def get_urls_from_input(file, name):
	if file is None:
		data = [[name]]
	else:
		try:
			with open(file, newline='\n') as f:
				reader = csv.reader(f)
				data = list(reader)
		except:
			print('Could not open file'+str(file))
			exit(1)
	data = clean_movie_input(data)

	try:
		with open('./movieIds.csv', 'r', newline='\n') as f:
			reader = csv.reader(f)
			ids = list(reader)
	except:
		print("Could not find movieIds.txt file")
		exit(1)

	new_data = []
	for movie in data:
		for index in ids:
			if movie == index[0]:
				new_data.append(index[2])
	if len(new_data) != 0:
		print(f"{len(new_data)}/{len(data)} movies were found!")
	else:
		print("No movies were found :(, try again with the full title")
		exit(1)

	return new_data

def get_m3u8_links(data, m3u8Downloader):
	m3u8_out = []
	name_list = []
	try:
		with m3u8Downloader(debug=args.debug) as m3u8Downloader:
			for url in data:
				m3u8Downloader.load_page(url)
				sleep(2)
				m3u8Downloader.press_play_button()
				m3u8Downloader.close_popup()
				sleep(10)
				final_m3u8, resolution = m3u8Downloader.network()

				if final_m3u8 is None:
					print("Could not save: " + m3u8Downloader.get_name(url))
					#print("Failed url: " + url)
				else:
					m3u8_out.append(final_m3u8)
					name_list.append(m3u8Downloader.get_name(url) + "-" + resolution)
			# print(name_list[-1])
	except:
		print("Error exception when retrieving m3u8 links!!")
		exit(1)
	if len(m3u8_out) == 0:
		print("No movies could be saved")
		exit(1)
	return m3u8_out, name_list

def get_output_dir(out):
	if out is None:
		out_dir = os.path.join(Path().absolute(), "Output")
	else:
		out_dir = out

	if not os.path.exists(out_dir): # Create new directory
		os.makedirs(out_dir)

	# Future: could verify directory itself

	return out_dir

def download_m3u8_links(m3u8s, name_list, dir):
	b = 0
	for i in range(len(m3u8s)):
		response = requests.get(m3u8s[i])
		out_dir = Path(str(os.path.join(dir, name_list[i])+'.m3u8'))
		open(out_dir, "wb").write(response.content)
		#b += int(Path(dir + name_list[i] + '.m3u8').stat().st_size) # get file sizes
		b += int(out_dir.stat().st_size)
	if len(os.listdir(dir)) == 0:
		print("Could not download any files") # Not getting here for some reason
		exit(1)
	return b

def convert_to_mp4(name_list, dir):
	for x in name_list:
		old_file = str(os.path.join(dir, x)+'.m3u8')
		new_file = str(os.path.join(dir, x) + '_2.mp4')
		command = ('ffmpeg.exe -protocol_whitelist file,http,https,tcp,tls,crypto -i '
			     + old_file + ' -c copy -bsf:a aac_adtstoasc ' + new_file)
		#print(command)
		try:
			subprocess.run(command,shell=True,stderr=subprocess.DEVNULL,stdout=subprocess.DEVNULL)
			#os.remove(old_file)
			#os.rename(new_file, str(os.path.join(dir, x) + '.mp4'))
			print("\tConverted: " + x + ".mp4")
		except subprocess.CalledProcessError:
			print("Could not convert: "+x)
		except FileNotFoundError:
			print("Could not find file? "+x)



if __name__ == '__main__':
	parser = argparse.ArgumentParser(description='M3U8-->MP4 Movie Scraper')
	group = parser.add_mutually_exclusive_group(required=True)
	group.add_argument('--file', type=str, help='path to txt file of all desired movie names by line')
	group.add_argument('--movie', type=str, help='movie name in quotes')
	parser.add_argument('--out', type=str, help='path to output directory for mp4', required=False)
	parser.set_defaults(debug=False) # Change to True to see selenium browser
	args = parser.parse_args()

	# 1.) Read, clean and cross-reference movie names to obtain links
	data = get_urls_from_input(args.file, args.movie)

	# 2.) Find m3u8 links for each movie using selenium wire
	print("Retrieving m3u8 links (~ "+str(round(len(data)*0.4,2))+" minutes)...")
	m3u8_out, name_list = get_m3u8_links(data, m3u8Downloader)

	# 3.) Handle output directory
	output_dir = get_output_dir(args.out) # Should handle "C:/user/..../..." or "../movies_folder/" or default

	# 4.) Download each m3u8 file by accessing the m3u8 links
	print("\nDownloading m3u8 files (~ "+str(round(len(m3u8_out)*0.05,2))+" minutes)...")
	m3u8_bytes = download_m3u8_links(m3u8_out, name_list, output_dir)

	# 5.) Using the m3u8 files, convert to mp4 using ffmpeg
	print("Beginning conversion now (~ "+str(round((m3u8_bytes / 1000) * (2.25 / 603), 1))+" minutes)...") # 2.5 mins for 1.5 hrs conversion
	convert_to_mp4(name_list, output_dir)

	print("Done!")
	exit(0)


#python .\m3u8Downloader.py --File "movies.txt"