import sys

from twisted.words.protocols.jabber import component
from twisted.internet import reactor

from config import Config
import h2x


def main():
	print("Hangouts to XMPP transport")

	config = Config()

	h2xComponent = h2x.h2xComponent(reactor, config)
	f = component.componentFactory(config.JID, config.PASSWORD)
	connector = component.buildServiceManager(config.JID, config.PASSWORD, "tcp:%s:%s" % (config.HOST, config.PORT))
	h2xComponent.setServiceParent(connector)
	connector.startService()
	reactor.run()


main()
