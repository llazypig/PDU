import gpiod
import time
import subprocess
import os
import signal

# GPIO配置
chip_name = "gpiochip6"
line_offset = 0  # GPIO6_A0 (IO1)
debounce_time = 0.05  # 去抖时间（秒）

# 用于运行 '1.py' 的进程
process = None

def start_script():
    """启动脚本 '1.py'。"""
    global process
    if process is None or process.poll() is not None:  # 检查进程是否未运行
        print("启动 1.py...")
        process = subprocess.Popen(["python3", "/usr/TFE/my_env/hc/1.py"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)

def stop_script():
    """停止脚本 '1.py'。"""
    global process
    if process is not None and process.poll() is None:  # 检查进程是否正在运行
        print("停止 1.py...")
        process.send_signal(signal.SIGTERM)  # 发送SIGTERM信号，平稳终止进程
        process.wait()  # 等待进程终止
        process = None

def monitor_gpio(chip_name, line_offset):
    """监控GPIO信号以控制 '1.py' 的启动和停止。"""
    global process
    chip = gpiod.Chip(chip_name)
    line = chip.get_line(line_offset)
    
    # 将GPIO线路请求为输入
    line.request(consumer="gpio_control", type=gpiod.LINE_REQ_DIR_IN)
    
    last_value = line.get_value()
    print("正在监控GPIO的变化...")
    
    while True:
        value = line.get_value()
        
        if value != last_value:  # 如果值发生变化
            if value == 1:
                start_script()
            else:
                stop_script()
                
            last_value = value
            time.sleep(debounce_time)  # 去抖动延迟

        time.sleep(0.01)  # 轮询延迟以避免高CPU占用

if __name__ == "__main__":
    try:
        monitor_gpio(chip_name, line_offset)
    except KeyboardInterrupt:
        print("用户中断。正在退出...")
        if process is not None:
            stop_script()
