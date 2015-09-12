import os
import configparser

class Config:
	def __init__(self, configname=["h2x.conf",os.path.expanduser("~/.h2x/h2x.conf"),"/etc/h2x/h2x.conf"]):
		config = configparser.ConfigParser()
		config.read(configname)
		self.JID = config.get("component", "JID")
		self.HOST = config.get("component", "Host")
		self.PORT = config.get("component", "Port")
		self.PASSWORD = config.get("component", "Password")
	
		self.DB_HOST = config.get("database", "Host")
		if self.DB_HOST == "":
			self.DB_HOST = None
		self.DB_TYPE = config.get("database", "Type")
		self.DB_USER = config.get("database", "User")
		self.DB_NAME = config.get("database", "Name")
		self.DB_PASS = config.get("database", "Password")
		self.DB_PREFIX = config.get("database", "Prefix")
