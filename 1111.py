def process_video(cap, frame_width, frame_height, merged_output_dir, rtmp_url, mac_address, ip_address, record_duration, record_size, frame_threshold):
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = None
    ret, prev_frame = cap.read()

    if not ret:
        logging.error("无法读取视频流的第一帧")
        cap.release()
        sys.exit(1)

    prev_gray = cv2.cvtColor(prev_frame, cv2.COLOR_BGR2GRAY)
    recording = False
    start_time = time.time()
    video_path = None

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            logging.error("无法读取视频流帧。")
            break

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        diff = cv2.absdiff(prev_gray, gray)
        _, thresh = cv2.threshold(diff, 30, 255, cv2.THRESH_BINARY)
        change = cv2.countNonZero(thresh)

        if change > frame_threshold and recording:
            out.write(frame)

        prev_gray = gray

        current_recording = is_recording()
        if current_recording and not recording:
            # 开始录制新文件
            current_time_filename = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            video_path = os.path.join(merged_output_dir, f"{current_time_filename}.mp4")
            out = cv2.VideoWriter(video_path, fourcc, 20.0, (frame_width, frame_height))
            recording = True
            start_time = time.time()
            logging.info(f"开始录制视频：{video_path}")
        elif not current_recording and recording:
            recording = False
            if out:
                logging.info("停止录制，正在保存文件...")
                out.release()
                out = None
                logging.info(f"文件 {video_path} 已保存完成")
            break

        if recording and (time.time() - start_time) >= record_duration:  # 用户设置的录制时间
            out.release()
            if video_path and os.path.getsize(video_path) < record_size * 1024 * 1024:  # 用户设置的文件大小
                os.remove(video_path)
                logging.info(f"文件 {video_path} 被删除，因为它小于{record_size}MB")

            current_time_filename = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            video_path = os.path.join(merged_output_dir, f"{current_time_filename}.mp4")
            out = cv2.VideoWriter(video_path, fourcc, 20.0, (frame_width, frame_height))
            start_time = time.time()
            logging.info(f"创建新视频文件：{video_path}")

    cap.release()
    if out:
        out.release()
    logging.info("视频流已关闭")
    sys.exit(0)
