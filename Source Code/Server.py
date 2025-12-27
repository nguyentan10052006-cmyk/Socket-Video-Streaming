import sys, socket, os

from ServerWorker import ServerWorker

class Server:   
    
    def main(self):
        try:
            SERVER_PORT = int(sys.argv[1])
        except:
            print("[Usage: Server.py Server_port]\n")
            return # Nên return để thoát hàm nếu lỗi tham số

        rtspSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        rtspSocket.bind(('', SERVER_PORT))
        rtspSocket.listen(5)        

        rtspSocket.settimeout(1.0) 
        # print(f"Server đang chạy trên port {SERVER_PORT}. Nhấn Ctrl+C để dừng.")

        try:
            while True:
                try:
                    clientInfo = {}
                    clientInfo['rtspSocket'] = rtspSocket.accept() 
                    ServerWorker(clientInfo).run()      
                
                except socket.timeout:
                    continue 

        except KeyboardInterrupt:
            print("\nhehe. Đã nhận lệnh dừng server!")
        
        finally:
            rtspSocket.close()
            print("Server socket đã được đóng an toàn.")

if __name__ == "__main__":
    (Server()).main()