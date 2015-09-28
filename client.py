# hangups client wrapper for h2x

import sys
import hangups
import time
import asyncio


class ClientWrapper:
	def __init__(self, h2x, user):
		self.h2x = h2x
		self.userdb = h2x.userdb
		self.user = user
				
		print("Initialized hangups client for: " + user.username)
		print("Getting cookies")
		
		# Provides token if refresh fails
		# Would be nice to ask user for token
		def getToken():
			return user.token
		
		print("Tokenpath: " + self.userdb.tokenPath(user))
		cookies = hangups.auth.get_auth(getToken, self.userdb.tokenRefreshPath(user))
		
		print("Attempting to initialize client")
		self.client = hangups.Client(cookies)
		print("Client initialization done")
		
		self.client.on_connect.add_observer(self.onConnect)
	
	def start(self):
		try:
			cookies = hangups.auth.get_auth_stdin(self.refreshTokenPath)
		except hangups.GoogleAuthError as e:
			sys.exit('Login failed ({})'.format(e))
		
		print("Attempting to initialize client")
		self.client = hangups.Client(cookies)
		print("Client initialization done")
		
		self.client.on_connect.add_observer(self.onConnect)
		
		print("Attempting to connect")
		# This will return when connection ends
		loop = asyncio.get_event_loop()

		try:
			print("Running in loop")
			loop.run_until_complete(self.client.connect())
			print("Loop done")
			print("Connection closed")
		finally:
			loop.close()

	@asyncio.coroutine
	def onConnect(self, initialData):
		print("Connected!")
		self.userList = yield from hangups.build_user_list(self.client, initialData)
		self.convList = hangups.ConversationList(self.client, initialData.conversation_states, self.userList, initialData.sync_timestamp)
		self.convList.on_event.add_observer(self.onEvent)

		for user in self.userList.get_all():
			pprint(vars(user))

		print("Disconnecting")
		self.client.disconnect()
		print("Connection handler end")
	
	def onEvent(self, convEvent):
		conv = self.convList.get(convEvent.conversation_id)
		user = conv.get_user(convEvent.user_id)
		print("Message")
		print(vars(user))
		print(vars(conv))
