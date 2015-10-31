# h2x (Hangouts to XMPP transport)

## Message to others

The code in this repository is somehow working. I use it as it is better than nothing. User registration may be more buggy as it is not so easy to test. The purpose of making this repository public is to show that someone is working on it. If someone would like to join, let me know before you start hacking as I am currently running in noncoperative mode.

## About project

The noble purpose of this project is to bridge the gap in between the Hangouts and the Jabber network which emerged when Google closed XMPP gateway to its chat services. The problem is tackled by providing Hangouts to XMPP transport, which allows users to add Hangouts contacts to their XMPP roaster while supporting bidirectional text messaging (the same way as pyicqt suports ICQ network).

## State of the transport
Generally working, user registration may be buggy.

### Working(Already "somehow" implemented):

- Registration
- Transport presence
- Multiple Jabber client support
- By-directional forwarding of messages
- Presence for imported hangouts users

### Not working(I would like to implement)

- Proper matching of Jabber messages to Hangouts
- Showing Jabber presence on Hangouts
- Adding new users to Hangouts


### First message forwarded by transport:

	[17:29:31] <100942746424564569874.100942746424564569874@hangouts.mattty.cz> Hello world !!!

## Used libraries, code

- Twisted words
 - XMPP component implementation
 - Fixed version for Python 3 required: https://github.com/vladamatena/twisted/tree/words-python3.5

- Hangups
 - Working reverse engendered Hangouts client library

## How to run it
Setup configuration file

	mkdir users
	python3.4 transport.py
