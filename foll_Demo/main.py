import cv2
import time
from rknnpool import rknnPoolExecutor
# 图像处理函数，实际应用过程中需要自行修改
from func import myFunc

# 确保CLASSES在main.py中可用，或者从func.py导入
from func import CLASSES

# 使用 GStreamer 硬解码管道来打开 RTSP 流
# 定义RTSP参数变量
image_width = 1920
image_height = 1080
rtsp_latency = 10  # 延迟（毫秒）
uri = "rtsp://admin:tfe12345@10.168.1.65/media/video1"

gst_str = (
    f"rtspsrc location={uri} latency={rtsp_latency} ! "
      "rtph264depay ! queue max-size-buffers=1 leaky=downstream ! "
      "h264parse ! queue max-size-buffers=1 leaky=downstream ! "
      "mppvideodec ! queue max-size-buffers=1 leaky=downstream ! "
      "videoconvert ! video/x-raw,format=BGR ! "
      "appsink drop=1 max-buffers=1 sync=false"
)

print(f'use gstream {gst_str}')  # 打印管道信息用于调试
cap = cv2.VideoCapture(gst_str, cv2.CAP_GSTREAMER)

# cap = cv2.VideoCapture('rtsp://admin:tfe123456@10.168.1.66/media/video1')

# 检查是否成功打开视频流
if not cap.isOpened():
    print("无法打开 RTSP 视频流")
    exit()

# 获取视频的帧率、宽度和高度
fps = cap.get(cv2.CAP_PROP_FPS)
width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

# 定义视频编码器并创建 VideoWriter 对象
fourcc = cv2.VideoWriter_fourcc(*'mp4v') # 或者使用 'XVID'  
out = cv2.VideoWriter('output.mp4', fourcc, fps, (width, height))

modelPath = "/media/monster/PU/dynamic_detection-mj-dt1.8/rknn3588-yolov8/rknnModel/fall.rknn"
# 线程数, 增大可提高帧率
TPEs = 3
# 初始化rknn池
pool = rknnPoolExecutor(
    rknnModel=modelPath,
    TPEs=TPEs,
    func=myFunc)

# 初始化异步所需要的帧
if (cap.isOpened()):
    for i in range(TPEs + 1):
        ret, frame = cap.read()
        if not ret:
            cap.release()
            del pool
            exit(-1)
        pool.put(frame)

frames, loopTime, initTime = 0, time.time(), time.time()

# 新增变量用于控制录制
is_recording = False
last_fire_detection_time = None

while (cap.isOpened()):
    frames += 1
    ret, frame = cap.read()
    if not ret:
        break
    
    pool.put(frame)
    processed_frame, flag = pool.get()

    if flag == False:
        break

    # 解包myFunc的返回值
    display_frame, boxes, classes, scores = processed_frame

    # 检查是否检测到'fire'
    fire_detected_in_current_frame = False
    if classes is not None:
        for cl in classes:
            if cl == CLASSES.index("other"): # 假设CLASSES中'fire'的索引是0
                fire_detected_in_current_frame = True
                break

    current_time = time.time()

    if fire_detected_in_current_frame:
        last_fire_detection_time = current_time
        if not is_recording:
            print("检测到'fire'，开始录制视频。")
            is_recording = True
    elif is_recording and last_fire_detection_time is not None and (current_time - last_fire_detection_time) >= 10:
        print("3秒内未检测到'fire'，停止录制视频。")
        is_recording = False
        last_fire_detection_time = None # 重置计时器

    if is_recording:
        out.write(display_frame) # 写入帧到视频文件

    cv2.imshow('yolov8', display_frame)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break
    if frames % 25 == 2:
        print("25帧平均帧率:\t", 25 / (time.time() - loopTime), "帧")
        loopTime = time.time()

print("总平均帧率\t", frames / (time.time() - initTime))
# 释放cap和rknn线程池
cap.release()
out.release() # 释放 VideoWriter 对象
cv2.destroyAllWindows()
pool.release()
