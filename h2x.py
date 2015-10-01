import sys
import time
import asyncio

from twisted.internet import reactor
from twisted.words.xish import domish,xpath
from twisted.words.xish.domish import Element
from twisted.words.protocols.jabber import xmlstream, client, jid, component
from twisted.words.protocols.jabber.jid import internJID, JID

from xml.sax.saxutils import escape

import hangups

from iq import Iq

from userdb import User
from client import ClientWrapper

class h2xComponent(component.Service):
	def __init__(self, reactor, config):
		self.config = config
		self.reactor = reactor
		self.iq = Iq(self)
		
		self.clients = {}

	def componentConnected(self, xs):
		self.xmlstream = xs
		
		self.xmlstream.addObserver("/iq", self.iq.onIq)
		self.xmlstream.addObserver("/presence", self.onPresence)
		self.xmlstream.addObserver("/message", self.onMessage)
		
		print("h2x component connected :-)")

	# Forward message to Hangouts client
	def onMessage(self, el):
		msgType = el.getAttribute("type")
		recipient = el.getAttribute("to")
		sender = el.getAttribute("from")
		text = el.firstChildElement().__str__()
		
		try:
			sender = JID(sender)
		except Exception as e:
			print("User JID parsing failed: " + e.__str__())
			return
		
		if msgType == "chat":
			user = User(sender.userhostJID().full())
			self.clients[user.username].sendMessage(recipient, text)
		else:
			raise NotImplementedError

	def onPresence(self, el):
		sender = el.getAttribute("from")
		to = el.getAttribute("to")
		presenceType = el.getAttribute("type")
		if not presenceType:
			presenceType = "available"
		
		try:
			sender = JID(sender)
		except Exception as e:
			print("User JID parsing failed: " + e.__str__())
			return
		
		
		# Check user is registered
		user = User(sender.userhostJID().full())
		try:
			user.token
		except Exception as e:
			print(e)
			self.sendPresenceError(to = sender, fro = to, eType="auth", condition="registration-required")
			return
		
		print("Presence:")
		print("> From: " + sender.full())
		print("> To: " + to)
		print("> Type: " + presenceType)

		# Service component presence
		if to == self.config.JID:
			self.componentPresence(el, sender, presenceType, user)
			return

	def componentPresence(self, el, sender, presenceType, user):
		client = self.ensureClient(user, sender)
		
		if presenceType == "available":
			client.connect()
		elif presenceType == "unavailable":
			client.disconnect()
		else:
			raise NotImplementedError("Presence type: " + presenceType)
	
	# Send presence
	def sendPresence(self, source, destination, presenceType, content):
		presence = Element((None,'presence'))
		presence.attributes['to'] = destination
		presence.attributes['from'] = source
		presence.attributes['type'] = presenceType
		presence.addElement('status').addContent(content)
		self.send(presence)

	# Send component presence
	def sendComponentPresence(self, destination, presenceType, content):
		self.sendPresence(self.config.JID, destination, presenceType, content)
	
	# Ensures existence of client wrapper for particular user
	# Client wrapper is returned
	def ensureClient(self, user, sender):
		try:
			return self.clients[user.username]
		except:
			self.clients[user.username] = ClientWrapper(self, user, sender.full())
			return self.clients[user.username]
		
	# Send message
	def sendMessage(self, to, fro, text, messageType = "chat"):
		el = Element((None, "message"))
		el.attributes["to"] = to
		el.attributes["from"] = fro
		el.attributes["type"] = messageType
		
		body = el.addElement("body")
		body.addContent(escape(text))
		self.send(el)
		
	# Register user
	def registerUser(self, username, token):
		# Debug info
		print("Registration processed:")
		print("Token: " + token)
		print("User: " + username)
		
		# Store user in db
		User(username).token = token
		

	def sendPresenceError(self, to, fro, eType, condition):
		raise NotImplementedError

	def sendMessageError(self, to, fro, eType, condition):
		raise NotImplementedError