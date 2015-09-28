# hangups client wrapper for h2x

import sys
import hangups
import time
import asyncio
from threading import Thread


class ClientWrapper:
	def __init__(self, h2x, user, userJID):
		self.h2x = h2x
		self.userdb = h2x.userdb
		self.user = user
		self.userJID = userJID
		
		self.thread = None
		self.loop = None
		
		self.h2x.sendComponentPresence(self.userJID, "unavailable", "Client wrapper created")
	
	# Provides token if refresh fails
	# Would be nice to ask user for token
	def getToken(self):
		return self.user.token
		
	def connect(self):
		print("Connect!!!")
		self.disconnect()
		
		self.thread = Thread(target = self.clientBody)
		self.thread.start()
	
	def disconnect(self):
		print("Disconnect!!!")
		
		if self.thread != None:
			print("Stopping client thread")
			
			print("Calling disconnect")
			print("Disconnecting")
	
			future = asyncio.async(self.client.disconnect(), loop = self.loop)
			future.add_done_callback(lambda future: print("Disconnect done"))
	
			print("Trashing references")
			self.thread = None
			self.loop = None
				
		self.h2x.sendComponentPresence(self.userJID, "unavailable", "Client disconnected")
		
		print("Disconnect done")
	
	def clientBody(self):
		# Initialize asyncio loop for this thread
		self.loop = asyncio.new_event_loop()
		loop = self.loop
		asyncio.set_event_loop(loop)
		
		# Get outh2 cookies
		self.h2x.sendComponentPresence(self.userJID, "unavailable", "Getting cookies")
		cookies = hangups.auth.get_auth(self.getToken, self.userdb.tokenRefreshPath(self.user))
		
		# Create client
		self.h2x.sendComponentPresence(self.userJID, "unavailable", "Initializing client")
		self.client = hangups.Client(cookies)
		
		# Add state change observers
		self.client.on_connect.add_observer(self.onConnect)
		self.client.on_disconnect.add_observer(self.onDisconnect)
		self.client.on_reconnect.add_observer(self.onReconnect)
		
		# Connect and run client
		self.h2x.sendComponentPresence(self.userJID, "unavailable", "Client connecting...")
		# This will return when connection ends
		try:
			print("Running in loop")
			loop.run_until_complete(self.client.connect())
			print("Loop done")
		finally:
			loop.close()
		
		# Notify about client termination
		self.h2x.sendComponentPresence(self.userJID, "unavailable", "Client disconnected")
		print("Client thread terminates")

	@asyncio.coroutine
	def onConnect(self, initialData):
		print("Connected!")
		self.h2x.sendComponentPresence(self.userJID, "available", "Online")
		
		self.userList = yield from hangups.build_user_list(self.client, initialData)
		self.convList = hangups.ConversationList(self.client, initialData.conversation_states, self.userList, initialData.sync_timestamp)
		self.convList.on_event.add_observer(self.onEvent)

		for user in self.userList.get_all():
			print(vars(user))
	
		print("Connection handler end")
		
	@asyncio.coroutine
	def onDisconnect(self):
		print("Disconnected")
		
	@asyncio.coroutine
	def onReconnect(self):
		print("Reconnected")
		
		
	def hang2JID(self, hangUser):
		return hangUser.id_.chat_id + "@" + self.h2x.config.JID
	
	def onEvent(self, convEvent):
		conv = self.convList.get(convEvent.conversation_id)
		user = conv.get_user(convEvent.user_id)
		print("Message")
		print("User:")
		print(vars(user))
		print("Conv:")
		print(vars(conv))
		
		
		for event in conv._events:
			print("Event")
			print(type(event))
			print(event.text)
			self.h2x.sendMessage(self.userJID, self.hang2JID(user), event.text)








