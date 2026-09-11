import telebot
import json
import time
import requests
import os
import psutil  
import imaplib
import email
import re
import shutil
import random
import threading
from queue import Queue
from threading import Thread
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
from datetime import datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError

# ==================== CẤU HÌNH HỆ THỐNG ====================
TOKEN = "7990637056:AAFm5RzSQokBVLQdlgnAE6ILqNYFTrl8CyU"
ADMIN_IDS_RAW = os.getenv("ADMIN_IDS", "7497594902,1234567890")
ADMIN_IDS = [int(x.strip()) for x in ADMIN_IDS_RAW.split(",") if x.strip().isdigit()]

bot = telebot.TeleBot(TOKEN)

# Hệ thống hàng đợi xử lý tập trung duy nhất
PLAYWRIGHT_QUEUE = Queue()

ACTIVE_BROWSERS = {}
STATUS_TRACKER = {} 

AUTO_STATUS_RUNNING = False
AUTO_STATUS_MESSAGE_ID = None
LOG_NEEDS_REPOST = False

# Trạng thái chờ upload file
UPLOAD_STATE = {}

def load_accounts():
    with open("accounts.json", "r", encoding="utf-8") as f:
        return json.load(f)

def is_admin(message):
    return message.from_user.id in ADMIN_IDS

def get_vietnam_time():
    tz_vietnam = timezone(timedelta(hours=7))
    return datetime.now(tz_vietnam).strftime('%H:%M:%S')

def get_hardware_status():
    cpu_usage = psutil.cpu_percent(interval=None)
    ram_info = psutil.virtual_memory()
    ram_usage = ram_info.percent
    ram_used_gb = round(ram_info.used / (1024**3), 2)
    ram_total_gb = round(ram_info.total / (1024**3), 2)
    return cpu_usage, ram_usage, ram_used_gb, ram_total_gb

def get_github_otp_from_imap(gmail_user, gmail_pass, chat_id=None, repo_name=""):
    """Lấy mã OTP từ Gmail, trả về mã hoặc None. Nếu có chat_id, gửi thông báo debug."""
    if not gmail_user or not gmail_pass:
        if chat_id:
            bot.send_message(chat_id, f"⚠️ {repo_name}: Thiếu thông tin Gmail.")
        return None
    mail = None
    try:
        mail = imaplib.IMAP4_SSL("imap.gmail.com")
        mail.login(gmail_user, gmail_pass)
        for folder in ["inbox", "[Gmail]/Spam"]:
            try:
                mail.select(folder)
                status, data = mail.search(None, '(FROM "noreply@github.com")')
                if status != "OK":
                    continue
                mail_ids = data[0].split()
                if not mail_ids:
                    continue
                for m_id in reversed(mail_ids[-10:]):
                    status, msg_data = mail.fetch(m_id, "(RFC822)")
                    if status != "OK":
                        continue
                    raw_email = msg_data[0][1]
                    msg = email.message_from_bytes(raw_email)
                    subject = str(msg.get("Subject", ""))
                    if "verification code" in subject.lower() or "device verification" in subject.lower() or "github" in subject.lower():
                        body = ""
                        if msg.is_multipart():
                            for part in msg.walk():
                                if part.get_content_type() == "text/plain":
                                    body = part.get_payload(decode=True).decode(errors="ignore")
                                    break
                        else:
                            body = msg.get_payload(decode=True).decode(errors="ignore")
                        otp_match = re.search(r'\b\d{6}\b', body)
                        if otp_match:
                            otp_code = otp_match.group(0)
                            return otp_code
            except Exception as e:
                print(f"Lỗi khi đọc thư mục {folder}: {e}")
                continue
        if chat_id:
            bot.send_message(chat_id, f"⚠️ {repo_name}: Không tìm thấy email OTP trong Inbox hoặc Spam.")
        return None
    except Exception as e:
        if chat_id:
            bot.send_message(chat_id, f"❌ {repo_name}: Lỗi IMAP: {str(e)[:80]}")
        print(f"Lỗi IMAP: {e}")
        return None
    finally:
        if mail:
            try:
                mail.logout()
            except:
                pass

def create_codespace_via_api(token, repo_url, max_retries=3):
    """Start codespace có sẵn của repo qua API GitHub.
    KHÔNG tạo codespace mới. Nếu repo không có codespace → trả None.
    Nếu codespace đang Shutdown → gọi start.
    Nếu codespace đang Available/Starting → trả web_url luôn (không start lại).
    Nếu start fail → retry tối đa max_retries lần.
    Trả về web_url nếu thành công, None nếu thất bại."""
    repo_path = repo_url.replace("https://github.com/", "").strip("/")
    api_url = f"https://api.github.com/repos/{repo_path}/codespaces"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28"
    }
    
    # Lấy danh sách codespace của repo
    try:
        res = requests.get(api_url, headers=headers, timeout=15)
    except Exception as e:
        print(f"Lỗi GET codespaces cho {repo_path}: {e}")
        return None
    
    if res.status_code != 200:
        print(f"GET codespaces trả về {res.status_code} cho {repo_path}")
        return None
    
    codespaces = res.json().get("codespaces", [])
    if not codespaces:
        print(f"❌ Repo {repo_path} không có codespace nào. KHÔNG tạo mới.")
        return None
    
    # Chỉ lấy codespace đầu tiên (theo yêu cầu: 1 repo = 1 codespace)
    cs = codespaces[0]
    cs_name = cs["name"]
    cs_state = str(cs.get("state", "")).lower()
    cs_web_url = cs.get("web_url")
    
    # Nếu codespace đã Available / Active / Starting → dùng luôn
    if cs_state in ["available", "active", "starting", "awaiting"]:
        print(f"ℹ️ Codespace {cs_name} đang state='{cs_state}', dùng web_url có sẵn.")
        return cs_web_url
    
    # Nếu codespace đang ShuttingDown hoặc Provisioning → chờ ngắn rồi thử lại
    if cs_state in ["shuttingdown", "shutting_down", "provisioning", "queued", "created"]:
        print(f"⏳ Codespace {cs_name} đang state='{cs_state}', chờ 5s...")
        time.sleep(5)
        # Refresh state
        try:
            res2 = requests.get(api_url, headers=headers, timeout=15)
            if res2.status_code == 200:
                codespaces2 = res2.json().get("codespaces", [])
                if codespaces2:
                    cs = codespaces2[0]
                    cs_name = cs["name"]
                    cs_state = str(cs.get("state", "")).lower()
                    cs_web_url = cs.get("web_url")
                    if cs_state in ["available", "active", "starting", "awaiting"]:
                        return cs_web_url
        except Exception as e:
            print(f"Lỗi refresh codespace: {e}")
    
    # Nếu codespace đang Shutdown → gọi start với retry
    if cs_state in ["shutdown", "unknown"]:
        start_url = f"https://api.github.com/user/codespaces/{cs_name}/start"
        for attempt in range(1, max_retries + 1):
            try:
                start_res = requests.post(start_url, headers=headers, timeout=15)
                if start_res.status_code in [200, 202]:
                    print(f"✅ Đã start codespace {cs_name} (lần {attempt}).")
                    return cs_web_url
                else:
                    print(f"⚠️ Start codespace lần {attempt} trả về {start_res.status_code}")
            except Exception as e:
                print(f"Lỗi start codespace (lần {attempt}): {e}")
            if attempt < max_retries:
                time.sleep(2 ** attempt)
        
        print(f"❌ Start codespace {cs_name} thất bại sau {max_retries} lần. KHÔNG tạo mới.")
        return None
    
    # Các state khác (failed, deleted, unavailable, moved, archived, exporting, rebuilding, updating)
    print(f"❌ Codespace {cs_name} ở state='{cs_state}' không start được. KHÔNG tạo mới.")
    return None

# ====================================================================
# [DEPRECATED - ĐÃ COMMENT OUT]
# Hàm clean_all_active_codespaces trước đây được gọi trong start_all:
#   - GET /user/codespaces → POST stop cho codespace state == "active"
# Lý do comment out:
#   - KHÔNG chờ codespace shutdown xong (GitHub API trả 202 ngay,
#     quá trình shutdown thực tế mất 2-5 giây)
#   - Filter state quá hẹp (chỉ "active", bỏ qua "starting", "available")
#   - start_all gọi hàm này chạy ngầm rồi sleep 2s → không kịp stop
#   - Kết quả: codespace không thực sự stop → tài nguyên không hồi
# Thay thế bằng: stop_target_repos_codespaces(token, repo_urls) — hàm mới
#   có chờ (poll) và filter state đúng.
# ====================================================================
# def clean_all_active_codespaces(token):
#     api_url = "https://api.github.com/user/codespaces"
#     headers = {
#         "Authorization": f"Bearer {token}",
#         "Accept": "application/vnd.github+json",
#         "X-GitHub-Api-Version": "2022-11-28"
#     }
#     try:
#         res = requests.get(api_url, headers=headers, timeout=15)
#         if res.status_code == 200:
#             codespaces = res.json().get("codespaces", [])
#             for cs in codespaces:
#                 if str(cs.get("state", "")).lower() == "active":
#                     cs_name = cs["name"]
#                     stop_url = f"https://api.github.com/user/codespaces/{cs_name}/stop"
#                     requests.post(stop_url, headers=headers, timeout=15)
#     except Exception as e:
#         print(f"Lỗi dọn dẹp: {e}")

