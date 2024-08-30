import subprocess
import sys

# 定义输入和输出文件路径
video_with_audio = "/home/monster/Desktop/share/DCIM/sp/aaf9b78f0914/rtspurl1/2024-08-30_11-08-41_camera1.mp4"
video_without_audio = "/home/monster/Desktop/share/DCIM/sp/aaf9b78f0914/rtspurl2/2024-08-30_11-08-41_camera2.mp4"
output_video = "/home/monster/Desktop/share/DCIM/sp/aaf9b78f0914/rtspurl_combined.mp4"

# 构建 ffmpeg 命令
ffmpeg_command = [
    "ffmpeg",
    "-i", video_with_audio,
    "-i", video_without_audio,
    "-filter_complex", "[0:v][1:v]hstack=inputs=2[v];[0:a]anull[a]",
    "-map", "[v]",
    "-map", "[a]",
    output_video
]

# 执行命令
subprocess.run(ffmpeg_command)

# 合成完成后退出
sys.exit()
