# hangups client wrapper for h2x

import sys
import hangups
import time
import asyncio
import re
import threading


class ClientWrapper:
	def __init__(self, h2x, user, userJID):
		self.h2x = h2x
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
		
		self.thread = threading.Thread(target = self.clientBody)
		self.thread.start()
	
	def disconnect(self):
		print("Disconnect!!!")
		
		if self.thread != None:
			print("Stopping client thread")
			
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
		cookies = hangups.auth.get_auth(self.getToken, self.user.tokenRefreshPath())
		
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
		
		# Send presence for users on contact list
		for user in self.userList.get_all():
			if user.is_self == False:
				self.h2x.sendPresence(self.hang2JID(user), self.userJID, "available", "Present in user list")
				
		print("Conversations: ")
		for c in self.convList.get_all():
			#print(vars(c))
			print("> Conversation users:")
			for u in c.users:
				print("> > User:")
				print(vars(u))
	
		print("Connection handler end")
		
	@asyncio.coroutine
	def onDisconnect(self):
		print("Disconnected")
		
	@asyncio.coroutine
	def onReconnect(self):
		print("Reconnected")
		
	def hang2JID(self, hangUser):
		return hangUser.id_.chat_id + "." + hangUser.id_.gaia_id + "@" + self.h2x.config.JID
	
	def JID2Hang(self, userJID):
		SUFFIX = "@" + self.h2x.config.JID + "$";
		print("Suffix: " + SUFFIX)
		if not re.match(".*" + SUFFIX, userJID):
			raise Exception(userJID + " is not valid user JID for the transport")
		userIdParts = re.sub(SUFFIX, "", userJID).split(".")
		userChatId = userIdParts[0]
		userGaiaId = userIdParts[1]
		return hangups.user.UserID(userChatId, userGaiaId)
	
	def onEvent(self, convEvent):
		# Chat message
		if type(convEvent) is hangups.conversation_event.ChatMessageEvent:
			# Not yet delivered chat message
			# TODO: Use conversation -> unread events
			if convEvent.timestamp.timestamp() > self.user.lastMessageTimestamp:
				# Deliver chat message
				conv = self.convList.get(convEvent.conversation_id)
				user = conv.get_user(convEvent.user_id)
				if not user.is_self:
					self.h2x.sendMessage(self.userJID, self.hang2JID(user), convEvent.text)
				
				self.user.lastMessageTimestamp = convEvent.timestamp.timestamp()
		# TODO: Handle other events

	def sendMessage(self, recipientJID, text):
		# Pick the coversation with the recipient user only
		conversation = None
		userId = self.JID2Hang(recipientJID)
		print(vars(userId))
		print("Inspecting conversations: ")
		for c in self.convList.get_all():
			print(vars(c))
			if len(c.users) == 2:
				print("Has 2 users")
				for u in c.users:
					print(vars(u))
					if u.id_.__dict__ == userId.__dict__:
						print("MATCHES")
						conversation = c
						
		if conversation == None:
			raise "No conversation found for the recipient"
		
		# Send message
		segments = hangups.ChatMessageSegment.from_str(text)
		asyncio.async(
			conversation.send_message(segments), loop = self.loop
		).add_done_callback(lambda x: print("Message sent"))