def stop_target_repos_codespaces(token, repo_urls, chat_id=None):
    """Stop codespaces của các repo được chỉ định qua API GitHub.
    - Với mỗi repo_url: GET /repos/{owner}/{repo}/codespaces
    - POST stop cho mọi codespace có state != shutdown
    - Poll tối đa 15 giây, mỗi 2 giây để kiểm tra đã shutdown hết chưa
    Trả về True nếu tất cả codespace đã shutdown, False nếu timeout."""
    if not repo_urls:
        return True
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28"
    }
    
    # Bước 1: Gửi stop cho tất cả codespace của từng repo
    all_cs_names = []
    for repo_url in repo_urls:
        repo_path = repo_url.replace("https://github.com/", "").strip("/")
        try:
            res = requests.get(
                f"https://api.github.com/repos/{repo_path}/codespaces",
                headers=headers, timeout=15
            )
            if res.status_code == 200:
                codespaces = res.json().get("codespaces", [])
                for cs in codespaces:
                    state = str(cs.get("state", "")).lower()
                    if state not in ["shutdown", "shutting_down", "shuttingdown"]:
                        cs_name = cs["name"]
                        stop_url = f"https://api.github.com/user/codespaces/{cs_name}/stop"
                        try:
                            requests.post(stop_url, headers=headers, timeout=15)
                            all_cs_names.append(cs_name)
                            print(f"🛑 Đã gửi stop cho codespace {cs_name}")
                        except Exception as e:
                            print(f"Lỗi stop {cs_name}: {e}")
        except Exception as e:
            print(f"Lỗi GET codespaces cho {repo_path}: {e}")
    
    if not all_cs_names:
        print("ℹ️ Không có codespace nào cần stop (đã shutdown sẵn).")
        return True
    
    # Bước 2: Poll đến khi tất cả shutdown (max 15s, mỗi 2s)
    print(f"⏳ Đang chờ {len(all_cs_names)} codespace shutdown (tối đa 15s)...")
    
    max_wait = 15
    poll_interval = 2
    elapsed = 0
    
    while elapsed < max_wait:
        time.sleep(poll_interval)
        elapsed += poll_interval
        
        all_shutdown = True
        for repo_url in repo_urls:
            repo_path = repo_url.replace("https://github.com/", "").strip("/")
            try:
                res = requests.get(
                    f"https://api.github.com/repos/{repo_path}/codespaces",
                    headers=headers, timeout=15
                )
                if res.status_code == 200:
                    codespaces = res.json().get("codespaces", [])
                    for cs in codespaces:
                        state = str(cs.get("state", "")).lower()
                        if state != "shutdown":
                            all_shutdown = False
                            break
                    if not all_shutdown:
                        break
            except Exception as e:
                print(f"Lỗi poll {repo_path}: {e}")
                all_shutdown = False
                break
        
        if all_shutdown:
            print(f"✅ Tất cả codespace đã shutdown sau {elapsed}s.")
            return True
    
    print(f"⚠️ Timeout sau {max_wait}s, một số codespace có thể chưa shutdown hẳn.")
    return False

# ==================== HÀM HELPER XỬ LÝ RELOAD CODESPACE ====================
def handle_codespace_reload(page):
    """Kiểm tra và bấm nút Reload nếu Codespace mất kết nối. Trả về True nếu đã reload."""
    reload_clicked = False
    try:
        reload_selectors = [
            "button:has-text('Reload')",
            "a:has-text('Reload')",
            "button:text('Reload')",
            "[role='button']:has-text('Reload')"
        ]
        for selector in reload_selectors:
            try:
                locator = page.locator(selector).first
                if locator.is_visible(timeout=1000):
                    locator.click(timeout=3000)
                    reload_clicked = True
                    print("🔄 Đã bấm nút Reload Codespace.")
                    time.sleep(5)
                    break
            except Exception:
                continue
        if not reload_clicked:
            try:
                disconnected = page.locator("text=Disconnected from Codespaces").first
                if disconnected.is_visible(timeout=1000):
                    page.keyboard.press("Enter")
                    reload_clicked = True
                    print("🔄 Đã nhấn Enter để reload Codespace.")
                    time.sleep(5)
            except Exception:
                pass
    except Exception as e:
        print(f"Lỗi khi xử lý reload: {e}")
    return reload_clicked

def wait_for_terminal_with_reload(page, repo_name, chat_id, max_iterations=45, sleep_interval=4):
    """Vòng lặp chờ Terminal, tự động xử lý reload khi mất kết nối. Trả về True nếu terminal sẵn sàng."""
    terminal_ready = False
    reload_attempts = 0
    max_reload_attempts = 5
    for _ in range(max_iterations):
        time.sleep(sleep_interval)
        try:
            has_loading = page.locator("text=Setting up remote connection, text=Opening Remote, text=Building codespace").first.is_visible()
            has_terminal = page.locator(".terminal, .xterm, .integrated-terminal-panel").first.is_visible()
            if not has_loading and has_terminal:
                terminal_ready = True
                break
            if reload_attempts < max_reload_attempts:
                if handle_codespace_reload(page):
                    reload_attempts += 1
                    print(f"🔄 Đã reload lần {reload_attempts} cho {repo_name}")
        except Exception as e:
            print(f"Lỗi trong wait_for_terminal cho {repo_name}: {e}")
            if reload_attempts < max_reload_attempts:
                try:
                    handle_codespace_reload(page)
                    reload_attempts += 1
                except:
                    pass
    return terminal_ready

# ==================== HÀM HELPER CHỤP ẢNH DEBUG ====================
def send_debug_screenshot(page, repo_name, chat_id, status_text):
    """Chụp ảnh màn hình hiện tại và gửi về Telegram, sau đó xóa file."""
    screenshot_path = None
    try:
        timestamp = int(time.time())
        screenshot_path = f"debug_{repo_name}_{timestamp}.png"
        page.screenshot(path=screenshot_path, full_page=False)
        if os.path.exists(screenshot_path):
            with open(screenshot_path, "rb") as photo:
                bot.send_photo(
                    chat_id,
                    photo,
                    caption=f"🔍 **DEBUG - {repo_name.upper()}**\n🕒 {get_vietnam_time()}\n📌 {status_text}",
                    parse_mode="Markdown"
                )
    except Exception as e:
        print(f"Lỗi chụp ảnh debug cho {repo_name}: {e}")
    finally:
        if screenshot_path and os.path.exists(screenshot_path):
            try:
                os.remove(screenshot_path)
            except:
                pass

# ==================== LÕI XỬ LÝ HÀNG ĐỢI TẬP TRUNG ====================
def playwright_queue_processor():
    print("🚀 Đã kích hoạt lõi xử lý hàng đợi tập trung...")
    while True:
        try:
            task = PLAYWRIGHT_QUEUE.get()
            task_type = task.get("type")
            try:
                if task_type == "account_batch":
                    process_account_batch_task(task)
                # ====================================================================
                # [DEPRECATED - ĐÃ COMMENT OUT nhánh "login"]
                # Nhánh này trước đây xử lý task type "login" bằng cách gọi
                # process_login_task(task) — hàm này đã bị comment out do
                # reset_multiple_bots chuyển sang dùng task "account_batch" (3 phase).
                # Nếu cần khôi phục: bỏ comment 2 dòng dưới và bỏ comment hàm
                # process_login_task ở phía dưới.
                # ====================================================================
                # elif task_type == "login":
                #     process_login_task(task)
                elif task_type == "resetcmd":
                    process_resetcmd_task(task)
                elif task_type == "screenshot":
                    process_screenshot_task(task)
            except Exception as e:
                print(f"Lỗi hệ thống khi chạy Task [{task_type}]: {e}")
            finally:
                PLAYWRIGHT_QUEUE.task_done()
        except Exception as e:
            print(f"Lỗi nghiêm trọng trong queue processor: {e}")
            time.sleep(1)

def process_account_batch_task(task):
    acc = task["acc"]
    chat_id = task["chat_id"]
    repos = task.get("repos", acc["repos"])
    mode = task.get("mode", "startall")
    
    print(f"📥 Bắt đầu account_batch (mode={mode}) với {len(repos)} repo cho account {acc['account_id']}")
    
    account_otp_lock = threading.Lock()
    max_workers = min(len(repos), 2)
    
    # ==================== PHASE 1: LOGIN SONG SONG ====================
    print(f"🔐 PHASE 1: Login song song cho {len(repos)} repo...")
    login_results = {}
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {}
        for index, repo in enumerate(repos):
            future = executor.submit(login_only_pipeline, acc, repo, chat_id, account_otp_lock, index)
            futures[future] = repo
        for future in futures:
            repo = futures[future]
            try:
                result = future.result(timeout=600)
                login_results[repo["name"]] = bool(result)
                print(f"  → {repo['name']}: login={'OK' if result else 'FAIL'}")
            except FutureTimeoutError:
                print(f"  → {repo['name']}: login TIMEOUT, hủy future")
                login_results[repo["name"]] = False
                future.cancel()
            except Exception as e:
                print(f"  → {repo['name']}: login EXCEPTION {e}")
                login_results[repo["name"]] = False
    
    success_repos = [r for r in repos if login_results.get(r["name"], False)]
    if not success_repos:
        print("❌ Không có repo nào login thành công. Bỏ qua Phase 2 và 3.")
        return
    
    # ==================== PHASE 2: STOP CODESPACE QUA API ====================
    print(f"🛑 PHASE 2: Stop codespace cho {len(success_repos)} repo đã login thành công...")
    repo_urls_to_stop = [r["url"] for r in success_repos]
    stop_target_repos_codespaces(acc["github_token"], repo_urls_to_stop, chat_id)
    
    # ==================== PHASE 3: START CODESPACE CÓ SẴN ====================
    print(f"🚀 PHASE 3: Start codespace có sẵn cho {len(success_repos)} repo...")
    with ThreadPoolExecutor(max_workers=min(len(success_repos), 2)) as executor:
        futures = []
        for index, repo in enumerate(success_repos):
            future = executor.submit(start_new_codespace_pipeline, acc, repo, chat_id, index, account_otp_lock)
            futures.append(future)
        for future in futures:
            try:
                future.result(timeout=600)
            except FutureTimeoutError:
                print(f"Phase 3 timeout, hủy future")
                future.cancel()
            except Exception as e:
                print(f"Phase 3 thất bại: {e}")
    
    print(f"✅ Hoàn tất account_batch (mode={mode}) cho account {acc['account_id']}")

