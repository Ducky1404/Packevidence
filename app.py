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
import base64
from datetime import datetime, date

# Import các module nội bộ
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))
from database import (
    init_db, login, get_order, get_order_items, update_order_status,
    save_video, log_video_action, search_videos, get_all_employees,
    get_stats_by_employee, add_employee, delete_employee,
    reset_password, get_all_orders, add_order, delete_order,
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

# Khởi tạo CSDL một lần duy nhất (cache_resource giữ kết quả xuyên suốt session)
@st.cache_resource
def _init_db_once():
    init_db()

_init_db_once()

# ── CSS tùy chỉnh ────────────────────────────────────────────────────────────

st.markdown("""
<style>
    #MainMenu, footer { visibility: hidden; }
    header { visibility: hidden; }
    header button,
    [data-testid="collapsedControl"],
    [data-testid="stSidebarCollapsedControl"] { visibility: visible !important; }

    :root {
        --green:        #1D9E75;
        --green-dark:   #0a1f14;
        --green-light:  #E8F5F0;
        --red-light:    #FCEBEB;
        --amber-light:  #FAEEDA;
        --blue-light:   #EEF2FF;
        --surface:      #FFFFFF;
        --border:       #E5E7EB;
        --text-pri:     #111827;
        --text-sec:     #111827;
    }

    /* ── SIDEBAR ─────────────────────────────── */
    [data-testid="stSidebar"] {
        background: linear-gradient(175deg, #2d6a4f 0%, #40916c 100%) !important;
        border-right: none;
    }
    [data-testid="stSidebar"] .stMarkdown p,
    [data-testid="stSidebar"] .stMarkdown span { color: rgba(255,255,255,0.88) !important; }
    [data-testid="stSidebar"] h1,
    [data-testid="stSidebar"] h2,
    [data-testid="stSidebar"] h3 { color: #ffffff !important; }
    [data-testid="stSidebar"] hr  { border-color: rgba(255,255,255,0.18) !important; }
    [data-testid="stSidebar"] label,
    [data-testid="stSidebar"] p,
    [data-testid="stSidebar"] span,
    [data-testid="stSidebar"] div { color: rgba(255,255,255,0.9) !important; }
    /* Chỉ style text của radio option, không đụng vào cấu trúc */
    [data-testid="stSidebar"] [data-testid="stRadio"] label span {
        color: rgba(255,255,255,0.9) !important;
        font-size: 0.9rem;
    }
    [data-testid="stSidebar"] [data-testid="stRadio"] label {
        padding: 0.4rem 0.6rem;
        border-radius: 8px;
    }
    [data-testid="stSidebar"] [data-testid="stRadio"] label:hover {
        background: rgba(255,255,255,0.12) !important;
    }
    [data-testid="stSidebar"] .stButton > button {
        background: rgba(255,255,255,0.15) !important;
        color: rgba(255,255,255,0.88) !important;
        border: 1px solid rgba(255,255,255,0.2) !important;
        border-radius: 8px !important;
        transition: all 0.2s !important;
    }
    [data-testid="stSidebar"] .stButton > button:hover {
        background: rgba(255,255,255,0.25) !important;
        color: #ffffff !important;
    }

    /* ── PAGE HEADER BANNER ───────────────────── */
    .page-header {
        background: linear-gradient(135deg, #b7e4c7 0%, #d8f3dc 100%);
        border-radius: 14px;
        padding: 1.4rem 1.8rem;
        margin-bottom: 1.6rem;
        display: flex;
        align-items: center;
        gap: 1rem;
        border: 1px solid #a0d9b4;
    }
    .ph-icon  { font-size: 2rem; line-height: 1; flex-shrink: 0; }
    .ph-title { color: #1a4731; margin: 0; font-size: 1.35rem; font-weight: 700; line-height: 1.2; }
    .ph-sub   { color: #2d6a4f; margin: 0.15rem 0 0; font-size: 0.82rem; }

    /* ── METRIC CARDS ─────────────────────────── */
    .metric-row { display: flex; gap: 1rem; margin-bottom: 1.6rem; flex-wrap: wrap; }
    .metric-card {
        flex: 1; min-width: 140px;
        background: #ffffff;
        border-radius: 12px;
        padding: 1.1rem 1.3rem;
        box-shadow: 0 1px 3px rgba(0,0,0,0.06), 0 4px 14px rgba(0,0,0,0.05);
        border: 1px solid var(--border);
        display: flex; align-items: center; gap: 1rem;
    }
    .mc-icon {
        width: 46px; height: 46px; border-radius: 11px; flex-shrink: 0;
        display: flex; align-items: center; justify-content: center; font-size: 1.4rem;
    }
    .mc-icon.green  { background: #c8f5df; }
    .mc-icon.blue   { background: #c5dff8; }
    .mc-icon.amber  { background: #fde8c0; }
    .mc-icon.purple { background: #e2d9f3; }
    .mc-val   { font-size: 1.65rem; font-weight: 700; color: var(--text-pri); line-height: 1.1; }
    .mc-label { font-size: 0.78rem; color: var(--text-sec); margin-top: 0.15rem; }

    /* ── BADGES ───────────────────────────────── */
    .badge { display: inline-block; padding: 3px 10px; border-radius: 12px; font-size: 12px; font-weight: 500; }
    .badge-green  { background: var(--green-light); color: #0F6E56; }
    .badge-blue   { background: var(--blue-light);  color: #3730A3; }
    .badge-amber  { background: var(--amber-light); color: #854F0B; }
    .badge-red    { background: var(--red-light);   color: #A32D2D; }

    /* ── MISC ─────────────────────────────────── */
    .tracking-code { font-family: monospace; font-size: 20px; font-weight: 700; color: var(--green); }
    .info-box { background: #f8fffe; border: 1.5px solid var(--green); border-radius: 10px; padding: 12px 16px; margin: 8px 0; }
    .warn-box { background: var(--amber-light); border: 1px solid #EF9F27; border-radius: 8px; padding: 10px 14px; color: #854F0B; }
    .err-box  { background: var(--red-light);   border: 1px solid #F09595; border-radius: 8px; padding: 10px 14px; color: #A32D2D; }

    /* ── CAPTION ─────────────────────────────── */
    [data-testid="stCaptionContainer"] p,
    [data-testid="stCaptionContainer"] { color: #111827 !important; font-weight: 600 !important; }

    /* ── FOOTER ───────────────────────────────── */
    .app-footer {
        text-align: center;
        padding: 2rem 0 0.5rem;
        color: #374151;
        font-size: 0.76rem;
        border-top: 1px solid var(--border);
        margin-top: 3rem;
    }
    .app-footer strong { color: #111827; }
</style>
""", unsafe_allow_html=True)

# ── Quản lý session state ─────────────────────────────────────────────────────

MIN_RECORD_SEC = 3   # Thời gian tối thiểu (giây) trước khi lần quét 2 có hiệu lực


def _beep(freq: int = 1000, duration: int = 200):
    """Phát tiếng bíp không chặn luồng chính."""
    threading.Thread(target=winsound.Beep, args=(freq, duration), daemon=True).start()


def ss_init():
    defaults = {
        "logged_in":            False,
        "user":                 None,
        "detector":             None,
        "cap":                  None,
        "camera_index":         0,
        "camera_list":          None,
        "current_code":         None,
        "current_order":        None,
        "scan_count":           0,
        "recording_start_time": 0.0,
        "session_packed":       0,
        "alerts":               [],
        "pending_scan":         None,
        "confirm_delete_order": None,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v
    # Khởi tạo riêng để tránh tạo VideoRecorder() mỗi lần rerun
    if "recorder" not in st.session_state:
        st.session_state["recorder"] = VideoRecorder()

ss_init()


def get_available_cameras(max_index=10):
    """Quét và trả về danh sách camera có sẵn {tên: index}."""
    cameras = {}
    for i in range(max_index):
        # Thử DSHOW trước (nhanh hơn trên Windows), fallback sang default backend
        cap = cv2.VideoCapture(i, cv2.CAP_DSHOW)
        if not cap.isOpened():
            cap = cv2.VideoCapture(i)
        if cap.isOpened():
            label = f"Camera {i}" + (" — mặc định" if i == 0 else f" — thiết bị {i}")
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

def render_page_header(icon: str, title: str, subtitle: str = ""):
    sub = f'<p class="ph-sub">{subtitle}</p>' if subtitle else ""
    st.markdown(f"""
    <div class="page-header">
        <div class="ph-icon">{icon}</div>
        <div><p class="ph-title">{title}</p>{sub}</div>
    </div>""", unsafe_allow_html=True)


def render_metrics(*cards):
    """cards: (icon, value, label, color) — color: green|blue|amber|purple"""
    inner = "".join(f"""
        <div class="metric-card">
            <div class="mc-icon {c}">{ic}</div>
            <div><div class="mc-val">{v}</div><div class="mc-label">{lb}</div></div>
        </div>""" for ic, v, lb, c in cards)
    st.markdown(f'<div class="metric-row">{inner}</div>', unsafe_allow_html=True)


def render_footer():
    st.markdown("""
    <div class="app-footer">
        © 2025 <strong>PackEvidence</strong> &nbsp;·&nbsp;
        Phát triển bởi <strong>Đào Minh Đức</strong>
    </div>""", unsafe_allow_html=True)


@st.cache_data
def _load_login_bg() -> str:
    bg_path = os.path.join(os.path.dirname(__file__), "image source", "login bg.png")
    with open(bg_path, "rb") as f:
        return base64.b64encode(f.read()).decode()


def page_login():
    _b64 = _load_login_bg()

    st.markdown(f"""
    <style>
    [data-testid="stSidebar"] {{ display: none !important; }}
    [data-testid="stSidebarCollapsedControl"] {{ display: none !important; }}
    [data-testid="stAppViewContainer"] {{
        background-image: url("data:image/png;base64,{_b64}");
        background-size: cover;
        background-position: center center;
        background-repeat: no-repeat;
        min-height: 100vh;
    }}
    [data-testid="block-container"] {{
        padding-top: 12vh !important;
        padding-left: 2rem !important;
        padding-right: 2rem !important;
        max-width: 100% !important;
    }}
    [data-testid="stForm"] {{
        background: white !important;
        border-radius: 14px !important;
        padding: 2rem !important;
        box-shadow: 0 8px 40px rgba(0, 0, 0, 0.12) !important;
        border: 1px solid #e0e0e0 !important;
    }}
    </style>
    """, unsafe_allow_html=True)

    _, col2 = st.columns([1.4, 1])
    with col2:
        st.markdown("""
        <div style="margin-bottom: 1.2rem;">
            <h2 style="color:#0f3b2b; margin:0 0 0.3rem; font-size:1.7rem; font-weight:700;">Đăng nhập</h2>
            <p style="color:#555; margin:0; font-size:0.9rem;">Vui lòng nhập thông tin để tiếp tục</p>
        </div>
        """, unsafe_allow_html=True)

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
    role_label = "Quản trị viên" if user["role"] == "admin" else "Nhân viên"
    role_icon  = "👑" if user["role"] == "admin" else "👤"
    with st.sidebar:
        st.markdown(f"""
        <div style="text-align:center;padding:1.8rem 0 1.2rem;">
            <div style="font-size:2.8rem;line-height:1;">📦</div>
            <div style="color:#ffffff;font-weight:700;font-size:1.1rem;margin-top:0.4rem;letter-spacing:-0.3px;">PackEvidence</div>
            <div style="color:rgba(255,255,255,0.78);font-size:0.72rem;margin-top:0.1rem;">Hệ thống giám sát đóng gói</div>
        </div>""", unsafe_allow_html=True)

        st.divider()

        st.markdown(f"""
        <div style="display:flex;align-items:center;gap:0.75rem;padding:0.4rem 0 1.1rem;">
            <div style="width:38px;height:38px;border-radius:50%;background:rgba(29,158,117,0.25);
                        display:flex;align-items:center;justify-content:center;font-size:1.1rem;flex-shrink:0;">
                {role_icon}
            </div>
            <div>
                <div style="color:#ffffff;font-weight:600;font-size:0.88rem;line-height:1.3;">{user['full_name']}</div>
                <div style="color:rgba(255,255,255,0.78);font-size:0.72rem;">{user['employee_code'] or 'Admin'} · {role_label}</div>
            </div>
        </div>""", unsafe_allow_html=True)

        if user["role"] == "employee":
            page = st.radio("Menu", [
                "📷 Quét & ghi hình",
                "📋 Đơn hàng",
                "📊 Ca làm việc",
            ], label_visibility="collapsed")
        else:
            page = st.radio("Menu", [
                "📊 Dashboard admin",
                "📋 Đơn hàng",
                "🎥 Quản lý video",
                "👥 Nhân viên",
                "📈 Thống kê",
            ], label_visibility="collapsed")

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
    render_page_header("📷", "Quét & Ghi hình", "Quét mã vận đơn để bắt đầu ghi hình bằng chứng")

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
        rec = st.session_state.recorder
        if rec.is_recording:
            elapsed = int(rec.elapsed_seconds)
            mm, ss  = divmod(elapsed, 60)
            st.markdown(
                f"<div style='background:#fff0f0;border:1.5px solid #e57373;border-radius:8px;"
                f"padding:0.5rem 0.85rem;margin-bottom:0.6rem;font-size:0.85rem;color:#c62828;'>"
                f"🔴 Đang ghi &nbsp;—&nbsp; {mm:02d}:{ss:02d}</div>",
                unsafe_allow_html=True
            )
            if st.button("⏹ Dừng ghi thủ công", use_container_width=True, type="primary"):
                _stop_and_save()
                st.rerun()
        else:
            st.markdown(
                "<div style='background:#f5f5f5;border:1px solid #e0e0e0;border-radius:8px;"
                "padding:0.5rem 0.85rem;margin-bottom:0.6rem;font-size:0.85rem;color:#9e9e9e;'>"
                "⬜ Chưa ghi — quét mã để bắt đầu</div>",
                unsafe_allow_html=True
            )

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


def _render_delete_order_btn(o: dict):
    """Hiển thị nút Xóa kèm bước xác nhận trước khi thực hiện."""
    oid = o["order_id"]
    if st.session_state.confirm_delete_order == oid:
        st.warning(f"Xóa đơn **{o['tracking_code']}**? Thao tác không thể hoàn tác.")
        c1, c2 = st.columns(2)
        if c1.button("✅ Xác nhận xóa", key=f"conf_{oid}", type="primary"):
            delete_order(oid)
            st.session_state.confirm_delete_order = None
            st.rerun()
        if c2.button("❌ Hủy", key=f"cancel_{oid}"):
            st.session_state.confirm_delete_order = None
            st.rerun()
    else:
        if st.button("🗑 Xóa", key=f"del_{oid}", type="secondary"):
            st.session_state.confirm_delete_order = oid
            st.rerun()


# ═══════════════════════════════════════════════════════════════════════════════
#  TRANG: QUẢN LÝ ĐƠN HÀNG (Nhân viên + Admin)
# ═══════════════════════════════════════════════════════════════════════════════

def page_orders():
    render_page_header("📋", "Đơn hàng", "Danh sách đơn hàng cần xử lý")

    is_admin = st.session_state.user["role"] == "admin"

    # ── Thêm đơn hàng (admin) ───────────────────────────────────────────────
    if is_admin:
        with st.expander("➕ Thêm đơn hàng mới"):
            with st.form("add_order_form", clear_on_submit=True):
                c1, c2, c3 = st.columns(3)
                new_code     = c1.text_input("Mã vận đơn *")
                new_customer = c2.text_input("Khách hàng")
                new_platform = c3.selectbox("Sàn", ["Shopee", "Lazada", "TikTok", "Khác"])
                products_raw = st.text_area(
                    "Sản phẩm (mỗi dòng 1 sản phẩm)",
                    height=100,
                    placeholder="Áo thun nam oversize\nQuần short kaki\n...",
                )
                if st.form_submit_button("Thêm đơn hàng", type="primary"):
                    if not new_code.strip():
                        st.warning("Vui lòng nhập mã vận đơn.")
                    else:
                        products = [p for p in products_raw.splitlines() if p.strip()]
                        ok, msg  = add_order(new_code, new_customer, new_platform, products)
                        if ok:
                            st.success(msg)
                            st.rerun()
                        else:
                            st.error(msg)

    # ── Bộ lọc ──────────────────────────────────────────────────────────────
    f1, f2 = st.columns([3, 1])
    q_code     = f1.text_input("🔍 Tìm mã vận đơn", placeholder="Nhập một phần mã...")
    q_platform = f2.selectbox("Lọc theo sàn", ["Tất cả", "Shopee", "Lazada", "TikTok", "Khác"])

    orders = get_all_orders()
    if q_code:
        orders = [o for o in orders if q_code.upper() in o["tracking_code"].upper()]
    if q_platform != "Tất cả":
        orders = [o for o in orders if o["platform"] == q_platform]

    pending = [o for o in orders if o["status"] == "pending"]
    packed  = [o for o in orders if o["status"] == "packed"]

    col_left, col_right = st.columns(2)

    with col_left:
        st.markdown(f"#### 🟡 Chờ xử lý ({len(pending)})")
        st.divider()
        if not pending:
            st.info("Không có đơn nào đang chờ.")
        for o in pending:
            with st.container(border=True):
                st.markdown(f"**`{o['tracking_code']}`** &nbsp; 🟡 Chờ xử lý",
                            unsafe_allow_html=True)
                st.markdown(
                    f"<p style='color:#111827;font-size:0.82rem;margin:0.15rem 0 0;'>"
                    f"👤 {o['customer_name'] or '—'} &nbsp;|&nbsp; "
                    f"🛒 {o['platform'] or '—'} &nbsp;|&nbsp; "
                    f"📦 {o['item_count']} sản phẩm</p>",
                    unsafe_allow_html=True
                )
                if is_admin:
                    _render_delete_order_btn(o)

    with col_right:
        st.markdown(f"#### 🟢 Đã đóng ({len(packed)})")
        st.divider()
        if not packed:
            st.info("Chưa có đơn nào hoàn thành.")
        for o in packed:
            with st.container(border=True):
                st.markdown(f"**`{o['tracking_code']}`** &nbsp; 🟢 Đã đóng",
                            unsafe_allow_html=True)
                st.markdown(
                    f"<p style='color:#111827;font-size:0.82rem;margin:0.15rem 0 0;'>"
                    f"👤 {o['customer_name'] or '—'} &nbsp;|&nbsp; "
                    f"🛒 {o['platform'] or '—'} &nbsp;|&nbsp; "
                    f"📦 {o['item_count']} sản phẩm</p>",
                    unsafe_allow_html=True
                )
                if is_admin:
                    bc1, bc2 = st.columns(2)
                    if bc1.button("↩ Reset", key=f"rst_{o['order_id']}", help="Đặt lại về Chờ xử lý"):
                        update_order_status(o["tracking_code"], "pending")
                        st.rerun()
                    with bc2:
                        _render_delete_order_btn(o)


# ═══════════════════════════════════════════════════════════════════════════════
#  TRANG: CA LÀM VIỆC (Nhân viên)
# ═══════════════════════════════════════════════════════════════════════════════

def page_session():
    user         = st.session_state.user
    selected_day = st.date_input("Chọn ngày", value=date.today(), max_value=date.today())
    render_page_header("📊", "Ca làm việc", f"Ngày {selected_day.strftime('%d/%m/%Y')}")

    day_str = selected_day.isoformat()
    videos  = search_videos(user_id=user["user_id"], date_from=day_str, date_to=day_str)
    total     = len(videos)
    total_sec = sum(v["duration_sec"] or 0 for v in videos)
    avg_sec   = (total_sec // total) if total else 0

    render_metrics(
        ("📦", total,                               "Kiện đã đóng",        "green"),
        ("⏱️", f"{total_sec//60}m {total_sec%60}s", "Tổng thời gian ghi",  "blue"),
        ("⌛", f"{avg_sec//60}m {avg_sec%60}s",     "Thời gian TB / kiện", "amber"),
    )

    st.divider()
    st.markdown(f"#### Video đã ghi ngày {selected_day.strftime('%d/%m/%Y')}")
    if not videos:
        st.info("Chưa có video nào được ghi trong ngày này.")
        render_footer()
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
    render_footer()


# ═══════════════════════════════════════════════════════════════════════════════
#  TRANG: DASHBOARD ADMIN
# ═══════════════════════════════════════════════════════════════════════════════

def page_admin_dashboard():
    render_page_header("📊", "Dashboard", "Tổng quan hoạt động hôm nay")
    today = date.today().isoformat()
    videos_today = search_videos(date_from=today, date_to=today)
    emps          = get_all_employees()
    stats         = get_stats_by_employee(today)
    total_gb = sum(v["file_size_mb"] or 0 for v in videos_today) / 1024

    render_metrics(
        ("📦", len(videos_today),             "Kiện đóng gói hôm nay",  "green"),
        ("👥", len(emps),                     "Nhân viên",               "blue"),
        ("💾", f"{total_gb:.2f} GB",          "Dung lượng hôm nay",     "amber"),
        ("🎥", len(search_videos(limit=9999)),"Tổng video đã lưu",      "purple"),
    )

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
    render_footer()


# ═══════════════════════════════════════════════════════════════════════════════
#  TRANG: QUẢN LÝ VIDEO (Admin)
# ═══════════════════════════════════════════════════════════════════════════════

def page_video_management():
    render_page_header("🎥", "Quản lý video", "Tìm kiếm và tải xuống video bằng chứng")

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
    st.markdown(f"<p style='color:#111827;font-size:0.82rem;'>Tìm thấy <strong>{len(videos)}</strong> video — tổng {total_size:.1f} MB</p>", unsafe_allow_html=True)
    st.divider()

    if not videos:
        st.info("Không có video nào phù hợp với bộ lọc.")
        render_footer()
        return

    for v in videos:
        c1, c2, c3 = st.columns([3, 2, 1])
        with c1:
            st.markdown(f"**`{v['tracking_code']}`** — {v['full_name']}")
            st.markdown(f"<p style='color:#111827;font-size:0.82rem;margin:0.1rem 0;'>{v['start_time']}  |  {v['duration_sec']}s  |  {v['file_size_mb']} MB</p>", unsafe_allow_html=True)
        with c2:
            st.markdown(f"<p style='color:#111827;font-size:0.82rem;margin:0.1rem 0;'>📁 {v['file_name']}</p>", unsafe_allow_html=True)
        with c3:
            if os.path.exists(v["file_path"]):
                with open(v["file_path"], "rb") as f:
                    st.download_button("⬇", data=f, file_name=v["file_name"],
                                       mime="video/mp4", key=f"dl2_{v['video_id']}")
        st.divider()
    render_footer()


# ═══════════════════════════════════════════════════════════════════════════════
#  TRANG: QUẢN LÝ NHÂN VIÊN (Admin)
# ═══════════════════════════════════════════════════════════════════════════════

def page_employees():
    render_page_header("👥", "Quản lý nhân viên", "Thêm, xóa và cấp lại mật khẩu nhân viên")

    tab_list, tab_add, tab_pwd = st.tabs(["Danh sách", "Thêm nhân viên", "Đổi mật khẩu"])

    with tab_list:
        emps = get_all_employees()
        for e in emps:
            col1, col2, col3, col4 = st.columns([3, 2, 1, 1])
            col1.markdown(f"**{e['full_name']}** (`{e['username']}`)")
            col2.markdown(f"<p style='color:#111827;font-size:0.82rem;margin:0.1rem 0;'>{e['employee_code']} | Tạo: {e['created_at'][:10]}</p>", unsafe_allow_html=True)
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
        st.markdown("#### Đổi mật khẩu nhân viên")
        emps    = get_all_employees()
        emp_map = {e["full_name"]: e for e in emps}

        sel_emp_name = st.selectbox("Chọn nhân viên", list(emp_map.keys()), key="pwd_emp_sel")

        if sel_emp_name:
            emp = emp_map[sel_emp_name]
            st.markdown(f"""
            <div style="background:#f0faf5;border:1px solid #a0d9b4;border-radius:10px;
                        padding:0.75rem 1.2rem;margin:0.4rem 0 1rem;">
                <div style="font-size:0.72rem;color:#2d6a4f;font-weight:700;
                            letter-spacing:0.05em;margin-bottom:0.45rem;">THÔNG TIN TÀI KHOẢN</div>
                <div style="display:flex;gap:2rem;">
                    <div>
                        <span style="color:#6b7280;font-size:0.8rem;">Tên đăng nhập</span><br>
                        <strong style="color:#111827;font-size:0.95rem;">{emp['username']}</strong>
                    </div>
                    <div>
                        <span style="color:#6b7280;font-size:0.8rem;">Mã nhân viên</span><br>
                        <strong style="color:#111827;font-size:0.95rem;">{emp['employee_code'] or '—'}</strong>
                    </div>
                    <div>
                        <span style="color:#6b7280;font-size:0.8rem;">Họ và tên</span><br>
                        <strong style="color:#111827;font-size:0.95rem;">{emp['full_name']}</strong>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)

            with st.form("pwd_form", clear_on_submit=True):
                col_a, col_b = st.columns(2)
                new_pw  = col_a.text_input("🔑 Mật khẩu mới", type="password",
                                           placeholder="Nhập mật khẩu mới...")
                conf_pw = col_b.text_input("✅ Xác nhận mật khẩu mới", type="password",
                                           placeholder="Nhập lại mật khẩu mới...")
                pwd_submitted = st.form_submit_button("Cập nhật mật khẩu",
                                                      type="primary", use_container_width=True)

            if pwd_submitted:
                if not all([new_pw, conf_pw]):
                    st.warning("Vui lòng điền đầy đủ tất cả các trường.")
                elif new_pw != conf_pw:
                    st.error("❌ Mật khẩu mới và xác nhận không khớp.")
                elif len(new_pw) < 6:
                    st.warning("Mật khẩu mới phải có ít nhất 6 ký tự.")
                else:
                    reset_password(emp["user_id"], new_pw)
                    st.success(f"✅ Đã đổi mật khẩu cho **{sel_emp_name}** thành công.")
    render_footer()


# ═══════════════════════════════════════════════════════════════════════════════
#  TRANG: THỐNG KÊ (Admin)
# ═══════════════════════════════════════════════════════════════════════════════

def page_stats():
    render_page_header("📈", "Thống kê & Báo cáo", "Phân tích năng suất nhân viên theo khoảng thời gian")

    try:
        import plotly.express as px
        import plotly.graph_objects as go
        HAS_PLOTLY = True
    except ImportError:
        HAS_PLOTLY = False

    col_f, col_t = st.columns(2)
    date_from = col_f.date_input("Từ ngày", value=date.today())
    date_to   = col_t.date_input("Đến ngày", value=date.today())

    if date_from > date_to:
        st.warning("Ngày bắt đầu phải nhỏ hơn hoặc bằng ngày kết thúc.")
        render_footer()
        return

    stats = get_stats_by_employee(str(date_from), str(date_to))

    if not stats:
        st.info("Không có dữ liệu cho ngày này.")
        render_footer()
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
    render_footer()


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
        elif "Đơn hàng" in page:
            page_orders()
        elif "video" in page.lower():
            page_video_management()
        elif "Nhân viên" in page:
            page_employees()
        else:
            page_stats()


if __name__ == "__main__":
    main()
