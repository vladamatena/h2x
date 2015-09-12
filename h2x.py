import sys

from twisted.internet import reactor
from twisted.words.xish import domish,xpath
from twisted.words.xish.domish import Element
from twisted.words.protocols.jabber import xmlstream, client, jid, component
from twisted.words.protocols.jabber.jid import internJID

import utils

class h2xComponent(component.Service):
	def __init__(self, reactor, config):
		self.config = config
		self.reactor = reactor

	def componentConnected(self, xs):
		self.xmlstream = xs
		
		self.xmlstream.addObserver("/iq", self.onIq)
		self.xmlstream.addObserver("/presence", self.onPresence)
		self.xmlstream.addObserver("/message", self.onMessage)
		
		print "h2x component connected :-)"

	def onMessage(self, el):
		print("onMessage")

	def onPresence(self, el):
		print("onPresence")

	def componentPresence(self, el, fro, presenceType):
		print("componentPresence")

	def onIq(self, el):
		fro = el.getAttribute("from")
		to = el.getAttribute("to")
		ID = el.getAttribute("ID")
		iqType = el.getAttribute("type")
		try:
			fro=internJID(fro)
			to=internJID(to)
		except Exception, e:
			return
		if to.full()==self.config.JID:
			self.componentIq(el,fro,ID,iqType)
			return
		
		# FIXME: Is this needed ???
		self.sendIqError(to=fro.full(),fro=to.full(),ID=ID,etype="cancel",condition="service-unavailable")

	def componentIq(self, el, fro, ID, iqType):
		for query in el.elements():
			xmlns = query.uri
			print("ComponentIq: " + xmlns)
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
			
			self.sendIqError(to = fro.full(), fro = self.config.JID, ID = ID, eType="cancel", condition="feature-not-implemented")

	def result_vCard(self, el, fro, ID):
		print("result vcard")

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
		print("getRegister")

	def setRegister(self, el, fro, ID):
		print("setRegister")

	def getIqGateway(self, fro, ID):
		print("getIqgateway")

	def setIqGateway(self, el, fro, ID):
		print("setIqGateway")

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
		identity = query.addElement("identity")
		identity.attributes["name"] = "Google Hangouts transport"
		identity.attributes["category"] = "gateway"
		identity.attributes["type"] = "XMPP"
		query.addElement("feature").attributes["var"] = "vcard-temp"
		query.addElement("feature").attributes["var"] = "http://jabber.org/protocol/disco#items"
		query.addElement("feature").attributes["var"] = "http://jabber.org/protocol/disco#info"
		query.addElement("feature").attributes["var"] = "jabber:iq:gateway"
		query.addElement("feature").attributes["var"] = "jabber:iq:register"
		query.addElement("feature").attributes["var"] = "jabber:iq:last"
		self.send(iq)

	def getDiscoItems(self, el, fro, ID, node):
		iq = Element((None,"iq"))
		iq.attributes["type"] = "result"
		iq.attributes["from"] = self.config.JID
		iq.attributes["to"] = fro.full()
		if ID:
			iq.attributes["id"] = ID
		query = iq.addElement("query")
		query.attributes["xmlns"] = "http://jabber.org/protocol/disco#items"
		if node:
			query.attributes["node"] = node
		self.send(iq)

	def sendIqResult(self, to, fro, ID, xmlns):
		print("sendIqResult")
	
	# TODO: Refactor
	def sendIqError(self, to, fro, ID, eType, condition, sender = None):
		el = Element((None, "iq"))
		el.attributes["to"] = to
		el.attributes["from"] = fro
		if ID:
			el.attributes["id"] = ID
			el.attributes["type"] = "error"
			error = el.addElement("error")
			error.attributes["type"] = etype
			error.attributes["code"] = str(utils.errorCodeMap[condition])
			cond = error.addElement(condition)
			cond.attributes["xmlns"]="urn:ietf:params:xml:ns:xmpp-stanzas"
			if not sender:
				sender=self
			sender.send(el)

	def sendPresenceError(self, to, fro, eType, condition):
		print("sendPresence")

	def sendMessageError(self, to, fro, eType, condition):
		print("sendMesageError")