def login_only_pipeline(acc, repo, chat_id, otp_lock, bot_index=0):
    """PHASE 1: Chỉ login vào GitHub, không chờ terminal, không mở terminal mới.
    Trả về True nếu login thành công, False nếu fail.
    Cookie được lưu vào browser_profiles để Phase 3 dùng lại."""
    global LOG_NEEDS_REPOST
    repo_name = repo["name"]
    
    if bot_index > 0:
        delay_time = bot_index * 25
        STATUS_TRACKER[repo_name]["status"] = f"💤 Phase 1: Giãn cách (Chờ {delay_time}s)..."
        STATUS_TRACKER[repo_name]["last_update"] = time.time()
        time.sleep(delay_time)
    
    STATUS_TRACKER[repo_name]["status"] = "🔐 Phase 1: Đang chuẩn bị login..."
    STATUS_TRACKER[repo_name]["last_update"] = time.time()
    
    web_url = create_codespace_via_api(acc["github_token"], repo["url"])
    if not web_url:
        STATUS_TRACKER[repo_name]["status"] = "❌ Phase 1: Không có codespace để start (không tạo mới)"
        STATUS_TRACKER[repo_name]["last_update"] = time.time()
        return False
    
    with sync_playwright() as p:
        context = None
        is_locked = False
        try:
            STATUS_TRACKER[repo_name]["status"] = "Phase 1: Khởi động trình duyệt..."
            STATUS_TRACKER[repo_name]["last_update"] = time.time()
            ram_optimize_args = [
                "--no-sandbox", "--disable-setuid-sandbox", "--disable-gpu",
                "--disable-dev-shm-usage", "--js-flags=--max-old-space-size=100",
                "--disable-extensions", "--mute-audio"
            ]
            user_data_dir = f"./browser_profiles/{repo_name}"
            context = p.chromium.launch_persistent_context(user_data_dir, headless=True, args=ram_optimize_args)
            page = context.new_page()
            
            page.route("**/*", lambda route: route.abort() if route.request.resource_type in ["image", "media", "font"] else route.continue_())
            
            if otp_lock:
                otp_lock.acquire()
                is_locked = True
            
            STATUS_TRACKER[repo_name]["status"] = "Phase 1: Đang tải trang..."
            STATUS_TRACKER[repo_name]["last_update"] = time.time()
            page.goto(web_url, timeout=30000, wait_until="commit")
            
            for _ in range(16):
                if page.locator("div.workbench, div#monaco-parts-splash, .monaco-workbench, input[name='login']").first.is_visible(): break
                time.sleep(0.5)
            
            is_workspace = page.locator("div.workbench, div#monaco-parts-splash, .monaco-workbench").is_visible()
            if not is_workspace:
                if page.locator("input[name='login']").is_visible() or "login" in page.url.lower():
                    STATUS_TRACKER[repo_name]["status"] = "Phase 1: Đang đăng nhập..."
                    STATUS_TRACKER[repo_name]["last_update"] = time.time()
                    
                    username = acc.get("account_id", "").strip()
                    password = acc.get("github_password", "").strip()
                    if not username or not password:
                        STATUS_TRACKER[repo_name]["status"] = "❌ Phase 1: Thiếu username/password"
                        STATUS_TRACKER[repo_name]["last_update"] = time.time()
                        send_debug_screenshot(page, repo_name, chat_id, "Phase 1: Thiếu username/password")
                        if is_locked:
                            otp_lock.release()
                            is_locked = False
                        return False
                    
                    page.fill("input[name='login']", username)
                    page.fill("input[name='password']", password)
                    page.click("input[type='submit']")
                    time.sleep(3)
                    
                    error_element = page.locator(".flash-error, #js-flash-container .flash-error, div.flash-error")
                    if error_element.count() > 0 and error_element.is_visible():
                        error_text = error_element.inner_text()
                        STATUS_TRACKER[repo_name]["status"] = "❌ Phase 1: Đăng nhập thất bại"
                        STATUS_TRACKER[repo_name]["last_update"] = time.time()
                        send_debug_screenshot(page, repo_name, chat_id, f"Phase 1 login lỗi: {error_text[:100]}")
                        if is_locked:
                            otp_lock.release()
                            is_locked = False
                        return False
                    
                    for _ in range(16):
                        if page.locator("div.workbench, input[id='app_totp'], input[id='otp'], input[name='otp']").first.is_visible(): break
                        time.sleep(0.5)
                    
                    if page.locator("input[id='app_totp'], input[id='otp'], input[name='otp'], input[id='verification_code']").first.is_visible():
                        STATUS_TRACKER[repo_name]["status"] = "Phase 1: Đang quét OTP từ Gmail..."
                        STATUS_TRACKER[repo_name]["last_update"] = time.time()
                        received_code = None
                        for _ in range(20):
                            received_code = get_github_otp_from_imap(
                                acc.get("gmail_login", ""),
                                acc.get("gmail_app_password", ""),
                                chat_id=chat_id,
                                repo_name=repo_name
                            )
                            if received_code: break
                            time.sleep(5)
                        
                        if received_code:
                            STATUS_TRACKER[repo_name]["status"] = f"Phase 1: Xác thực OTP ({received_code})..."
                            STATUS_TRACKER[repo_name]["last_update"] = time.time()
                            page.locator("input[id='app_totp'], input[id='otp'], input[name='otp'], input[id='verification_code']").fill(received_code)
                            page.keyboard.press("Enter")
                            for _ in range(20):
                                if page.locator("div.workbench, .monaco-workbench").first.is_visible(): break
                                time.sleep(0.5)
                        else:
                            STATUS_TRACKER[repo_name]["status"] = "❌ Phase 1: Kẹt OTP Gmail"
                            STATUS_TRACKER[repo_name]["last_update"] = time.time()
                            send_debug_screenshot(page, repo_name, chat_id, "Phase 1: Không lấy được OTP sau 20 lần thử")
                            if is_locked:
                                otp_lock.release()
                                is_locked = False
                            return False
            
            try:
                page.locator("div.workbench, .monaco-workbench").wait_for(state="visible", timeout=15000)
            except:
                pass
            
            if is_locked:
                otp_lock.release()
                is_locked = False
            
            STATUS_TRACKER[repo_name]["status"] = "✅ Phase 1: Login OK, đã lưu cookie"
            STATUS_TRACKER[repo_name]["last_update"] = time.time()
            return True
        except Exception as e:
            STATUS_TRACKER[repo_name]["status"] = f"❌ Phase 1 lỗi: {str(e)[:40]}"
            STATUS_TRACKER[repo_name]["last_update"] = time.time()
            try:
                if 'page' in locals():
                    send_debug_screenshot(page, repo_name, chat_id, f"Phase 1 Exception: {str(e)[:50]}")
            except:
                pass
            return False
        finally:
            if is_locked:
                otp_lock.release()
            if context:
                context.close()

