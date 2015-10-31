from twisted.words.protocols.jabber import jid
from twisted.words.protocols.jabber.jid import internJID, JID
from twisted.words.xish.domish import Element
import hangups

from userdb import User

# Builder for form element
class Form:
	# Creates form
	def __init__(self, iq):
		self.iq = iq
		
		# Create form element
		self.form = iq.addElement("x")
		self.form.attributes["xmlns"] = "jabber:x:data"
		self.form.attributes["type"] = "form"

	# Adds title to form element
	def addTitle(self, caption):
		self.form.addElement("title", content = caption)

	# Adds text box to form element
	def addTextBox(self, name, caption, value, required = False):
		textBox = self.form.addElement("field")
		textBox.attributes["type"] = "text-single"
		textBox.attributes["var"] = name
		textBox.attributes["label"] = caption
		textBox.addElement("value", content = value)
		if required:
			textBox.addElement("required")

ERROR_CODE_MAP = {
	"bad-request"				: 400,
	"conflict"					: 409,
	"feature-not-implemented"	: 501,
	"forbidden"					: 403,
	"gone"						: 302,
	"internal-server-error"		: 500,
	"item-not-found"			: 404,
	"jid-malformed"				: 400,
	"not-acceptable"			: 406,
	"not-allowed"				: 405,
	"not-authorized"			: 401,
	"payment-required"			: 402,
	"recipient-unavailable"		: 404,
	"redirect"					: 302,
	"registration-required"		: 407,
	"remote-server-not-found"	: 404,
	"remote-server-timeout"		: 504,
	"resource-constraint"		: 500,
	"service-unavailable"		: 503,
	"subscription-required"		: 407,
	"undefined-condition"		: 500,
	"unexpected-request"		: 400
}

