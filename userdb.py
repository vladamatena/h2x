# User database for h2x component
#
# Stores tokens in files according to username
#

import os
import shlex

class User:
	def __init__(self, username, token):
		self.username = username
		self.token = token

class UserDB:
	def __init__(self):
		self.STORAGE = "users/"
		
	def __userPath(self, username):
		return shlex.quote(self.STORAGE + username)
	
	def tokenPath(self, user):
		return self.__userPath(user.username)
	
	def tokenRefreshPath(self, user):
		return self.__userPath(user.username) + ".refresh"
		
	def getUser(self, username):
		try:
			file = open(self.__userPath(username), 'r')
			token = file.read()
		except Exception as e:
			print("User lookup failed:" + e.__str__())
			return None
		
		return User(username, token)
	
	def putUser(self, user):
		file = open(self.__userPath(user.username), 'w')
		file.write(user.token)
		file.close()
	
	def removeUser(self, user):
		os.remove(self.__userPath(user.username))
