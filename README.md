# PackEvidence — Hệ thống giám sát đóng gói hàng hóa

Ứng dụng web hỗ trợ nhân viên kho quét mã vận đơn, ghi hình bằng chứng đóng gói và thống kê năng suất theo nhân viên.

---

## Yêu cầu hệ thống

- **Python** 3.10 trở lên
- **Webcam** (để quét mã vạch và ghi hình)
- **Windows** 10/11 (đã kiểm thử)

---

## Cài đặt

### 1. Tải source code

```
git clone https://github.com/Ducky1404/Packevidence.git
cd Packevidence
```

Hoặc tải file ZIP từ GitHub rồi giải nén.

### 2. Tạo môi trường ảo

```
python -m venv venv
venv\Scripts\activate
```

### 3. Cài thư viện

```
pip install streamlit opencv-python pyzbar plotly
```

> **Lưu ý:** Nếu chạy bị lỗi liên quan đến `zbar`, thử cài thêm:
> ```
> pip install pyzbar[scripts]
> ```

### 4. Chạy ứng dụng

```
streamlit run app.py
```

Trình duyệt sẽ tự mở tại `http://localhost:8501`

---

## Tài khoản mặc định

| Vai trò | Tên đăng nhập | Mật khẩu |
|---|---|---|
| Quản trị viên | `admin` | `admin123` |
| Nhân viên 1 | `nv001` | `nv001` |
| Nhân viên 2 | `nv002` | `nv002` |
| Nhân viên 3 | `nv003` | `nv003` |

---

## Cấu trúc thư mục

```
Packevidence/
├── app.py                  # File chạy chính (Streamlit)
├── src/
│   ├── database.py         # Quản lý cơ sở dữ liệu SQLite
│   ├── barcode_detector.py # Nhận diện mã vạch qua camera
│   └── video_recorder.py   # Ghi hình và đóng gói metadata
├── data/
│   └── packevidence.db     # Cơ sở dữ liệu SQLite
├── videos/                 # Thư mục lưu video bằng chứng
└── image source/           # Ảnh nền giao diện
```

---

## Hướng dẫn sử dụng nhanh

**Nhân viên:**
1. Đăng nhập bằng tài khoản nhân viên
2. Vào **Quét & Ghi hình** → chọn camera → quét mã vận đơn lần 1 để bắt đầu ghi
3. Đối soát sản phẩm trong đơn → quét lại cùng mã để dừng ghi
4. Video được lưu tự động, đơn hàng chuyển sang trạng thái **Đã đóng**

**Quản trị viên:**
- **Dashboard** — xem tổng quan hoạt động trong ngày
- **Quản lý video** — tìm kiếm và tải xuống video bằng chứng
- **Thống kê** — biểu đồ năng suất và thời gian đóng gói trung bình theo nhân viên
- **Nhân viên** — thêm, xóa, đổi mật khẩu tài khoản

---

## Thư viện sử dụng

| Thư viện | Phiên bản | Mục đích |
|---|---|---|
| Streamlit | 1.58.0 | Giao diện web |
| OpenCV | 4.13.0 | Xử lý camera và video |
| pyzbar | 0.1.9 | Nhận diện mã vạch / QR |
| Plotly | 6.7.0 | Biểu đồ thống kê |
| SQLite3 | tích hợp sẵn | Cơ sở dữ liệu |

---

*Đồ án tốt nghiệp — Đào Minh Đức*
