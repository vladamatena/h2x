from twisted.words.protocols.jabber import jid
from twisted.words.protocols.jabber.jid import internJID, JID
from twisted.words.xish.domish import Element
from twisted.words.protocols.jabber.client import IQ
import hangups
import h2x

from userdb import User


# Builder for form element
class Form:
	# Creates form
	def __init__(self, iq: IQ):
		self.iq = iq

		# Create form element
		self.form = iq.addElement("x")
		self.form.attributes["xmlns"] = "jabber:x:data"
		self.form.attributes["type"] = "form"

	# Adds title to form element
	def addTitle(self, caption: str):
		self.form.addElement("title", content=caption)

	# Adds text box to form element
	def addTextBox(self, name: str, caption: str, value: str, required: bool = False):
		textBox = self.form.addElement("field")
		textBox.attributes["type"] = "text-single"
		textBox.attributes["var"] = name
		textBox.attributes["label"] = caption
		textBox.addElement("value", content=value)
		if required:
			textBox.addElement("required")


ERROR_CODE_MAP = {
	"bad-request": 400,
	"conflict": 409,
	"feature-not-implemented": 501,
	"forbidden": 403,
	"gone": 302,
	"internal-server-error": 500,
	"item-not-found": 404,
	"jid-malformed": 400,
	"not-acceptable": 406,
	"not-allowed": 405,
	"not-authorized": 401,
	"payment-required": 402,
	"recipient-unavailable": 404,
	"redirect": 302,
	"registration-required": 407,
	"remote-server-not-found": 404,
	"remote-server-timeout": 504,
	"resource-constraint": 500,
	"service-unavailable": 503,
	"subscription-required": 407,
	"undefined-condition": 500,
	"unexpected-request": 400
}


