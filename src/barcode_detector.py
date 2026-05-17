"""
barcode_detector.py — Module nhận diện mã vạch thời gian thực
Sử dụng OpenCV + pyzbar để phát hiện và giải mã Barcode/QR Code từ camera.
"""

import cv2
import time
import numpy as np
from pyzbar import pyzbar
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ScanResult:
    """Kết quả nhận diện một mã vạch."""
    code: str              # Chuỗi mã vận đơn đã giải mã
    code_type: str         # Loại mã: CODE128, QRCODE, …
    polygon: list = field(default_factory=list)  # Toạ độ vùng chứa mã
    timestamp: float = field(default_factory=time.time)


class BarcodeDetector:
    """
    Lớp nhận diện mã vạch liên tục từ luồng camera.

    Luồng hoạt động:
        1. Đọc frame từ cv2.VideoCapture
        2. Tiền xử lý (grayscale → GaussianBlur → adaptiveThreshold)
        3. Pyzbar phát hiện + giải mã mã vạch
        4. Lọc kết quả trùng lặp trong khoảng thời gian debounce_sec
        5. Trả ScanResult hoặc None cho caller
    """

    def __init__(
        self,
        camera_index: int = 0,
        debounce_sec: float = 1.5,
        min_width: int = 40,
    ):
        self.camera_index  = camera_index
        self.debounce_sec  = debounce_sec   # Thời gian chống nhận diện trùng
        self.min_width     = min_width      # Chiều rộng tối thiểu vùng mã (px)
        self._last_code: Optional[str]   = None
        self._last_time: float           = 0.0
        self._cap: Optional[cv2.VideoCapture] = None

    # ── Kết nối camera ──────────────────────────────────────────────────────

    def open(self) -> bool:
        """Mở camera. Trả True nếu thành công."""
        self._cap = cv2.VideoCapture(self.camera_index)
        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH,  1280)
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT,  720)
        self._cap.set(cv2.CAP_PROP_FPS,            30)
        return self._cap.isOpened()

    def release(self):
        """Giải phóng camera."""
        if self._cap and self._cap.isOpened():
            self._cap.release()
        self._cap = None

    def is_opened(self) -> bool:
        return self._cap is not None and self._cap.isOpened()

    # ── Đọc frame ───────────────────────────────────────────────────────────

    def read_frame(self):
        """Đọc một frame. Trả (ok, frame)."""
        if not self.is_opened():
            return False, None
        return self._cap.read()

    # ── Tiền xử lý ──────────────────────────────────────────────────────────

    @staticmethod
    def preprocess(frame: np.ndarray) -> np.ndarray:
        """
        Chuẩn bị ảnh để nhận diện mã vạch:
          - Grayscale   → giảm độ phức tạp
          - GaussianBlur → giảm nhiễu
          - CLAHE       → tăng tương phản cục bộ
          - adaptiveThreshold → tách mã khỏi nền
        """
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (3, 3), 0)

        # Tăng tương phản cục bộ bằng CLAHE
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(blurred)

        # Phân ngưỡng adaptive để làm rõ vạch đen/trắng
        thresh = cv2.adaptiveThreshold(
            enhanced, 255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY, 11, 2
        )
        return thresh

    # ── Nhận diện mã vạch ───────────────────────────────────────────────────

    def detect(self, frame: np.ndarray) -> Optional[ScanResult]:
        """
        Phát hiện và giải mã mã vạch trong frame.
        Áp dụng cơ chế debounce để tránh nhận diện trùng lặp.
        Trả ScanResult hoặc None.
        """
        preprocessed = self.preprocess(frame)

        # Thử trên ảnh đã xử lý trước, nếu không thành công thử ảnh xám gốc
        for img in (preprocessed, cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)):
            barcodes = pyzbar.decode(img)
            if barcodes:
                break

        if not barcodes:
            return None

        for barcode in barcodes:
            # Lọc vùng quá nhỏ (camera ở xa)
            x, y, w, h = barcode.rect
            if w < self.min_width:
                continue

            raw = barcode.data.decode("utf-8", errors="replace").strip()
            if not raw:
                continue

            now = time.time()
            # Debounce: bỏ qua nếu cùng mã trong khoảng debounce_sec giây
            if raw == self._last_code and (now - self._last_time) < self.debounce_sec:
                continue

            self._last_code = raw
            self._last_time = now

            polygon = [(p.x, p.y) for p in barcode.polygon]
            return ScanResult(
                code=raw,
                code_type=barcode.type,
                polygon=polygon,
                timestamp=now,
            )

        return None

    # ── Vẽ chú thích lên frame ───────────────────────────────────────────────

    @staticmethod
    def draw_overlay(frame: np.ndarray, result: ScanResult) -> np.ndarray:
        """
        Vẽ khung xanh và thông tin mã vận đơn lên frame để hiển thị cho người dùng.
        """
        if result.polygon and len(result.polygon) == 4:
            pts = np.array(result.polygon, dtype=np.int32)
            cv2.polylines(frame, [pts], True, (0, 200, 100), 2)

        # Lấy bounding rect để vẽ label
        x = min(p[0] for p in result.polygon) if result.polygon else 10
        y = min(p[1] for p in result.polygon) if result.polygon else 10

        label = f"{result.code_type}: {result.code}"
        (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 1)
        cv2.rectangle(frame, (x, y - th - 10), (x + tw + 8, y), (0, 200, 100), -1)
        cv2.putText(frame, label, (x + 4, y - 4),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1)
        return frame

    @staticmethod
    def draw_scan_guide(frame: np.ndarray) -> np.ndarray:
        """Vẽ khung hướng dẫn quét ở giữa frame."""
        h, w = frame.shape[:2]
        cx, cy = w // 2, h // 2
        box_w, box_h = 320, 160
        x1, y1 = cx - box_w // 2, cy - box_h // 2
        x2, y2 = cx + box_w // 2, cy + box_h // 2

        # Khung chính
        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 180, 90), 1)

        # 4 góc nổi bật
        L = 20
        for px, py, dx, dy in [(x1, y1, 1, 1), (x2, y1, -1, 1),
                                 (x1, y2, 1, -1), (x2, y2, -1, -1)]:
            cv2.line(frame, (px, py), (px + dx * L, py), (0, 220, 110), 3)
            cv2.line(frame, (px, py), (px, py + dy * L), (0, 220, 110), 3)

        # Đường quét động (dựa trên thời gian)
        t = time.time() % 2.0
        scan_y = int(y1 + (y2 - y1) * (t / 2.0))
        cv2.line(frame, (x1 + 4, scan_y), (x2 - 4, scan_y), (0, 255, 140), 1)

        cv2.putText(frame, "Đưa mã vận đơn vào khung",
                    (cx - 115, y2 + 22),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.48, (200, 200, 200), 1)
        return frame


# ── Hàm tiện ích độc lập ─────────────────────────────────────────────────────

def decode_from_image_file(path: str) -> Optional[ScanResult]:
    """Nhận diện mã vạch từ file ảnh tĩnh (dùng cho kiểm thử)."""
    img = cv2.imread(path)
    if img is None:
        return None
    detector = BarcodeDetector()
    return detector.detect(img)
