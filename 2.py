import gpiod
import time
import os
import subprocess

# 配置 GPIO
chip_name = "gpiochip6"
line_offset = 0
debounce_time = 0.05

# 初始化 GPIO 芯片和线
chip = gpiod.Chip(chip_name)
line = chip.get_line(line_offset)
line.request(consumer="gpio_control", type=gpiod.LINE_REQ_DIR_IN)

# 记录低电平检测次数
low_count = 0

def send_stop_signal():
    with open("stop_signal.txt", "w") as f:
        f.write("stop")
    print("停止信号已发送")

try:
    while True:
        # 读取 GPIO 线的电平
        value = line.get_value()
        
        if value == 0:  # 检测到低电平
            low_count += 1
            print(f"检测到低电平次数: {low_count}")
            time.sleep(debounce_time) 

            if low_count == 1:
                subprocess.Popen(["python3", "1.py"])
                print("1.py 已启动")
                # 添加延迟，确保按钮释放后再继续检测
                time.sleep(1)
            elif low_count == 2:
                send_stop_signal()
                break

        time.sleep(0.1)  # 稍作延迟

except KeyboardInterrupt:
    print("程序被手动中断")

finally:
    line.release()
    chip.close()