def start_new_codespace_pipeline(acc, repo, chat_id, bot_index=0, otp_lock=None):
    """PHASE 3: Start codespace có sẵn (không tạo mới) và vào workspace,
    chờ terminal, mở terminal mới.
    Sử dụng cookie đã lưu từ Phase 1."""
    global LOG_NEEDS_REPOST
    repo_name = repo["name"]
    
    if bot_index > 0:
        delay_time = bot_index * 25
        STATUS_TRACKER[repo_name]["status"] = f"💤 Phase 3: Giãn cách (Chờ {delay_time}s)..."
        STATUS_TRACKER[repo_name]["last_update"] = time.time()
        time.sleep(delay_time)
    
    STATUS_TRACKER[repo_name]["status"] = "🚀 Phase 3: Đang start codespace có sẵn..."
    STATUS_TRACKER[repo_name]["last_update"] = time.time()
    
    web_url = create_codespace_via_api(acc["github_token"], repo["url"])
    if not web_url:
        STATUS_TRACKER[repo_name]["status"] = "❌ Phase 3: Không start được codespace (không tạo mới)"
        STATUS_TRACKER[repo_name]["last_update"] = time.time()
        return
    
    with sync_playwright() as p:
        context = None
        is_locked = False
        try:
            STATUS_TRACKER[repo_name]["status"] = "Phase 3: Khởi động trình duyệt..."
            STATUS_TRACKER[repo_name]["last_update"] = time.time()
            ram_optimize_args = [
                "--no-sandbox", "--disable-setuid-sandbox", "--disable-gpu",
                "--disable-dev-shm-usage", "--js-flags=--max-old-space-size=100",
                "--disable-extensions", "--mute-audio"
            ]
            user_data_dir = f"./browser_profiles/{repo_name}"
            context = p.chromium.launch_persistent_context(user_data_dir, headless=True, args=ram_optimize_args)
            page = context.new_page()
            
            page.route("**/*", lambda route: route.abort() if route.request.resource_type in ["image", "media", "font"] else route.continue_())
            
            STATUS_TRACKER[repo_name]["status"] = "Phase 3: Đang tải trang kết nối..."
            STATUS_TRACKER[repo_name]["last_update"] = time.time()
            page.goto(web_url, timeout=30000, wait_until="commit")
            
            for _ in range(16):
                if page.locator("div.workbench, div#monaco-parts-splash, .monaco-workbench, input[name='login']").first.is_visible(): break
                time.sleep(0.5)
            
            is_workspace = page.locator("div.workbench, div#monaco-parts-splash, .monaco-workbench").is_visible()
            
            if not is_workspace:
                if page.locator("input[name='login']").is_visible() or "login" in page.url.lower():
                    STATUS_TRACKER[repo_name]["status"] = "Phase 3: Cookie hết hạn, đang login lại..."
                    STATUS_TRACKER[repo_name]["last_update"] = time.time()
                    
                    if otp_lock:
                        otp_lock.acquire()
                        is_locked = True
                    
                    username = acc.get("account_id", "").strip()
                    password = acc.get("github_password", "").strip()
                    if not username or not password:
                        STATUS_TRACKER[repo_name]["status"] = "❌ Phase 3: Thiếu username/password"
                        STATUS_TRACKER[repo_name]["last_update"] = time.time()
                        return
                    
                    page.fill("input[name='login']", username)
                    page.fill("input[name='password']", password)
                    page.click("input[type='submit']")
                    time.sleep(3)
                    
                    error_element = page.locator(".flash-error, #js-flash-container .flash-error, div.flash-error")
                    if error_element.count() > 0 and error_element.is_visible():
                        error_text = error_element.inner_text()
                        STATUS_TRACKER[repo_name]["status"] = "❌ Phase 3: Login lại thất bại"
                        STATUS_TRACKER[repo_name]["last_update"] = time.time()
                        send_debug_screenshot(page, repo_name, chat_id, f"Phase 3 login lỗi: {error_text[:100]}")
                        if is_locked:
                            otp_lock.release()
                            is_locked = False
                        return
                    
                    for _ in range(16):
                        if page.locator("div.workbench, input[id='app_totp'], input[id='otp'], input[name='otp']").first.is_visible(): break
                        time.sleep(0.5)
                    
                    if page.locator("input[id='app_totp'], input[id='otp'], input[name='otp'], input[id='verification_code']").first.is_visible():
                        STATUS_TRACKER[repo_name]["status"] = "Phase 3: Đang quét OTP..."
                        STATUS_TRACKER[repo_name]["last_update"] = time.time()
                        received_code = None
                        for _ in range(20):
                            received_code = get_github_otp_from_imap(
                                acc.get("gmail_login", ""),
                                acc.get("gmail_app_password", ""),
                                chat_id=chat_id,
                                repo_name=repo_name
                            )
                            if received_code: break
                            time.sleep(5)
                        
                        if received_code:
                            page.locator("input[id='app_totp'], input[id='otp'], input[name='otp'], input[id='verification_code']").fill(received_code)
                            page.keyboard.press("Enter")
                            for _ in range(20):
                                if page.locator("div.workbench, .monaco-workbench").first.is_visible(): break
                                time.sleep(0.5)
                        else:
                            STATUS_TRACKER[repo_name]["status"] = "❌ Phase 3: Kẹt OTP"
                            STATUS_TRACKER[repo_name]["last_update"] = time.time()
                            send_debug_screenshot(page, repo_name, chat_id, "Phase 3: Không lấy được OTP")
                            if is_locked:
                                otp_lock.release()
                                is_locked = False
                            return
                    
                    if is_locked:
                        otp_lock.release()
                        is_locked = False
            
            try:
                page.locator("div.workbench, .monaco-workbench").wait_for(state="visible", timeout=15000)
            except:
                pass
            
            STATUS_TRACKER[repo_name]["status"] = "Phase 3: Đang đợi Codespace nạp Terminal..."
            STATUS_TRACKER[repo_name]["last_update"] = time.time()
            
            terminal_ready = wait_for_terminal_with_reload(page, repo_name, chat_id, max_iterations=45, sleep_interval=4)
            
            if not terminal_ready:
                STATUS_TRACKER[repo_name]["status"] = "❌ Phase 3: Timeout Terminal (GitHub Treo)"
                STATUS_TRACKER[repo_name]["last_update"] = time.time()
                send_debug_screenshot(page, repo_name, chat_id, "Phase 3 Timeout Terminal")
                return
            
            time.sleep(3)
            
            STATUS_TRACKER[repo_name]["status"] = "⌨️ Phase 3: Ép mở Terminal mới..."
            STATUS_TRACKER[repo_name]["last_update"] = time.time()
            page.keyboard.press("F1")
            time.sleep(1)
            page.keyboard.type("Terminal: Create New Terminal")
            time.sleep(0.5)
            page.keyboard.press("Enter")
            
            time.sleep(5)
            screenshot_path = f"success_{repo_name}.png"
            page.screenshot(path=screenshot_path)
            if os.path.exists(screenshot_path):
                with open(screenshot_path, "rb") as photo:
                    bot.send_photo(chat_id, photo, caption=f"🎉 [KÍCH HOẠT THÀNH CÔNG - {repo_name.upper()}]\n✅ Hệ thống đã ép mở Terminal mới ổn định!")
                os.remove(screenshot_path)
                LOG_NEEDS_REPOST = True
            
            STATUS_TRACKER[repo_name]["status"] = "Active: Đã kích hoạt hoàn tất 🟢"
            STATUS_TRACKER[repo_name]["last_update"] = time.time()
            ACTIVE_BROWSERS[repo_name] = {"active": True}
        except Exception as e:
            STATUS_TRACKER[repo_name]["status"] = "❌ Phase 3: Lỗi nạp phiên chạy"
            STATUS_TRACKER[repo_name]["last_update"] = time.time()
            try:
                if 'page' in locals():
                    send_debug_screenshot(page, repo_name, chat_id, f"Phase 3 Exception: {str(e)[:50]}")
            except:
                pass
        finally:
            if is_locked and otp_lock:
                otp_lock.release()
            if context:
                context.close()

