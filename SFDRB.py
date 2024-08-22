import cv2
import os
import gpiod
import time
from datetime import datetime
from ffpyplayer.player import MediaPlayer

# 设置输出目录和RTSP URL
merged_output_dir = '/home/monster/Desktop/share/DCIM/hc/'
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
fourcc = cv2.VideoWriter_fourcc(*'XVID')
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

def merge_audio_video(video_file, audio_file, output_dir):
    current_time_filename = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    output_file = os.path.join(output_dir, f"{current_time_filename}.mp4")
    video_clip = VideoFileClip(video_file)
    audio_clip = AudioFileClip(audio_file)
    final_clip = video_clip.set_audio(audio_clip)
    final_clip.write_videofile(output_file, codec='libx264', audio_codec='aac')
    print(f"合并后的文件已保存到: {output_file}")

def get_audio_frame(player):
    audio_frame, val = player.get_frame()
    return audio_frame, val

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

    # 如果变化超过一定阈值，则认为有变化
    if change > 5000 and recording:
        out.write(frame)

    # 更新前一帧
    prev_gray = gray

    # 显示当前帧
    cv2.imshow('frame', frame)

    # 检测GPIO高电平
    if line.get_value() == 1 and (time.time() - last_toggle_time) > lockout_time:
        last_toggle_time = time.time()
        if not recording:
            current_time_filename = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            video_path = os.path.join(merged_output_dir, f"{current_time_filename}.avi")
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
