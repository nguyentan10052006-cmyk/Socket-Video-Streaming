import cv2
import os

def convert_mp4_to_lab_mjpeg(input_video, output_file):
    # Kiểm tra file đầu vào
    if not os.path.exists(input_video):
        print(f"Lỗi: Không tìm thấy file '{input_video}'")
        return

    print(f"Đang đọc video: {input_video} ...")
    
    # Mở video bằng OpenCV
    cap = cv2.VideoCapture(input_video)
    
    if not cap.isOpened():
        print("Không thể mở file video. Hãy chắc chắn bạn đã cài 'opencv-python'.")
        return

    # Lấy thông số video
    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    
    print(f"Thông tin: {width}x{height} | {fps} FPS | Tổng {total_frames} frames")
    print("Đang chuyển đổi... (Vui lòng đợi)")

    count = 0
    with open(output_file, 'wb') as out:
        while True:
            ret, frame = cap.read()
            if not ret:
                break # Hết video
            
            # (Tùy chọn) Resize nếu video quá to (ví dụ 4K xuống HD)
            # frame = cv2.resize(frame, (1280, 720))

            # 1. Nén frame thành JPEG
            # quality=50 để giảm dung lượng, giúp truyền UDP mượt hơn
            encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), 50] 
            result, encoded_img = cv2.imencode('.jpg', frame, encode_param)
            
            if not result:
                continue
                
            data = encoded_img.tobytes()
            size = len(data)
            
            # 2. Tạo Header 6 số (QUAN TRỌNG)
            # Ví dụ: ảnh 45KB -> "045000"
            header = "{:06}".format(size)
            
            # 3. Ghi vào file
            out.write(header.encode())
            out.write(data)
            
            count += 1
            if count % 100 == 0:
                print(f"   Đã xử lý {count}/{total_frames} frames...")

    cap.release()
    print("-" * 30)
    print(f"XONG! Đã tạo file: {output_file}")
    print(f"Tổng số frame: {count}")
    print("Bạn có thể dùng file này chạy Server ngay lập tức.")

# --- CẤU HÌNH ---
# Đổi tên file video của bạn ở đây
INPUT_VIDEO = "Download.mp4"  
OUTPUT_FILE = "video_converted.Mjpeg"

if __name__ == "__main__":
    convert_mp4_to_lab_mjpeg(INPUT_VIDEO, OUTPUT_FILE)