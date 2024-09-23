import cv2 
from ultralytics import YOLO
import threading
import queue
import time
import random
import numpy as np

class VideoCapture:
    def __init__(self, name):
        self.cap = cv2.VideoCapture(name)
        self.q = queue.Queue()
        t = threading.Thread(target=self._reader)
        t.daemon = True
        t.start()

    def _reader(self):
        while True:
            ret, frame = self.cap.read()
            if not ret:
                break
            if not self.q.empty():
                try:
                    self.q.get_nowait()  # 删除上一个帧（未处理的）
                except queue.Empty:
                    pass
            self.q.put(frame)

    def read(self):
        return self.q.get()

def create_kalman_filter():
    """初始化卡尔曼滤波器"""
    kf = cv2.KalmanFilter(4, 2)
    kf.measurementMatrix = np.array([[1, 0, 0, 0], [0, 1, 0, 0]], np.float32)
    kf.transitionMatrix = np.array([[1, 0, 1, 0], [0, 1, 0, 1], [0, 0, 1, 0], [0, 0, 0, 1]], np.float32)
    kf.processNoiseCov = np.eye(4, dtype=np.float32) * 0.03
    return kf

def assign_color():
    """随机分配颜色给每只老鼠"""
    return (random.randint(0, 255), random.randint(0, 255), random.randint(0, 255))

def detect_rats(model_path, video_source):
    model = YOLO(model_path)
    cap = VideoCapture(video_source)
    rat_tracks = {}  # 存储每只老鼠的ID及其轨迹和颜色
    rat_outside = False
    video_writer = None  # 初始化为空，不立即创建视频保存器
    saving_video = False  # 控制是否正在保存视频
    last_seen_time = time.time()
    max_distance = 50  # 两帧之间最大距离，超过这个距离就认为是不同的老鼠
    countdown = 5  # 倒计时5秒

    def process_frame():
        nonlocal rat_outside, video_writer, saving_video, rat_tracks, last_seen_time, countdown
        while True:
            frame = cap.read()
            if frame is None:
                print("无法读取帧，视频结束或出现错误")
                break

            results = model(frame, conf=0.3, iou=0.4)  # 调整置信度阈值和NMS阈值
            current_positions = []

            for result in results:
                for box in result.boxes:
                    x1, y1, x2, y2 = box.xyxy[0]
                    confidence = box.conf[0]
                    cls = int(box.cls[0])

                    if cls == 0 and confidence > 0.3:  # 检测到老鼠
                        center_x = int((x1 + x2) / 2)
                        center_y = int((y1 + y2) / 2)
                        current_positions.append((center_x, center_y))
                        cv2.rectangle(frame, (int(x1), int(y1)), (int(x2), int(y2)), (0, 255, 0), 2)
                        cv2.putText(frame, f"Rat: {confidence:.2f}", (int(x1), int(y1) - 10),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

            # 更新每只老鼠的轨迹
            for position in current_positions:
                assigned = False
                # 遍历已有的老鼠轨迹，找到最近的轨迹并更新
                for rat_id, track_data in rat_tracks.items():
                    track_positions = track_data["positions"]
                    kalman_filter = track_data["kf"]
                    predicted_position = kalman_filter.predict()[:2]
                    distance = np.linalg.norm(predicted_position - np.array([position[0], position[1]]))

                    if distance < max_distance:  # 如果距离小于设定的阈值，认为是同一只老鼠
                        track_positions.append(position)
                        # 更新卡尔曼滤波器
                        measurement = np.array([[np.float32(position[0])], [np.float32(position[1])]])
                        kalman_filter.correct(measurement)
                        assigned = True
                        break

                if not assigned:
                    # 如果没有找到合适的轨迹，创建新的老鼠轨迹
                    rat_id = len(rat_tracks) + 1
                    rat_tracks[rat_id] = {"positions": [position], "color": assign_color(), "kf": create_kalman_filter()}
                    # 初始化卡尔曼滤波器的初始位置
                    initial_measurement = np.array([[np.float32(position[0])], [np.float32(position[1])]])
                    rat_tracks[rat_id]["kf"].correct(initial_measurement)

            # 如果当前没有保存视频，则开始保存
            if current_positions and not saving_video:
                # 获取当前时间并生成视频文件名
                current_time = time.strftime("%Y%m%d%H%M%S")
                video_filename = f"{current_time}.mp4"
                print(f"开始保存视频: {video_filename}")

                # 初始化视频保存器
                fourcc = cv2.VideoWriter_fourcc(*'mp4v')
                video_writer = cv2.VideoWriter(video_filename, fourcc, 20.0,
                                               (frame.shape[1], frame.shape[0]))
                saving_video = True  # 标记为正在保存视频
                last_seen_time = time.time()  # 重置最后看到老鼠的时间
                countdown = 5  # 重置倒计时

            # 如果没有检测到老鼠，启动倒计时
            if not current_positions:
                if countdown > 0:
                    countdown -= 1/60  # 每帧倒计时 1/60 秒
                elif countdown <= 0 and saving_video:  # 倒计时结束后保存视频
                    print("倒计时结束，保存视频")
                    video_writer.release()
                    saving_video = False
                    rat_tracks.clear()  # 清空轨迹

            # 绘制每只老鼠的轨迹并保存到视频
            for rat_id, track_data in rat_tracks.items():
                track_positions = track_data["positions"]
                color = track_data["color"]
                for i in range(1, len(track_positions)):
                    cv2.line(frame, track_positions[i - 1], track_positions[i], color, 2)

            if saving_video and video_writer is not None:
                video_writer.write(frame)

            # 显示实时检测画面
            cv2.imshow('Rat Detection', frame)

            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

            time.sleep(1/60)  # 增加帧率以匹配60帧每秒

        cv2.destroyAllWindows()
        if video_writer is not None:
            video_writer.release()  # 确保程序结束时释放资源

    def log_results():
        with open("detection_log.txt", "a") as log_file:
            while True:
                frame = cap.read()
                if frame is None:
                    break

                results = model(frame, conf=0.3, iou=0.4)  # 调整置信度阈值和NMS阈值
                for result in results:
                    for box in result.boxes:
                        x1, y1, x2, y2 = box.xyxy[0]
                        confidence = box.conf[0]
                        cls = int(box.cls[0])

                        if cls == 0 and confidence > 0.3:  # 调整置信度阈值
                            log_file.write(f"Rat detected with confidence {confidence:.2f} at [{x1}, {y1}, {x2}, {y2}]\n")

                time.sleep(1/60)  # 增加帧率以匹配60帧每秒

    threading.Thread(target=process_frame).start()
    threading.Thread(target=log_results).start()

model_path = r"best.pt"
video_source = "rtsp://admin:tfe123456@10.168.1.66/media/video1"
detect_rats(model_path, video_source)
