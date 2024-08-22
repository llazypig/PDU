import cv2
import os
import gpiod
import time
from datetime import datetime

# 设置输出目录和RTSP URL
merged_output_dir = '/home/monster/Desktop/share/DCIM/hcz/'
rtmp_url = 'rtsp://admin:tfe123456@10.168.1.66/media/video1/multicast'

# 创建输出目录
if not os.path.exists(merged_output_dir):
    os.makedirs(merged_output_dir)

# 打开RTSP流
cap = cv2.VideoCapture(rtmp_url)

# 获取视频的宽度和高度
frame_width = int(cap.get(3))
frame_height = int(cap.get(4))

# 定义编解码器
fourcc = cv2.VideoWriter_fourcc(*'mp4v') 
out = None

# 读取第一帧
ret, prev_frame = cap.read()
prev_gray = cv2.cvtColor(prev_frame, cv2.COLOR_BGR2GRAY)

recording = False

# GPIO配置
chip_name = "gpiochip6"
line_offset = 1  # GPIO6_A1 (IO2)
debounce_time = 0.05  # 去抖动时间（秒）
lockout_time = 1  # 状态锁定时间（秒）

chip = gpiod.Chip(chip_name)
line = chip.get_line(line_offset)
line.request(consumer="record_toggle", type=gpiod.LINE_REQ_DIR_IN)

last_toggle_time = 0

while cap.isOpened():
    ret, frame = cap.read()
    if not ret:
        break

    # 转换为灰度图像
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    # 计算当前帧与前一帧的差异
    diff = cv2.absdiff(prev_gray, gray)
    _, thresh = cv2.threshold(diff, 30, 255, cv2.THRESH_BINARY)

    # 计算变化的像素数量
    change = cv2.countNonZero(thresh)

    # 如果变化超过一定阈值，并且处于录制状态，则保存当前帧
    if change > 5000 and recording:
        out.write(frame)

    # 更新前一帧
    prev_gray = gray

    # 显示当前帧
    cv2.imshow('frame', frame)

    # 检测GPIO低电平
    if line.get_value() == 0 and (time.time() - last_toggle_time) > lockout_time:
        last_toggle_time = time.time()
        if not recording:
            current_time_filename = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            video_path = os.path.join(merged_output_dir, f"{current_time_filename}.mp4")
            out = cv2.VideoWriter(video_path, fourcc, 20.0, (frame_width, frame_height))
            recording = True
            print("开始录制")
        else:
            recording = False
            out.release()
            out = None
            print("停止录制")

    # 按'q'键退出
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

# 释放资源
cap.release()
if out:
    out.release()
cv2.destroyAllWindows()
