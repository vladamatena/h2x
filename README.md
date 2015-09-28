# h2x (Hangouts to XMPP transport)

## Message to others
The code in this repository is absolutely disgusting, broken and incomplete. The purpose of making this repository public is to show that someone is working on it.

## About project
The noble purpose of this project is to bridge the gap in between the Hangouts and the Jabber network which emerged when Google closed XMPP gateway to its chat services. The problem is tackled by providing Hangouts to XMPP transport, which allows users to add Hangouts contacts to their XMPP roaster while supporting bidirectional text messaging (the same way as pyicqt suports ICQ network).

## State of the transport
Bad news is that it is hard to find some time to work on the project.
Even worse is that I am learning python on the go.

Working(Already "somehow" implemented):
1. Registration
2. Transport logon
3. Transport logoff
4. Forwarding messages from Hangouts to Jabber (Barely working, all message are resend every time, ...)
5. Basic presence for contacts on Hangouts contact list

Not working(I would like to implement)
1. Propper routing of messages from Hangouts to Jabber
2. Routing of messages from Jabber to Hangouts
3. Subscription to Hangouts contact presence
4. Showing Jabber presence on Hangouts

5. Adding new users to Hangouts



First message forwared by transport:
[17:29:31] <100942746420725866514@hangouts.mattty.cz> Hello world!!!
