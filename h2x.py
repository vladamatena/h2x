import sys
import time
import asyncio

from twisted.internet import reactor
from twisted.words.xish import domish,xpath
from twisted.words.xish.domish import Element
from twisted.words.protocols.jabber import xmlstream, client, jid, component
from twisted.words.protocols.jabber.jid import internJID, JID

import hangups

import utils

from userdb import UserDB
from userdb import User
from client import ClientWrapper

class h2xComponent(component.Service):
	def __init__(self, reactor, config):
		self.config = config
		self.reactor = reactor
		
		self.userdb = UserDB()
		self.clients = {}

	def componentConnected(self, xs):
		self.xmlstream = xs
		
		self.xmlstream.addObserver("/iq", self.onIq)
		self.xmlstream.addObserver("/presence", self.onPresence)
		self.xmlstream.addObserver("/message", self.onMessage)
		
		print("h2x component connected :-)")

	def onMessage(self, el):
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
		user = self.userdb.getUser(sender.userhostJID().full())
		if not user:
			self.sendPresenceError(to = sender, fro = to, eType="auth", condition="registration-required")
			return
		
		print("Presence:")
		print("From: " + sender.full())
		print("To: " + to)
		print("Type: " + presenceType)

		# Service component presence
		if to == self.config.JID:
			self.componentPresence(el, sender, presenceType, user)
			return
        
		print("Presence:")
		print("From: " + sender.full())
		print("To: " + to)
		print("Type" + presenceType)

	def componentPresence(self, el, sender, presenceType, user):
		# raise NotImplementedError
		
		presence = Element((None,'presence'))
		presence.attributes['to'] = sender.full()
		presence.attributes['from'] = self.config.JID
		presence.attributes['type'] = presenceType#'available'
		presence.addElement('status', content="Logging in...")
		self.send(presence)
		
