# hangups client wrapper for h2x

import sys
import hangups
import time
import asyncio
import re
import threading
import itertools

from enum import Enum

# Client connection state
class State(Enum):
	disconnected = 0
	connecting = 1
	connected = 2
	disconnecting = 3

# Wapper for single hangouts client
class ClientWrapper:
	def __init__(self, h2x, user, userJID):
		self.h2x = h2x
		self.user = user
		self.userJID = userJID
		
		self.state = State.disconnected
		
		self.thread = None
		self.loop = None
		
		self.h2x.sendPresence(self.userJID, "unavailable", "Client wrapper created")
	
	# Provides token if refresh fails
	# Would be nice to ask user for token
	def getToken(self):
		return self.user.token
		
	def connect(self):
		if self.state == State.disconnected:
			self.state = State.connecting
			print("Connect!!!")
			self.thread = threading.Thread(target = self.clientBody)
			self.thread.start()
	
	def disconnect(self):
		if self.state == State.connected:
			self.state == State.disconnecting
			print("Disconnect!!!")
			
			self.sendPresence()
		
			future = asyncio.async(self.client.disconnect(), loop = self.loop)
			future.add_done_callback(lambda future: print("Disconnect done"))
			
			self.sendPresence()
	
	def clientBody(self):
		# Initialize asyncio loop for this thread
		self.loop = asyncio.new_event_loop()
		loop = self.loop
		asyncio.set_event_loop(loop)
		
		# Get outh2 cookies
		self.h2x.sendPresence(self.userJID, "unavailable", "Getting cookies")
		cookies = hangups.auth.get_auth(self.getToken, self.user.tokenRefreshPath())
		
		# Create client
		self.h2x.sendPresence(self.userJID, "unavailable", "Initializing client")
		self.client = hangups.Client(cookies)
		
		# Add state change observers
		self.client.on_connect.add_observer(self.onConnect)
		self.client.on_disconnect.add_observer(self.onDisconnect)
		self.client.on_reconnect.add_observer(self.onReconnect)
		self.client.on_state_update.add_observer(self.onStateUpdate)
		
		# Connect and run client
		self.sendPresence()
		# This will return when connection ends
		try:
			print("Running in loop")
			loop.run_until_complete(self.client.connect())
			print("Loop done")
		finally:
			loop.close()
		
		self.state = State.disconnected
		
		# Notify about client termination
		self.sendPresence()
		print("Client thread terminates")

	@asyncio.coroutine
	def onConnect(self):
		print("Connected!")
		self.state = State.connected
		self.h2x.sendPresence(self.userJID, "available", "Online")
		
		self.userList, self.convList = (
            yield from hangups.build_user_conversation_list(self.client)
        )
		self.convList.on_event.add_observer(self.onEvent)
		
		yield from self.updateParticipantPresence()
	
	@asyncio.coroutine
	def updateParticipantPresence(self):
		print("Sending presence for hangouts users")
		# Create list of all participants
		participants = []
		for user in self.userList.get_all():
			if user.is_self == False:
				participant = hangups.hangouts_pb2.ParticipantId(
					gaia_id = user.id_.gaia_id,
					chat_id = user.id_.chat_id
				)
				participants.append(participant)
		
		# Create presence request
		req = hangups.hangouts_pb2.QueryPresenceRequest(
			participant_id = iter(participants),
			field_mask = iter([1, 2, 7]) # All fields (reachable, available, device)
		)
		
		# Send the request
		resp = yield from asyncio.async(self.client.query_presence(req), loop = self.loop)
		
		# Process presence from result
		presences = resp.presence_result
		for presence in presences:
			if presence.presence.reachable:
				state = "available"
			else:
				state = "unavailable"
			
			if presence.presence.available:
				show = "xa"
			else:
				show = None
		
			self.h2x.sendPresence(self.userJID, state, source = self.participant2JID(presence.user_id), show = show)
		
				
	# Check if uses is in contact list
	def isSubscribed(self, jid):
		user = self.JID2Hang(jid)
		if self.userList.get_user(user):
			return True
		else:
			return False
		
	# Send current presence to jabber client
	def sendPresence(self):
		if self.state == State.disconnected:
			self.h2x.sendPresence(self.userJID, "unavailable", "Client disconnected")
		elif self.state == State.connecting:
			self.h2x.sendPresence(self.userJID, "unavailable", "Client connecting...")
		elif self.state == State.connected:
			self.h2x.sendPresence(self.userJID, "available", "Client connected")
		elif self.state == State.disconnecting:
			self.h2x.sendPresence(self.userJID, "available", "Client disconnecting...")
	
	def getUser(self, jid):
		uid = self.JID2Hang(jid) 
		return self.userList.get_user(uid)
		
	# Import Hangouts contacts to jabber
	def importContacts(self):
		print("Importing contacts")
		
		for user in self.userList.get_all():
			if user.is_self == False:
				self.h2x.sendPresence(self.userJID, "subscribe", source = self.hang2JID(user), nick = user.full_name)
		
	@asyncio.coroutine
	def onDisconnect(self):
		print("Disconnected")
		
	@asyncio.coroutine
	def onReconnect(self):
		print("Reconnected")
		
	@asyncio.coroutine
	def onStateUpdate(self, state):
		print("StateUpdate")
		# TODO: This is stupid but works, we would like to update only changed presence
		yield from self.updateParticipantPresence()
	
	def ids2JID(self, chat_id, gaia_id):
		return chat_id + "." + gaia_id + "@" + self.h2x.config.JID
	
	def participant2JID(self, participant):
		return self.ids2JID(participant.chat_id, participant.gaia_id)
		
	def hang2JID(self, hangUser):
		return self.ids2JID(hangUser.id_.chat_id, hangUser.id_.gaia_id)
		
	def JID2Hang(self, userJID):
		if not self.h2x.isHangUser(userJID):
			raise Exception(userJID + " is not valid user JID for the transport")
		userIdParts = re.sub(self.h2x.SUFFIX, "", userJID).split(".")
		userChatId = userIdParts[0]
		userGaiaId = userIdParts[1]
		return hangups.user.UserID(userChatId, userGaiaId)
	
	def onEvent(self, convEvent):
		# Chat message
		if type(convEvent) is hangups.conversation_event.ChatMessageEvent:
			conv = self.convList.get(convEvent.conversation_id)
			# Not yet delivered chat message
			if convEvent.timestamp > conv.latest_read_timestamp:
				# Deliver chat message
				user = conv.get_user(convEvent.user_id)
				if not user.is_self:
					# TODO: message tiestamp for offline delivery
					self.h2x.sendMessage(self.userJID, self.hang2JID(user), convEvent.text)
			conv.update_read_timestamp()
		
		# TODO: Handle other events

	def sendMessage(self, recipientJID, text):
		# Pick the coversation with the recipient user only
		conversation = None
		userId = self.JID2Hang(recipientJID)
		for c in self.convList.get_all():
			if len(c.users) == 2:
				for u in c.users:
					if u.id_.__dict__ == userId.__dict__:
						conversation = c

		if conversation == None:
			raise "No conversation found for the recipient"
		
		# Send message
		segments = hangups.ChatMessageSegment.from_str(text)
		asyncio.async(
			conversation.send_message(segments), loop = self.loop
		).add_done_callback(lambda x: print("Message sent"))