# ====================================================================
# [DEPRECATED - ĐÃ COMMENT OUT]
# Hàm run_single_bot_pipeline trước đây xử lý toàn bộ pipeline cho 1 repo
# trong 1 lần chạy duy nhất: create codespace + login + OTP + chờ terminal
# + mở terminal mới.
# Lý do comment out:
#   - Không có bước stop codespace cũ → tài nguyên không hồi.
#   - Không tách biệt login và start → không thể stop codespace sau khi
#     đã login mà trước khi start phiên mới.
# Thay thế bằng:
#   - login_only_pipeline() — Phase 1: login + lưu cookie.
#   - stop_target_repos_codespaces() — Phase 2: stop qua API.
#   - start_new_codespace_pipeline() — Phase 3: start codespace có sẵn.
# Cả 3 hàm được gọi tuần tự trong process_account_batch_task().
# ====================================================================
# def run_single_bot_pipeline(acc, repo, chat_id, otp_lock, bot_index=0):
#     global LOG_NEEDS_REPOST
#     repo_name = repo["name"]
#     
#     if bot_index > 0:
#         delay_time = bot_index * 25
#         STATUS_TRACKER[repo_name]["status"] = f"💤 Giãn cách pha (Chờ {delay_time}s hạ nhiệt CPU)..."
#         STATUS_TRACKER[repo_name]["last_update"] = time.time()
#         time.sleep(delay_time)
#     
#     STATUS_TRACKER[repo_name]["status"] = "Đang điều phối API... 🚀"
#     STATUS_TRACKER[repo_name]["last_update"] = time.time()
#     
#     web_url = create_codespace_via_api(acc["github_token"], repo["url"])
#     if not web_url:
#         STATUS_TRACKER[repo_name]["status"] = "Thất bại: Lỗi API GitHub ❌"
#         return
#
#     with sync_playwright() as p:
#         context = None
#         is_locked = False
#         try:
#             STATUS_TRACKER[repo_name]["status"] = "Khởi động lõi ảo cấu hình... 🌐"
#             STATUS_TRACKER[repo_name]["last_update"] = time.time()
#             ram_optimize_args = [
#                 "--no-sandbox", "--disable-setuid-sandbox", "--disable-gpu",                  
#                 "--disable-dev-shm-usage", "--js-flags=--max-old-space-size=100", 
#                 "--disable-extensions", "--mute-audio"                     
#             ]
#             user_data_dir = f"./browser_profiles/{repo_name}"
#             context = p.chromium.launch_persistent_context(user_data_dir, headless=True, args=ram_optimize_args)
#             page = context.new_page()
#             
#             page.route("**/*", lambda route: route.abort() if route.request.resource_type in ["image", "media", "font"] else route.continue_())
#             
#             if otp_lock:
#                 otp_lock.acquire()
#                 is_locked = True
#                 
#             STATUS_TRACKER[repo_name]["status"] = "Đang tải trang kết nối... ⏳"
#             STATUS_TRACKER[repo_name]["last_update"] = time.time()
#             page.goto(web_url, timeout=30000, wait_until="commit")
#             
#             for _ in range(16):
#                 if page.locator("div.workbench, div#monaco-parts-splash, .monaco-workbench, input[name='login']").first.is_visible(): break
#                 time.sleep(0.5)
#                 
#             is_workspace = page.locator("div.workbench, div#monaco-parts-splash, .monaco-workbench").is_visible()
#             if not is_workspace:
#                 if page.locator("input[name='login']").is_visible() or "login" in page.url.lower():
#                     STATUS_TRACKER[repo_name]["status"] = "Nạp thông tin bảo mật... 🔐"
#                     STATUS_TRACKER[repo_name]["last_update"] = time.time()
#                     
#                     username = acc.get("account_id", "").strip()
#                     password = acc.get("github_password", "").strip()
#                     if not username or not password:
#                         STATUS_TRACKER[repo_name]["status"] = "Offline: Thiếu username hoặc password ❌"
#                         STATUS_TRACKER[repo_name]["last_update"] = time.time()
#                         send_debug_screenshot(page, repo_name, chat_id, "Thiếu username/password trong accounts.json")
#                         if is_locked:
#                             otp_lock.release()
#                             is_locked = False
#                         return
#                     
#                     page.fill("input[name='login']", username)
#                     page.fill("input[name='password']", password)
#                     page.click("input[type='submit']")
#                     time.sleep(3)
#                     
#                     error_element = page.locator(".flash-error, #js-flash-container .flash-error, div.flash-error")
#                     if error_element.count() > 0 and error_element.is_visible():
#                         error_text = error_element.inner_text()
#                         STATUS_TRACKER[repo_name]["status"] = f"Offline: Đăng nhập thất bại ❌"
#                         STATUS_TRACKER[repo_name]["last_update"] = time.time()
#                         send_debug_screenshot(page, repo_name, chat_id, f"Login lỗi: {error_text[:100]}")
#                         if is_locked:
#                             otp_lock.release()
#                             is_locked = False
#                         return
#                     
#                     for _ in range(16):
#                         if page.locator("div.workbench, input[id='app_totp'], input[id='otp'], input[name='otp']").first.is_visible(): break
#                         time.sleep(0.5)
#                         
#                     if page.locator("input[id='app_totp'], input[id='otp'], input[name='otp'], input[id='verification_code']").first.is_visible():
#                         STATUS_TRACKER[repo_name]["status"] = "🤖 Đang quét giải mã OTP từ Gmail..."
#                         STATUS_TRACKER[repo_name]["last_update"] = time.time()
#                         received_code = None
#                         for _ in range(20):
#                             received_code = get_github_otp_from_imap(
#                                 acc.get("gmail_login", ""), 
#                                 acc.get("gmail_app_password", ""),
#                                 chat_id=chat_id,
#                                 repo_name=repo_name
#                             )
#                             if received_code: break
#                             time.sleep(5)
#                             
#                         if received_code:
#                             STATUS_TRACKER[repo_name]["status"] = f"🎯 Xác thực OTP ({received_code})... ⚙️"
#                             STATUS_TRACKER[repo_name]["last_update"] = time.time()
#                             page.locator("input[id='app_totp'], input[id='otp'], input[name='otp'], input[id='verification_code']").fill(received_code)
#                             page.keyboard.press("Enter")
#                             for _ in range(20):
#                                 if page.locator("div.workbench, .monaco-workbench").first.is_visible(): break
#                                 time.sleep(0.5)
#                         else:
#                             STATUS_TRACKER[repo_name]["status"] = "Offline: Kẹt OTP Gmail ❌"
#                             STATUS_TRACKER[repo_name]["last_update"] = time.time()
#                             send_debug_screenshot(page, repo_name, chat_id, "Không lấy được OTP từ Gmail sau 20 lần thử")
#                             if is_locked:
#                                 otp_lock.release()
#                                 is_locked = False
#                             return
#
#             try:
#                 page.locator("div.workbench, .monaco-workbench").wait_for(state="visible", timeout=15000)
#             except:
#                 pass
#
#             if is_locked:
#                 STATUS_TRACKER[repo_name]["status"] = "🔌 Đã vượt OTP, nhường khóa cho bot sau..."
#                 STATUS_TRACKER[repo_name]["last_update"] = time.time()
#                 otp_lock.release()
#                 is_locked = False
#
#             STATUS_TRACKER[repo_name]["status"] = "⏳ Đang đợi Codespace nạp Terminal..."
#             STATUS_TRACKER[repo_name]["last_update"] = time.time()
#             
#             terminal_ready = wait_for_terminal_with_reload(page, repo_name, chat_id, max_iterations=45, sleep_interval=4)
#             
#             if not terminal_ready:
#                 STATUS_TRACKER[repo_name]["status"] = "Offline: Quá thời gian nạp Terminal (GitHub Treo) ❌"
#                 STATUS_TRACKER[repo_name]["last_update"] = time.time()
#                 send_debug_screenshot(page, repo_name, chat_id, "Timeout Terminal - GitHub Treo")
#                 return 
#             
#             time.sleep(3) 
#             
#             STATUS_TRACKER[repo_name]["status"] = "⌨️ Ép mở Terminal mới để chạy lệnh..."
#             STATUS_TRACKER[repo_name]["last_update"] = time.time()
#             page.keyboard.press("F1")
#             time.sleep(1)
#             page.keyboard.type("Terminal: Create New Terminal")
#             time.sleep(0.5)
#             page.keyboard.press("Enter")
#             
#             time.sleep(5)
#             screenshot_path = f"success_{repo_name}.png"
#             page.screenshot(path=screenshot_path)
#             if os.path.exists(screenshot_path):
#                 with open(screenshot_path, "rb") as photo:
#                     bot.send_photo(chat_id, photo, caption=f"🎉 [KÍCH HOẠT THÀNH CÔNG - {repo_name.upper()}]\n✅ Hệ thống đã ép mở Terminal mới ổn định!")
#                 os.remove(screenshot_path)
#                 LOG_NEEDS_REPOST = True  
#                 
#             STATUS_TRACKER[repo_name]["status"] = "Active: Đã kích hoạt hoàn tất 🟢"
#             STATUS_TRACKER[repo_name]["last_update"] = time.time()
#             ACTIVE_BROWSERS[repo_name] = {"active": True}
#         except Exception as e:
#             STATUS_TRACKER[repo_name]["status"] = "Offline: Lỗi nạp phiên chạy ❌"
#             STATUS_TRACKER[repo_name]["last_update"] = time.time()
#             try:
#                 if 'page' in locals():
#                     send_debug_screenshot(page, repo_name, chat_id, f"Exception: {str(e)[:50]}")
#             except:
#                 pass
#         finally:
#             if is_locked:
#                 otp_lock.release()
#             if context:
#                 context.close()

