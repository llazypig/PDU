import cv2
import os

# 设置输出目录和RTSP URL
merged_output_dir = '/home/monster/Desktop/share/DCIM/hc/'
rtmp_url = 'rtsp://admin:tfe123456@10.168.1.66/media/video1/multicast'

# 创建输出目录（如果不存在）
if not os.path.exists(merged_output_dir):
    os.makedirs(merged_output_dir)

# 打开RTSP流
cap = cv2.VideoCapture(rtmp_url)

# 获取视频的宽度和高度
frame_width = int(cap.get(3))
frame_height = int(cap.get(4))

# 定义编解码器并创建VideoWriter对象
fourcc = cv2.VideoWriter_fourcc(*'XVID')
out = cv2.VideoWriter(os.path.join(merged_output_dir, 'output.avi'), fourcc, 20.0, (frame_width, frame_height))

# 读取第一帧
ret, prev_frame = cap.read()
prev_gray = cv2.cvtColor(prev_frame, cv2.COLOR_BGR2GRAY)

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
    if change > 5000:
        out.write(frame)

    # 更新前一帧
    prev_gray = gray

    # 显示当前帧
    cv2.imshow('frame', frame)

    # 按'r'键启动录制
    if cv2.waitKey(1) & 0xFF == ord('r'):
        out.write(frame)

    # 按'q'键退出
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

# 释放资源
cap.release()
out.release()
cv2.destroyAllWindows()
