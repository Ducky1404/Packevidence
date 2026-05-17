# 📦 PackEvidence — Hệ thống giám sát và lưu trữ bằng chứng đóng gói hàng hóa

> Đồ án tốt nghiệp — Đào Minh Đức — Đại học Thủy Lợi — 2026

---

## 🎯 Giới thiệu

PackEvidence là hệ thống tự động giám sát và lưu trữ bằng chứng đóng gói hàng hóa,
ứng dụng kỹ thuật nhận diện mã vạch (Barcode/QR Code) và thị giác máy tính (Computer Vision).

**Luồng hoạt động chính:**
1. Nhân viên đưa phiếu vận đơn vào camera → hệ thống tự động nhận diện mã vạch
2. Mã vận đơn hợp lệ → hệ thống bắt đầu ghi hình tự động (có watermark)
3. Nhân viên quét lại mã lần 2 → hệ thống dừng ghi, lưu video vào CSDL
4. Admin tra cứu video theo mã đơn, ngày, nhân viên khi có khiếu nại

---

## 🛠 Công nghệ sử dụng

| Thành phần        | Công nghệ                     |
|-------------------|-------------------------------|
| Ngôn ngữ          | Python 3.10+                  |
| Xử lý hình ảnh    | OpenCV 4.8                    |
| Nhận diện mã vạch | pyzbar / ZBar                 |
| Giao diện         | Streamlit 1.35                |
| Cơ sở dữ liệu     | SQLite 3 (via sqlite3 stdlib) |
| Biểu đồ           | Plotly Express (tùy chọn)     |

---

## 📁 Cấu trúc dự án

```
PackEvidence/
├── app.py                  # Ứng dụng Streamlit chính
├── requirements.txt        # Danh sách thư viện
├── README.md
├── src/
│   ├── database.py         # Khởi tạo & CRUD SQLite
│   ├── barcode_detector.py # Nhận diện mã vạch (OpenCV + pyzbar)
│   └── video_recorder.py   # Ghi hình + watermark (OpenCV)
├── data/
│   └── packevidence.db     # Cơ sở dữ liệu SQLite (tự tạo khi chạy)
└── videos/                 # Thư mục lưu video bằng chứng
```

---

## ⚙️ Cài đặt và chạy

### 1. Yêu cầu hệ thống

- Python 3.10 trở lên
- Webcam hoặc camera USB
- Hệ điều hành: Windows 10+ / Ubuntu 20.04+ / macOS 12+

### 2. Cài đặt thư viện

```bash
# Tạo môi trường ảo (khuyến nghị)
python -m venv venv
source venv/bin/activate          # Linux/macOS
venv\Scripts\activate             # Windows

# Cài thư viện
pip install -r requirements.txt

# Ubuntu/Debian: cài thêm thư viện hệ thống cho pyzbar
sudo apt-get install libzbar0
```

### 3. Chạy ứng dụng

```bash
streamlit run app.py
```

Mở trình duyệt tại: http://localhost:8501

---

## 🔐 Tài khoản demo mặc định

| Tài khoản | Mật khẩu | Vai trò        |
|-----------|----------|----------------|
| admin     | admin123 | Quản trị viên  |
| nv001     | nv001    | Đào Minh Đức   |
| nv002     | nv002    | Trần Thị Hà    |
| nv003     | nv003    | Phạm Thảo      |

---

## 💡 Hướng dẫn sử dụng

### Nhân viên kho

1. Đăng nhập bằng tài khoản nhân viên
2. Vào tab **Quét & ghi hình**
3. Đưa phiếu vận đơn vào khung camera
4. Hệ thống tự động:
   - Nhận diện mã vạch
   - Hiển thị thông tin đơn hàng
   - Bắt đầu ghi hình
5. Tiến hành đóng gói và đối soát sản phẩm ở tab **Đối soát**
6. Quét lại mã vận đơn lần 2 → hệ thống dừng ghi và lưu video

### Quản trị viên

1. Đăng nhập bằng tài khoản admin
2. **Dashboard**: Theo dõi năng suất toàn kho
3. **Quản lý video**: Tìm kiếm và tải video theo mã đơn / ngày / nhân viên
4. **Nhân viên**: Thêm, sửa, reset mật khẩu tài khoản nhân viên
5. **Thống kê**: Xem biểu đồ năng suất theo ngày

---

## 🗄 Cấu trúc cơ sở dữ liệu

```
users           — Tài khoản hệ thống (nhân viên & admin)
orders          — Thông tin đơn hàng (mã vận đơn, trạng thái)
order_items     — Danh sách sản phẩm trong đơn hàng
evidence_videos — Thông tin video bằng chứng đã ghi
video_logs      — Nhật ký thao tác với video (xem, tải, xóa)
```

---

## 📝 Ghi chú phát triển

- **Mở rộng camera**: Thay `camera_index=0` thành số thứ tự camera khác (1, 2…)
- **Nén video**: Thay codec `mp4v` bằng `avc1` (H.264) để nén tốt hơn
- **Tự động xóa video cũ**: Thêm cron job chạy `cleanup.py` xóa video > 60 ngày
- **Xuất báo cáo**: Dùng `pandas.DataFrame.to_excel()` từ kết quả `search_videos()`

---

*Đại học Thủy Lợi — Khoa Công nghệ Thông tin — 2026*
