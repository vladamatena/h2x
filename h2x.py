import re
from xml.sax.saxutils import escape
from twisted.words.protocols.jabber import component
from twisted.words.protocols.jabber.jid import JID
from twisted.words.protocols.jabber.xmlstream import XmlStream
from twisted.words.xish.domish import Element
from twisted.internet import reactor

from iq import Iq
from config import Config
from userdb import User
from client import ClientWrapper
from client import UserNotRegistered


class h2xComponent(component.Service):
	def __init__(self, react: reactor, config: Config):
		self.config = config
		self.reactor = react
		self.iq = Iq(self)

		# Connected users
		# As hash map user@jabber.org -> ClientWrapper
		self.__clients = {}

	def componentConnected(self, xmlStream: XmlStream):
		self.xmlstream = xmlStream

		self.xmlstream.addObserver("/iq", self.iq.onIq)
		self.xmlstream.addObserver("/presence", self.onPresence)
		self.xmlstream.addObserver("/message", self.onMessage)

		print("h2x component connected :-)")

	# Forward message to Hangouts client
	def onMessage(self, element: Element):
		msgType = element.getAttribute("type")
		recipient = JID(element.getAttribute("to"))
		sender = JID(element.getAttribute("from"))
		text = element.firstChildElement().__str__()

		if msgType == "chat":
			self.getClient(sender).sendMessage(recipient, text)
		else:
			raise NotImplementedError

	def onPresence(self, element: Element):
		sender = JID(element.getAttribute("from"))
		recipient = JID(element.getAttribute("to"))
		presenceType = element.getAttribute("type")
		if not presenceType:
			presenceType = "available"

		print("PresenceReceived: " + sender.full() + " -> " + recipient.full() + " : " + presenceType)

		# Create client instance on available from XMPP client
		if self.getClient(sender) is None:
			if presenceType == "available":
				try:
					self.addClient(ClientWrapper(self, sender))
				except UserNotRegistered as e:
					print(e)
					self.sendPresenceError(recipient=sender, sender=recipient, errorType="auth",
										   condition="registration-required")
					return
			else:
				print("Operation on client which has not yet send available presence !!! (responding as if we are not available)")
				self.sendPresence(sender, "unavailable")
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
	def getClient(self, jid: JID):
		try:
			return self.__clients[jid.userhost()]
		except:
			return None

	# Add new client to client map
	def addClient(self, client: ClientWrapper):
		self.__clients[client.jid.userhost()] = client

	# Send presence
	def sendPresence(self, destination: JID, presenceType: str, status: str = None, show: str = None,
					 priority: int = None, source: JID = None, nick: str = None):
		if not source:
			source = JID(self.config.JID)
		presence = Element((None, 'presence'))
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
			nickElement = presence.addElement('nick', content=nick)
			nickElement.attributes["xmlns"] = "http://jabber.org/protocol/nick"
		print("PresenceSend: " + source.full() + " -> " + destination.full() + " : " + presenceType)
		self.send(presence)

	# Send message
	def sendMessage(self, recipient: JID, sender: JID, text: str, messageType: str = "chat"):
		el = Element((None, "message"))
		el.attributes["to"] = recipient.full()
		el.attributes["from"] = sender.full()
		el.attributes["type"] = messageType

		body = el.addElement("body")
		body.addContent(escape(text))
		self.send(el)

	# Register user
	def registerUser(self, username: str, token: str):
		# Debug info
		print("Registration processed:")
		print("Token: " + token)
		print("User: " + username)

		# Store user in db
		User(username).token = token

	@property
	def SUFFIX(self):
		return "@" + self.config.JID + "$"

	def isHangUser(self, jid: JID):
		return re.match(".*" + self.SUFFIX, jid.userhost())

	def sendPresenceError(self, recipient: JID, sender: JID, errorType: str, condition: str):
		raise NotImplementedError

	def sendMessageError(self, recipient: JID, sender: JID, errorType: str, condition: str):
		raise NotImplementedError
