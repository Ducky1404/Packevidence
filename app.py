"""
app.py — Ứng dụng chính Streamlit
Hệ thống giám sát và lưu trữ bằng chứng đóng gói hàng hóa

Chạy: streamlit run app.py
"""

import streamlit as st
import cv2
import time
import os
import math
import threading
import winsound
from datetime import datetime, date

# Import các module nội bộ
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))
from database import (
    init_db, login, get_order, get_order_items, update_order_status,
    save_video, log_video_action, search_videos, get_all_employees,
    get_stats_by_employee, add_employee, delete_employee,
    reset_password, get_all_orders,
)
from barcode_detector import BarcodeDetector
from video_recorder    import VideoRecorder

# ── Cấu hình trang ───────────────────────────────────────────────────────────

st.set_page_config(
    page_title="PackEvidence",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Khởi tạo CSDL lần đầu
init_db()

# ── CSS tùy chỉnh ────────────────────────────────────────────────────────────

st.markdown("""
<style>
    /* Ẩn menu mặc định của Streamlit */
    #MainMenu, footer { visibility: hidden; }
    header { visibility: hidden; }

    /* Giữ lại nút mở/đóng sidebar (khi sidebar đã thu gọn) */
    header button,
    [data-testid="collapsedControl"],
    [data-testid="stSidebarCollapsedControl"] {
        visibility: visible !important;
    }

    /* Màu chủ đạo */
    :root {
        --green:  #1D9E75;
        --green-light: #E1F5EE;
        --red-light:   #FCEBEB;
        --amber-light: #FAEEDA;
        --blue-light:  #E6F1FB;
    }

    /* Badge trạng thái */
    .badge {
        display: inline-block;
        padding: 3px 10px;
        border-radius: 12px;
        font-size: 12px;
        font-weight: 500;
    }
    .badge-green  { background: var(--green-light); color: #0F6E56; }
    .badge-blue   { background: var(--blue-light);  color: #185FA5; }
    .badge-amber  { background: var(--amber-light); color: #854F0B; }
    .badge-red    { background: var(--red-light);   color: #A32D2D; }

    /* Tiêu đề mã vận đơn */
    .tracking-code {
        font-family: monospace;
        font-size: 20px;
        font-weight: 700;
        color: var(--green);
    }

    /* Ô thông tin */
    .info-box {
        background: #f8fffe;
        border: 1.5px solid var(--green);
        border-radius: 10px;
        padding: 12px 16px;
        margin: 8px 0;
    }
    .warn-box {
        background: var(--amber-light);
        border: 1px solid #EF9F27;
        border-radius: 8px;
        padding: 10px 14px;
        color: #854F0B;
    }
    .err-box {
        background: var(--red-light);
        border: 1px solid #F09595;
        border-radius: 8px;
        padding: 10px 14px;
        color: #A32D2D;
    }
</style>
""", unsafe_allow_html=True)

# ── Quản lý session state ─────────────────────────────────────────────────────

MIN_RECORD_SEC = 3   # Thời gian tối thiểu (giây) trước khi lần quét 2 có hiệu lực


def _beep(freq: int = 1000, duration: int = 200):
    """Phát tiếng bíp không chặn luồng chính."""
    threading.Thread(target=winsound.Beep, args=(freq, duration), daemon=True).start()


def ss_init():
    defaults = {
        "logged_in":          False,
        "user":               None,
        "detector":           None,
        "recorder":           VideoRecorder(),
        "cap":                None,
        "camera_index":       0,
        "camera_list":        None,
        "current_code":       None,
        "current_order":      None,
        "scan_count":         0,
        "recording_start_time": 0.0,
        "session_packed":     0,
        "alerts":             [],
        "pending_scan":       None,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

ss_init()


def get_available_cameras(max_index=6):
    """Quét và trả về danh sách camera có sẵn {tên: index}."""
    cameras = {}
    for i in range(max_index):
        # Thử default backend trước, nếu không được thì thử DSHOW
        cap = cv2.VideoCapture(i)
        if not cap.isOpened():
            cap = cv2.VideoCapture(i, cv2.CAP_DSHOW)
        if cap.isOpened():
            label = f"Camera {i}" + (" — mặc định" if i == 0 else " — thiết bị ngoài")
            cameras[label] = i
            cap.release()
    return cameras or {"Camera 0 — mặc định": 0}


@st.fragment(run_every=0.1)
def _camera_fragment():
    """Fragment tự refresh mỗi 100ms — chỉ cập nhật ảnh camera, không re-render trang."""
    cap      = st.session_state.get("cap")
    detector = st.session_state.get("detector")
    recorder = st.session_state.get("recorder")

    if not cap or not cap.isOpened():
        st.error("❌ Camera chưa được mở.")
        return

    ret, frame = cap.read()
    if not ret:
        st.warning("Không đọc được frame từ camera.")
        return

    if detector:
        result = detector.detect(frame)
        if result:
            BarcodeDetector.draw_overlay(frame, result)
            st.session_state.pending_scan = result.code
            st.rerun()  # Kích hoạt full rerun để xử lý mã quét

    BarcodeDetector.draw_scan_guide(frame)

    if recorder and recorder.is_recording:
        elapsed = recorder.elapsed_seconds
        mm, ss = divmod(elapsed, 60)
        cv2.putText(frame, f"● GHI HINH  {mm:02d}:{ss:02d}",
                    (10, frame.shape[0] - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 50, 230), 2)

    frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    st.image(frame_rgb, channels="RGB", use_container_width=True)


# ═══════════════════════════════════════════════════════════════════════════════
#  MÀN HÌNH ĐĂNG NHẬP
# ═══════════════════════════════════════════════════════════════════════════════

def page_login():
    col1, col2, col3 = st.columns([1, 1.2, 1])
    with col2:
        st.markdown("## 📦 PackEvidence")
        st.markdown("**Hệ thống giám sát đóng gói hàng hóa**")
        st.divider()

        with st.form("login_form"):
            username = st.text_input("Tên đăng nhập", placeholder="Nhập username…")
            password = st.text_input("Mật khẩu", type="password", placeholder="Nhập mật khẩu…")
            submitted = st.form_submit_button("Đăng nhập →", use_container_width=True, type="primary")

        if submitted:
            user = login(username, password)
            if user:
                st.session_state.logged_in = True
                st.session_state.user = user
                st.success(f"Chào mừng {user['full_name']}!")
                time.sleep(0.8)
                st.rerun()
            else:
                st.error("Sai tên đăng nhập hoặc mật khẩu.")


# ═══════════════════════════════════════════════════════════════════════════════
#  SIDEBAR — ĐIỀU HƯỚNG
# ═══════════════════════════════════════════════════════════════════════════════

def render_sidebar():
    user = st.session_state.user
    with st.sidebar:
        st.markdown(f"### 👤 {user['full_name']}")
        st.caption(f"{user['employee_code'] or 'Admin'} • {user['role'].capitalize()}")
        st.divider()

        if user["role"] == "employee":
            page = st.radio("Chức năng", [
                "📷 Quét & ghi hình",
                "📋 Đơn hàng",
                "📊 Ca làm việc",
            ])
        else:
            page = st.radio("Chức năng", [
                "📊 Dashboard admin",
                "🎥 Quản lý video",
                "👥 Nhân viên",
                "📈 Thống kê",
            ])

        st.divider()
        if st.button("🚪 Đăng xuất", use_container_width=True):
            _logout()

    return page


def _logout():
    """Đăng xuất và giải phóng camera."""
    rec = st.session_state.get("recorder")
    if rec and rec.is_recording:
        rec.stop()
    cap = st.session_state.get("cap")
    if cap and cap.isOpened():
        cap.release()
    for k in list(st.session_state.keys()):
        del st.session_state[k]
    ss_init()
    st.rerun()


# ═══════════════════════════════════════════════════════════════════════════════
#  TRANG: QUÉT & GHI HÌNH (Nhân viên)
# ═══════════════════════════════════════════════════════════════════════════════

def page_scan():
    st.markdown("### 📷 Quét mã vận đơn & ghi hình")

    # ── Chọn camera ─────────────────────────────────────────────────────────
    if st.session_state.camera_list is None:
        with st.spinner("Đang tìm kiếm camera..."):
            st.session_state.camera_list = get_available_cameras()

    col_sel, col_refresh = st.columns([5, 1])
    cam_options = list(st.session_state.camera_list.keys())
    cur_values  = list(st.session_state.camera_list.values())
    default_pos = cur_values.index(st.session_state.camera_index) \
                  if st.session_state.camera_index in cur_values else 0

    with col_sel:
        selected_cam = st.selectbox("Chọn camera", cam_options, index=default_pos)
    with col_refresh:
        st.markdown("<div style='margin-top:28px'>", unsafe_allow_html=True)
        if st.button("🔄 Quét lại", help="Tìm lại danh sách camera"):
            st.session_state.camera_list = None
            if st.session_state.cap and st.session_state.cap.isOpened():
                st.session_state.cap.release()
                st.session_state.cap = None
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

    selected_index = st.session_state.camera_list[selected_cam]

    # Nếu người dùng đổi camera → đóng camera cũ
    if st.session_state.camera_index != selected_index:
        if st.session_state.cap and st.session_state.cap.isOpened():
            st.session_state.cap.release()
            st.session_state.cap = None
        st.session_state.camera_index = selected_index

    # Mở camera
    if st.session_state.cap is None or not st.session_state.cap.isOpened():
        cap = cv2.VideoCapture(selected_index)
        if not cap.isOpened():
            cap = cv2.VideoCapture(selected_index, cv2.CAP_DSHOW)
        if cap.isOpened():
            cap.set(cv2.CAP_PROP_FRAME_WIDTH,  1280)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT,  720)
            st.session_state.cap = cap
            st.session_state.detector = BarcodeDetector(debounce_sec=1.5)
        else:
            st.error("❌ Không thể mở camera. Kiểm tra kết nối thiết bị.")
            return

    # Xử lý mã quét được từ camera fragment (nếu có)
    if st.session_state.pending_scan:
        _handle_scan_result(st.session_state.pending_scan)
        st.session_state.pending_scan = None

    col_cam, col_info = st.columns([2, 1])

    with col_cam:
        _camera_fragment()

    with col_info:
        st.markdown("#### Thông tin & đối soát")
        _render_order_info()

        st.divider()
        st.markdown("#### Điều khiển ghi hình")
        ctrl_col1, ctrl_col2 = st.columns(2)
        with ctrl_col1:
            manual_start = st.button("▶ Bắt đầu ghi", use_container_width=True)
        with ctrl_col2:
            manual_stop = st.button("⏹ Dừng ghi", use_container_width=True)

        if manual_start and not st.session_state.recorder.is_recording:
            if st.session_state.current_code:
                _start_recording()
        if manual_stop and st.session_state.recorder.is_recording:
            _stop_and_save()

        st.divider()
        st.metric("Kiện đã đóng ca này", st.session_state.session_packed)

        for alert in st.session_state.alerts[-3:]:
            if alert["type"] == "warn":
                st.warning(alert["msg"])
            elif alert["type"] == "error":
                st.error(alert["msg"])
            else:
                st.success(alert["msg"])


def _handle_scan_result(code: str):
    """Xử lý kết quả quét mã vận đơn."""
    rec = st.session_state.recorder

    if not rec.is_recording:
        # Quét lần 1 → bắt đầu ghi hình
        order = get_order(code)
        if order is None:
            st.session_state.alerts.append({
                "type": "error",
                "msg": f"❌ Mã {code} không tồn tại trong hệ thống."
            })
            return

        if order["status"] == "packed":
            st.session_state.alerts.append({
                "type": "warn",
                "msg": f"⚠️ Mã {code} đã được đóng gói trước đó."
            })
            return

        st.session_state.current_code  = code
        st.session_state.current_order = order
        st.session_state.scan_count    = 1
        update_order_status(code, "packing")
        _start_recording()

    else:
        # Quét lần 2 cùng mã → dừng ghi (phải đủ thời gian tối thiểu)
        if code == st.session_state.current_code:
            elapsed = time.time() - st.session_state.recording_start_time
            if elapsed < MIN_RECORD_SEC:
                remaining = int(MIN_RECORD_SEC - elapsed) + 1
                st.session_state.alerts.append({
                    "type": "warn",
                    "msg": f"⏳ Chờ thêm ~{remaining}s trước khi quét để dừng."
                })
            else:
                _stop_and_save()
        else:
            st.session_state.alerts.append({
                "type": "warn",
                "msg": f"⚠️ Đang ghi hình cho {st.session_state.current_code}. "
                       "Quét lại cùng mã để dừng."
            })


def _start_recording():
    user = st.session_state.user
    cap  = st.session_state.cap
    code = st.session_state.current_code
    st.session_state.recorder.start(code, user["full_name"], cap)
    st.session_state.recording_start_time = time.time()
    # Reset debounce detector để lần quét tiếp theo tính từ đầu
    if st.session_state.detector:
        st.session_state.detector._last_code = None
    _beep(1000, 200)   # Bíp 1 lần — bắt đầu ghi


def _stop_and_save():
    """Dừng ghi hình và lưu vào CSDL."""
    _beep(800, 150)    # Bíp 2 lần — kết thúc ghi
    _beep(800, 150)
    meta  = st.session_state.recorder.stop()
    order = st.session_state.current_order
    user  = st.session_state.user

    if meta and order:
        vid_id = save_video(
            order_id      = order["order_id"],
            user_id       = user["user_id"],
            tracking_code = st.session_state.current_code,
            file_name     = meta["file_name"],
            file_path     = meta["file_path"],
            file_size_mb  = meta["file_size_mb"],
            duration_sec  = meta["duration_sec"],
            start_time    = meta["start_time"],
            end_time      = meta["end_time"],
        )
        log_video_action(vid_id, "save", meta["file_path"])
        update_order_status(st.session_state.current_code, "packed")

        st.session_state.session_packed += 1
        st.session_state.alerts.append({
            "type": "success",
            "msg": f"✅ Đã lưu video bằng chứng cho {st.session_state.current_code} "
                   f"({meta['duration_sec']}s, {meta['file_size_mb']} MB)"
        })

    st.session_state.current_code  = None
    st.session_state.current_order = None


def _render_order_info():
    order = st.session_state.current_order
    if order is None:
        st.info("Quét mã vận đơn để hiển thị thông tin đơn hàng.")
        return

    items = get_order_items(order["order_id"])
    checked_key = f"checked_{order['order_id']}"
    if checked_key not in st.session_state:
        st.session_state[checked_key] = [False] * len(items)

    st.markdown(
        f"<div class='tracking-code'>{order['tracking_code']}</div>",
        unsafe_allow_html=True
    )
    st.markdown(
        f"**Khách hàng:** {order['customer_name'] or '—'}  \n"
        f"**Sàn:** {order['platform'] or '—'}"
    )
    st.markdown("**Đối soát sản phẩm:**")
    all_checked = True
    for i, item in enumerate(items):
        checked = st.checkbox(
            f"{item['product_name']}  ×{item['quantity']}",
            key=f"chk_{order['order_id']}_{i}",
        )
        st.session_state[checked_key][i] = checked
        if not checked:
            all_checked = False

    done = sum(st.session_state[checked_key])
    st.progress(
        done / len(items) if items else 0,
        text=f"{done}/{len(items)} sản phẩm đã kiểm"
    )
    if all_checked:
        st.success("✅ Đủ hàng — quét lại mã để dừng ghi.")
    else:
        st.warning("⚠️ Còn sản phẩm chưa kiểm tra.")


# ═══════════════════════════════════════════════════════════════════════════════
#  TRANG: QUẢN LÝ ĐƠN HÀNG (Nhân viên)
# ═══════════════════════════════════════════════════════════════════════════════

def page_orders():
    st.markdown("### 📋 Danh sách đơn hàng")

    orders = get_all_orders()
    pending = [o for o in orders if o["status"] in ("pending", "packing")]
    packed  = [o for o in orders if o["status"] == "packed"]

    col_left, col_right = st.columns(2)

    with col_left:
        st.markdown(f"#### 🟡 Chưa đóng gói ({len(pending)})")
        st.divider()
        if not pending:
            st.info("Không có đơn nào đang chờ.")
        for o in pending:
            badge = "🔵 Đang đóng" if o["status"] == "packing" else "🟡 Chờ xử lý"
            with st.container(border=True):
                st.markdown(f"**`{o['tracking_code']}`** &nbsp; {badge}",
                            unsafe_allow_html=True)
                st.caption(
                    f"👤 {o['customer_name'] or '—'} &nbsp;|&nbsp; "
                    f"🛒 {o['platform'] or '—'} &nbsp;|&nbsp; "
                    f"📦 {o['item_count']} sản phẩm"
                )

    with col_right:
        st.markdown(f"#### 🟢 Đã đóng gói ({len(packed)})")
        st.divider()
        if not packed:
            st.info("Chưa có đơn nào hoàn thành.")
        for o in packed:
            with st.container(border=True):
                st.markdown(f"**`{o['tracking_code']}`** &nbsp; 🟢 Đã đóng",
                            unsafe_allow_html=True)
                st.caption(
                    f"👤 {o['customer_name'] or '—'} &nbsp;|&nbsp; "
                    f"🛒 {o['platform'] or '—'} &nbsp;|&nbsp; "
                    f"📦 {o['item_count']} sản phẩm"
                )


# ═══════════════════════════════════════════════════════════════════════════════
#  TRANG: CA LÀM VIỆC (Nhân viên)
# ═══════════════════════════════════════════════════════════════════════════════

def page_session():
    st.markdown("### 📊 Ca làm việc")
    user = st.session_state.user

    videos = search_videos(user_id=user["user_id"],
                            date_from=date.today().isoformat(),
                            date_to=date.today().isoformat())
    total = len(videos)
    total_sec = sum(v["duration_sec"] or 0 for v in videos)
    avg_sec = (total_sec // total) if total else 0

    c1, c2, c3 = st.columns(3)
    c1.metric("Kiện đã đóng hôm nay", total)
    c2.metric("Tổng thời gian ghi",
              f"{total_sec // 60}m {total_sec % 60}s")
    c3.metric("Thời gian TB / kiện",
              f"{avg_sec // 60}m {avg_sec % 60}s")

    st.divider()
    st.markdown("#### Video đã ghi hôm nay")
    if not videos:
        st.info("Chưa có video nào được ghi trong ca này.")
        return

    for v in videos:
        with st.expander(f"📹 {v['tracking_code']}  —  {v['start_time']}"):
            st.write(f"**Thời lượng:** {v['duration_sec']}s")
            st.write(f"**Dung lượng:** {v['file_size_mb']} MB")
            st.write(f"**File:** `{v['file_name']}`")
            if os.path.exists(v["file_path"]):
                with open(v["file_path"], "rb") as f:
                    st.download_button(
                        "⬇ Tải xuống",
                        data=f,
                        file_name=v["file_name"],
                        mime="video/mp4",
                        key=f"dl_{v['video_id']}"
                    )


# ═══════════════════════════════════════════════════════════════════════════════
#  TRANG: DASHBOARD ADMIN
# ═══════════════════════════════════════════════════════════════════════════════

def page_admin_dashboard():
    st.markdown("### 📊 Dashboard quản trị")
    today = date.today().isoformat()
    videos_today = search_videos(date_from=today, date_to=today)
    emps          = get_all_employees()
    stats         = get_stats_by_employee(today)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Tổng kiện hôm nay",   len(videos_today))
    c2.metric("Nhân viên",            len(emps))
    total_gb = sum(v["file_size_mb"] or 0 for v in videos_today) / 1024
    c3.metric("Dung lượng hôm nay",   f"{total_gb:.2f} GB")
    c4.metric("Video đã lưu (tổng)", len(search_videos(limit=9999)))

    st.divider()
    st.markdown("#### Năng suất nhân viên hôm nay")
    if stats:
        for s in stats:
            packed = s["total_packed"] or 0
            max_p  = max((r["total_packed"] or 0) for r in stats) or 1
            pct    = int(packed / max_p * 100)
            st.markdown(f"**{s['full_name']}** ({s['employee_code'] or '—'})")
            col_bar, col_num = st.columns([5, 1])
            col_bar.progress(pct / 100)
            col_num.write(f"**{packed}** kiện")
    else:
        st.info("Chưa có dữ liệu hôm nay.")


# ═══════════════════════════════════════════════════════════════════════════════
#  TRANG: QUẢN LÝ VIDEO (Admin)
# ═══════════════════════════════════════════════════════════════════════════════

def page_video_management():
    st.markdown("### 🎥 Quản lý video bằng chứng")

    with st.expander("🔍 Bộ lọc tìm kiếm", expanded=True):
        f1, f2, f3, f4 = st.columns(4)
        q_code   = f1.text_input("Mã vận đơn")
        q_from   = f2.date_input("Từ ngày", value=None)
        q_to     = f3.date_input("Đến ngày", value=None)
        emps     = get_all_employees()
        emp_opts = {"Tất cả": None} | {e["full_name"]: e["user_id"] for e in emps}
        q_emp    = f4.selectbox("Nhân viên", list(emp_opts.keys()))

    videos = search_videos(
        tracking_code = q_code,
        user_id       = emp_opts[q_emp],
        date_from     = str(q_from) if q_from else "",
        date_to       = str(q_to)   if q_to   else "",
    )

    total_size = sum(v["file_size_mb"] or 0 for v in videos)
    st.caption(f"Tìm thấy **{len(videos)}** video — tổng {total_size:.1f} MB")
    st.divider()

    if not videos:
        st.info("Không có video nào phù hợp với bộ lọc.")
        return

    for v in videos:
        c1, c2, c3 = st.columns([3, 2, 1])
        with c1:
            st.markdown(f"**`{v['tracking_code']}`** — {v['full_name']}")
            st.caption(f"{v['start_time']}  |  {v['duration_sec']}s  |  {v['file_size_mb']} MB")
        with c2:
            st.caption(f"📁 {v['file_name']}")
        with c3:
            if os.path.exists(v["file_path"]):
                with open(v["file_path"], "rb") as f:
                    st.download_button("⬇", data=f, file_name=v["file_name"],
                                       mime="video/mp4", key=f"dl2_{v['video_id']}")
        st.divider()


# ═══════════════════════════════════════════════════════════════════════════════
#  TRANG: QUẢN LÝ NHÂN VIÊN (Admin)
# ═══════════════════════════════════════════════════════════════════════════════

def page_employees():
    st.markdown("### 👥 Quản lý nhân viên")

    tab_list, tab_add, tab_pwd = st.tabs(["Danh sách", "Thêm nhân viên", "Đổi mật khẩu"])

    with tab_list:
        emps = get_all_employees()
        for e in emps:
            col1, col2, col3, col4 = st.columns([3, 2, 1, 1])
            col1.markdown(f"**{e['full_name']}** (`{e['username']}`)")
            col2.caption(f"{e['employee_code']} | Tạo: {e['created_at'][:10]}")
            is_active = bool(e["is_active"])
            col3.markdown("🟢 Hoạt động" if is_active else "⚫ Vô hiệu")
            if col4.button("Xóa", key=f"del_{e['user_id']}", type="secondary"):
                delete_employee(e["user_id"])
                st.rerun()
            st.divider()

    with tab_add:
        st.markdown("#### Thêm nhân viên mới")
        with st.form("add_emp_form", clear_on_submit=True):
            new_full = st.text_input("Họ và tên")
            new_user = st.text_input("Tên đăng nhập")
            new_code = st.text_input("Mã nhân viên (VD: NV-010)")
            new_pass = st.text_input("Mật khẩu ban đầu", type="password")
            add_submitted = st.form_submit_button("Thêm nhân viên", type="primary")

        if add_submitted:
            if all([new_full, new_user, new_code, new_pass]):
                ok, msg = add_employee(new_user, new_pass, new_full, new_code)
                if ok:
                    st.success(msg)
                    time.sleep(0.8)
                    st.rerun()
                else:
                    st.error(msg)
            else:
                st.warning("Vui lòng điền đầy đủ thông tin.")

    with tab_pwd:
        st.markdown("#### Reset mật khẩu")
        emps    = get_all_employees()
        emp_map = {e["full_name"]: e["user_id"] for e in emps}
        with st.form("pwd_form", clear_on_submit=True):
            sel_emp = st.selectbox("Chọn nhân viên", list(emp_map.keys()))
            new_pw  = st.text_input("Mật khẩu mới", type="password")
            pwd_submitted = st.form_submit_button("Cập nhật mật khẩu")

        if pwd_submitted:
            if sel_emp and new_pw:
                reset_password(emp_map[sel_emp], new_pw)
                st.success(f"Đã cập nhật mật khẩu cho {sel_emp}.")
            else:
                st.warning("Vui lòng chọn nhân viên và nhập mật khẩu mới.")


# ═══════════════════════════════════════════════════════════════════════════════
#  TRANG: THỐNG KÊ (Admin)
# ═══════════════════════════════════════════════════════════════════════════════

def page_stats():
    st.markdown("### 📈 Thống kê & báo cáo")

    try:
        import plotly.express as px
        import plotly.graph_objects as go
        HAS_PLOTLY = True
    except ImportError:
        HAS_PLOTLY = False

    sel_date = st.date_input("Chọn ngày", value=date.today())
    stats = get_stats_by_employee(str(sel_date))

    if not stats:
        st.info("Không có dữ liệu cho ngày này.")
        return

    names  = [s["full_name"] for s in stats]
    packed = [s["total_packed"] or 0 for s in stats]
    avg_s  = [int(s["avg_seconds"] or 0) for s in stats]

    c1, c2 = st.columns(2)

    with c1:
        st.markdown("#### Số kiện đã đóng")
        if HAS_PLOTLY:
            fig = px.bar(x=names, y=packed, labels={"x": "Nhân viên", "y": "Kiện"},
                         color_discrete_sequence=["#1D9E75"])
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.bar_chart(dict(zip(names, packed)))

    with c2:
        st.markdown("#### Thời gian trung bình / kiện (giây)")
        if HAS_PLOTLY:
            fig2 = px.bar(x=names, y=avg_s, labels={"x": "Nhân viên", "y": "Giây"},
                          color_discrete_sequence=["#185FA5"])
            st.plotly_chart(fig2, use_container_width=True)
        else:
            st.bar_chart(dict(zip(names, avg_s)))


# ═══════════════════════════════════════════════════════════════════════════════
#  ĐIỂM VÀO CHÍNH
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    if not st.session_state.logged_in:
        page_login()
        return

    page = render_sidebar()
    user = st.session_state.user

    # Định tuyến trang
    if user["role"] == "employee":
        if "Quét" in page:
            page_scan()
        elif "Đơn hàng" in page:
            page_orders()
        else:
            page_session()
    else:
        if "Dashboard" in page:
            page_admin_dashboard()
        elif "video" in page.lower():
            page_video_management()
        elif "Nhân viên" in page:
            page_employees()
        else:
            page_stats()


if __name__ == "__main__":
    main()
