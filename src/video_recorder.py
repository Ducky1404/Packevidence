"""
video_recorder.py — Module ghi hình video bằng chứng tự động
Tự động bắt đầu/dừng ghi, chèn watermark (timestamp, nhân viên, mã đơn).
"""

import cv2
import os
import time
import threading
import numpy as np
from datetime import datetime
from typing import Optional

VIDEO_DIR = os.path.join(os.path.dirname(__file__), "..", "videos")


class VideoRecorder:
    """
    Ghi hình quá trình đóng gói một kiện hàng.

    Cơ chế:
        - start(tracking_code, user_name) → bắt đầu ghi hình vào thread riêng
        - stop()                          → dừng ghi, trả metadata video
        - Mỗi frame được chèn watermark timestamp, tên nhân viên và mã đơn hàng
        - File được lưu dưới dạng: <tracking_code>_<user>_<HH-MM-SS>.mp4
    """

    FONT       = cv2.FONT_HERSHEY_SIMPLEX
    CODEC      = "mp4v"                   # Codec MP4 tương thích rộng
    FPS_OUT    = 20                        # FPS đầu ra (ổn định hơn 30 trên webcam)
    RESOLUTION = (1280, 720)

    def __init__(self, camera_index: int = 0):
        self.camera_index  = camera_index
        self._cap: Optional[cv2.VideoCapture] = None
        self._writer: Optional[cv2.VideoWriter] = None
        self._thread: Optional[threading.Thread] = None
        self._recording    = False
        self._start_time: Optional[datetime] = None
        self._end_time: Optional[datetime]   = None
        self._file_path    = ""
        self._file_name    = ""
        self._tracking_code = ""
        self._user_name    = ""
        self._frame_count  = 0
        self._lock = threading.Lock()

    # ── Điều khiển ghi hình ─────────────────────────────────────────────────

    def start(self, tracking_code: str, user_name: str, cap: cv2.VideoCapture) -> str:
        """
        Bắt đầu ghi hình.

        Args:
            tracking_code: Mã vận đơn hiện tại
            user_name:     Tên nhân viên đang đăng nhập
            cap:           Đối tượng VideoCapture đang mở (dùng chung)

        Returns:
            Đường dẫn file video sẽ được lưu
        """
        if self._recording:
            return self._file_path

        os.makedirs(VIDEO_DIR, exist_ok=True)

        self._tracking_code = tracking_code
        self._user_name     = user_name
        self._cap           = cap
        self._start_time    = datetime.now()
        self._frame_count   = 0

        # Tạo tên file chuẩn
        safe_user = user_name.replace(" ", "_")
        time_str  = self._start_time.strftime("%H-%M-%S")
        self._file_name = f"{tracking_code}_{safe_user}_{time_str}.mp4"
        self._file_path = os.path.join(VIDEO_DIR, self._file_name)

        # Khởi tạo VideoWriter
        fourcc = cv2.VideoWriter_fourcc(*self.CODEC)
        self._writer = cv2.VideoWriter(
            self._file_path, fourcc, self.FPS_OUT, self.RESOLUTION
        )

        if not self._writer.isOpened():
            return ""

        self._recording = True
        self._thread = threading.Thread(target=self._record_loop, daemon=True)
        self._thread.start()

        return self._file_path

    def stop(self) -> dict:
        """
        Dừng ghi hình.

        Returns:
            dict chứa metadata: file_path, file_name, file_size_mb,
                                duration_sec, start_time, end_time
        """
        if not self._recording:
            return {}

        self._recording = False
        if self._thread:
            self._thread.join(timeout=5)

        self._end_time = datetime.now()
        if self._writer:
            self._writer.release()
            self._writer = None

        duration = (self._end_time - self._start_time).seconds if self._start_time else 0
        size_mb   = 0.0
        if os.path.exists(self._file_path):
            size_mb = round(os.path.getsize(self._file_path) / (1024 * 1024), 2)

        return {
            "file_path":    self._file_path,
            "file_name":    self._file_name,
            "file_size_mb": size_mb,
            "duration_sec": duration,
            "start_time":   self._start_time.strftime("%Y-%m-%d %H:%M:%S") if self._start_time else "",
            "end_time":     self._end_time.strftime("%Y-%m-%d %H:%M:%S")   if self._end_time   else "",
        }

    @property
    def is_recording(self) -> bool:
        return self._recording

    @property
    def elapsed_seconds(self) -> int:
        if self._recording and self._start_time:
            return int((datetime.now() - self._start_time).total_seconds())
        return 0

    # ── Vòng ghi hình chạy trong thread ─────────────────────────────────────

    def _record_loop(self):
        """Thread ghi từng frame vào file video."""
        frame_interval = 1.0 / self.FPS_OUT
        while self._recording:
            t0 = time.time()

            ret, frame = self._cap.read()
            if not ret:
                self._recording = False
                break

            frame = self._add_watermark(frame)
            resized = cv2.resize(frame, self.RESOLUTION)

            with self._lock:
                if self._writer and self._writer.isOpened():
                    self._writer.write(resized)
                    self._frame_count += 1

            # Chỉ sleep phần thời gian còn lại để đạt đúng FPS mục tiêu
            remaining = frame_interval - (time.time() - t0)
            if remaining > 0:
                time.sleep(remaining)

    # ── Watermark ────────────────────────────────────────────────────────────

    def _add_watermark(self, frame: np.ndarray) -> np.ndarray:
        """
        Chèn thông tin bằng chứng vào góc trái phía trên và dưới:
          - Dòng trên: [REC] Mã vận đơn | Nhân viên | Ngày giờ
          - Dòng dưới: Số frame / FPS (cho phần kỹ thuật)
        """
        now_str = datetime.now().strftime("%Y-%m-%d  %H:%M:%S")
        elapsed = self.elapsed_seconds
        mm, ss  = divmod(elapsed, 60)

        # Thanh nền bán trong suốt phía trên
        overlay = frame.copy()
        cv2.rectangle(overlay, (0, 0), (frame.shape[1], 36), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.55, frame, 0.45, 0, frame)

        # Dấu REC màu đỏ nhấp nháy
        if int(time.time()) % 2 == 0:
            cv2.circle(frame, (12, 18), 7, (0, 50, 220), -1)
        cv2.putText(frame, "REC", (22, 24), self.FONT, 0.52, (255, 255, 255), 1)

        # Mã vận đơn
        cv2.putText(frame, f"{self._tracking_code}", (60, 24),
                    self.FONT, 0.52, (80, 220, 140), 1)

        # Nhân viên
        cv2.putText(frame, f"| {self._user_name}", (240, 24),
                    self.FONT, 0.48, (200, 200, 200), 1)

        # Thời gian thực
        cv2.putText(frame, now_str, (frame.shape[1] - 230, 24),
                    self.FONT, 0.48, (200, 200, 200), 1)

        # Đồng hồ đếm thời gian ghi hình (góc dưới trái)
        cv2.putText(frame, f"DUR  {mm:02d}:{ss:02d}", (10, frame.shape[0] - 10),
                    self.FONT, 0.45, (150, 150, 150), 1)

        return frame


# ── Hàm tiện ích ─────────────────────────────────────────────────────────────

def get_video_duration(file_path: str) -> int:
    """Đọc độ dài video (giây) từ file MP4."""
    cap = cv2.VideoCapture(file_path)
    if not cap.isOpened():
        return 0
    fps    = cap.get(cv2.CAP_PROP_FPS) or 1
    frames = cap.get(cv2.CAP_PROP_FRAME_COUNT)
    cap.release()
    return int(frames / fps)


def get_video_thumbnail(file_path: str, second: int = 2) -> Optional[np.ndarray]:
    """Trích xuất một frame (thumbnail) tại giây thứ `second`."""
    cap = cv2.VideoCapture(file_path)
    if not cap.isOpened():
        return None
    fps = cap.get(cv2.CAP_PROP_FPS) or 25
    cap.set(cv2.CAP_PROP_POS_FRAMES, int(fps * second))
    ret, frame = cap.read()
    cap.release()
    return frame if ret else None