# ====================================================================
# [DEPRECATED - ĐÃ COMMENT OUT]
# Hàm process_login_task trước đây xử lý task type "login":
#   - Nhận 1 repo cụ thể, mở browser, login + OTP, chờ terminal
#   - Không có bước stop codespace → tài nguyên không hồi
# Lý do comment out:
#   - reset_multiple_bots đã chuyển sang dùng task "account_batch"
#     để nhóm các repo theo account, chạy Phase 1-2-3 đầy đủ.
#   - Hàm cũ không còn được gọi từ bất kỳ đâu.
# Nếu cần khôi phục: bỏ comment hàm này và bỏ comment 2 dòng
#   elif task_type == "login": process_login_task(task)
#   trong playwright_queue_processor.
# ====================================================================
# def process_login_task(task):
#     global LOG_NEEDS_REPOST
#     acc, repo, chat_id = task["acc"], task["repo"], task["chat_id"]
#     repo_name = repo["name"]
#     
#     STATUS_TRACKER[repo_name]["status"] = "Đang điều phối API... 🚀"
#     STATUS_TRACKER[repo_name]["last_update"] = time.time()
#     
#     web_url = create_codespace_via_api(acc["github_token"], repo["url"])
#     if not web_url:
#         STATUS_TRACKER[repo_name]["status"] = "Thất bại: Lỗi API GitHub ❌"
#         return
#
#     with sync_playwright() as p:
#         context = None
#         try:
#             STATUS_TRACKER[repo_name]["status"] = "Khởi động lõi ảo cấu hình... 🌐"
#             STATUS_TRACKER[repo_name]["last_update"] = time.time()
#             ram_optimize_args = ["--no-sandbox", "--disable-setuid-sandbox", "--disable-gpu", "--disable-dev-shm-usage", "--js-flags=--max-old-space-size=100", "--disable-extensions", "--mute-audio"]
#             user_data_dir = f"./browser_profiles/{repo_name}"
#             context = p.chromium.launch_persistent_context(user_data_dir, headless=True, args=ram_optimize_args)
#             page = context.new_page()
#             
#             page.route("**/*", lambda route: route.abort() if route.request.resource_type in ["image", "media", "font"] else route.continue_())
#             
#             STATUS_TRACKER[repo_name]["status"] = "Đang tải trang kết nối... ⏳"
#             STATUS_TRACKER[repo_name]["last_update"] = time.time()
#             page.goto(web_url, timeout=30000, wait_until="commit")
#             
#             for _ in range(16):
#                 if page.locator("div.workbench, div#monaco-parts-splash, .monaco-workbench, input[name='login']").first.is_visible(): break
#                 time.sleep(0.5)
#                 
#             is_workspace = page.locator("div.workbench, div#monaco-parts-splash, .monaco-workbench").is_visible()
#             if not is_workspace:
#                 if page.locator("input[name='login']").is_visible() or "login" in page.url.lower():
#                     STATUS_TRACKER[repo_name]["status"] = "Nạp thông tin bảo mật... 🔐"
#                     STATUS_TRACKER[repo_name]["last_update"] = time.time()
#                     
#                     username = acc.get("account_id", "").strip()
#                     password = acc.get("github_password", "").strip()
#                     if not username or not password:
#                         STATUS_TRACKER[repo_name]["status"] = "Offline: Thiếu username hoặc password ❌"
#                         STATUS_TRACKER[repo_name]["last_update"] = time.time()
#                         send_debug_screenshot(page, repo_name, chat_id, "Thiếu username/password trong accounts.json")
#                         return
#                     
#                     page.fill("input[name='login']", username)
#                     page.fill("input[name='password']", password)
#                     page.click("input[type='submit']")
#                     time.sleep(3)
#                     
#                     error_element = page.locator(".flash-error, #js-flash-container .flash-error, div.flash-error")
#                     if error_element.count() > 0 and error_element.is_visible():
#                         error_text = error_element.inner_text()
#                         STATUS_TRACKER[repo_name]["status"] = f"Offline: Đăng nhập thất bại ❌"
#                         STATUS_TRACKER[repo_name]["last_update"] = time.time()
#                         send_debug_screenshot(page, repo_name, chat_id, f"Login lỗi: {error_text[:100]}")
#                         return
#                     
#                     for _ in range(16):
#                         if page.locator("div.workbench, input[id='app_totp'], input[id='otp'], input[name='otp']").first.is_visible(): break
#                         time.sleep(0.5)
#                         
#                     if page.locator("input[id='app_totp'], input[id='otp'], input[name='otp'], input[id='verification_code']").first.is_visible():
#                         STATUS_TRACKER[repo_name]["status"] = "🤖 Đang quét giải mã OTP từ Gmail..."
#                         STATUS_TRACKER[repo_name]["last_update"] = time.time()
#                         received_code = None
#                         for _ in range(20):
#                             received_code = get_github_otp_from_imap(
#                                 acc.get("gmail_login", ""), 
#                                 acc.get("gmail_app_password", ""),
#                                 chat_id=chat_id,
#                                 repo_name=repo_name
#                             )
#                             if received_code: break
#                             time.sleep(5)
#                             
#                         if received_code:
#                             STATUS_TRACKER[repo_name]["status"] = f"🎯 Xác thực OTP ({received_code})... ⚙️"
#                             STATUS_TRACKER[repo_name]["last_update"] = time.time()
#                             page.locator("input[id='app_totp'], input[id='otp'], input[name='otp'], input[id='verification_code']").fill(received_code)
#                             page.keyboard.press("Enter")
#                             for _ in range(20):
#                                 if page.locator("div.workbench, .monaco-workbench").first.is_visible(): break
#                                 time.sleep(0.5)
#                         else:
#                             STATUS_TRACKER[repo_name]["status"] = "Offline: Kẹt OTP Gmail ❌"
#                             STATUS_TRACKER[repo_name]["last_update"] = time.time()
#                             send_debug_screenshot(page, repo_name, chat_id, "Không lấy được OTP từ Gmail sau 20 lần thử")
#                             return
#
#             STATUS_TRACKER[repo_name]["status"] = "⏳ Đang đợi Codespace nạp Terminal..."
#             STATUS_TRACKER[repo_name]["last_update"] = time.time()
#             
#             terminal_ready = wait_for_terminal_with_reload(page, repo_name, chat_id, max_iterations=45, sleep_interval=4)
#             
#             if not terminal_ready:
#                 STATUS_TRACKER[repo_name]["status"] = "Offline: Quá thời gian nạp Terminal (GitHub Treo) ❌"
#                 STATUS_TRACKER[repo_name]["last_update"] = time.time()
#                 send_debug_screenshot(page, repo_name, chat_id, "Timeout Terminal - GitHub Treo")
#                 return
#             
#             time.sleep(3)
#             
#             STATUS_TRACKER[repo_name]["status"] = "⌨️ Ép mở Terminal mới để chạy lệnh..."
#             STATUS_TRACKER[repo_name]["last_update"] = time.time()
#             page.keyboard.press("F1")
#             time.sleep(1)
#             page.keyboard.type("Terminal: Create New Terminal")
#             time.sleep(0.5)
#             page.keyboard.press("Enter")
#             
#             time.sleep(5)
#             screenshot_path = f"success_{repo_name}.png"
#             page.screenshot(path=screenshot_path)
#             if os.path.exists(screenshot_path):
#                 with open(screenshot_path, "rb") as photo:
#                     bot.send_photo(chat_id, photo, caption=f"🎉 [KÍCH HOẠT THÀNH CÔNG - {repo_name.upper()}]\n✅ Hệ thống đã ép mở Terminal mới và kích hoạt toàn bộ chuỗi bot con ổn định!")
#                 os.remove(screenshot_path)
#                 LOG_NEEDS_REPOST = True
#                 
#             STATUS_TRACKER[repo_name]["status"] = "Active: Đã kích hoạt hoàn tất 🟢"
#             STATUS_TRACKER[repo_name]["last_update"] = time.time()
#             ACTIVE_BROWSERS[repo_name] = {"active": True}
#         except Exception as e:
#             STATUS_TRACKER[repo_name]["status"] = "Offline: Lỗi nạp phiên chạy ❌"
#             STATUS_TRACKER[repo_name]["last_update"] = time.time()
#             try:
#                 if 'page' in locals():
#                     send_debug_screenshot(page, repo_name, chat_id, f"Exception: {str(e)[:50]}")
#             except:
#                 pass
#         finally:
#             if context:
#                 context.close()

def process_resetcmd_task(task):
    global LOG_NEEDS_REPOST
    target_repo, chat_id = task["target_repo"], task["chat_id"]
    STATUS_TRACKER[target_repo]["status"] = "⚡ Đang xử lý resetcmd xếp hàng..."
    STATUS_TRACKER[target_repo]["last_update"] = time.time()
    
    accounts = load_accounts()
    found_acc, found_repo = None, None
    for acc in accounts:
        for r in acc["repos"]:
            if r["name"].lower() == target_repo:
                found_acc, found_repo = acc, r
                break
                
    if found_repo:
        web_url = create_codespace_via_api(found_acc["github_token"], found_repo["url"])
        if web_url:
            with sync_playwright() as p:
                context = None
                try:
                    ram_optimize_args = ["--no-sandbox", "--disable-setuid-sandbox", "--disable-gpu", "--disable-dev-shm-usage", "--js-flags=--max-old-space-size=100"]
                    user_data_dir = f"./browser_profiles/{target_repo}"
                    context = p.chromium.launch_persistent_context(user_data_dir, headless=True, args=ram_optimize_args)
                    page = context.new_page()
                    
                    page.route("**/*", lambda route: route.abort() if route.request.resource_type in ["image", "media", "font"] else route.continue_())
                    
                    page.goto(web_url, timeout=30000, wait_until="commit")
                    
                    terminal_ready = wait_for_terminal_with_reload(page, target_repo, chat_id, max_iterations=45, sleep_interval=4)
                    
                    if not terminal_ready:
                        STATUS_TRACKER[target_repo]["status"] = "Offline: Quá thời gian nạp Terminal ❌"
                        STATUS_TRACKER[target_repo]["last_update"] = time.time()
                        bot.send_message(chat_id, f"❌ Timeout Terminal khi reset `{target_repo.upper()}`")
                        LOG_NEEDS_REPOST = True
                        return
                    
                    time.sleep(5)
                    
                    page.keyboard.press("F1")
                    time.sleep(1)
                    page.keyboard.type("Terminal: Kill All Terminals")
                    time.sleep(0.5)
                    page.keyboard.press("Enter")
                    time.sleep(1.5)
                    
                    page.keyboard.press("F1")
                    time.sleep(1)
                    page.keyboard.type("Terminal: Create New Terminal")
                    time.sleep(0.5)
                    page.keyboard.press("Enter")
                    time.sleep(5)
                    
                    screenshot_path = f"reset_cmd_{target_repo}.png"
                    page.screenshot(path=screenshot_path)
                    if os.path.exists(screenshot_path):
                        with open(screenshot_path, "rb") as photo:
                            bot.send_photo(chat_id, photo, caption=f"🎯 [MỚI HOÁ TERMINAL THÀNH CÔNG - {target_repo.upper()}]\n✅ Đã làm mới phiên chạy hoàn tất!")
                        os.remove(screenshot_path)
                        LOG_NEEDS_REPOST = True
                except Exception as e:
                    bot.send_message(chat_id, f"❌ Lỗi xử lý lệnh trên `{target_repo.upper()}`: {str(e)[:80]}")
                    LOG_NEEDS_REPOST = True
                    try:
                        if 'page' in locals():
                            send_debug_screenshot(page, target_repo, chat_id, f"Resetcmd lỗi: {str(e)[:50]}")
                    except:
                        pass
                finally:
                    if context:
                        context.close()
                    
    STATUS_TRACKER[target_repo]["status"] = "Active: Đã kích hoạt hoàn tất 🟢"
    STATUS_TRACKER[target_repo]["last_update"] = time.time()

def process_screenshot_task(task):
    global LOG_NEEDS_REPOST
    target_repo, chat_id = task["target_repo"], task["chat_id"]
    accounts = load_accounts()
    found_acc, found_repo = None, None
    for acc in accounts:
        for r in acc["repos"]:
            if r["name"].lower() == target_repo:
                found_acc, found_repo = acc, r
                break
                
    if found_repo:
        web_url = create_codespace_via_api(found_acc["github_token"], found_repo["url"])
        if web_url:
            with sync_playwright() as p:
                context = None
                try:
                    ram_optimize_args = ["--no-sandbox", "--disable-setuid-sandbox", "--disable-gpu", "--disable-dev-shm-usage"]
                    user_data_dir = f"./browser_profiles/{target_repo}"
                    context = p.chromium.launch_persistent_context(user_data_dir, headless=True, args=ram_optimize_args)
                    page = context.new_page()
                    page.goto(web_url, timeout=30000, wait_until="commit")
                    time.sleep(15)
                    handle_codespace_reload(page)
                    time.sleep(3)
                    temp_shot = f"live_{target_repo}.png"
                    page.screenshot(path=temp_shot)
                    if os.path.exists(temp_shot):
                        with open(temp_shot, "rb") as photo:
                            bot.send_photo(chat_id, photo, caption=f"📸 Ảnh thực tế live của `{target_repo.upper()}`\n🕒 Lúc: `{get_vietnam_time()}`", parse_mode="Markdown")
                        os.remove(temp_shot)
                        LOG_NEEDS_REPOST = True
                except Exception as e:
                    bot.send_message(chat_id, f"❌ Lỗi trích xuất ảnh `{target_repo.upper()}`: {str(e)[:80]}")
                    LOG_NEEDS_REPOST = True
                finally:
                    if context:
                        context.close()

