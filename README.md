# h2x (Hangouts to XMPP transport)

## Message to others

The code in this repository is disgusting, lacking even signs of proper architecture, but somehow working. The purpose of making this repository public is to show that someone is working on it. If someone would like to join, let me know before you start hacking as I am currently running in noncoperative mode.

## About project

The noble purpose of this project is to bridge the gap in between the Hangouts and the Jabber network which emerged when Google closed XMPP gateway to its chat services. The problem is tackled by providing Hangouts to XMPP transport, which allows users to add Hangouts contacts to their XMPP roaster while supporting bidirectional text messaging (the same way as pyicqt suports ICQ network).

## State of the transport
Bad news is that it is hard to find some time to work on the project. Even worse is that I am learning python on the go.

### Working(Already "somehow" implemented):

- Registration
- Transport presence
- Multiple Jabber client support
- Bydirectional forwarding of messages
- Presence for imported hangouts users

### Not working(I would like to implement)

- Proper matching of Jabber messages to Hangouts
- Showing Jabber presence on Hangouts
- Adding new users to Hangouts


### First message forwared by transport:

	[17:29:31] <100942746420725866514@hangouts.mattty.cz> Hello world!!!

## Used libraries, code

- Twisted words (for XMPP component implementation) (request specialy fixed version for Python 3 support)
- Hangups (Working reverese engeneered Hangouts client library)
- Some inspiration and code from j2j
- Some inspiration and code from pyicqt

## How to run it
Setup configuration file

	mkdir users
	python3.4 transport.py