# Inteligent query handling
class Iq:
	def __init__(self, h2x):
		self.h2x = h2x

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
		
		print("IqReceived " + fro.full() + " -> " + to.full() + ": " + iqType)
		
		# Process component iq
		if to.full() == self.h2x.config.JID:
			self.componentIq(el, fro, ID, iqType)
			return
		
		# Process user iq
		if self.h2x.isHangUser(to.userhost()):
			self.userIq(el, fro, to, ID, iqType)
			return
		
		# TODO: Can we send something like wrong request?
		self.__sendIqError(to = fro.full(), fro = to.full(), ID = ID, eType = "cancel", condition = "service-unavailable")
		
	def componentIq(self, el, fro, ID, iqType):
		for query in el.elements():
			xmlns = query.uri
			node = query.getAttribute("node")
			
			if xmlns == "http://jabber.org/protocol/disco#info" and iqType == "get":
				self.__getDiscoInfo(el, fro, ID, node)
				return
			
			if xmlns == "http://jabber.org/protocol/disco#items" and iqType == "get":
				self.__getDiscoItems(el, fro, ID, node)
				return
			
			if xmlns == "jabber:iq:register" and iqType == "get":
				self.__getRegister(el, fro, ID)
				return

			if xmlns == "jabber:iq:register" and iqType == "set":
				self.__setRegister(el, fro, ID)
				return
			
			if xmlns == "http://jabber.org/protocol/commands" and query.name=="command" and iqType=="set":
				self.__command(query, fro, ID, node)
				return

			self.__sendIqError(to = fro.full(), fro = self.h2x.config.JID, ID = ID, eType = "cancel", condition = "feature-not-implemented")
			
	def userIq(self, el, fro, to, ID, iqType):
		for query in el.elements():
			xmlns = query.uri
			node = query.getAttribute("node")
			
			if xmlns == "jabber:iq:version" and iqType == "get":
				self.__getVersion(fro, to, ID)
				return
			
			if xmlns == "vcard-temp" and iqType == "get" and query.name == "vCard":
				self.__getVCard(fro, to, ID)
				return
			
			self.__sendIqError(to = fro.full(), fro = self.h2x.config.JID, ID = ID, eType = "cancel", condition = "feature-not-implemented")
	
	def __getVersion(self, fro, to, ID):
		iq = Element((None,"iq"))
		iq.attributes["type"] = "result"
		iq.attributes["from"] = to.full()
		iq.attributes["to"] = fro.full()
		if ID:
			iq.attributes["id"] = ID
		query = iq.addElement("query")
		query.attributes["xmlns"] = "jabber:iq:version"
		query.addElement("name", content = "h2x transport")
		query.addElement("version", content = 0)
		self.h2x.send(iq)
		
	def __getVCard(self, fro, to, ID):
		iq = Element((None, "iq"))
		iq.attributes["type"] = "result"
		iq.attributes["from"] = to.full()
		iq.attributes["to"] = fro.full()
		if ID:
			iq.attributes["id"] = ID
		vcard = iq.addElement("vCard")
		vcard.attributes["xmlns"] = "vcard-temp"

		userInfo = self.h2x.getClient(fro).getUser(to.userhost())

		# TODO: Get more user info
		vcard.addElement("FN", content = userInfo.full_name)
		vcard.addElement("NICKNAME", content = userInfo.full_name)
		emails = vcard.addElement("EMAIL")
		for email in userInfo.emails:
			emails.addElement("USERID", content = email)

		self.h2x.send(iq)

	def __getRegister(self, el, fro, ID):
		iq = Element((None,"iq"))
		iq.attributes["type"] = "result"
		iq.attributes["from"] = self.h2x.config.JID
		iq.attributes["to"] = fro.full()
		if ID:
			iq.attributes["id"]=ID
		query = iq.addElement("query")
		query.attributes["xmlns"] = "jabber:iq:register"
		
		# Create registration form
		form = Form(query)
		form.addTitle("Hangouts registration form")
		form.addTextBox("token", "Replace link by token", hangups.auth.OAUTH2_LOGIN_URL, required = True)
		self.h2x.send(iq)

	def __setRegister(self, data, sender, ID):
		try:
			user = sender.userhost()
			token = data.firstChildElement().firstChildElement().firstChildElement().firstChildElement().__str__()
		except Exception as e:
			# Fail registration
			print("Register reponse processing failed: " + e.__str__())
			# FIXME: Send negative response here !!!
			self.__sendIqResult(sender.full(), self.h2x.config.JID, ID, "jabber:iq:register")
			return
		
		self.h2x.registerUser(user, token)
		
		# Send registration done
		self.__sendIqResult(sender.full(), self.h2x.config.JID, ID, "jabber:iq:register")
		
		# Request subscription
		self.h2x.sendPresence(sender.userhost(), "subscribe")

	def __getDiscoInfo(self, el, fro, ID, node):
		iq = Element((None, "iq"))
		iq.attributes["type"] = "result"
		iq.attributes["from"] = self.h2x.config.JID
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
			query.addElement("feature").attributes["var"] = "jabber:iq:gateway"
			query.addElement("feature").attributes["var"] = "jabber:iq:register"
			query.addElement("feature").attributes["var"] = "jabber:iq:version"
			
		# Generic features for both node and component
		query.addElement("feature").attributes["var"] = "http://jabber.org/protocol/commands"
		query.addElement("feature").attributes["var"] = "http://jabber.org/protocol/disco#items"
		query.addElement("feature").attributes["var"] = "http://jabber.org/protocol/disco#info"
			
		self.h2x.send(iq)

	def __getDiscoItems(self, el, fro, ID, node):
		iq = Element((None, "iq"))
		iq.attributes["type"] = "result"
		iq.attributes["from"] = self.h2x.config.JID
		iq.attributes["to"] = fro.full()
		
		if ID:
			iq.attributes["id"] = ID
		query = iq.addElement("query")
		query.attributes["xmlns"] = "http://jabber.org/protocol/disco#items"
		
		if node:
			query.attributes["node"] = node
			
		if node == None:
			self.__addDiscoItem(query, self.h2x.config.JID, "Commands", 'http://jabber.org/protocol/commands')
		if node == "http://jabber.org/protocol/commands":
			self.__addDiscoItem(query, self.h2x.config.JID, "Import contacts from Hangouts", "import_contacts")
		
		self.h2x.send(iq)
		
	def __addDiscoItem(self, query, jid, name = None, node = None):
		item = query.addElement("item")
		item.attributes["jid"] = jid
		if name:
			item.attributes["name"] = name
		if node:
			item.attributes["node"] = node
		return item
	
	def __command(self, query, fro, ID, node):
		if node == "import_contacts":
			self.h2x.getClient(fro).importContacts()

	def __sendIqResult(self, to, fro, ID, xmlns):
		el = Element((None,"iq"))
		el.attributes["to"] = to
		el.attributes["from"] = fro
		if ID:
			el.attributes["id"] = ID
			el.attributes["type"] = "result"
			self.h2x.send(el)
	
	# TODO: Refactor
	def __sendIqError(self, to, fro, ID, eType, condition, sender = None):
		el = Element((None, "iq"))
		el.attributes["to"] = to
		el.attributes["from"] = fro
		if ID:
			el.attributes["id"] = ID
			el.attributes["type"] = "error"
			error = el.addElement("error")
			error.attributes["type"] = eType
			error.attributes["code"] = str(ERROR_CODE_MAP[condition])
			cond = error.addElement(condition)
			cond.attributes["xmlns"] = "urn:ietf:params:xml:ns:xmpp-stanzas"
			if not sender:
				sender = self.h2x
			sender.send(el)