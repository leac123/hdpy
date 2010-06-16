#!/usr/bin/env python

from mcap_defs import *
from mcap import *
from test1 import *
import time
import sys
import glib
import threading

class MCAPSessionClientStub:

	sent = [ 
		"0AFF000ABC", # send an invalid message (Op Code does not exist)
		"01FF000ABC", # send a CREATE_MD_REQ (0x01) with invalid MDLID == 0xFF00 (DO NOT ACCEPT)
        	"0100230ABC", # send a CREATE_MD_REQ (0x01) MDEPID == 0x0A MDLID == 0x0023 CONF = 0xBC (ACCEPT)
		"0100240ABC", # send a CREATE_MD_REQ (0x01) MDEPID == 0x0A MDLID == 0x0024 CONF = 0xBC (ACCEPT)
        	"0100270ABC",  # send a CREATE_MD_REQ (0x01) MDEPID == 0x0A MDLID == 0x0027 CONF = 0xBC (ACCEPT)
        	"050027", # send an invalid ABORT_MD_REQ (0x05) MDLID == 0x0027 (DO NOT ACCEPT - not on PENDING state)
        	"070030", # send a valid DELETE_MD_REQ (0x07) MDLID == 0x0027
        	"07FFFF", # send a valid DELETE_MD_REQ (0x07) MDLID == MDL_ID_ALL (0XFFFF)
		]

	received = [
		"00010000", # receive a ERROR_RSP (0x00) with RSP Invalid OP (0x01)
		"0205FF00BC", # receive a CREATE_MD_RSP (0x02) with RSP Invalid MDL (0x05)
        	"02000023BC", # receive a CREATE_MD_RSP (0x02) with RSP Sucess (0x00)
		"02000024BC", # receive a CREATE_MD_RSP (0x02) with RSP Sucess (0x00)
        	"02000027BC", # receive a CREATE_MD_RSP (0x02) with RSP Sucess (0x00)
        	"06070027", # receive a ABORT_MD_RSP (0x06) with RSP Invalid Operation (0x07)
        	"08000030", # receive a DELETE_MD_RSP (0x08) with RSP Sucess (0x00)
        	"0800FFFF", # receive a DELETE_MD_RSP (0x08) with RSP Sucess (0x00)
		]

	def __init__(self, _mcl):
		self.bclock = threading.Lock()
		self.can_write = True
 		self.counter = 0
		self.mcl = _mcl
		self.mcl_state_machine = MCLStateMachine(_mcl)

	def stop_session(self):
		self.mcl.close_cc()
		glib.MainLoop.quit(self.inLoop)

	def start_session(self):
		if ( self.mcl.is_cc_open() ):
			glib.io_add_watch(self.mcl.cc, glib.IO_IN, self.read_cb)
			glib.io_add_watch(self.mcl.cc, glib.IO_OUT, self.write_cb)
			glib.io_add_watch(self.mcl.cc, glib.IO_ERR, self.close_cb)
			glib.io_add_watch(self.mcl.cc, glib.IO_HUP, self.close_cb)

	def read_cb(self, socket, *args):
		try:
			if ( self.mcl.is_cc_open() ):
				message = self.mcl.read()
				if (message != ''):
					# do whatever you want
					self.mcl_state_machine.receive_message(message)
					assert(message == testmsg(self.received[self.counter]))
					self.check_asserts(self.counter)
					self.bclock.acquire()
					self.can_write = True
					self.counter = self.counter + 1
					self.bclock.release()
		except Exception as inst:
			print "CANNOT READ: " + repr(inst)
			return False
		return True

	def write_cb(self, socket, *args):
		#print "CAN WRITE"
		if ( self.counter >= len(testmsg(self.sent)) ):
			self.stop_session()
			return True

		if (self.can_write) :
			self.mcl_state_machine.send_raw_message(testmsg(self.sent[self.counter]))
			self.bclock.acquire()
			self.can_write = False
			self.bclock.release()
		return True

	def close_cb(self, socket, *args):
		self.stop_session()
		return True

	def loop(self):
		self.inLoop = glib.MainLoop()
		self.inLoop.run()

	def check_asserts(self, counter):
		if (self.counter == 2):
			assert(self.mcl.count_mdls() == 1)
			assert(self.mcl_state_machine.state == MCAP_STATE_READY)
			assert(self.mcl.state == MCAP_MCL_STATE_ACTIVE)
		elif (self.counter == 3):
			assert(self.mcl.count_mdls() == 2)
			assert(self.mcl_state_machine.state == MCAP_STATE_READY)
			assert(self.mcl.state == MCAP_MCL_STATE_ACTIVE)		
		elif (self.counter == 4):
			assert(self.mcl.count_mdls() == 3)
			assert(self.mcl_state_machine.state == MCAP_STATE_READY)
			assert(self.mcl.state == MCAP_MCL_STATE_ACTIVE)
		elif (self.counter == 5):
			assert(self.mcl.count_mdls() == 3)
			assert(self.mcl.state == MCAP_MCL_STATE_ACTIVE)
			assert(self.mcl_state_machine.state == MCAP_STATE_READY)
		elif (self.counter == 6):			
			assert(self.mcl.count_mdls() == 2)
			assert(self.mcl.state == MCAP_MCL_STATE_ACTIVE)
			assert(self.mcl_state_machine.state == MCAP_STATE_READY)
		elif (self.counter == 7):
			assert(self.mcl.count_mdls() == 0)
			assert(self.mcl.state == MCAP_MCL_STATE_CONNECTED)
			assert(self.mcl_state_machine.state == MCAP_STATE_READY)

		

if __name__=='__main__':

	btaddr = sys.argv[1]
	psm = sys.argv[2]

	mcl = MCL(btaddr, MCAP_MCL_ROLE_INITIATOR)

	mcap_session = MCAPSessionClientStub(mcl)

	assert(mcl.state == MCAP_MCL_STATE_IDLE)

	print "Requesting connection..."
	if ( not mcl.is_cc_open() ):
		mcl.connect_cc((btaddr, int(psm)))

	print "Connected!"
	assert(mcl.state == MCAP_MCL_STATE_CONNECTED)

	if ( mcl.is_cc_open() ):
		mcap_session.start_session()
	else:
		raise Exception ('ERROR: Cannot open control channel for initiator')

	mcap_session.loop()

	print 'TESTS OK' 