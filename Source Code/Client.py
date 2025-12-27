from tkinter import *
import tkinter.messagebox as tkMessageBox  
from PIL import Image, ImageTk, ImageDraw, ImageFont
import socket, threading, sys, traceback, os
import time
from collections import deque 
from RtpPacket import RtpPacket
import struct
import io

CACHE_FILE_NAME = "cache-"
CACHE_FILE_EXT = ".jpg"
FORMAT = "utf-8"			

class Client:
	INIT = 0
	READY = 1
	PLAYING = 2
	# Trang thai ban dau
	state = INIT
	
	SETUP = 0
	PLAY = 1
	PAUSE = 2
	TEARDOWN = 3
	
	# Them de giup server biet tinh hinh mang client 
	SENDSPEED = 4

	def __init__(self, master, serveraddr, serverport, rtpport, filename):
		self.master = master
		self.master.protocol("WM_DELETE_WINDOW", self.handler)
		self.createWidgets()
		self.serverAddr = serveraddr
		self.serverPort = int(serverport)
		self.rtpPort = int(rtpport)
		self.fileName = filename
		self.rtspSeq = 0
		self.sessionId = 0
		self.requestSent = -1
		self.teardownAcked = 0
		self.connectToServer()
		self.frameNbr = 0 

		# Handle HD video 
		# Seqnum hien tai
		self.lastSeqNum = 0 
		# Buffer de ghep manh
		self.frameBuffer = b""
		# So luong byte da nhan trong 1s
		self.totalByte = 0
		# Thoi gian
		self.startTime = 0
	
		# Handle buffering
		# Buffer
		self.frameQueue = deque()
		# Kich thuoc toi da
		self.CACHE_SIZE = 200
		# Neu TRUE thi tien hanh dung chieu de nap buffer
		self.isBuffering = True	
		# Neu FALSE thi dung phat de lam can buffer
		self.isAutoPaused = False
		# Nguong bat dau phat
		self.START_THRESHOLD = 50  
		# Nguong thap de tang do tre phat, neu qua thap thi co the server da ngat ket noi
		self.PANIC_THRESHOLD = 10 
		# Thoi gian kiem tra server da ngat ket noi hay chua
		self.BUFFERING_TIMEOUT = 1.0
		self.isServerDown = False
		
		# Xu li khi server ngung
		# Thoi gian bat dau buffer, co the tinh toan du theo timeout
		self.bufferingStartTime = 0
		self.playEvent = threading.Event()

		# Tinh frame loss va speed 
		# So frame thuc nhan
		self.intervalReceivedFrames = 0 
		# So frame mat mat
		self.intervalLostFrames = 0
		self.createIcons()
		self.current_frame = None

		# Jitter 
		self.currJitter = 0.0
		# Thoi gian nhan goi RTP truoc do tren ly thuyet
		self.prevRtpTime = 0
		# Thoi gian thuc nhan goi RTP truoc do
		self.prevRecvTime = 0
  
		# ICON
		self.spinner_angle = 0 
		self.base_spinner = self.create_base_spinner()
	def create_base_spinner(self):
		size = 60 
		img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
		draw = ImageDraw.Draw(img)
		draw.arc([2, 2, size-2, size-2], start=30, end=330, fill=(255, 255, 255, 255), width=6)
		return img

	def createIcons(self):
		"""Tạo icon có nền bán trong suốt để đè lên video."""
		width, height = 380, 280
		self.icon_pause_img = Image.new('RGBA', (width, height), (0, 0, 0, 100))
		draw = ImageDraw.Draw(self.icon_pause_img)
		bar_w, bar_h = 40, 100
		cx, cy = width // 2, height // 2
		draw.rectangle([cx - 30 - bar_w/2, cy - bar_h/2, cx - 30 + bar_w/2, cy + bar_h/2], fill=(255, 255, 255, 255))
		draw.rectangle([cx + 30 - bar_w/2, cy - bar_h/2, cx + 30 + bar_w/2, cy + bar_h/2], fill=(255, 255, 255, 255))
		
		self.icon_loading_img = Image.new('RGBA', (width, height), (0, 0, 0, 100))
		draw = ImageDraw.Draw(self.icon_loading_img)
		
		try:
			font = ImageFont.truetype("arial.ttf", 30)
		except:
			font = None
			
		text = "Buffering..."
		draw.text((cx - 60, cy - 15), text, fill=(255, 255, 255, 255), font=font)
		draw.arc([cx - 50, cy + 30, cx + 50, cy + 130], start=0, end=360, fill=(255, 255, 0, 255), width=5)
	def createWidgets(self):
		"""Build GUI."""
		# Create Setup button
		self.setup = Button(self.master, width=20, padx=3, pady=3)
		self.setup["text"] = "Setup"
		self.setup["command"] = self.setupMovie
		self.setup.grid(row=1, column=0, padx=2, pady=2)
		
		# Create Play button		
		self.start = Button(self.master, width=20, padx=3, pady=3)
		self.start["text"] = "Play"
		self.start["command"] = self.playMovie
		self.start.grid(row=1, column=1, padx=2, pady=2)
		
		# Create Pause button			
		self.pause = Button(self.master, width=20, padx=3, pady=3)
		self.pause["text"] = "Pause"
		self.pause["command"] = self.pauseMovie
		self.pause.grid(row=1, column=2, padx=2, pady=2)
		
		# Create Teardown button
		self.teardown = Button(self.master, width=20, padx=3, pady=3)
		self.teardown["text"] = "Teardown"
		self.teardown["command"] =  self.exitClient
		self.teardown.grid(row=1, column=3, padx=2, pady=2)
		
		# Tao GUI cho frame loss and speed
		self.startLabel = Label(self.master, text = "Speed: N/A, Loss: 0%, Jitter: 0ms", font = ("Arial", 10, "bold"), fg = "blue")
		self.startLabel.grid(row = 2, column=0, columnspan=4, sticky=W+E+N+S, padx=5, pady=5)
  
		# Create a label to display the movie
		self.label = Label(self.master, bg="black") 
		self.label.grid(row=0, column=0, columnspan=4, sticky=W+E+N+S, padx=5, pady=5) 
		
		self.master.grid_rowconfigure(0, weight=1) 
    
		for i in range(4):
			self.master.grid_columnconfigure(i, weight=1)
		
		self.master.geometry("800x600")
	
 
	def setupMovie(self):
		"""Setup button handler."""
		if self.state == self.INIT:
			# self.openRtpPort()
			self.sendRtspRequest(self.SETUP)
	
	def exitClient(self):
		"""Teardown button handler."""
		self.sendRtspRequest(self.TEARDOWN)		
		self.master.destroy()
		os.remove(CACHE_FILE_NAME + str(self.sessionId) + CACHE_FILE_EXT)

	def playMovie(self):
		"""Play button handler."""
		if self.state == self.READY:
			self.startTime = time.time()
			self.totalByte = 0
		
			# Da co the chay buffer 
			# Xu ly truong hop khi buffer ma server da ngat ket noi
			if self.frameQueue.__len__() < self.START_THRESHOLD and not self.isServerDown:
				self.bufferingStartTime = time.time()
				self.isBuffering = True	
			else :
				self.isBuffering = False
    
			self.sendRtspRequest(self.PLAY)
			self.playBuffer()
	
	def listenRtp(self): 
			"""Listen for RTP packets."""
			while True:	
				# Handle buffer overflow
				if len(self.frameQueue) > self.CACHE_SIZE:
					if not self.isAutoPaused and self.state != self.INIT and self.teardownAcked == 0:
						self.isAutoPaused = True					
						self.sendRtspRequest(self.PAUSE)
					if self.teardownAcked == 1:
						break
				try:
					data = self.rtpSocket.recv(20480)
					if data:	
						rtpPacket = RtpPacket()
						rtpPacket.decode(data)
					
						currSeqNum = rtpPacket.seqNum()
						payload = rtpPacket.getPayload()
						
						if self.lastSeqNum != 0 and currSeqNum > self.lastSeqNum + 1:
							lostCount = currSeqNum - self.lastSeqNum - 1
							self.intervalLostFrames += lostCount
							# Clear buffer cu vi frame bi dut quang
							self.frameBuffer = b"" 
						
						# Neu nhan duoc frame moi (Sequence tang len)
						if currSeqNum > self.lastSeqNum:
							self.intervalReceivedFrames += 1
							self.lastSeqNum = currSeqNum
						
						# Gop manh frame (Fragmentation handling)
						if currSeqNum == self.lastSeqNum: 
							self.frameBuffer += payload
							self.totalByte += len(data) 
						
						# Den cuoi frame (Marker bit = 1)
						if rtpPacket.getMarker() == 1:
							if len(self.frameBuffer) >= 4:
								try:
									# Su dung 4 byte dau de lay kich thuoc frame
									expected_frame_size = struct.unpack("!I", self.frameBuffer[:4])[0]
									actual_received_size = len(self.frameBuffer) - 4
									
									image_data = self.frameBuffer[4:]
									
									if actual_received_size == expected_frame_size and actual_received_size > 0: 
										self.frameQueue.append(image_data)
									else:
										self.intervalLostFrames += 1										
										if self.intervalReceivedFrames > 0:
											self.intervalReceivedFrames -= 1
								except Exception as err:
									print(f"Error decoding frame: {err}")
							
							self.frameNbr += 1 
							self.frameBuffer = b""

						curTime = time.time()
						# Thoi gian thuc nhan goi RTP
						currRecvTime = int(curTime * 1000)
						# Thoi gian ly thuyet tren goi RTP
						currRTPTime = rtpPacket.timestamp()
						if self.prevRtpTime != 0 and self.prevRecvTime != 0:
							diffRecv = currRecvTime - self.prevRecvTime
							diffRtp = currRTPTime - self.prevRtpTime
							diff = diffRecv - diffRtp
							# cong thuc tinh jitter RFC 3550
							self.currJitter += (abs(diff) - self.currJitter) / 16
						self.prevRecvTime = currRecvTime
						self.prevRtpTime = currRTPTime
						
						# Gui du lieu flow control den sever moi 1s
						if (curTime - self.startTime >= 1.0):
							speed = (self.totalByte * 8) / (1024 * 1024 * (curTime - self.startTime))
							
							lossRate = 0.0
							totalExpectedFrames = self.intervalReceivedFrames + self.intervalLostFrames
							
							if totalExpectedFrames > 0:
								lossRate = (self.intervalLostFrames / totalExpectedFrames) * 100.0
							
							self.startLabel.config(text = "Speed: %.2f Mbps, Loss: %.2f%%, Jitter: %.2f ms" %(speed, lossRate, self.currJitter))
							self.sendRtspRequest(self.SENDSPEED)
							
							# Reset counters
							self.startTime = curTime
							self.totalByte = 0
							self.intervalReceivedFrames = 0
							self.intervalLostFrames = 0
				except Exception as e:
					if self.playEvent.isSet(): 
						break
					if self.teardownAcked == 1:
						self.rtpSocket.shutdown(socket.SHUT_RDWR)
						self.rtpSocket.close()
						break
	
	# isBuffering = TRUE thi khong chay ma doi den nguong buffer
	# isAutoPaused = TRUE thi da tu dong pause do tran buffer
	def playBuffer(self):
		# Luc Pause thi khong chay
		if self.requestSent == self.PAUSE and not self.isAutoPaused:
			return	
		if self.requestSent == self.TEARDOWN:
			return
		# Tu dong play khi buffer du
		if self.isAutoPaused and len(self.frameQueue) < self.START_THRESHOLD:
			self.sendRtspRequest(self.PLAY)
			self.isAutoPaused = False
		# Xu ly khi dang buffering
		if self.isBuffering:
			if not self.isAutoPaused:
				self.show_overlay(self.icon_loading_img)
				self.show_overlay("loading")
				self.spinner_angle = (self.spinner_angle + 30) % 360
			curTime = time.time()
			elapsed = curTime - self.bufferingStartTime
			# self.bufferingStartTime = curTime
			if len(self.frameQueue) >= self.START_THRESHOLD:
				self.isBuffering = False
			# Truong hop timeout
			elif elapsed > self.BUFFERING_TIMEOUT and len(self.frameQueue) > 0:
				# Bat co len de chay het buffer con lai
				self.isBuffering = False
			else:
				# Dung de quy co dinh 30 fps
				self.master.after(17, self.playBuffer)
				return
		# Chieu hinh anh
		if len(self.frameQueue) > 0:
			frame_path = self.frameQueue.popleft()
			self.updateMovie(frame_path)
			# print("Buffer Size:", len(self.frameQueue))
			curSizeBuffer = len(self.frameQueue)
			# fps = 30
			delay = 17
			# Xu ly delay dua theo kich thuoc buffer
			if curSizeBuffer <= self.PANIC_THRESHOLD:
				delay = 100
				self.bufferingStartTime = time.time()
			self.master.after(delay, self.playBuffer)
		else:
			# Can buffer, bat co de nap them
			self.isBuffering = True
			self.master.after(17, self.playBuffer)
				
	def writeFrame(self, data):
		"""Write the received frame to a temp image file. Return the image file."""
		cachename = CACHE_FILE_NAME + str(self.sessionId) + "_" + str(self.frameNbr) + CACHE_FILE_EXT
		
		with open(cachename, "wb") as file:
			file.write(data)
		
		return cachename
	
	def updateMovie(self, image_data):
		"""Update the image file as video frame in the GUI."""
		try:
			image_stream = io.BytesIO(image_data)
			image = Image.open(image_stream)
			
			master_w = self.master.winfo_width()
			master_h = self.master.winfo_height()
			target_w = master_w - 10 
			target_h = master_h - 100 
			if target_w < 10: target_w = 640
			if target_h < 10: target_h = 480
			img_w, img_h = image.size
			scale = min(target_w / img_w, target_h / img_h)
			new_w = int(img_w * scale)
			new_h = int(img_h * scale)
			
			image = image.resize((new_w, new_h), Image.Resampling.LANCZOS)
			
			final_image = Image.new("RGBA", (target_w, target_h), (0, 0, 0, 255))
			
			pos_x = (target_w - new_w) // 2
			pos_y = (target_h - new_h) // 2
			final_image.paste(image, (pos_x, pos_y))

			self.current_frame = final_image
			photo = ImageTk.PhotoImage(final_image)
			
			self.label.configure(image = photo) 
			self.label.image = photo
			
		except Exception as e:
			print(f"Error updating movie: {e}")
	
	def pauseMovie(self):
		"""Pause button handler."""
		if self.state == self.PLAYING:
			self.sendRtspRequest(self.PAUSE)
			# Pause do client, khong phai do tran buffer
			self.isAutoPaused = False
   
			self.show_overlay("pause")
			return
		# Tu dong gui lenh pause do tran buffer
		if self.isAutoPaused:
			self.sendRtspRequest(self.PAUSE)
			# Reset lai co
			self.isAutoPaused = False
			return
		# if self.requestSent == self.PAUSE:
			
	def connectToServer(self):
		"""Connect to the Server. Start a new RTSP/TCP session."""
		self.rtspSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		try:
			self.rtspSocket.connect((self.serverAddr, self.serverPort))
		except:
			tkMessageBox.showwarning('Connection Failed', 'Connection to \'%s\' failed.' %self.serverAddr)
	
	# Lam
	def sendRtspRequest(self, requestCode):
		request = ""
		if requestCode == self.SETUP and self.state == self.INIT:
			threading.Thread(target=self.recvRtspReply).start()
			self.rtspSeq += 1	
			request += "SETUP " + str(self.fileName) + " RTSP/1.0\n"
			request += "CSeq: " + str(self.rtspSeq) + "\n"
			request += "Transport: RTP/UDP; client_port= " + str(self.rtpPort) + "\n"
			self.requestSent = self.SETUP
			# self.isAutoPaused = 
   
		elif requestCode == self.PLAY and self.state == self.READY:
			self.rtspSeq += 1
			request += "PLAY " + str(self.fileName) + " RTSP/1.0\n" 
			request += "CSeq: " + str(self.rtspSeq) + "\n"
			request += "Session: " + str(self.sessionId) + "\n"
			self.requestSent = self.PLAY
	
		elif requestCode == self.PAUSE:
			self.rtspSeq += 1
			request += "PAUSE " + str(self.fileName) + " RTSP/1.0\n" 
			request += "CSeq: " + str(self.rtspSeq) + "\n"
			request += "Session: " + str(self.sessionId) + "\n"
			self.requestSent = self.PAUSE
			
		elif requestCode == self.TEARDOWN and not self.state == self.INIT:
			self.rtspSeq += 1
			request += "TEARDOWN " + str(self.fileName) + " RTSP/1.0\n" 
			request += "CSeq: " + str(self.rtspSeq) + "\n"
			request += "Session: " + str(self.sessionId) + "\n"
			self.requestSent = self.TEARDOWN
		elif requestCode == self.SENDSPEED and self.state == self.PLAYING:
			lossRate = 0.0
			total = self.intervalReceivedFrames + self.intervalLostFrames
			if total > 0:
				lossRate = (self.intervalLostFrames / total) * 100.0
			
			self.rtspSeq += 1
			request += "SENDSPEED " + str(lossRate) + " RTSP/1.0\n"
			request += "CSeq: " + str(self.rtspSeq) + "\n"
			request += "Session: " + str(self.sessionId) + "\n"

		else:
			return
		try:
			self.rtspSocket.send(request.encode())
		# khong cho client gui neu server da ngung
		except Exception as e:
			print(f"⚠️ Warning: Failed to send RTSP request (Server down?): {e}")
			if requestCode == self.PAUSE:
				self.state = self.READY 
			
			elif requestCode == self.PLAY:
				self.state = self.PLAYING 
			
			elif requestCode == self.TEARDOWN:
				self.state = self.INIT
				self.teardownAcked = 1
				self.master.destroy()
			self.isServerDown = True
	def recvRtspReply(self):
		"""Receive RTSP reply from the server."""
		while True:
			reply = self.rtspSocket.recv(1024)
			
			if reply: 
				self.parseRtspReply(reply.decode("utf-8"))
			else :
				break
			# Close the RTSP socket upon requesting Teardown
			if self.requestSent == self.TEARDOWN:
				self.rtspSocket.shutdown(socket.SHUT_RDWR)
				self.rtspSocket.close()
				self.state = self.INIT
				break
	
	def parseRtspReply(self, data):
		"""Parse the RTSP reply from the server."""
		try:
			lines = data.split('\n')
			seqNum = int(lines[1].split(' ')[1])
			
			# Process only if the server reply's sequence number is the same as the request's
			if seqNum == self.rtspSeq:
				session = int(lines[2].split(' ')[1])
				# New RTSP session ID
				if self.sessionId == 0:
					self.sessionId = session
				
				# Process only if the session ID is the same
				if self.sessionId == session:
					if int(lines[0].split(' ')[1]) == 200: 
						if self.requestSent == self.SETUP:
							#-------------
							# TO COMPLETE
							#-------------
							# Update RTSP state.
							self.state = self.READY
							
							# Open RTP port.
							self.openRtpPort()
							self.isBuffering = True 
							self.frameQueue.clear()

							threading.Thread(target=self.listenRtp).start()
							self.playEvent = threading.Event()
							self.playEvent.clear()	
						elif self.requestSent == self.PLAY:
							self.state = self.PLAYING
						elif self.requestSent == self.PAUSE:
							self.state = self.READY
							
							# The play thread exits. A new thread is created on resume.
							# self.playEvent.set()
						elif self.requestSent == self.TEARDOWN:
							self.state = self.INIT
							
							# Flag the teardownAcked to close the socket.
							self.teardownAcked = 1 
		except Exception as e:
			print(f"⚠️ Warning: Failed to parse RTSP reply: {e}")
			# if (self.requestSent == self.PAUSE) :
			# 	self.isAutoPaused = True
			# 	self.state = self.READY
			# elif (self.requestSent == self.PLAY) :
			# 	self.isAutoPaused = False
			# 	self.state = self.PLAYING
			# 	self.isBuffering = False
	
	def get_overlay_image(self, overlay_type="loading"):
		if self.current_frame:
			w, h = self.current_frame.size
		else:
			w, h = 380, 280
		overlay = Image.new('RGBA', (w, h), (0, 0, 0, 100))
		draw = ImageDraw.Draw(overlay)
		cx, cy = w // 2, h // 2 

		if overlay_type == "pause":
			bar_w, bar_h = 20, 60 
			gap = 15
			draw.rectangle([cx - gap - bar_w, cy - bar_h//2, cx - gap, cy + bar_h//2], fill="white")
			draw.rectangle([cx + gap, cy - bar_h//2, cx + gap + bar_w, cy + bar_h//2], fill="white")
			
		elif overlay_type == "loading":
			rotated_spinner = self.base_spinner.rotate(self.spinner_angle)
			
			sw, sh = rotated_spinner.size
			overlay.paste(rotated_spinner, (cx - sw//2, cy - sh//2), rotated_spinner)
			
			text = "Buffering..."
			draw.text((cx - 35, cy + 35), text, fill="white")
			
		return overlay

	def show_overlay(self, type="loading"):
		icon_image = self.get_overlay_image(type)

		if self.current_frame:
			base_image = self.current_frame.copy()
			base_image.alpha_composite(icon_image)
			
			photo = ImageTk.PhotoImage(base_image)
			self.label.configure(image=photo, height=288)
			self.label.image = photo
		else:
			bg = Image.new("RGB", icon_image.size, (0, 0, 0))
			bg.paste(icon_image, (0, 0), icon_image)
			photo = ImageTk.PhotoImage(bg)
			self.label.configure(image=photo, height=288)
			self.label.image = photo
	
	# Lam
	def openRtpPort(self):
		self.rtpSocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM) # UDP
		self.rtpSocket.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 10 * 1024 * 1024) #Buffer
		# Set the timeout value of the socket to 0.5sec
		self.rtpSocket.settimeout(0.5)
		
		try:
			self.rtpSocket.bind(("", self.rtpPort))
		except:
			tkMessageBox.showwarning('Unable to Bind', 'Unable to bind PORT=%d' %self.rtpPort)

	def handler(self):
		"""Handler on explicitly closing the GUI window."""
		self.pauseMovie()
		if tkMessageBox.askokcancel("Quit?", "Are you sure you want to quit?"):
			self.exitClient()
		else: # When the user presses cancel, resume playing.
			self.playMovie()
#hello