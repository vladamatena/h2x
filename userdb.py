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
		
	def __userPath(self, user):
		return shlex.quote(self.STORAGE + user.username)
		
	def getUser(self, username):
		try:
			file = open(self.__userPath(user), 'r')
			token = file.read()
		except:
			return None
		
		return User(username, token)
	
	def putUser(self, user):
		file = open(self.__userPath(user), 'w')
		file.write(user.token)
		file.close()
	
	def removeUser(self, user):
		os.remove(self.__userPath(user))
