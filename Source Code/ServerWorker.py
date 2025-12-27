from random import randint
import sys, traceback, threading, socket

from VideoStream import VideoStream
from RtpPacket import RtpPacket
import struct
import time
# import random
from random import uniform

class ServerWorker:
	SETUP = 'SETUP'
	PLAY = 'PLAY'
	PAUSE = 'PAUSE'
	TEARDOWN = 'TEARDOWN'
	# Them moi lenh de dieu chinh toc do gui RTP
	SENDSPEED = 'SENDSPEED'
	
	INIT = 0
	READY = 1
	PLAYING = 2
	state = INIT

	OK_200 = 0
	FILE_NOT_FOUND_404 = 1
	CON_ERR_500 = 2
	
	clientInfo = {}
	
	def __init__(self, clientInfo):
		self.clientInfo = clientInfo
		self.clientInfo['interval'] = 0.05
		
	def run(self):
		t = threading.Thread(target=self.recvRtspRequest)
		# Đặt là daemon TRƯỚC KHI start
		t.daemon = True 
		t.start()
	
	def recvRtspRequest(self):
		"""Receive RTSP request from the client."""
		connSocket = self.clientInfo['rtspSocket'][0]
		while True:            
			data = connSocket.recv(256)
			if data:
				# print("Data received:\n" + data.decode("utf-8"))
				self.processRtspRequest(data.decode("utf-8"))
	
	# Lam 
	def processRtspRequest(self, data):
		"""Process RTSP request sent from the client."""
		# Get the request type
		request = data.split('\n')
		line1 = request[0].split(' ')
		requestType = line1[0]
		
		# Get the media file name
		filename = line1[1]
		
		# Get the RTSP sequence number 
		seq = request[1].split(' ')
		
		# Process SETUP request
		if requestType == self.SETUP:
			if self.state == self.INIT:
				# Update state
				# print("processing SETUP\n")
				
				try:
					self.clientInfo['videoStream'] = VideoStream(filename)
					self.state = self.READY
					self.clientInfo['interval'] = 0.05
				except IOError:
					self.replyRtsp(self.FILE_NOT_FOUND_404, seq[1])
				
				# Generate a randomized RTSP session ID
				self.clientInfo['session'] = randint(100000, 999999)
				
				self.clientInfo["rtpSocket"] = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
				# Tao buffer lon de chua duoc anh HD
				self.clientInfo["rtpSocket"].setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 10 * 1024 * 1024)
    
				# Send RTSP reply
				self.replyRtsp(self.OK_200, seq[1])
				
				time.sleep(0.5)

				self.clientInfo['event'] = threading.Event()
				self.clientInfo['worker']= threading.Thread(target=self.sendRtp) 
				self.clientInfo['worker'].daemon = True
				self.clientInfo['worker'].start()
    
				# Get the RTP/UDP port from the last line
				self.clientInfo['rtpPort'] = request[2].split(' ')[3]	
		# Process PLAY request 		
		elif requestType == self.PLAY:
			if self.state == self.READY:
				# print("processing PLAY\n")
				self.state = self.PLAYING
				
				self.replyRtsp(self.OK_200, seq[1])
				
				thread_is_alive = False
				if 'worker' in self.clientInfo:
					if self.clientInfo['worker'].is_alive():
						thread_is_alive = True
				
				if thread_is_alive:
					# print("Thread already running. Continuing...")
					pass
				else:
					print("Resuming: Starting new thread.")
					self.clientInfo['event'] = threading.Event()
					self.clientInfo['worker'] = threading.Thread(target=self.sendRtp) 
					self.clientInfo['worker'].start()
				# ---------------------------------------------------------------
		
		# Process PAUSE request
		elif requestType == self.PAUSE:
			# self.PLAYING la do lenh tu dong pause vi tran buffer nen khong reset duoc state
			if self.state == self.PLAYING or self.state == self.READY:
				# print("processing PAUSE\n")
				self.state = self.READY
				
				self.clientInfo['event'].set()
			
				self.replyRtsp(self.OK_200, seq[1])
		
		# Process TEARDOWN request
		elif requestType == self.TEARDOWN:
			# print("processing TEARDOWN\n")

			self.clientInfo['event'].set()
			
			self.replyRtsp(self.OK_200, seq[1])
			
			# Close the RTP socket
			self.clientInfo['rtpSocket'].close()
		elif requestType == self.SENDSPEED:
			try:
				lossRate = float(filename) 
				# Xu ly dieu chinh interval gui RTP dua tren loss rate
				self.adjustRate(lossRate)
			except ValueError:
				pass
	
	def adjustRate(self, lossRate):
		cur = self.clientInfo['interval']
		# Mat goi > 5%
		if (lossRate > 5.0):
			new_interval = cur * 1.5
		# Mat goi > 0.5%
		elif lossRate > 0.5:
			new_interval = cur * 1.1
		else:
			if cur > 0.005:
				new_interval = cur * 0.9
			else:
				new_interval = cur
		self.clientInfo['interval'] = max(0.005, min(new_interval, 0.1))
 	
	# Lam 
	def sendRtp(self):
			"""Send RTP packets over UDP."""
			while True:
				# self.clientInfo['event'].wait(0.0166) 
				# interval = self.clientInfo.get('interval', 0.05)
				self.clientInfo['event'].wait(self.clientInfo['interval'])
				if self.clientInfo['event'].isSet(): 
					break 
					
				data = self.clientInfo['videoStream'].nextFrame()
				
				if data: 
					frameNumber = self.clientInfo['videoStream'].frameNbr()
					try:
						address = self.clientInfo['rtspSocket'][1][0]
						port = int(self.clientInfo['rtpPort'])

						frameLength = len(data) 
						size_header = struct.pack("!I", frameLength) 
						
						# Cau truc: | Size (4 bytes) | Data (frameLength bytes) |
						send_data = size_header + data 
						
						# Phan manh RTP va gui
						MAXLEN = 1400
						dataLen = len(send_data) 
						i = 0
						while i < dataLen:
							dataFrame = send_data[i:i + MAXLEN]
							
							# Da den cuoi file
							if (i + MAXLEN) >= dataLen:
								marker = 1 
							else:
								marker = 0
							self.clientInfo['rtpSocket'].sendto(self.makeRtp(dataFrame, frameNumber, marker), (address, port))
							
							i += MAXLEN
					except:
						print("Connection Error")

	def makeRtp(self, payload, frameNbr, marker = 0):
		"""RTP-packetize the video data."""
		version = 2
		padding = 0
		extension = 0
		cc = 0
		# marker = 0
		pt = 26 # MJPEG type
		seqnum = frameNbr
		ssrc = 0 
		
		rtpPacket = RtpPacket()
		
		rtpPacket.encode(version, padding, extension, cc, seqnum, marker, pt, ssrc, payload)
		
		return rtpPacket.getPacket()
		
	def replyRtsp(self, code, seq):
		"""Send RTSP reply to the client."""
		if code == self.OK_200:
			#print("200 OK")
			reply = 'RTSP/1.0 200 OK\nCSeq: ' + seq + '\nSession: ' + str(self.clientInfo['session'])
			connSocket = self.clientInfo['rtspSocket'][0]
			connSocket.send(reply.encode())
		
		# Error messages
		elif code == self.FILE_NOT_FOUND_404:
			print("404 NOT FOUND")
		elif code == self.CON_ERR_500:
			print("500 CONNECTION ERROR")