# Inteligent query handling
class Iq:
	def __init__(self, h2x):
		self.h2x = h2x

	def onIq(self, element: Element):
		source = JID(element.getAttribute("from"))
		recipient = JID(element.getAttribute("to"))
		identification = element.getAttribute("id")
		iqType = element.getAttribute("type")

		print("IqReceived " + source.full() + " -> " + recipient.full() + ": " + iqType)

		# Process component iq
		if recipient.full() == self.h2x.config.JID:
			self.componentIq(element, source, identification, iqType)
			return

		# Process user iq
		if self.h2x.isHangUser(recipient):
			self.userIq(element, source, recipient, identification, iqType)
			return

		# TODO: Can we send something like wrong request?
		self.__sendIqError(recipient=source.full(), sender=recipient.full(), identification=identification,
						   errorType="cancel", condition="service-unavailable")

	def componentIq(self, element: Element, sender: JID, identifier: str, iqType: str):
		for query in element.elements():
			xmlns = query.uri
			node = query.getAttribute("node")

			if xmlns == "http://jabber.org/protocol/disco#info" and iqType == "get":
				self.__getDiscoInfo(sender, identifier, node)
				return

			if xmlns == "http://jabber.org/protocol/disco#items" and iqType == "get":
				self.__getDiscoItems(sender, identifier, node)
				return

			if xmlns == "jabber:iq:register" and iqType == "get":
				self.__getRegister(sender, identifier)
				return

			if xmlns == "jabber:iq:register" and iqType == "set":
				self.__setRegister(element, sender, identifier)
				return

			if xmlns == "http://jabber.org/protocol/commands" and query.name == "command" and iqType == "set":
				self.__command(query, sender, identifier, node)
				return

			self.__sendIqError(recipient=sender.full(), sender=self.h2x.config.JID, identification=identifier,
							   errorType="cancel", condition="feature-not-implemented")

	def userIq(self, element: Element, sender: JID, recipient: JID, identifier: str, iqType: str):
		for query in element.elements():
			xmlns = query.uri
			node = query.getAttribute("node")

			if xmlns == "jabber:iq:version" and iqType == "get":
				self.__getVersion(sender, recipient, identifier)
				return

			if xmlns == "vcard-temp" and iqType == "get" and query.name == "vCard":
				self.__getVCard(sender, recipient, identifier)
				return

			self.__sendIqError(recipient=sender.full(), sender=self.h2x.config.JID, identification=identifier,
							   errorType="cancel", condition="feature-not-implemented")

	def __getVersion(self, sender: JID, recipient: JID, identifier: str):
		iq = Element((None, "iq"))
		iq.attributes["type"] = "result"
		iq.attributes["from"] = recipient.full()
		iq.attributes["to"] = sender.full()
		if identifier:
			iq.attributes["id"] = identifier
		query = iq.addElement("query")
		query.attributes["xmlns"] = "jabber:iq:version"
		query.addElement("name", content="h2x transport")
		query.addElement("version", content=0)
		self.h2x.send(iq)

	def __getVCard(self, sender: JID, recipient: JID, identifier):
		iq = Element((None, "iq"))
		iq.attributes["type"] = "result"
		iq.attributes["from"] = recipient.full()
		iq.attributes["to"] = sender.full()
		if identifier:
			iq.attributes["id"] = identifier
		vcard = iq.addElement("vCard")
		vcard.attributes["xmlns"] = "vcard-temp"

		userInfo = self.h2x.getClient(sender).getUser(recipient)

		# TODO: Get more user info
		vcard.addElement("FN", content=userInfo.full_name)
		vcard.addElement("NICKNAME", content=userInfo.full_name)
		emails = vcard.addElement("EMAIL")
		for email in userInfo.emails:
			emails.addElement("USERID", content=email)

		self.h2x.send(iq)

	def __getRegister(self, sender: JID, identifier: str):
		iq = Element((None, "iq"))
		iq.attributes["type"] = "result"
		iq.attributes["from"] = self.h2x.config.JID
		iq.attributes["to"] = sender.full()
		if identifier:
			iq.attributes["id"] = identifier
		query = iq.addElement("query")
		query.attributes["xmlns"] = "jabber:iq:register"

		# Create registration form
		form = Form(query)
		form.addTitle("Hangouts registration form")
		form.addTextBox("token", "Replace link by token", hangups.auth.OAUTH2_LOGIN_URL, required=True)
		self.h2x.send(iq)

	def __setRegister(self, data: Element, sender: JID, identifier: str):
		try:
			user = sender.userhost()
			token = data.firstChildElement().firstChildElement().firstChildElement().firstChildElement().__str__()
		except Exception as e:
			# Fail registration
			print("Register reponse processing failed: " + e.__str__())
			# FIXME: Send negative response here !!!
			self.__sendIqResult(sender.full(), self.h2x.config.JID, identifier, "jabber:iq:register")
			return

		self.h2x.registerUser(user, token)

		# Send registration done
		self.__sendIqResult(sender.full(), self.h2x.config.JID, identifier, "jabber:iq:register")

		# Request subscription
		self.h2x.sendPresence(sender, "subscribe")

	def __getDiscoInfo(self, sender: JID, identifier: str, node: str):
		iq = Element((None, "iq"))
		iq.attributes["type"] = "result"
		iq.attributes["from"] = self.h2x.config.JID
		iq.attributes["to"] = sender.full()
		if identifier:
			iq.attributes["id"] = identifier
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

	def __getDiscoItems(self, sender: JID, identifier: str, node: str):
		iq = Element((None, "iq"))
		iq.attributes["type"] = "result"
		iq.attributes["from"] = self.h2x.config.JID
		iq.attributes["to"] = sender.full()

		if identifier:
			iq.attributes["id"] = identifier
		query = iq.addElement("query")
		query.attributes["xmlns"] = "http://jabber.org/protocol/disco#items"

		if node:
			query.attributes["node"] = node

		if node == None:
			self.__addDiscoItem(query, self.h2x.config.JID, "Commands", 'http://jabber.org/protocol/commands')
		if node == "http://jabber.org/protocol/commands":
			self.__addDiscoItem(query, self.h2x.config.JID, "Import contacts from Hangouts", "import_contacts")

		self.h2x.send(iq)

	def __addDiscoItem(self, query, jid: str, name: str = None, node: str = None):
		item = query.addElement("item")
		item.attributes["jid"] = jid
		if name:
			item.attributes["name"] = name
		if node:
			item.attributes["node"] = node
		return item

	def __command(self, query, sender: JID, identifier: str, node: str):
		if node == "import_contacts":
			self.h2x.getClient(sender).importContacts()

	def __sendIqResult(self, recipient: str, sender: str, identification: str, xmlns: str):
		# TODO: use xmlns
		el = Element((None, "iq"))
		el.attributes["to"] = recipient
		el.attributes["from"] = sender
		if identification:
			el.attributes["id"] = identification
			el.attributes["type"] = "result"
			self.h2x.send(el)

	# TODO: Refactor
	def __sendIqError(self, recipient: str, sender: str, identification, errorType: str, condition: str,
					  source: str = None):
		el = Element((None, "iq"))
		el.attributes["to"] = recipient
		el.attributes["from"] = sender
		if identification:
			el.attributes["id"] = identification
			el.attributes["type"] = "error"
			error = el.addElement("error")
			error.attributes["type"] = errorType
			error.attributes["code"] = str(ERROR_CODE_MAP[condition])
			cond = error.addElement(condition)
			cond.attributes["xmlns"] = "urn:ietf:params:xml:ns:xmpp-stanzas"
			self.h2x.send(el)
