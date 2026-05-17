"""
database.py — Khởi tạo và quản lý cơ sở dữ liệu SQLite
Hệ thống giám sát và lưu trữ bằng chứng đóng gói hàng hóa
"""

import sqlite3
import hashlib
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "packevidence.db")


def get_connection():
    """Trả về kết nối đến cơ sở dữ liệu SQLite."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def hash_password(password: str) -> str:
    """Mã hóa mật khẩu bằng SHA-256."""
    return hashlib.sha256(password.encode()).hexdigest()


def init_db():
    """Tạo toàn bộ bảng dữ liệu và dữ liệu mẫu ban đầu."""
    conn = get_connection()
    cur = conn.cursor()

    # ── 1. Bảng users ──────────────────────────────────────────────────────────
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

    # ── 2. Bảng orders ─────────────────────────────────────────────────────────
    cur.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            order_id      INTEGER PRIMARY KEY AUTOINCREMENT,
            tracking_code TEXT    NOT NULL UNIQUE,
            customer_name TEXT,
            platform      TEXT,
            status        TEXT    NOT NULL DEFAULT 'pending'
                              CHECK(status IN ('pending','packing','packed')),
            created_at    TEXT    NOT NULL DEFAULT (datetime('now','localtime'))
        )
    """)

    # ── 3. Bảng order_items ────────────────────────────────────────────────────
    cur.execute("""
        CREATE TABLE IF NOT EXISTS order_items (
            item_id      INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id     INTEGER NOT NULL REFERENCES orders(order_id),
            product_name TEXT    NOT NULL,
            quantity     INTEGER NOT NULL DEFAULT 1
        )
    """)

    # ── 4. Bảng evidence_videos ────────────────────────────────────────────────
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

    # ── 5. Bảng video_logs ─────────────────────────────────────────────────────
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

    # ── Dữ liệu mẫu ────────────────────────────────────────────────────────────
    # Tài khoản admin mặc định
    cur.execute("SELECT COUNT(*) FROM users WHERE username='admin'")
    if cur.fetchone()[0] == 0:
        cur.executemany(
            "INSERT INTO users (username,password,full_name,role,employee_code) VALUES (?,?,?,?,?)",
            [
                ("admin",    hash_password("admin123"),  "Quản trị viên",  "admin",    None),
                ("nv001",    hash_password("nv001"),     "Đào Minh Đức",   "employee", "NV-001"),
                ("nv002",    hash_password("nv002"),     "Trần Thị Hà",    "employee", "NV-002"),
                ("nv003",    hash_password("nv003"),     "Phạm Thảo",      "employee", "NV-003"),
            ]
        )

    # Đơn hàng mẫu
    cur.execute("SELECT COUNT(*) FROM orders")
    if cur.fetchone()[0] == 0:
        sample_orders = [
            # Đã đóng gói (để demo video lưu sẵn)
            ("SP260516-00101", "Nguyễn Văn An",     "Shopee", "packed"),
            ("LZ260516-00201", "Trần Thị Hương",    "Lazada", "packed"),
            # Đang xử lý
            ("TT260516-00301", "Phạm Quốc Bảo",    "TikTok", "packing"),
            # Chờ đóng gói — dùng để quét demo
            ("SP260516-00102", "Lê Minh Tuấn",      "Shopee", "pending"),
            ("SP260516-00103", "Vũ Thị Lan",         "Shopee", "pending"),
            ("LZ260516-00202", "Đặng Văn Hải",      "Lazada", "pending"),
            ("LZ260516-00203", "Bùi Thị Thu",        "Lazada", "pending"),
            ("TT260516-00302", "Ngô Thị Phương",    "TikTok", "pending"),
            ("TT260516-00303", "Hoàng Văn Đức",     "TikTok", "pending"),
            ("SP260516-00104", "Trịnh Thị Mai",      "Shopee", "pending"),
        ]
        cur.executemany(
            "INSERT INTO orders (tracking_code,customer_name,platform,status) VALUES (?,?,?,?)",
            sample_orders
        )

        # Sản phẩm cho từng đơn (order_id theo thứ tự insert ở trên)
        items = [
            # order 1 — SP260516-00101 (packed)
            (1, "Áo thun nam oversize trắng", 2),
            (1, "Quần short kaki be", 1),
            (1, "Túi zip chống ẩm", 3),
            # order 2 — LZ260516-00201 (packed)
            (2, "Giày thể thao Nike Air Force 1", 1),
            (2, "Tất thể thao (cặp)", 2),
            (2, "Hộp đựng giày + gói hút ẩm", 1),
            # order 3 — TT260516-00301 (packing)
            (3, "Son môi 3CE màu đỏ gạch", 1),
            (3, "Kem dưỡng ẩm Innisfree mini", 2),
            (3, "Mặt nạ dưỡng da JM Solution (hộp 10)", 1),
            # order 4 — SP260516-00102
            (4, "Váy hoa nhí vintage size M", 1),
            (4, "Thắt lưng da nâu", 1),
            # order 5 — SP260516-00103
            (5, "Balo laptop 15.6 inch chống nước", 1),
            (5, "Cáp sạc USB-C 1m", 2),
            (5, "Miếng dán bảo vệ màn hình 15.6", 1),
            # order 6 — LZ260516-00202
            (6, "Nồi chiên không dầu 5L", 1),
            (6, "Giấy lót nồi chiên (100 tờ)", 1),
            # order 7 — LZ260516-00203
            (7, "Đèn bàn học LED cảm ứng", 1),
            (7, "Pin AA Panasonic (vỉ 4)", 1),
            # order 8 — TT260516-00302
            (8, "Vòng tay đá thạch anh tím", 2),
            (8, "Hộp đựng trang sức nhỏ", 1),
            # order 9 — TT260516-00303
            (9, "Ốp lưng iPhone 15 Pro trong suốt", 1),
            (9, "Kính cường lực iPhone 15 Pro", 2),
            (9, "Dây sạc MagSafe 1m", 1),
            # order 10 — SP260516-00104
            (10, "Chăn lông vũ 180x200cm", 1),
            (10, "Vỏ gối cotton 50x70cm", 2),
        ]
        cur.executemany(
            "INSERT INTO order_items (order_id,product_name,quantity) VALUES (?,?,?)",
            items
        )

    conn.commit()
    conn.close()


