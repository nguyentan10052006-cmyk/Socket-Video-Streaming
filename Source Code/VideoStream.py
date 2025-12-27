class VideoStream:
	def __init__(self, filename):
		self.filename = filename
		try:
			self.file = open(filename, 'rb')
		except:
			raise IOError
		self.frameNum = 0
		self.buffer = b""
		
	def nextFrame(self):

		if self.filename.endswith(".Mjpeg"):
			data = self.file.read(5) # Get the framelength from the first 5 bits
			if data: 
				framelength = int(data)
								
				data = self.file.read(framelength)
				self.frameNum += 1
			return data
		else:
			while True:
				start = self.buffer.find(b"\xff\xd8")
				end = self.buffer.find(b"\xff\xd9")
				if start != -1 and end != -1 and end > start:
					temp_data = self.buffer[start:end + 2]
					self.buffer = self.buffer[end + 2:]
					self.frameNum += 1
					return temp_data
				new_data = self.file.read(8192)
				if not new_data:
					return None
				self.buffer += new_data

		
	def frameNbr(self):
		"""Get frame number."""
		return self.frameNum
	