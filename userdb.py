# User database for h2x component
#
# Stores tokens in files according to username
#

import os
import shlex
import datetime

STORAGE = "users/"

class User:
	def __init__(self, username):
		self.__username = username
		
	def __userPath(self):
		return shlex.quote(STORAGE + self.username)
		
	@property
	def username(self):
		return self.__username

	@property
	def token(self):
		try:
			file = open(self.__userPath(), 'r')
			return file.read()
		except BaseException as e:
			raise Exception("Token not available for user " + self.username) from e
        
	@token.setter
	def token(self, value):
		self.__token = value;
	
	def tokenPath(self):
		return self.__userPath()
	
	def tokenRefreshPath(self):
		return self.__userPath() + ".refresh"
