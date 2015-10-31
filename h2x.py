import asyncio
import re
from xml.sax.saxutils import escape
from twisted.words.xish.domish import Element
from twisted.words.protocols.jabber import xmlstream, client, jid, component
from twisted.words.protocols.jabber.jid import internJID, JID

from iq import Iq
from userdb import User
from client import ClientWrapper

class h2xComponent(component.Service):
	def __init__(self, reactor, config):
		self.config = config
		self.reactor = reactor
		self.iq = Iq(self)

		# Connected users
		# As hash map user@jabber.org -> ClientWrapper
		self.clients = {}

		# Track connected instances of XMPP clients, for presence control
		self.xmppClients = set()
		
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
			self.clients[sender.userhost()].sendMessage(recipient, text)
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
			print("User JID parsing failed: " + sender + ": " + e.__str__())
			return
		
		# Check user is registered
		user = User(sender.userhost())
		try:
			user.token
		except Exception as e:
			print(e)
			self.sendPresenceError(to = sender, fro = to, eType="auth", condition="registration-required")
			return
		
		print("PresenceReceived: " + sender.full() + " -> " + to + " : " + presenceType)

		# Service component presence
		if to == self.config.JID:
			self.componentPresence(el, sender, presenceType, user, to)
			return
		
		# Subscription request
		if presenceType == "subscribe":
			client = self.getClient(user)
			if client.isSubscribed(to):
				self.sendPresence(sender.full(), "subscribed", source = to)
				if client.loop:
					asyncio.async(client.updateParticipantPresence(), loop = client.loop)
			else:
				self.sendPresence(sender.full(), "unsubscribed", source = to)

	def componentPresence(self, el, sender, presenceType, user, to):
		client = self.ensureClient(user, sender)
		
		if presenceType == "available":
			if not self.xmppClients:
				client.connect()
			else:
				# Tell the client we are online
				self.sendPresence(sender.full(), "available")
				if client.loop:
					asyncio.async(client.updateParticipantPresence(), loop = client.loop)
			self.xmppClients.add(sender)
		elif presenceType == "unavailable":
			self.xmppClients.discard(sender)
			if not self.xmppClients:
				client.disconnect()
			else:
				self.sendPresence(sender.full(), "unavailable")
		elif presenceType == "probe":
			client.sendPresence()
		elif presenceType == "subscribed":
			print("Presence type subscribed not supported")
		elif presenceType == "subscribe":
			self.sendPresence(sender.full(), "subscribed", source = to)
		else:
			raise NotImplementedError("Presence type: " + presenceType)

	# Send presence
	def sendPresence(self, destination, presenceType, status = None, show = None, priority = None, source = None, nick = None):
		if not source:
			source = self.config.JID
		presence = Element((None,'presence'))
		presence.attributes['to'] = destination
		presence.attributes['from'] = source
		presence.attributes['type'] = presenceType
		if status:
			presence.addElement('status').addContent(status)
		if show:
			presence.addElement('show').addContent(show)
		if priority:
			presence.addElement('priority').addContent(priority)
		if nick:
			nickElement = presence.addElement('nick', content = nick)
			nickElement.attributes["xmlns"] = "http://jabber.org/protocol/nick"
		print("PresenceSend: " + source + " -> " + destination + " : " + presenceType)
		self.send(presence)
	
	def getClientByJID(self, jid):
		return self.clients[jid]
	
	def getClient(self, user):
		return self.getClientByJID(user.username)
	
	# Ensures existence of client wrapper for particular user
	# Client wrapper is returned
	def ensureClient(self, user, sender):
		try:
			return self.getClient(user)
		except:
			self.clients[user.username] = ClientWrapper(self, user, sender.userhost())
			return self.getClient(user)
		
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
		
	@property
	def SUFFIX(self):
		return "@" + self.config.JID + "$";
	
	def isHangUser(self, jid):
		return re.match(".*" + self.SUFFIX, jid)

	def sendPresenceError(self, to, fro, eType, condition):
		raise NotImplementedError

	def sendMessageError(self, to, fro, eType, condition):
		raise NotImplementedError