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

	@property
	def lastMessageTimestamp(self):
		try:
			file = open(self.__userPath() + ".lastmessage", 'r')
			return float(file.read())
		except:
			return 0
		
	@lastMessageTimestamp.setter
	def lastMessageTimestamp(self, value):
		try:
			file = open(self.__userPath() + ".lastmessage", 'w')
			file.write(str(value))
			file.close()
		except BaseException as e:
			raise("Failed to read last message time for user " + self.username) from e
	
	def tokenPath(self):
		return self.__userPath()
	
	def tokenRefreshPath(self):
		return self.__userPath() + ".refresh"