#		if presenceType == "available":
#			self.clientLogOn(user)

		self.ensureClient(user)
	
	# Ensures existence of client wrapper for particular user
	# Client wrapper is returned
	def ensureClient(self, user):
		try:
			return self.clients[user.username]
		except:
			self.clients[user.username] = ClientWrapper(self, user)
			return self.clients[user.username]
		
	def clientLogOn(self, user):
		print("Getting cookies")
		
		def failedToken():
			#raise RuntimeError("Authentification token is invalid")
			return user.token
		
		print("Tokenpath: " + self.userdb.tokenPath(user))
		cookies = hangups.auth.get_auth(failedToken, self.userdb.tokenPath(user) + ".refresh")
		
		print("Attempting to initialize client")
		self.clients[user.username] = hangups.Client(cookies)
		client = self.clients[user.username]
		print("Client initialization done")
		
		client.on_connect.add_observer(self.onConnect)
		
	@asyncio.coroutine
	def onConnect(self, initialData):
		self.userList = yield from hangups.build_user_list(self.client, initialData)
		self.convList = hangups.ConversationList(self.client, initialData.conversation_states, self.userList, initialData.sync_timestamp)
		self.convList.on_event.add_observer(self.onEvent)

		for user in self.userList.get_all():
			pprint(vars(user))

		print("Disconnecting")
		self.client.disconnect()
		print("Connection handler end")
		
		# FIXME: make this generic we need to distinguish user
		
		# Send user presence
		#presence = Element((None,'presence'))
		#presence.attributes['to'] = sender.full()
		#presence.attributes['from'] = self.config.JID
		#presence.attributes['type'] = "available"
		#presence.addElement('status', content="Connected")
		#self.send(presence)

	def onIq(self, el):
		fro = el.getAttribute("from")
		to = el.getAttribute("to")
		ID = el.getAttribute("id")
		iqType = el.getAttribute("type")
		try:
			fro = internJID(fro)
			to = internJID(to)
		except Exception as e:
			return
		if to.full() == self.config.JID:
			self.componentIq(el, fro, ID, iqType)
			return
		
		# FIXME: Is this needed ???
		self.sendIqError(to = fro.full(), fro = to.full(), ID=ID,eType="cancel", condition = "service-unavailable")

	def componentIq(self, el, fro, ID, iqType):
		for query in el.elements():
			xmlns = query.uri
			print("Processing ComponentIq: " + xmlns + " ID: " + ID)
			node = query.getAttribute("node")
			
			if xmlns == "http://jabber.org/protocol/disco#info" and iqType == "get":
				self.getDiscoInfo(el, fro, ID, node)
				return
			
			if xmlns == "http://jabber.org/protocol/disco#items" and iqType == "get":
				self.getDiscoItems(el, fro, ID, node)
				return
			
			if xmlns == "jabber:iq:register" and iqType == "get":
				self.getRegister(el, fro, ID)
				return

			if xmlns == "jabber:iq:register" and iqType == "set":
				self.setRegister(el, fro, ID)
				return
			
			if xmlns == "vcard-temp" and iqType == "result":
				self.result_vCard(el, fro, ID)
				return
			
			if xmlns=="jabber:iq:last" and iqType=="get":
				self.getLast(fro, ID)
				return
			
			if xmlns == "jabber:iq:gateway" and iqType == "get":
				self.getIqGateway(fro, ID)
				return

			if xmlns == "jabber:iq:gateway" and iqType == "set":
				self.setIqGateway(el, fro, ID)
				return

			if xmlns == "vcard-temp" and iqType == "get" and query.name == "vCard":
				self.getvcard(fro, ID)
				return
			
			print("Iq unhandled")
			
			self.sendIqError(to = fro.full(), fro = self.config.JID, ID = ID, eType="cancel", condition="feature-not-implemented")

	def result_vCard(self, el, fro, ID):
		raise NotImplementedError

	def getvcard(self, fro, ID):
		iq = Element((None, "iq"))
		iq.attributes["type"] = "result"
		iq.attributes["from"] = self.config.JID
		iq.attributes["to"] = fro.full()
		if ID:
			iq.attributes["id"] = ID
		vcard = iq.addElement("vCard")
		vcard.attributes["xmlns"] = "vcard-temp"
		vcard.addElement("NICKNAME", content = "h2x")
		vcard.addElement("DESC", content = "Google Hangouts to XMPP Transport")
		vcard.addElement("URL", content = "http://mattty.cz")
		self.send(iq)

	def getRegister(self, el, fro, ID):
		iq = Element((None,"iq"))
		iq.attributes["type"]="result"
		iq.attributes["from"]=self.config.JID
		iq.attributes["to"]=fro.full()
		if ID:
			iq.attributes["id"]=ID
		query=iq.addElement("query")
		query.attributes["xmlns"]="jabber:iq:register"
		
		# Create registration form
		form = utils.createForm(query, "form")
		utils.addTitle(form, "Hangouts registration form")
		utils.addTextBox(form, "token", "Replace link by token", hangups.auth.OAUTH2_LOGIN_URL, required = True)
      
		print("Sending registration form")
		self.send(iq)


	def setRegister(self, data, sender, ID):
		print("Processing registration form data")
		
		try:
			user = sender.userhost()
			token = data.firstChildElement().firstChildElement().firstChildElement().firstChildElement().__str__()
		except Exception as e:
			# Fail registration
			print("Register reponse processing failed: " + e.__str__())
			# FIXME: Send negative response here !!!
			self.sendIqResult(sender.full(), self.config.JID, ID, "jabber:iq:register")
			return
		
		# Debug info
		print("Registration processed:")
		print("Token: " + token)
		print("User: " + user)
		
		# Store user in db
		self.userdb.putUser(User(user, token))
		
		# Send registration done
		self.sendIqResult(sender.full(), self.config.JID, ID, "jabber:iq:register")
		
		# Request subscription
		presence = Element((None,"presence"))
		presence.attributes["to"] = sender.userhost()
		presence.attributes["from"] = self.config.JID
		presence.attributes["type"] = "subscribe"
		self.send(presence)

	def getIqGateway(self, fro, ID):
		raise NotImplementedError

	def setIqGateway(self, el, fro, ID):
		raise NotImplementedError

	def getLast(self, fro, ID):
		iq = Element((None,"iq"))
		iq.attributes["type"]="result"
		iq.attributes["from"]=self.config.JID
		iq.attributes["to"]=fro.full()
		if ID:
			iq.attributes["id"]=ID
		query=iq.addElement("query")
		query.attributes["xmlns"]="jabber:iq:last"
		query.attributes["seconds"]=str(int(time.time()-self.startTime))
		self.send(iq)

	def getDiscoInfo(self, el, fro, ID, node):
		iq = Element((None, "iq"))
		iq.attributes["type"] = "result"
		iq.attributes["from"] = self.config.JID
		iq.attributes["to"] = fro.full()
		if ID:
			iq.attributes["id"] = ID
		query = iq.addElement("query")
		query.attributes["xmlns"] = "http://jabber.org/protocol/disco#info"
		
		# Node not set -> send component identity
		if node == None:
			identity = query.addElement("identity")
			identity.attributes["name"] = "Google Hangouts transport"
			identity.attributes["category"] = "gateway"
			identity.attributes["type"] = "XMPP"
			query.addElement("feature").attributes["var"] = "vcard-temp"
			query.addElement("feature").attributes["var"] = "http://jabber.org/protocol/commands"
			query.addElement("feature").attributes["var"] = "http://jabber.org/protocol/stats"
			
			query.addElement("feature").attributes["var"] = "jabber:iq:gateway"
			query.addElement("feature").attributes["var"] = "jabber:iq:register"
			query.addElement("feature").attributes["var"] = "jabber:iq:last"
			query.addElement("feature").attributes["var"] = "jabber:iq:version"
		
		# Generic features for both node and component
		query.addElement("feature").attributes["var"] = "http://jabber.org/protocol/disco#items"
		query.addElement("feature").attributes["var"] = "http://jabber.org/protocol/disco#info"
			
		self.send(iq)

	def getDiscoItems(self, el, fro, ID, node):
		iq = Element((None, "iq"))
		iq.attributes["type"] = "result"
		iq.attributes["from"] = self.config.JID
		iq.attributes["to"] = fro.full()
		
		if ID:
			iq.attributes["id"] = ID
		query = iq.addElement("query")
		query.attributes["xmlns"] = "http://jabber.org/protocol/disco#items"
		
		if node:
			query.attributes["node"] = node
			
		if node==None:
			utils.addDiscoItem(query, self.config.JID, "Commands", 'http://jabber.org/protocol/commands')
		
		self.send(iq)

	def sendIqResult(self, to, fro, ID, xmlns):
		el = Element((None,"iq"))
		el.attributes["to"] = to
		el.attributes["from"] = fro
		if ID:
			el.attributes["id"] = ID
			el.attributes["type"] = "result"
			self.send(el)
	
	# TODO: Refactor
	def sendIqError(self, to, fro, ID, eType, condition, sender = None):
		el = Element((None, "iq"))
		el.attributes["to"] = to
		el.attributes["from"] = fro
		if ID:
			el.attributes["id"] = ID
			el.attributes["type"] = "error"
			error = el.addElement("error")
			error.attributes["type"] = eType
			error.attributes["code"] = str(utils.errorCodeMap[condition])
			cond = error.addElement(condition)
			cond.attributes["xmlns"]="urn:ietf:params:xml:ns:xmpp-stanzas"
			if not sender:
				sender=self
			sender.send(el)

	def sendPresenceError(self, to, fro, eType, condition):
		raise NotImplementedError

	def sendMessageError(self, to, fro, eType, condition):
		raise NotImplementedError