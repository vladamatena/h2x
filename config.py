import os
import configparser

class Config:
	def __init__(self, configname=["h2x.conf", os.path.expanduser("~/.h2x/h2x.conf"), "/etc/h2x/h2x.conf"]):
		config = configparser.ConfigParser()
		config.read(configname)
		
		self.JID = config.get("component", "JID")
		self.HOST = config.get("component", "Host")
		self.PORT = config.get("component", "Port")
		self.PASSWORD = config.get("component", "Password")
