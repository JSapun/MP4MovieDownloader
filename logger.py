
import time
from termcolor import colored

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