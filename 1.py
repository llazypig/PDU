import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst, GLib
import threading
import time
import os
import uuid
import logging
from datetime import datetime

# 初始化 GStreamer
Gst.init(None)

# 配置日志记录
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# 定义 RTSP URL
rtsp_url_1 = "rtsp://admin:tfe123456@10.168.1.66/media/video1"
rtsp_url_2 = "rtsp://admin:tfe123456@10.168.1.67/media/video1"

# 获取设备的 MAC 地址并格式化
mac_address = uuid.UUID(int=uuid.getnode()).hex[-12:]
mac_folder = f"/home/monster/Desktop/share/DCIM/sp/{mac_address}"

# 终止信号
terminate_event = threading.Event()

def create_pipeline(rtsp_url, output_path, video_only=False):
    """
    创建一个 GStreamer 管道，用于将 RTSP 流录制到 MP4 文件。
    """
    if video_only:
        # 仅视频管道
        pipeline_str = (
            f"rtspsrc location={rtsp_url} ! rtph264depay ! h264parse ! "
            f"mp4mux name=mux ! filesink location={output_path}"
        )
    else:
        # 视频和音频管道，使用 voaacenc 进行音频编码
        pipeline_str = (
            f"rtspsrc location={rtsp_url} ! rtph264depay ! h264parse ! mux. "
            f"rtspsrc location={rtsp_url} ! decodebin name=d "
            f"d. ! audioconvert ! voaacenc ! aacparse ! mux. "
            f"mp4mux name=mux ! filesink location={output_path}"
        )

    return pipeline_str

def record_stream(rtsp_url, output_path, video_only=False):
    """
    开始录制流的函数。
    """
    pipeline_str = create_pipeline(rtsp_url, output_path, video_only)
    pipeline = Gst.parse_launch(pipeline_str)

    loop = GLib.MainLoop()
    bus = pipeline.get_bus()
    bus.add_signal_watch()

    def on_message(bus, message):
        t = message.type
        if t == Gst.MessageType.EOS:
            logging.info("流结束")
            loop.quit()
        elif t == Gst.MessageType.ERROR:
            err, debug = message.parse_error()
            logging.error(f"错误: {err}, {debug}")
            loop.quit()

    bus.connect("message", on_message)

    try:
        pipeline.set_state(Gst.State.PLAYING)
        logging.info(f"录制开始: {output_path}")

        while not terminate_event.is_set():
            time.sleep(1)

        logging.info("终止管道...")
        pipeline.send_event(Gst.Event.new_eos())  # 发送 EOS 事件以完成文件写入

        loop.run()
    except Exception as e:
        logging.error(f"录制期间出错: {e}")
    finally:
        pipeline.set_state(Gst.State.NULL)

def stop_recording():
    terminate_event.set()
    logging.info("收到停止信号")

if __name__ == '__main__':
    # 根据 MAC 地址创建目录结构
    os.makedirs(mac_folder, exist_ok=True)
    rtspurl1_path = os.path.join(mac_folder, "rtspurl1")
    rtspurl2_path = os.path.join(mac_folder, "rtspurl2")
    os.makedirs(rtspurl1_path, exist_ok=True)
    os.makedirs(rtspurl2_path, exist_ok=True)

    # 获取当前时间并格式化为字符串
    current_time_str = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

    # 定义包含时间戳的输出路径
    output_path_1 = os.path.join(rtspurl1_path, f"{current_time_str}_camera1.mp4")
    output_path_2 = os.path.join(rtspurl2_path, f"{current_time_str}_camera2.mp4")

    # 启动录制线程
    recording_thread_1 = threading.Thread(target=record_stream, args=(rtsp_url_1, output_path_1))
    recording_thread_2 = threading.Thread(target=record_stream, args=(rtsp_url_2, output_path_2, True))

    recording_thread_1.start()
    recording_thread_2.start()

    try:
        while True:
            if os.path.exists("stop_signal.txt"):
                logging.info("检测到停止信号文件，停止录制...")
                stop_recording()
                break
            time.sleep(1)
    except Exception as e:
        logging.error(f"主循环期间出错: {e}")
    finally:
        # 等待线程结束
        recording_thread_1.join()
        recording_thread_2.join()
        logging.info("录制停止。文件保存于:")
        logging.info(output_path_1)
        logging.info(output_path_2)

        # 删除停止信号文件
        if os.path.exists("stop_signal.txt"):
            os.remove("stop_signal.txt")
            logging.info("停止信号文件已删除")
