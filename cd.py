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
    kf.measurementNoiseCov = np.eye(2, dtype=np.float32) * 0.1  # 增加测量噪声，减少抖动
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
    max_distance = 100  # 两帧之间最大距离，适当增加阈值
    countdown = 5  # 倒计时5秒
    missed_frames_limit = 10  # 最大丢失帧数

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
            updated_tracks = set()
            for position in current_positions:
                assigned = False
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
                        track_data["missed_frames"] = 0  # 重置丢失帧计数
                        assigned = True
                        updated_tracks.add(rat_id)
                        break

                if not assigned:
                    # 如果没有找到合适的轨迹，创建新的老鼠轨迹
                    rat_id = len(rat_tracks) + 1
                    rat_tracks[rat_id] = {"positions": [position], "color": assign_color(),
                                          "kf": create_kalman_filter(), "missed_frames": 0}
                    # 初始化卡尔曼滤波器的初始位置
                    initial_measurement = np.array([[np.float32(position[0])], [np.float32(position[1])]])
                    rat_tracks[rat_id]["kf"].correct(initial_measurement)
                    updated_tracks.add(rat_id)

            # 增加对未更新轨迹的丢失计数
            for rat_id, track_data in list(rat_tracks.items()):
                if rat_id not in updated_tracks:
                    track_data["missed_frames"] += 1
                    # 超过丢失阈值则删除轨迹
                    if track_data["missed_frames"] > missed_frames_limit:
                        del rat_tracks[rat_id]

            # 如果当前没有保存视频，则开始保存
            if current_positions and not saving_video:
                current_time = time.strftime("%Y%m%d%H%M%S")
                video_filename = f"{current_time}.mp4"
                print(f"开始保存视频: {video_filename}")

                fourcc = cv2.VideoWriter_fourcc(*'mp4v')
                video_writer = cv2.VideoWriter(video_filename, fourcc, 20.0,
                                               (frame.shape[1], frame.shape[0]))
                saving_video = True
                last_seen_time = time.time()
                countdown = 5

            if not current_positions:
                if countdown > 0:
                    countdown -= 1 / 60
                elif countdown <= 0 and saving_video:
                    print("倒计时结束，保存视频")
                    video_writer.release()
                    saving_video = False
                    rat_tracks.clear()

            # 绘制每只老鼠的轨迹并保存到视频
            for rat_id, track_data in rat_tracks.items():
                track_positions = track_data["positions"]
                color = track_data["color"]
                for i in range(1, len(track_positions)):
                    cv2.line(frame, track_positions[i - 1], track_positions[i], color, 2)

            if saving_video and video_writer is not None:
                video_writer.write(frame)

            cv2.imshow('Rat Detection', frame)

            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

            time.sleep(1 / 60)

        cv2.destroyAllWindows()
        if video_writer is not None:
            video_writer.release()

    threading.Thread(target=process_frame).start()

model_path = r"best.pt"
video_source = "rtsp://admin:tfe123456@10.168.1.66/media/video1"
detect_rats(model_path, video_source)