# ── Các hàm CRUD ────────────────────────────────────────────────────────────

def login(username: str, password: str):
    """Xác thực đăng nhập. Trả về dict user hoặc None."""
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM users WHERE username=? AND password=? AND is_active=1",
        (username, hash_password(password))
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def get_order(tracking_code: str):
    """Lấy thông tin đơn hàng theo mã vận đơn."""
    conn = get_connection()
    order = conn.execute(
        "SELECT * FROM orders WHERE tracking_code=?", (tracking_code,)
    ).fetchone()
    conn.close()
    return dict(order) if order else None


def get_order_items(order_id: int):
    """Lấy danh sách sản phẩm của một đơn hàng."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM order_items WHERE order_id=?", (order_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def update_order_status(tracking_code: str, status: str):
    conn = get_connection()
    conn.execute(
        "UPDATE orders SET status=? WHERE tracking_code=?", (status, tracking_code)
    )
    conn.commit()
    conn.close()


def save_video(order_id, user_id, tracking_code, file_name, file_path,
               file_size_mb, duration_sec, start_time, end_time):
    """Lưu thông tin video bằng chứng vào CSDL."""
    conn = get_connection()
    cur = conn.execute(
        """INSERT INTO evidence_videos
           (order_id,user_id,tracking_code,file_name,file_path,
            file_size_mb,duration_sec,start_time,end_time)
           VALUES (?,?,?,?,?,?,?,?,?)""",
        (order_id, user_id, tracking_code, file_name, file_path,
         file_size_mb, duration_sec, start_time, end_time)
    )
    video_id = cur.lastrowid
    conn.commit()
    conn.close()
    return video_id


def log_video_action(video_id: int, action: str, file_path: str = None, note: str = None):
    """Ghi nhật ký thao tác với video."""
    conn = get_connection()
    conn.execute(
        "INSERT INTO video_logs (video_id,action,file_path,note) VALUES (?,?,?,?)",
        (video_id, action, file_path, note)
    )
    conn.commit()
    conn.close()


def search_videos(tracking_code="", user_id=None, date_from="", date_to="", limit=100):
    """Tìm kiếm video theo nhiều tiêu chí."""
    conn = get_connection()
    query = """
        SELECT v.*,
               COALESCE(u.full_name, '(Đã xóa)')   AS full_name,
               COALESCE(u.employee_code, '—')        AS employee_code
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


def get_all_employees():
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM users WHERE role='employee' ORDER BY full_name"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_stats_by_employee(date_str: str = None):
    """Thống kê số kiện hàng đã đóng theo nhân viên."""
    conn = get_connection()
    date_filter = date_str or datetime.now().strftime("%Y-%m-%d")
    rows = conn.execute("""
        SELECT u.full_name, u.employee_code,
               COUNT(v.video_id)          AS total_packed,
               SUM(v.duration_sec)        AS total_seconds,
               AVG(v.duration_sec)        AS avg_seconds
        FROM users u
        LEFT JOIN evidence_videos v
               ON u.user_id = v.user_id
              AND DATE(v.created_at) = ?
        WHERE u.role = 'employee'
        GROUP BY u.user_id
        ORDER BY total_packed DESC
    """, (date_filter,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_all_orders():
    """Lấy toàn bộ đơn hàng kèm số lượng sản phẩm."""
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


def add_employee(username, password, full_name, employee_code):
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO users (username,password,full_name,role,employee_code) VALUES (?,?,?,?,?)",
            (username, hash_password(password), full_name, "employee", employee_code)
        )
        conn.commit()
        return True, "Thêm nhân viên thành công."
    except sqlite3.IntegrityError:
        return False, "Tài khoản đã tồn tại."
    finally:
        conn.close()


def deactivate_employee(user_id: int):
    conn = get_connection()
    conn.execute("UPDATE users SET is_active=0 WHERE user_id=?", (user_id,))
    conn.commit()
    conn.close()


def delete_employee(user_id: int):
    """Xóa vĩnh viễn nhân viên. Lịch sử video giữ nguyên (user_id thành NULL)."""
    conn = get_connection()
    conn.execute("PRAGMA foreign_keys = OFF")
    conn.execute("UPDATE evidence_videos SET user_id = NULL WHERE user_id = ?", (user_id,))
    conn.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.execute("PRAGMA foreign_keys = ON")
    conn.close()


def reset_password(user_id: int, new_password: str):
    conn = get_connection()
    conn.execute(
        "UPDATE users SET password=? WHERE user_id=?",
        (hash_password(new_password), user_id)
    )
    conn.commit()
    conn.close()
