# -*- coding: utf-8 -*-
"""
database.py
-----------
Quản lý cơ sở dữ liệu SQLite cho hệ thống PackEvidence.

Cấu trúc file:
    1. Kết nối & tiện ích
    2. Khởi tạo CSDL (tạo bảng + dữ liệu mẫu)
    3. Xác thực đăng nhập
    4. Quản lý đơn hàng
    5. Quản lý video bằng chứng
    6. Quản lý nhân viên & thống kê
"""

import sqlite3
import hashlib
import os
from datetime import datetime

# Đường dẫn đến file cơ sở dữ liệu (nằm trong thư mục data/)
DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "packevidence.db")


# ═══════════════════════════════════════════════════════════════════════════════
# 1. KẾT NỐI & TIỆN ÍCH
# ═══════════════════════════════════════════════════════════════════════════════

def get_connection():
    """Mở và trả về kết nối SQLite. Luôn gọi conn.close() sau khi dùng xong."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row        # Truy xuất cột bằng tên thay vì chỉ số
    conn.execute("PRAGMA foreign_keys = ON")  # Bật kiểm tra khóa ngoại
    return conn


def hash_password(password: str) -> str:
    """Mã hóa mật khẩu bằng SHA-256 trước khi lưu vào CSDL."""
    return hashlib.sha256(password.encode()).hexdigest()


# ═══════════════════════════════════════════════════════════════════════════════
# 2. KHỞI TẠO CƠ SỞ DỮ LIỆU
# ═══════════════════════════════════════════════════════════════════════════════

def init_db():
    """
    Khởi tạo toàn bộ CSDL khi chạy lần đầu:
        - Tạo 5 bảng (nếu chưa tồn tại)
        - Chèn tài khoản mặc định và 25 đơn hàng mẫu
    Hàm này an toàn để gọi nhiều lần (dùng CREATE TABLE IF NOT EXISTS).
    """
    conn = get_connection()
    cur  = conn.cursor()

    # ── Tạo bảng users (tài khoản người dùng) ─────────────────────────────────
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id       INTEGER PRIMARY KEY AUTOINCREMENT,
            username      TEXT    NOT NULL UNIQUE,
            password      TEXT    NOT NULL,
            full_name     TEXT    NOT NULL,
            role          TEXT    NOT NULL CHECK(role IN ('admin', 'employee')),
            employee_code TEXT,
            is_active     INTEGER NOT NULL DEFAULT 1,
            created_at    TEXT    NOT NULL DEFAULT (datetime('now','localtime'))
        )
    """)

    # ── Tạo bảng orders (đơn hàng) ────────────────────────────────────────────
    cur.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            order_id      INTEGER PRIMARY KEY AUTOINCREMENT,
            tracking_code TEXT    NOT NULL UNIQUE,
            customer_name TEXT,
            platform      TEXT,
            status        TEXT    NOT NULL DEFAULT 'pending'
                              CHECK(status IN ('pending', 'packed')),
            created_at    TEXT    NOT NULL DEFAULT (datetime('now','localtime'))
        )
    """)

    # ── Tạo bảng order_items (sản phẩm trong đơn hàng) ────────────────────────
    cur.execute("""
        CREATE TABLE IF NOT EXISTS order_items (
            item_id      INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id     INTEGER NOT NULL REFERENCES orders(order_id),
            product_name TEXT    NOT NULL,
            quantity     INTEGER NOT NULL DEFAULT 1
        )
    """)

    # ── Tạo bảng evidence_videos (video bằng chứng đóng gói) ──────────────────
    cur.execute("""
        CREATE TABLE IF NOT EXISTS evidence_videos (
            video_id      INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id      INTEGER REFERENCES orders(order_id),
            user_id       INTEGER NOT NULL REFERENCES users(user_id),
            tracking_code TEXT    NOT NULL,
            file_name     TEXT    NOT NULL,
            file_path     TEXT    NOT NULL,
            file_size_mb  REAL,
            duration_sec  INTEGER,
            start_time    TEXT,
            end_time      TEXT,
            created_at    TEXT    NOT NULL DEFAULT (datetime('now','localtime'))
        )
    """)

    # ── Tạo bảng video_logs (lịch sử thao tác với video) ─────────────────────
    cur.execute("""
        CREATE TABLE IF NOT EXISTS video_logs (
            log_id      INTEGER PRIMARY KEY AUTOINCREMENT,
            video_id    INTEGER NOT NULL REFERENCES evidence_videos(video_id),
            action      TEXT    NOT NULL,
            file_path   TEXT,
            action_time TEXT    NOT NULL DEFAULT (datetime('now','localtime')),
            note        TEXT
        )
    """)

    # ── Chèn tài khoản mặc định (chỉ khi chưa có) ────────────────────────────
    cur.execute("SELECT COUNT(*) FROM users WHERE username = 'admin'")
    if cur.fetchone()[0] == 0:
        cur.executemany(
            "INSERT INTO users (username, password, full_name, role, employee_code) "
            "VALUES (?, ?, ?, ?, ?)",
            [
                ("admin", hash_password("admin123"), "Quản trị viên", "admin",    None),
                ("nv001", hash_password("nv001"),    "Đào Minh Đức",  "employee", "NV-001"),
                ("nv002", hash_password("nv002"),    "Trần Thị Hà",   "employee", "NV-002"),
                ("nv003", hash_password("nv003"),    "Phạm Thảo",     "employee", "NV-003"),
            ]
        )

    # ── Chèn đơn hàng mẫu (chỉ khi chưa có) ──────────────────────────────────
    # Mỗi phần tử: (mã_vận_đơn, khách_hàng, sàn, trạng_thái, [(sản_phẩm, số_lượng), ...])
    cur.execute("SELECT COUNT(*) FROM orders")
    if cur.fetchone()[0] == 0:
        sample_orders = [
            ("SP260516-00101", "Nguyễn Văn An",    "Shopee", "pending", [
                ("Áo thun nam oversize trắng", 2),
                ("Quần short kaki be", 1),
                ("Túi zip chống ẩm", 3),
            ]),
            ("LZ260516-00201", "Trần Thị Hương",   "Lazada", "pending", [
                ("Giày thể thao Nike Air Force 1", 1),
                ("Tất thể thao (cặp)", 2),
                ("Hộp đựng giày + gói hút ẩm", 1),
            ]),
            ("TT260516-00301", "Phạm Quốc Bảo",   "TikTok", "pending", [
                ("Son môi 3CE màu đỏ gạch", 1),
                ("Kem dưỡng ẩm Innisfree mini", 2),
                ("Mặt nạ dưỡng da JM Solution hộp 10", 1),
            ]),
            # ── Chờ đóng gói (pending) ────────────────────────────────────────
            ("SP260516-00102", "Lê Minh Tuấn",     "Shopee", "pending", [
                ("Váy hoa nhí vintage size M", 1),
                ("Thắt lưng da nâu", 1),
            ]),
            ("SP260516-00103", "Vũ Thị Lan",        "Shopee", "pending", [
                ("Balo laptop 15.6 inch chống nước", 1),
                ("Cáp sạc USB-C 1m", 2),
                ("Miếng dán bảo vệ màn hình 15.6", 1),
            ]),
            ("LZ260516-00202", "Đặng Văn Hải",     "Lazada", "pending", [
                ("Nồi chiên không dầu 5L", 1),
                ("Giấy lót nồi chiên 100 tờ", 1),
            ]),
            ("LZ260516-00203", "Bùi Thị Thu",       "Lazada", "pending", [
                ("Đèn bàn học LED cảm ứng", 1),
                ("Pin AA Panasonic vỉ 4", 1),
            ]),
            ("TT260516-00302", "Ngô Thị Phương",   "TikTok", "pending", [
                ("Vòng tay đá thạch anh tím", 2),
                ("Hộp đựng trang sức nhỏ", 1),
            ]),
            ("TT260516-00303", "Hoàng Văn Đức",    "TikTok", "pending", [
                ("Ốp lưng iPhone 15 Pro trong suốt", 1),
                ("Kính cường lực iPhone 15 Pro", 2),
                ("Dây sạc MagSafe 1m", 1),
            ]),
            ("SP260516-00104", "Trịnh Thị Mai",     "Shopee", "pending", [
                ("Chăn lông vũ 180x200cm", 1),
                ("Vỏ gối cotton 50x70cm", 2),
            ]),
            ("SP260601-00105", "Nguyễn Thị Bình",  "Shopee", "pending", [
                ("Áo khoác denim nữ size M", 1),
                ("Khuyên tai bạc tròn", 2),
            ]),
            ("SP260601-00106", "Trần Minh Khoa",    "Shopee", "pending", [
                ("Bàn phím cơ Keychron K2", 1),
                ("Cáp USB-C 2m", 1),
            ]),
            ("LZ260601-00204", "Đinh Thị Lan Anh",  "Lazada", "pending", [
                ("Nước hoa mini CK One 30ml", 1),
            ]),
            ("LZ260601-00205", "Phạm Văn Cường",    "Lazada", "pending", [
                ("Tai nghe Sony WH-1000XM5", 1),
                ("Túi đựng tai nghe da", 1),
            ]),
            ("TT260601-00304", "Vũ Thị Thu Hà",     "TikTok", "pending", [
                ("Son kem lì Black Rouge A47", 2),
                ("Tẩy trang Bioderma 500ml", 1),
            ]),
            ("TT260601-00305", "Hoàng Đức Anh",     "TikTok", "pending", [
                ("Giày sneaker trắng size 42", 1),
            ]),
            ("SP260601-00107", "Lý Thị Ngọc Hân",   "Shopee", "pending", [
                ("Chăn bông mùa đông 2kg", 1),
                ("Áo gối cotton 50x70", 2),
            ]),
            ("SP260601-00108", "Ngô Văn Hùng",      "Shopee", "pending", [
                ("Cân điện tử nhà bếp 5kg", 1),
            ]),
            ("LZ260601-00206", "Bùi Thị Hoa",       "Lazada", "pending", [
                ("Máy sấy tóc Panasonic 2000W", 1),
            ]),
            ("LZ260601-00207", "Đỗ Minh Tú",        "Lazada", "pending", [
                ("Sách lập trình Python cơ bản", 1),
                ("Sách Clean Code", 1),
            ]),
            ("TT260601-00306", "Trương Thị Kim Chi", "TikTok", "pending", [
                ("Mặt nạ collagen 3D hộp 5 cái", 2),
            ]),
            ("TT260601-00307", "Cao Văn Phúc",      "TikTok", "pending", [
                ("Dép xỏ ngón nam size 42", 1),
                ("Tất nam ngắn cổ 3 đôi", 1),
            ]),
            ("SP260601-00109", "Phan Thị Yến Nhi",  "Shopee", "pending", [
                ("Kẹp tóc nhựa handmade set 6", 1),
                ("Dây buộc tóc màu pastel", 2),
            ]),
            ("SP260601-00110", "Lê Hoàng Nam",      "Shopee", "pending", [
                ("Ốp lưng Samsung S24 chống sốc", 1),
                ("Kính cường lực S24", 1),
            ]),
            ("LZ260601-00208", "Hà Thị Thu Thảo",   "Lazada", "pending", [
                ("Bình giữ nhiệt Thermos 500ml", 1),
            ]),
        ]

        for tracking_code, customer, platform, status, items in sample_orders:
            cur.execute(
                "INSERT INTO orders (tracking_code, customer_name, platform, status) "
                "VALUES (?, ?, ?, ?)",
                (tracking_code, customer, platform, status)
            )
            order_id = cur.lastrowid
            cur.executemany(
                "INSERT INTO order_items (order_id, product_name, quantity) VALUES (?, ?, ?)",
                [(order_id, name, qty) for name, qty in items]
            )

    conn.commit()
    conn.close()


# ═══════════════════════════════════════════════════════════════════════════════
# 3. XÁC THỰC ĐĂNG NHẬP
# ═══════════════════════════════════════════════════════════════════════════════

def login(username: str, password: str):
    """
    Kiểm tra tên đăng nhập và mật khẩu.
    Trả về dict thông tin user nếu đúng, None nếu sai.
    """
    conn = get_connection()
    row  = conn.execute(
        "SELECT * FROM users WHERE username = ? AND password = ? AND is_active = 1",
        (username, hash_password(password))
    ).fetchone()
    conn.close()
    return dict(row) if row else None


# ═══════════════════════════════════════════════════════════════════════════════
# 4. QUẢN LÝ ĐƠN HÀNG
# ═══════════════════════════════════════════════════════════════════════════════

def get_order(tracking_code: str):
    """Lấy thông tin một đơn hàng theo mã vận đơn. Trả về None nếu không tìm thấy."""
    conn  = get_connection()
    order = conn.execute(
        "SELECT * FROM orders WHERE tracking_code = ?", (tracking_code,)
    ).fetchone()
    conn.close()
    return dict(order) if order else None


def get_order_items(order_id: int):
    """Lấy danh sách sản phẩm của một đơn hàng."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM order_items WHERE order_id = ?", (order_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_all_orders():
    """Lấy toàn bộ đơn hàng, kèm số lượng sản phẩm trong mỗi đơn."""
    conn = get_connection()
    rows = conn.execute("""
        SELECT o.*, COUNT(i.item_id) AS item_count
        FROM orders o
        LEFT JOIN order_items i ON o.order_id = i.order_id
        GROUP BY o.order_id
        ORDER BY o.created_at DESC
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def update_order_status(tracking_code: str, status: str):
    """Cập nhật trạng thái đơn hàng (pending → packed)."""
    conn = get_connection()
    conn.execute(
        "UPDATE orders SET status = ? WHERE tracking_code = ?",
        (status, tracking_code)
    )
    conn.commit()
    conn.close()


def add_order(tracking_code: str, customer_name: str, platform: str, products: list):
    """
    Thêm đơn hàng mới vào hệ thống.
    products: danh sách tên sản phẩm (số lượng mặc định = 1).
    Trả về (True, thông báo) hoặc (False, lỗi).
    """
    conn = get_connection()
    try:
        cur = conn.execute(
            "INSERT INTO orders (tracking_code, customer_name, platform, status) "
            "VALUES (?, ?, ?, 'pending')",
            (tracking_code.strip(), customer_name.strip(), platform.strip())
        )
        order_id = cur.lastrowid
        if products:
            conn.executemany(
                "INSERT INTO order_items (order_id, product_name, quantity) VALUES (?, ?, 1)",
                [(order_id, p.strip()) for p in products if p.strip()]
            )
        conn.commit()
        return True, "Thêm đơn hàng thành công."
    except sqlite3.IntegrityError:
        return False, "Mã vận đơn đã tồn tại."
    finally:
        conn.close()


def delete_order(order_id: int):
    """Xóa đơn hàng và toàn bộ sản phẩm liên quan. Video bằng chứng vẫn giữ lại."""
    conn = get_connection()
    conn.execute("PRAGMA foreign_keys = OFF")
    conn.execute("UPDATE evidence_videos SET order_id = NULL WHERE order_id = ?", (order_id,))
    conn.execute("DELETE FROM order_items WHERE order_id = ?", (order_id,))
    conn.execute("DELETE FROM orders WHERE order_id = ?", (order_id,))
    conn.commit()
    conn.execute("PRAGMA foreign_keys = ON")
    conn.close()


# ═══════════════════════════════════════════════════════════════════════════════
# 5. QUẢN LÝ VIDEO BẰNG CHỨNG
# ═══════════════════════════════════════════════════════════════════════════════

def save_video(order_id, user_id, tracking_code, file_name, file_path,
               file_size_mb, duration_sec, start_time, end_time):
    """Lưu thông tin video bằng chứng vào CSDL sau khi ghi xong. Trả về video_id."""
    conn     = get_connection()
    cur      = conn.execute(
        """INSERT INTO evidence_videos
               (order_id, user_id, tracking_code, file_name, file_path,
                file_size_mb, duration_sec, start_time, end_time)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (order_id, user_id, tracking_code, file_name, file_path,
         file_size_mb, duration_sec, start_time, end_time)
    )
    video_id = cur.lastrowid
    conn.commit()
    conn.close()
    return video_id


def log_video_action(video_id: int, action: str, file_path: str = None, note: str = None):
    """Ghi nhật ký thao tác với video (tạo, xem, tải xuống...)."""
    conn = get_connection()
    conn.execute(
        "INSERT INTO video_logs (video_id, action, file_path, note) VALUES (?, ?, ?, ?)",
        (video_id, action, file_path, note)
    )
    conn.commit()
    conn.close()


def search_videos(tracking_code="", user_id=None, date_from="", date_to="", limit=100):
    """
    Tìm kiếm video theo nhiều tiêu chí (có thể kết hợp):
        tracking_code : lọc theo mã vận đơn (tìm gần đúng)
        user_id       : lọc theo nhân viên
        date_from/to  : lọc theo khoảng ngày tạo
        limit         : giới hạn số kết quả trả về
    """
    conn   = get_connection()
    query  = """
        SELECT v.*,
               COALESCE(u.full_name,     '(Đã xóa)') AS full_name,
               COALESCE(u.employee_code, '—')          AS employee_code
        FROM evidence_videos v
        LEFT JOIN users u ON v.user_id = u.user_id
        WHERE 1=1
    """
    params = []

    if tracking_code:
        query += " AND v.tracking_code LIKE ?"
        params.append(f"%{tracking_code}%")
    if user_id:
        query += " AND v.user_id = ?"
        params.append(user_id)
    if date_from:
        query += " AND DATE(v.created_at) >= ?"
        params.append(date_from)
    if date_to:
        query += " AND DATE(v.created_at) <= ?"
        params.append(date_to)

    query += " ORDER BY v.created_at DESC LIMIT ?"
    params.append(limit)

    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ═══════════════════════════════════════════════════════════════════════════════
# 6. QUẢN LÝ NHÂN VIÊN & THỐNG KÊ
# ═══════════════════════════════════════════════════════════════════════════════

def get_all_employees():
    """Lấy danh sách toàn bộ nhân viên (không bao gồm admin), sắp xếp theo tên."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM users WHERE role = 'employee' ORDER BY full_name"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_stats_by_employee(date_from: str = None, date_to: str = None):
    """
    Thống kê năng suất đóng gói của từng nhân viên trong khoảng thời gian.
    Nếu không truyền ngày, mặc định lấy dữ liệu hôm nay.
    """
    conn  = get_connection()
    today = datetime.now().strftime("%Y-%m-%d")
    df    = date_from or today
    dt    = date_to   or df      # Nếu chỉ có date_from, date_to = date_from (1 ngày)

    rows = conn.execute("""
        SELECT u.full_name,
               u.employee_code,
               COUNT(v.video_id)   AS total_packed,
               SUM(v.duration_sec) AS total_seconds,
               AVG(v.duration_sec) AS avg_seconds
        FROM users u
        LEFT JOIN evidence_videos v
               ON u.user_id = v.user_id
              AND DATE(v.created_at) BETWEEN ? AND ?
        WHERE u.role = 'employee'
        GROUP BY u.user_id
        ORDER BY total_packed DESC
    """, (df, dt)).fetchall()

    conn.close()
    return [dict(r) for r in rows]


def add_employee(username: str, password: str, full_name: str, employee_code: str):
    """
    Thêm nhân viên mới vào hệ thống.
    Trả về (True, thông báo) nếu thành công, (False, lỗi) nếu tài khoản đã tồn tại.
    """
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO users (username, password, full_name, role, employee_code) "
            "VALUES (?, ?, ?, 'employee', ?)",
            (username, hash_password(password), full_name, employee_code)
        )
        conn.commit()
        return True, "Thêm nhân viên thành công."
    except sqlite3.IntegrityError:
        return False, "Tên đăng nhập đã tồn tại."
    finally:
        conn.close()


def delete_employee(user_id: int):
    """
    Xóa vĩnh viễn tài khoản nhân viên.
    Video bằng chứng do nhân viên này ghi vẫn được giữ lại (user_id → NULL).
    """
    conn = get_connection()
    conn.execute("PRAGMA foreign_keys = OFF")
    conn.execute(
        "UPDATE evidence_videos SET user_id = NULL WHERE user_id = ?", (user_id,)
    )
    conn.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.execute("PRAGMA foreign_keys = ON")
    conn.close()


def reset_password(user_id: int, new_password: str):
    """Đặt lại mật khẩu cho nhân viên (admin thực hiện)."""
    conn = get_connection()
    conn.execute(
        "UPDATE users SET password = ? WHERE user_id = ?",
        (hash_password(new_password), user_id)
    )
    conn.commit()
    conn.close()


def check_password(user_id: int, password: str) -> bool:
    """Kiểm tra mật khẩu hiện tại của một user."""
    conn = get_connection()
    row = conn.execute(
        "SELECT 1 FROM users WHERE user_id = ? AND password = ?",
        (user_id, hash_password(password))
    ).fetchone()
    conn.close()
    return row is not None
