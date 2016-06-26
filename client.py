# hangups client wrapper for h2x

import asyncio
import re
import threading
from enum import Enum
from pprint import pprint

from twisted.words.protocols.jabber.jid import JID

import hangups

from userdb import User


class UserNotRegistered(Exception):
	def __init__(self, jid):
		self.jid = jid

	def __str__(self):
		return "User not registered: " + repr(self.jid.full())


# Client connection state
class State(Enum):
	disconnected = 0
	connecting = 1
	connected = 2
	disconnecting = 3


# Wrapper for single hangouts client
class ClientWrapper:
	def __init__(self, h2x, jid: JID):
		self.h2x = h2x
		self.jid = jid
		self.user = User(jid.userhost())
		self.state = State.disconnected
		self.targetState = State.disconnected
		self.thread = None
		self.loop = None
		self.client = None
		self.userList = None

		# Track connected instances of XMPP clients, for presence control
		self.xmppClients = set()

		if not self.user.token:
			raise UserNotRegistered(jid)

		self.h2x.sendPresence(self.jid, "unavailable", "Client wrapper created")

	# Provides token if refresh fails
	# Would be nice to ask user for token
	def getToken(self):
		return self.user.token

	def connect(self):
		self.targetState = State.connected
		if self.state == State.disconnected:
			self.state = State.connecting
			print("Connect!!!")
			self.thread = threading.Thread(target=self.clientBody)
			self.thread.start()
		self.sendPresence()

	def disconnect(self):
		self.targetState = State.disconnected
		if self.state == State.connected:
			self.state == State.disconnecting
			print("Disconnect!!!")

			self.sendPresence()

			try:
				future = asyncio.async(self.client.disconnect(), loop=self.loop)
				future.add_done_callback(lambda future: print("Disconnect done"))
			except Exception as e:
				print("Disconnect failed: ", e)

			self.sendPresence()

	def stateUpdate(self, current: State = None):
		if current:
			self.state = current
		print("StateSwitch: now: " + self.state.__str__() + " want: " + self.targetState.__str__())

		if self.targetState == State.connected and self.state == State.disconnected:
			self.connect()
		if self.targetState == State.disconnected and self.state == State.connected:
			self.disconnect()

		self.sendPresence()

	def clientBody(self):
		# Initialize asyncio loop for this thread
		self.loop = asyncio.new_event_loop()
		asyncio.set_event_loop(self.loop)

		# Get oauth2 cookies
		self.h2x.sendPresence(self.jid, "unavailable", "Getting cookies")
		cookies = hangups.auth.get_auth(self.getToken, self.user.tokenRefreshPath())

		# Create client
		self.h2x.sendPresence(self.jid, "unavailable", "Initializing client")
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
			self.loop.run_until_complete(self.client.connect())
			print("Loop done")
		finally:
			self.loop.close()

		# Notify about client termination, resolve possible requested state change
		self.stateUpdate(State.disconnected)

		print("Client thread terminates")

	@asyncio.coroutine
	def onConnect(self):
		print("Connected!")
		self.state = State.connected
		self.h2x.sendPresence(self.jid, "available", "Online")

		self.userList, self.convList = (
			yield from hangups.build_user_conversation_list(self.client)
		)
		self.convList.on_event.add_observer(self.onEvent)

		yield from self.updateParticipantPresence()

		self.stateUpdate()

		# Test presence setting
		print("Trying to set presence")

	#		print("PresenceStateSettings:")
	#		pprint(vars(hangups.hangouts_pb2.PresenceStateSetting))
	#		print("DND settings")
	#		pprint(vars(hangups.hangouts_pb2.DndSetting))
	#		print("DesktopOff")
	#		pprint(vars(hangups.hangouts_pb2.DesktopOffSetting))
	#		print("Mood")
	#		pprint(vars(hangups.hangouts_pb2.MoodSetting))


	# ClientPresenceStateType
	#		setPresenceRequest = hangups.hangouts_pb2.SetPresenceRequest(
	#			presence_state_setting = hangups.hangouts_pb2.PresenceStateSetting(
	#				timeout_secs = 30,
	#				type = 0
	#			),
	#			dnd_setting = hangups.hangouts_pb2.DndSetting(
	#				do_not_disturb = 0,
	#				timeout_secs = 30
	#			),
	#			desktop_off_setting = hangups.hangouts_pb2.DesktopOffSetting(
	#				desktop_off = 0
	#			)
	#		)

	##		,mood_setting = hangups.hangouts_pb2.MoodSetting(
	##			mood_message = hangups.hangouts_pb2.MoodMessage(
	##				mood_content = "Online"
	##			)
	##		)

	##		#hangups.hangouts_pb2.ClientPresenceStateType._enum_type.values[0],
	#		asyncio.async(self.client.set_presence(setPresenceRequest), loop=self.loop)
	#		print("Presence set started")

	@asyncio.coroutine
	def updateParticipantPresence(self):
		print("Sending presence for hangouts users")

		# Guard for empty user list (possibly not yet connected client)
		if not self.userList:
			return

		# Create list of all participants
		participants = []
		for user in self.userList.get_all():
			if not user.is_self:
				participant = hangups.hangouts_pb2.ParticipantId(
						gaia_id=user.id_.gaia_id,
						chat_id=user.id_.chat_id
				)
				participants.append(participant)

		# If we are supposed to be connected, query state
		if self.targetState == State.connected:
			# Create presence request
			req = hangups.hangouts_pb2.QueryPresenceRequest(
					participant_id=iter(participants),
					field_mask=iter([1, 2, 7])  # All fields (reachable, available, device)
			)

			# Send the request
			resp = yield from asyncio.async(self.client.query_presence(req), loop=self.loop)

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

				self.h2x.sendPresence(self.jid, state, source=self.participant2JID(presence.user_id), show=show)
		else:
			# If we are disconnected just say everybody is disconnected
			for participant in participants:
				self.h2x.sendPresence(self.jid, "unavailable", source=self.participant2JID(participant))

	# Check if uses is in contact list
	def isSubscribed(self, jid: JID):
		user = self.JID2Hang(jid)
		if self.userList.get_user(user):
			return True
		else:
			return False

	# Send current presence to jabber client
	def sendPresence(self):
		if self.state == State.disconnected:
			self.h2x.sendPresence(self.jid, "unavailable", "Client disconnected")
		elif self.state == State.connecting:
			self.h2x.sendPresence(self.jid, "unavailable", "Client connecting...")
		elif self.state == State.connected:
			self.h2x.sendPresence(self.jid, "available", "Client connected")
		elif self.state == State.disconnecting:
			self.h2x.sendPresence(self.jid, "available", "Client disconnecting...")

		if self.loop and not self.loop.is_closed():
			asyncio.async(self.updateParticipantPresence(), loop=self.loop)

	def getUser(self, jid: JID):
		uid = self.JID2Hang(jid)
		return self.userList.get_user(uid)

	# Import Hangouts contacts to jabber
	def importContacts(self):
		print("Importing contacts")

		for user in self.userList.get_all():
			if user.is_self == False:
				self.h2x.sendPresence(self.jid, "subscribe", source=self.hang2JID(user), nick=user.full_name)

	@asyncio.coroutine
	def onDisconnect(self):
		print("Disconnected")
		self.stateUpdate(State.disconnected)

	@asyncio.coroutine
	def onReconnect(self):
		print("Reconnected")
		self.stateUpdate(State.connected)

	@asyncio.coroutine
	def onStateUpdate(self, state: hangups.hangouts_pb2.StateUpdate):
		print("StateUpdate:" + state.__str__())
		# TODO: This is stupid but works, we would like to update only changed presence
		try:
			yield from self.updateParticipantPresence()
		except Exception as e:
			print("Update participant presence failed with exception " + str(e));
			print("Forcing reconnect")
			self.stateUpdate(State.disconnected)

	def ids2JID(self, chat_id: str, gaia_id: str):
		return chat_id + "." + gaia_id + "@" + self.h2x.config.JID

	def participant2JID(self, participant: hangups.user):
		return JID(self.ids2JID(participant.chat_id, participant.gaia_id))

	def hang2JID(self, hangUser: hangups.user):
		return JID(self.ids2JID(hangUser.id_.chat_id, hangUser.id_.gaia_id))

	def JID2Hang(self, jid: JID):
		if not self.h2x.isHangUser(jid):
			raise Exception(jid.full() + " is not valid user JID for the transport")
		userIdParts = jid.user.split(".")
		userChatId = userIdParts[0]
		userGaiaId = userIdParts[1]
		return hangups.user.UserID(userChatId, userGaiaId)

	def onEvent(self, convEvent: hangups.conversation_event):
		# Chat message
		if type(convEvent) is hangups.conversation_event.ChatMessageEvent:
			conv = self.convList.get(convEvent.conversation_id)
			# Not yet delivered chat message
			if convEvent.timestamp > conv.latest_read_timestamp:
				# Deliver chat message
				user = conv.get_user(convEvent.user_id)
				if not user.is_self:
					# TODO: message timestamp for offline delivery
					self.h2x.sendMessage(self.jid, self.hang2JID(user), convEvent.text)
			conv.update_read_timestamp()
		else:
			print("Unsupported conversation event " + type(convEvent))
		# TODO: Handle other events

	def sendMessage(self, recipient: JID, text: str):
		# Pick the conversation with the recipient user only
		conversation = None
		userId = self.JID2Hang(recipient)
		for c in self.convList.get_all():
			if len(c.users) == 2:
				for u in c.users:
					if u.id_.__dict__ == userId.__dict__:
						conversation = c

		if conversation is None:
			raise Exception("No conversation found for the recipient")

		# Send message
		segments = hangups.ChatMessageSegment.from_str(text)
		asyncio.async(
				conversation.send_message(segments), loop=self.loop
		).add_done_callback(lambda x: print("Message sent"))

	def processPresence(self, recipient, presence):
		# TODO: Send presence to hangouts users
		print("Sending presence to hangouts user is not implemented")

	def processSubscription(self, recipient: JID):
		if self.isSubscribed(recipient):
			self.h2x.sendPresence(self.jid, "subscribed", source=recipient)
			if self.loop:
				asyncio.async(self.updateParticipantPresence(), loop=self.loop)
		else:
			self.h2x.sendPresence(self.jid, "unsubscribed", source=recipient)
		return

	def processComponentPresence(self, sender: JID, presenceType: str, recipient: JID):
		if presenceType == "available":
			if not self.xmppClients:
				print("Available requested, no xmpp clients yet -> connect")
				self.targetState = State.connected
			self.xmppClients.add(sender)
		elif presenceType == "unavailable":
			self.xmppClients.discard(sender)
			if not self.xmppClients:
				print("Unavailable requested, no xmpp clients now -> disconnect")
				self.targetState = State.disconnected
		elif presenceType == "probe":
			self.sendPresence()
		elif presenceType == "subscribed":
			print("Presence type subscribed not supported")
		elif presenceType == "subscribe":
			self.h2x.sendPresence(self.jid, "subscribed", source=recipient)
		else:
			raise NotImplementedError("Presence type: " + presenceType)

		# Ensure we are in the requested state
		self.stateUpdate()