# ==================== CÁC LỆNH TELEGRAM ====================
@bot.message_handler(commands=['resetcmd'])
def reset_terminal_command(message):
    global LOG_NEEDS_REPOST
    if not is_admin(message): return
    parts = message.text.split()
    if len(parts) < 2:
        bot.reply_to(message, "⚠️ Cú pháp chuẩn:\n`/resetcmd bot2 bot3`", parse_mode="Markdown")
        return
    target_repos = []
    for p in parts[1:]:
        name = p.strip().lower()
        if name and name not in target_repos: target_repos.append(name)
            
    bot.reply_to(message, f"⏳ Đã xếp hàng `{len(target_repos)}` mục tiêu vào lõi xử lý tập trung. Tiến trình đang chạy tuần tự...", parse_mode="Markdown")
    LOG_NEEDS_REPOST = True
    active_snapshots = list(ACTIVE_BROWSERS.keys())
    for r in target_repos:
        if r in active_snapshots:
            PLAYWRIGHT_QUEUE.put({"type": "resetcmd", "target_repo": r, "chat_id": message.chat.id})
        else:
            bot.send_message(message.chat.id, f"❌ Bỏ qua: Bot `{r.upper()}` hiện đang offline.")
            LOG_NEEDS_REPOST = True

@bot.message_handler(commands=['shutdown'])
def shutdown_specific_bot(message):
    global LOG_NEEDS_REPOST
    if not is_admin(message): return
    try:
        parts = message.text.split()
        if len(parts) < 2:
            bot.reply_to(message, "⚠️ Cú pháp chuẩn:\n`/shutdown [Tên_Bot]`", parse_mode="Markdown")
            return
        target_repo = parts[1].strip().lower()
        accounts = load_accounts()
        found_acc = None
        for acc in accounts:
            for r in acc["repos"]:
                if r["name"].lower() == target_repo:
                    found_acc = acc
                    break
            if found_acc: break
        if not found_acc:
            bot.reply_to(message, "❌ Không hoàn thành.")
            return
            
        acc_id = found_acc["account_id"]
        headers = {"Authorization": f"Bearer {found_acc['github_token']}", "Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
        res = requests.get("https://api.github.com/user/codespaces", headers=headers, timeout=15)
        if res.status_code != 200:
            bot.reply_to(message, "❌ Không hoàn thành.")
            return
            
        if target_repo in ACTIVE_BROWSERS: del ACTIVE_BROWSERS[target_repo]
        if target_repo in STATUS_TRACKER:
            STATUS_TRACKER[target_repo]["status"] = "Đã dừng chủ động 🛑"
            STATUS_TRACKER[target_repo]["last_update"] = time.time()
                
        fail_triggered = False
        for cs in res.json().get("codespaces", []):
            if str(cs.get("state", "")).lower() in ["active", "starting", "available"]:
                stop_res = requests.post(f"https://api.github.com/user/codespaces/{cs['name']}/stop", headers=headers, timeout=15)
                if stop_res.status_code not in [200, 202]: fail_triggered = True
                
        if fail_triggered: bot.reply_to(message, "❌ Không hoàn thành.")
        else: bot.reply_to(message, f"✅ Hoàn thành, đã có thể chạy lại bot. (Tài khoản `{acc_id}` đã sạch kẹt)")
        LOG_NEEDS_REPOST = True
    except Exception as e:
        bot.reply_to(message, "❌ Không hoàn thành.")

@bot.message_handler(commands=['anh'])
def capture_realtime_screenshot(message):
    global LOG_NEEDS_REPOST
    if not is_admin(message): return
    parts = message.text.split()
    if len(parts) < 2: return
    target_repo = parts[1].strip().lower()
    active_snapshots = list(ACTIVE_BROWSERS.keys())
    if target_repo in active_snapshots:
        bot.reply_to(message, f"⏳ Đã xếp hàng lệnh chụp ảnh live cho `{target_repo.upper()}`...")
        PLAYWRIGHT_QUEUE.put({"type": "screenshot", "target_repo": target_repo, "chat_id": message.chat.id})
    else:
        bot.reply_to(message, f"❌ Bot `{target_repo.upper()}` không trực tuyến.")
    LOG_NEEDS_REPOST = True

@bot.message_handler(commands=['startbot'])
def check_all_codespaces_hardware(message):
    global LOG_NEEDS_REPOST
    if not is_admin(message): return
    bot.reply_to(message, "🔍 Đang đồng bộ cấu hình phần cứng từ GitHub API...", parse_mode="Markdown")
    try:
        accounts = load_accounts()
        report_msg = f"📊 **BÁO CÁO CẤU HÌNH CODESPACES**\n🕒 Lúc: `{get_vietnam_time()}`\n───────────────────\n"
        for acc in accounts:
            headers = {"Authorization": f"Bearer {acc['github_token']}", "Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
            for repo in acc["repos"]:
                repo_name = repo["name"]
                repo_path = repo["url"].replace("https://github.com/", "").strip("/")
                res = requests.get(f"https://api.github.com/repos/{repo_path}/codespaces", headers=headers, timeout=15)
                if res.status_code == 200:
                    for cs in res.json().get("codespaces", []):
                        cs_state = cs.get("state", "Unknown").upper()
                        report_msg += f"📁 **Bot:** `{repo_name.upper()}`\n↳ Trạng thái: {'🟢 ACTIVE' if cs_state=='ACTIVE' else '🔴 ' + cs_state}\n↳ Cấu hình: `{cs.get('machine', {}).get('display_name', 'Standard')}`\n\n"
        bot.send_message(message.chat.id, report_msg, parse_mode="Markdown")
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Lỗi /startbot: {e}")
    LOG_NEEDS_REPOST = True

@bot.message_handler(commands=['start'])
def send_hardware_only(message):
    global LOG_NEEDS_REPOST
    if not is_admin(message): return
    now_str = get_vietnam_time()
    cpu_usage, ram_usage, ram_used_gb, ram_total_gb = get_hardware_status()
    hw_msg = f"🖥️ **BÁO CÁO PHẦN CỨNG ĐIỀU KHIỂN**\n🕒 Lúc: `{now_str}`\n\n⚡ **CPU:** `{cpu_usage}%`\n🧠 **RAM:** `{ram_usage}%` (`{ram_used_gb}GB/{ram_total_gb}GB`)\n👥 **Hàng chờ xử lý:** Cụm tài khoản lệch pha (Đã tối ưu 2-Core an toàn)"
    bot.reply_to(message, hw_msg, parse_mode="Markdown")
    LOG_NEEDS_REPOST = True

@bot.message_handler(commands=['help'])
def send_help_menu(message):
    global LOG_NEEDS_REPOST
    if not is_admin(message): return
    help_text = (
        f"📖 **HƯỚNG DẪN ĐIỀU HÀNH HỆ THỐNG TRƠN TRU**\n\n"
        f"🚀 `/startall` : Kích hoạt toàn bộ danh sách bot (Phase 1 login → Phase 2 stop → Phase 3 start).\n"
        f"🎯 `/startall bot2 bot3` : Chỉ kích hoạt đích danh bot2 và bot3 chỉ định.\n"
        f"📊 `/startbot` : Kiểm tra trạng thái máy ảo trực tiếp từ GitHub.\n"
        f"🛑 `/shutdown [Tên_Bot]` : Ép tắt làm sạch kẹt slot trên tài khoản.\n"
        f"🔄 `/reset [Tên_Bot]` : Reset (login → stop → start) các bot được chỉ định.\n"
        f"⚡ `/resetcmd [Bot1] [Bot2]` : Sạch Terminal tuần tự xếp hàng 100% không lỗi luồng.\n"
        f"📸 `/anh [Tên_Bot]` : Chụp ảnh giao diện không lo sập RAM.\n"
        f"🖥️ `/start` : Xem thông số phần cứng thực tế của VPS.\n"
        f"📤 `/upload` : Upload file `accounts.json` mới từ Telegram.\n"
        f"⚠️ Lệnh /startall và /reset hỗ trợ chọn lọc bot tùy biến mà vẫn bảo lưu khóa OTP theo cụm tài khoản."
    )
    bot.reply_to(message, help_text, parse_mode="Markdown")
    LOG_NEEDS_REPOST = True

@bot.message_handler(commands=['reset'])
def reset_multiple_bots(message):
    global LOG_NEEDS_REPOST
    if not is_admin(message): return
    parts = message.text.split()
    if len(parts) < 2: return
    target_repos = list(set([r.strip().lower() for r in parts[1:]]))
    accounts = load_accounts()
    
    # Nhóm các target_repos theo account (account nào chứa repo nào)
    account_groups = {}
    for target_repo in target_repos:
        for acc in accounts:
            matched = False
            for r in acc["repos"]:
                if r["name"].lower() == target_repo:
                    acc_id = acc["account_id"]
                    if acc_id not in account_groups:
                        account_groups[acc_id] = {"acc": acc, "repos": []}
                    account_groups[acc_id]["repos"].append(r)
                    matched = True
                    break
            if matched:
                break
    
    if not account_groups:
        bot.reply_to(message, f"❌ Không tìm thấy bot nào khớp với danh sách: `{', '.join(target_repos)}`", parse_mode="Markdown")
        return
    
    total_repos = sum(len(g["repos"]) for g in account_groups.values())
    bot.reply_to(message, f"⏳ Đã nhận yêu cầu reset `{total_repos}` bot (thuộc `{len(account_groups)}` tài khoản). Tiến trình: login → stop codespace → start codespace...", parse_mode="Markdown")
    LOG_NEEDS_REPOST = True
    
    # Cập nhật STATUS_TRACKER ban đầu
    for group in account_groups.values():
        for repo in group["repos"]:
            repo_name = repo["name"]
            if repo_name in ACTIVE_BROWSERS:
                del ACTIVE_BROWSERS[repo_name]
            STATUS_TRACKER[repo_name] = {
                "status": "Chờ xếp hàng reset (stop → start)... ⏳",
                "acc": group["acc"]["account_id"],
                "last_update": time.time()
            }
    
    # Đẩy task account_batch cho mỗi account với mode="reset"
    for group in account_groups.values():
        PLAYWRIGHT_QUEUE.put({
            "type": "account_batch",
            "acc": group["acc"],
            "chat_id": message.chat.id,
            "repos": group["repos"],
            "mode": "reset"
        })
    
    LOG_NEEDS_REPOST = True

@bot.message_handler(commands=['clearcache'])
def clear_cache_command(message):
    global LOG_NEEDS_REPOST
    if not is_admin(message): return
    if os.path.exists("browser_profiles"):
        try:
            shutil.rmtree("browser_profiles")
            bot.reply_to(message, "🎉 Đã làm sạch Cookie đệm.")
        except Exception as e:
            bot.reply_to(message, f"❌ Không thể xóa cache do một số file đang bận: {e}")
    LOG_NEEDS_REPOST = True

@bot.message_handler(commands=['startall'])
def start_all(message):
    if not is_admin(message): return
    global AUTO_STATUS_RUNNING
    try:
        accounts = load_accounts()
    except Exception as e:
        bot.reply_to(message, f"❌ Lỗi đọc file cấu hình: {e}")
        return
    
    parts = message.text.split()
    target_bots = list(set([p.strip().lower() for p in parts[1:]])) if len(parts) > 1 else []
    
    filtered_accounts = []
    if target_bots:
        for acc in accounts:
            matching_repos = [r for r in acc.get("repos", []) if r["name"].lower() in target_bots]
            if matching_repos:
                acc_copy = acc.copy()
                acc_copy["repos"] = matching_repos
                filtered_accounts.append(acc_copy)
        
        if not filtered_accounts:
            bot.reply_to(message, f"❌ Không tìm thấy bot nào khớp với danh sách: `{', '.join(target_bots)}`", parse_mode="Markdown")
            return
    else:
        filtered_accounts = accounts
    
    if target_bots:
        bot.send_message(message.chat.id, f"⚡ Đang phân bổ các bot `{', '.join(target_bots).upper()}` vào hàng đợi (login → stop → start)...", parse_mode="Markdown")
    else:
        bot.send_message(message.chat.id, "⚡ Đang phân bổ danh sách TÀI KHOẢN vào hàng đợi nạp phiên chạy (login → stop → start)...")
    
    for acc in filtered_accounts:
        for repo in acc["repos"]:
            repo_name = repo["name"]
            STATUS_TRACKER[repo_name] = {
                "status": "Chờ xếp hàng... ⏳",
                "acc": acc["account_id"],
                "last_update": time.time()
            }
    
    for acc in filtered_accounts:
        PLAYWRIGHT_QUEUE.put({
            "type": "account_batch",
            "acc": acc,
            "chat_id": message.chat.id,
            "repos": acc["repos"],
            "mode": "startall"
        })
    
    if not AUTO_STATUS_RUNNING:
        AUTO_STATUS_RUNNING = True
        Thread(target=send_auto_status, args=(message.chat.id,)).start()

def send_auto_status(chat_id):
    global AUTO_STATUS_MESSAGE_ID, AUTO_STATUS_RUNNING, LOG_NEEDS_REPOST
    while AUTO_STATUS_RUNNING:
        now_str = get_vietnam_time()
        cpu_usage, ram_usage, ram_used_gb, ram_total_gb = get_hardware_status()
        
        tracker_snapshot = list(STATUS_TRACKER.items())
        msg_text = f"📊 **BÁO CÁO VẬN HÀNH CODESPACES (BATCH-LOCK)**\n🕒 Lúc: `{now_str}`\n\n🖥️ **VPS:** CPU `{cpu_usage}%` | RAM `{ram_usage}%` (`{ram_used_gb}GB/{ram_total_gb}GB`)\n👥 **Hàng đợi cụm:** `{PLAYWRIGHT_QUEUE.qsize()}` tài khoản chờ duyệt\n───────────────────\n\n"
        
        for name, info in sorted(tracker_snapshot, key=lambda x: x[1].get("last_update", 0), reverse=True):
            msg_text += f"📁 **{name}** (`{info['acc']}`)\n↳ {info['status']}\n\n"
        
        try:
            if AUTO_STATUS_MESSAGE_ID is not None and LOG_NEEDS_REPOST:
                try:
                    bot.delete_message(chat_id, AUTO_STATUS_MESSAGE_ID)
                except:
                    pass
                AUTO_STATUS_MESSAGE_ID = None
                LOG_NEEDS_REPOST = False

            if AUTO_STATUS_MESSAGE_ID is None:
                sent_msg = bot.send_message(chat_id, msg_text, parse_mode="Markdown")
                AUTO_STATUS_MESSAGE_ID = sent_msg.message_id
            else:
                try:
                    bot.edit_message_text(msg_text, chat_id, AUTO_STATUS_MESSAGE_ID, parse_mode="Markdown")
                except Exception as edit_err:
                    err_str = str(edit_err).lower()
                    if "message is not modified" in err_str:
                        pass
                    elif "message to edit not found" in err_str or "chat not found" in err_str:
                        AUTO_STATUS_MESSAGE_ID = None
        except:
            pass
            
        time.sleep(10)

@bot.message_handler(commands=['stopall'])
def stop_all(message):
    if not is_admin(message): return
    global AUTO_STATUS_RUNNING, AUTO_STATUS_MESSAGE_ID
    bot.reply_to(message, "🛑 Đang giải phóng toàn bộ hàng đợi ngầm...")
    AUTO_STATUS_RUNNING = False
    AUTO_STATUS_MESSAGE_ID = None
    with PLAYWRIGHT_QUEUE.mutex: PLAYWRIGHT_QUEUE.queue.clear()
    STATUS_TRACKER.clear()
    ACTIVE_BROWSERS.clear()
    bot.send_message(message.chat.id, f"🎯 Đã dừng toàn bộ hệ thống.")

# ==================== LỆNH UPLOAD FILE ACCOUNTS.JSON ====================
@bot.message_handler(commands=['upload'])
def upload_accounts_command(message):
    """Bắt đầu quy trình upload file accounts.json mới."""
    if not is_admin(message):
        bot.reply_to(message, "⛔ Bạn không có quyền sử dụng lệnh này.")
        return
    chat_id = message.chat.id
    UPLOAD_STATE[chat_id] = True
    bot.reply_to(message, "📤 Vui lòng gửi file `accounts.json` (dưới dạng tài liệu) để cập nhật.\n"
                          "Bot sẽ kiểm tra, lưu và áp dụng file mới ngay lập tức.\n"
                          "Nếu muốn hủy, hãy gửi lệnh `/cancel_upload`.")

@bot.message_handler(commands=['cancel_upload'])
def cancel_upload(message):
    """Hủy trạng thái chờ upload file."""
    if not is_admin(message):
        return
    chat_id = message.chat.id
    if chat_id in UPLOAD_STATE:
        del UPLOAD_STATE[chat_id]
        bot.reply_to(message, "❌ Đã hủy quá trình upload file.")
    else:
        bot.reply_to(message, "ℹ️ Bạn chưa có tiến trình upload nào đang chờ.")

@bot.message_handler(content_types=['document'])
def handle_uploaded_file(message):
    """Xử lý file được gửi đến khi đang chờ upload."""
    if not is_admin(message):
        return
    chat_id = message.chat.id
    if chat_id not in UPLOAD_STATE:
        return

    document = message.document
    if not document:
        bot.reply_to(message, "❌ Vui lòng gửi file dưới dạng tài liệu (document).")
        return

    file_name = document.file_name if document.file_name else ""
    if not file_name.lower().endswith(".json"):
        bot.reply_to(message, "❌ Chỉ chấp nhận file có đuôi `.json`. Bạn đã gửi file: `{}`".format(file_name), parse_mode="Markdown")
        return

    try:
        file_info = bot.get_file(document.file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        content = downloaded_file.decode('utf-8')
    except Exception as e:
        bot.reply_to(message, f"❌ Lỗi khi tải file: {str(e)[:100]}")
        return

    try:
        json_data = json.loads(content)
    except json.JSONDecodeError as e:
        bot.reply_to(message, f"❌ File JSON không hợp lệ: {str(e)}")
        return

    try:
        with open("accounts.json", "w", encoding="utf-8") as f:
            json.dump(json_data, f, indent=2, ensure_ascii=False)
        bot.reply_to(message, "✅ Đã lưu file `accounts.json` thành công. Bot sẽ sử dụng cấu hình mới ngay lập tức.")
        if chat_id in UPLOAD_STATE:
            del UPLOAD_STATE[chat_id]
    except Exception as e:
        bot.reply_to(message, f"❌ Lỗi khi lưu file: {str(e)[:100]}")

if __name__ == "__main__":
    Thread(target=playwright_queue_processor, daemon=True).start()
    while True:
        try:
            bot.infinity_polling()
        except Exception as e:
            print(f"Telegram polling bị lỗi: {e}. Khởi động lại sau 5 giây...")
            time.sleep(5)
        except KeyboardInterrupt:
            print("Dừng bởi người dùng.")
            break