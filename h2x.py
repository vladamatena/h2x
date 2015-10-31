import asyncio
import re
from xml.sax.saxutils import escape
from twisted.words.xish.domish import Element
from twisted.words.protocols.jabber import component
from twisted.words.protocols.jabber.jid import JID

from iq import Iq
from userdb import User
from client import ClientWrapper
from client import UserNotRegistered


class h2xComponent(component.Service):
	def __init__(self, reactor, config):
		self.config = config
		self.reactor = reactor
		self.iq = Iq(self)

		# Connected users
		# As hash map user@jabber.org -> ClientWrapper
		self.__clients = {}

	def componentConnected(self, xs):
		self.xmlstream = xs
		
		self.xmlstream.addObserver("/iq", self.iq.onIq)
		self.xmlstream.addObserver("/presence", self.onPresence)
		self.xmlstream.addObserver("/message", self.onMessage)
		
		print("h2x component connected :-)")

	# Forward message to Hangouts client
	def onMessage(self, el):
		msgType = el.getAttribute("type")
		recipient = JID(el.getAttribute("to"))
		sender = JID(el.getAttribute("from"))
		text = el.firstChildElement().__str__()

		if msgType == "chat":
			self.getClient(sender).sendMessage(recipient, text)
		else:
			raise NotImplementedError

	def onPresence(self, element):
		sender = JID(element.getAttribute("from"))
		recipient = JID(element.getAttribute("to"))
		presenceType = element.getAttribute("type")
		if not presenceType:
			presenceType = "available"

		print("PresenceReceived: " + sender.full() + " -> " + recipient.full() + " : " + presenceType)

		# Create client instance on available from XMPP client
		if self.getClient(sender) is None and presenceType == "available":
			try:
				self.addClient(ClientWrapper(self, sender))
			except UserNotRegistered as e:
				print(e)
				self.sendPresenceError(to = sender, fro = recipient, eType="auth", condition="registration-required")
				return

		# Service component presence
		if recipient == JID(self.config.JID):
			self.getClient(sender).processComponentPresence(sender, presenceType, recipient)

		# Subscription request
		elif presenceType == "subscribe":
			self.getClient(sender).processSubscription(recipient)

		# Presence to Hangouts user
		elif self.isHangUser(recipient):
			self.getClient(sender).processPresence(recipient, presenceType)

		# Unimplemented feature
		else:
			raise NotImplemented(element)

	# Get hangups client by JID instance
	def getClient(self, jid):
		try:
			return self.__clients[jid.userhost()]
		except:
			return None

	# Add new client to client map
	def addClient(self, client):
		self.__clients[client.jid.userhost()] = client

	# Send presence
	def sendPresence(self, destination, presenceType, status = None, show = None, priority = None, source = None, nick = None):
		if not source:
			source = JID(self.config.JID)
		presence = Element((None,'presence'))
		presence.attributes['to'] = destination.userhost()
		presence.attributes['from'] = source.userhost()
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
		print("PresenceSend: " + source.full() + " -> " + destination.full() + " : " + presenceType)
		self.send(presence)
		
	# Send message
	def sendMessage(self, recipient, sender, text, messageType = "chat"):
		el = Element((None, "message"))
		el.attributes["to"] = recipient.full();
		el.attributes["from"] = sender.full()
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
		return re.match(".*" + self.SUFFIX, jid.userhost())

	def sendPresenceError(self, to, fro, eType, condition):
		raise NotImplementedError

	def sendMessageError(self, to, fro, eType, condition):
		raise NotImplementedError