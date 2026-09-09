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
TOKEN = "8744525541:AAFNemNTHe_vveDQGSygwWcLRgxwd7rsTjM"
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
        # Thử cả Inbox và Spam
        for folder in ["inbox", "[Gmail]/Spam"]:
            try:
                mail.select(folder)
                status, data = mail.search(None, '(FROM "noreply@github.com")')
                if status != "OK":
                    continue
                mail_ids = data[0].split()
                if not mail_ids:
                    continue
                # Duyệt từ mới nhất đến cũ, tối đa 10 email
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
        # Đảm bảo đóng kết nối IMAP trong mọi trường hợp
        if mail:
            try:
                mail.logout()
            except:
                pass

def create_codespace_via_api(token, repo_url, max_retries=3):
    """Tạo hoặc start codespace, retry tối đa 3 lần khi lỗi."""
    repo_path = repo_url.replace("https://github.com/", "").strip("/")
    api_url = f"https://api.github.com/repos/{repo_path}/codespaces"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28"
    }
    for attempt in range(1, max_retries + 1):
        try:
            res = requests.get(api_url, headers=headers, timeout=15)
            if res.status_code == 200:
                codespaces = res.json().get("codespaces", [])
                if codespaces:
                    cs = codespaces[0]
                    cs_name = cs["name"]
                    start_url = f"https://api.github.com/user/codespaces/{cs_name}/start"
                    start_res = requests.post(start_url, headers=headers, timeout=15)
                    if start_res.status_code in [200, 202]:
                        return cs["web_url"]
                    else:
                        # Nếu start thất bại, thử tạo mới
                        pass
                # Không có codespace hoặc start thất bại -> tạo mới
                payload = {"machine": "standardLinux32gb"}
                create_res = requests.post(api_url, headers=headers, json=payload, timeout=15)
                if create_res.status_code in [201, 202]:
                    return create_res.json().get("web_url")
            # Nếu status code không 200, hoặc không có web_url, tiếp tục retry
        except Exception as e:
            print(f"Lỗi API GitHub (lần {attempt}): {e}")
        # Đợi trước khi retry (backoff)
        if attempt < max_retries:
            time.sleep(2 ** attempt)  # 2, 4, 8 giây
    return None

def clean_all_active_codespaces(token):
    api_url = "https://api.github.com/user/codespaces"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28"
    }
    try:
        res = requests.get(api_url, headers=headers, timeout=15)
        if res.status_code == 200:
            codespaces = res.json().get("codespaces", [])
            for cs in codespaces:
                if str(cs.get("state", "")).lower() == "active":
                    cs_name = cs["name"]
                    stop_url = f"https://api.github.com/user/codespaces/{cs_name}/stop"
                    requests.post(stop_url, headers=headers, timeout=15)
    except Exception as e:
        print(f"Lỗi dọn dẹp: {e}")

def send_debug_screenshot(page, repo_name, chat_id, status_text):
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

def playwright_queue_processor():
    print("🚀 Đã kích hoạt lõi xử lý hàng đợi tập trung...")
    while True:
        try:
            task = PLAYWRIGHT_QUEUE.get()
            task_type = task.get("type")
            try:
                if task_type == "account_batch":
                    process_account_batch_task(task)
                elif task_type == "login":
                    process_login_task(task)
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
    
    account_otp_lock = threading.Lock()
    repos = acc["repos"]
    max_workers = min(len(repos), 2)
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = []
        for index, repo in enumerate(repos):
            future = executor.submit(run_single_bot_pipeline, acc, repo, chat_id, account_otp_lock, index)
            futures.append(future)
        for future in futures:
            try:
                future.result(timeout=600)
            except FutureTimeoutError:
                print(f"Pipeline timeout, hủy future")
                future.cancel()
            except Exception as e:
                print(f"Pipeline thất bại: {e}")

def run_single_bot_pipeline(acc, repo, chat_id, otp_lock, bot_index=0):
    global LOG_NEEDS_REPOST
    repo_name = repo["name"]
    
    if bot_index > 0:
        delay_time = bot_index * 25
        STATUS_TRACKER[repo_name]["status"] = f"💤 Giãn cách pha (Chờ {delay_time}s hạ nhiệt CPU)..."
        STATUS_TRACKER[repo_name]["last_update"] = time.time()
        time.sleep(delay_time)
    
    STATUS_TRACKER[repo_name]["status"] = "Đang điều phối API... 🚀"
    STATUS_TRACKER[repo_name]["last_update"] = time.time()
    
    web_url = create_codespace_via_api(acc["github_token"], repo["url"])
    if not web_url:
        STATUS_TRACKER[repo_name]["status"] = "Thất bại: Lỗi API GitHub ❌"
        return

    with sync_playwright() as p:
        context = None
        is_locked = False
        try:
            STATUS_TRACKER[repo_name]["status"] = "Khởi động lõi ảo cấu hình... 🌐"
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
            
            # ===== GIAI ĐOẠN 1: ĐĂNG NHẬP & OTP =====
            if otp_lock:
                otp_lock.acquire()
                is_locked = True
                
            STATUS_TRACKER[repo_name]["status"] = "Đang tải trang kết nối... ⏳"
            STATUS_TRACKER[repo_name]["last_update"] = time.time()
            page.goto(web_url, timeout=30000, wait_until="commit")
            
            for _ in range(16):
                if page.locator("div.workbench, div#monaco-parts-splash, .monaco-workbench, input[name='login']").first.is_visible(): break
                time.sleep(0.5)
                
            is_workspace = page.locator("div.workbench, div#monaco-parts-splash, .monaco-workbench").is_visible()
            if not is_workspace:
                if page.locator("input[name='login']").is_visible() or "login" in page.url.lower():
                    STATUS_TRACKER[repo_name]["status"] = "Nạp thông tin bảo mật... 🔐"
                    STATUS_TRACKER[repo_name]["last_update"] = time.time()
                    
                    username = acc.get("account_id", "").strip()
                    password = acc.get("github_password", "").strip()
                    if not username or not password:
                        STATUS_TRACKER[repo_name]["status"] = "Offline: Thiếu username hoặc password ❌"
                        STATUS_TRACKER[repo_name]["last_update"] = time.time()
                        send_debug_screenshot(page, repo_name, chat_id, "Thiếu username/password trong accounts.json")
                        if is_locked:
                            otp_lock.release()
                            is_locked = False
                        return
                    
                    page.fill("input[name='login']", username)
                    page.fill("input[name='password']", password)
                    page.click("input[type='submit']")
                    time.sleep(3)
                    
                    error_element = page.locator(".flash-error, #js-flash-container .flash-error, div.flash-error")
                    if error_element.count() > 0 and error_element.is_visible():
                        error_text = error_element.inner_text()
                        STATUS_TRACKER[repo_name]["status"] = f"Offline: Đăng nhập thất bại ❌"
                        STATUS_TRACKER[repo_name]["last_update"] = time.time()
                        send_debug_screenshot(page, repo_name, chat_id, f"Login lỗi: {error_text[:100]}")
                        if is_locked:
                            otp_lock.release()
                            is_locked = False
                        return
                    
                    for _ in range(16):
                        if page.locator("div.workbench, input[id='app_totp'], input[id='otp'], input[name='otp']").first.is_visible(): break
                        time.sleep(0.5)
                        
                    if page.locator("input[id='app_totp'], input[id='otp'], input[name='otp'], input[id='verification_code']").first.is_visible():
                        STATUS_TRACKER[repo_name]["status"] = "🤖 Đang quét giải mã OTP từ Gmail..."
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
                            STATUS_TRACKER[repo_name]["status"] = f"🎯 Xác thực OTP ({received_code})... ⚙️"
                            STATUS_TRACKER[repo_name]["last_update"] = time.time()
                            page.locator("input[id='app_totp'], input[id='otp'], input[name='otp'], input[id='verification_code']").fill(received_code)
                            page.keyboard.press("Enter")
                            for _ in range(20):
                                if page.locator("div.workbench, .monaco-workbench").first.is_visible(): break
                                time.sleep(0.5)
                        else:
                            STATUS_TRACKER[repo_name]["status"] = "Offline: Kẹt OTP Gmail ❌"
                            STATUS_TRACKER[repo_name]["last_update"] = time.time()
                            send_debug_screenshot(page, repo_name, chat_id, "Không lấy được OTP từ Gmail sau 20 lần thử")
                            if is_locked:
                                otp_lock.release()
                                is_locked = False
                            return

            try:
                page.locator("div.workbench, .monaco-workbench").wait_for(state="visible", timeout=15000)
            except:
                pass

            if is_locked:
                STATUS_TRACKER[repo_name]["status"] = "🔌 Đã vượt OTP, nhường khóa cho bot sau..."
                STATUS_TRACKER[repo_name]["last_update"] = time.time()
                otp_lock.release()
                is_locked = False

            # ===== GIAI ĐOẠN 2: CHỜ TERMINAL =====
            STATUS_TRACKER[repo_name]["status"] = "⏳ Đang đợi Codespace nạp Terminal..."
            STATUS_TRACKER[repo_name]["last_update"] = time.time()
            
            terminal_ready = False
            for _ in range(45):  
                time.sleep(4)
                has_loading = page.locator("text=Setting up remote connection, text=Opening Remote, text=Building codespace").first.is_visible()
                has_terminal = page.locator(".terminal, .xterm, .integrated-terminal-panel").first.is_visible()
                if not has_loading and has_terminal:
                    terminal_ready = True
                    break
            
            if not terminal_ready:
                STATUS_TRACKER[repo_name]["status"] = "Offline: Quá thời gian nạp Terminal (GitHub Treo) ❌"
                STATUS_TRACKER[repo_name]["last_update"] = time.time()
                send_debug_screenshot(page, repo_name, chat_id, "Timeout Terminal - GitHub Treo")
                return 
            
            time.sleep(3) 
            
            STATUS_TRACKER[repo_name]["status"] = "⌨️ Ép mở Terminal mới để chạy lệnh..."
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
            STATUS_TRACKER[repo_name]["status"] = "Offline: Lỗi nạp phiên chạy ❌"
            STATUS_TRACKER[repo_name]["last_update"] = time.time()
            try:
                if 'page' in locals():
                    send_debug_screenshot(page, repo_name, chat_id, f"Exception: {str(e)[:50]}")
            except:
                pass
        finally:
            if is_locked:
                otp_lock.release()
            if context:
                context.close()  

def process_login_task(task):
    global LOG_NEEDS_REPOST
    acc, repo, chat_id = task["acc"], task["repo"], task["chat_id"]
    repo_name = repo["name"]
    
    STATUS_TRACKER[repo_name]["status"] = "Đang điều phối API... 🚀"
    STATUS_TRACKER[repo_name]["last_update"] = time.time()
    
    web_url = create_codespace_via_api(acc["github_token"], repo["url"])
    if not web_url:
        STATUS_TRACKER[repo_name]["status"] = "Thất bại: Lỗi API GitHub ❌"
        return

    with sync_playwright() as p:
        context = None
        try:
            STATUS_TRACKER[repo_name]["status"] = "Khởi động lõi ảo cấu hình... 🌐"
            STATUS_TRACKER[repo_name]["last_update"] = time.time()
            ram_optimize_args = ["--no-sandbox", "--disable-setuid-sandbox", "--disable-gpu", "--disable-dev-shm-usage", "--js-flags=--max-old-space-size=100", "--disable-extensions", "--mute-audio"]
            user_data_dir = f"./browser_profiles/{repo_name}"
            context = p.chromium.launch_persistent_context(user_data_dir, headless=True, args=ram_optimize_args)
            page = context.new_page()
            
            page.route("**/*", lambda route: route.abort() if route.request.resource_type in ["image", "media", "font"] else route.continue_())
            
            STATUS_TRACKER[repo_name]["status"] = "Đang tải trang kết nối... ⏳"
            STATUS_TRACKER[repo_name]["last_update"] = time.time()
            page.goto(web_url, timeout=30000, wait_until="commit")
            
            for _ in range(16):
                if page.locator("div.workbench, div#monaco-parts-splash, .monaco-workbench, input[name='login']").first.is_visible(): break
                time.sleep(0.5)
                
            is_workspace = page.locator("div.workbench, div#monaco-parts-splash, .monaco-workbench").is_visible()
            if not is_workspace:
                if page.locator("input[name='login']").is_visible() or "login" in page.url.lower():
                    STATUS_TRACKER[repo_name]["status"] = "Nạp thông tin bảo mật... 🔐"
                    STATUS_TRACKER[repo_name]["last_update"] = time.time()
                    
                    username = acc.get("account_id", "").strip()
                    password = acc.get("github_password", "").strip()
                    if not username or not password:
                        STATUS_TRACKER[repo_name]["status"] = "Offline: Thiếu username hoặc password ❌"
                        STATUS_TRACKER[repo_name]["last_update"] = time.time()
                        send_debug_screenshot(page, repo_name, chat_id, "Thiếu username/password trong accounts.json")
                        return
                    
                    page.fill("input[name='login']", username)
                    page.fill("input[name='password']", password)
                    page.click("input[type='submit']")
                    time.sleep(3)
                    
                    error_element = page.locator(".flash-error, #js-flash-container .flash-error, div.flash-error")
                    if error_element.count() > 0 and error_element.is_visible():
                        error_text = error_element.inner_text()
                        STATUS_TRACKER[repo_name]["status"] = f"Offline: Đăng nhập thất bại ❌"
                        STATUS_TRACKER[repo_name]["last_update"] = time.time()
                        send_debug_screenshot(page, repo_name, chat_id, f"Login lỗi: {error_text[:100]}")
                        return
                    
                    for _ in range(16):
                        if page.locator("div.workbench, input[id='app_totp'], input[id='otp'], input[name='otp']").first.is_visible(): break
                        time.sleep(0.5)
                        
                    if page.locator("input[id='app_totp'], input[id='otp'], input[name='otp'], input[id='verification_code']").first.is_visible():
                        STATUS_TRACKER[repo_name]["status"] = "🤖 Đang quét giải mã OTP từ Gmail..."
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
                            STATUS_TRACKER[repo_name]["status"] = f"🎯 Xác thực OTP ({received_code})... ⚙️"
                            STATUS_TRACKER[repo_name]["last_update"] = time.time()
                            page.locator("input[id='app_totp'], input[id='otp'], input[name='otp'], input[id='verification_code']").fill(received_code)
                            page.keyboard.press("Enter")
                            for _ in range(20):
                                if page.locator("div.workbench, .monaco-workbench").first.is_visible(): break
                                time.sleep(0.5)
                        else:
                            STATUS_TRACKER[repo_name]["status"] = "Offline: Kẹt OTP Gmail ❌"
                            STATUS_TRACKER[repo_name]["last_update"] = time.time()
                            send_debug_screenshot(page, repo_name, chat_id, "Không lấy được OTP từ Gmail sau 20 lần thử")
                            return

            STATUS_TRACKER[repo_name]["status"] = "⏳ Đang đợi Codespace nạp Terminal..."
            STATUS_TRACKER[repo_name]["last_update"] = time.time()
            
            terminal_ready = False
            for _ in range(45):
                time.sleep(4)
                has_loading = page.locator("text=Setting up remote connection, text=Opening Remote, text=Building codespace").first.is_visible()
                has_terminal = page.locator(".terminal, .xterm, .integrated-terminal-panel").first.is_visible()
                if not has_loading and has_terminal:
                    terminal_ready = True
                    break
            
            if not terminal_ready:
                STATUS_TRACKER[repo_name]["status"] = "Offline: Quá thời gian nạp Terminal (GitHub Treo) ❌"
                STATUS_TRACKER[repo_name]["last_update"] = time.time()
                send_debug_screenshot(page, repo_name, chat_id, "Timeout Terminal - GitHub Treo")
                return
            
            time.sleep(3)
            
            STATUS_TRACKER[repo_name]["status"] = "⌨️ Ép mở Terminal mới để chạy lệnh..."
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
                    bot.send_photo(chat_id, photo, caption=f"🎉 [KÍCH HOẠT THÀNH CÔNG - {repo_name.upper()}]\n✅ Hệ thống đã ép mở Terminal mới và kích hoạt toàn bộ chuỗi bot con ổn định!")
                os.remove(screenshot_path)
                LOG_NEEDS_REPOST = True
                
            STATUS_TRACKER[repo_name]["status"] = "Active: Đã kích hoạt hoàn tất 🟢"
            STATUS_TRACKER[repo_name]["last_update"] = time.time()
            ACTIVE_BROWSERS[repo_name] = {"active": True}
        except Exception as e:
            STATUS_TRACKER[repo_name]["status"] = "Offline: Lỗi nạp phiên chạy ❌"
            STATUS_TRACKER[repo_name]["last_update"] = time.time()
            try:
                if 'page' in locals():
                    send_debug_screenshot(page, repo_name, chat_id, f"Exception: {str(e)[:50]}")
            except:
                pass
        finally:
            if context:
                context.close()  

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
                    
                    for _ in range(45):
                        time.sleep(4)
                        if not page.locator("text=Setting up remote connection, text=Opening Remote, text=Building codespace").first.is_visible():
                            break
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
        f"🚀 `/startall` : Kích hoạt toàn bộ danh sách bot.\n"
        f"🎯 `/startall bot2 bot3` : Chỉ kích hoạt đích danh bot2 và bot3 chỉ định.\n"
        f"📊 `/startbot` : Kiểm tra trạng thái máy ảo trực tiếp từ GitHub.\n"
        f"🛑 `/shutdown [Tên_Bot]` : Ép tắt làm sạch kẹt slot trên tài khoản.\n"
        f"🔄 `/reset [Tên_Bot]` : Khởi động lại một phiên đăng nhập đơn lẻ.\n"
        f"⚡ `/resetcmd [Bot1] [Bot2]` : Sạch Terminal tuần tự xếp hàng 100% không lỗi luồng.\n"
        f"📸 `/anh [Tên_Bot]` : Chụp ảnh giao diện không lo sập RAM.\n"
        f"🖥️ `/start` : Xem thông số phần cứng thực tế của VPS.\n"
        f"⚠️ Lệnh /startall hỗ trợ chọn lọc bot tùy biến mà vẫn bảo lưu khóa OTP theo cụm tài khoản."
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
    
    for target_repo in target_repos:
        found_acc, found_repo = None, None
        for acc in accounts:
            for r in acc["repos"]:
                if r["name"].lower() == target_repo:
                    found_acc, found_repo = acc, r
                    break
        if not found_repo: continue
        if target_repo in ACTIVE_BROWSERS: del ACTIVE_BROWSERS[target_repo]
        STATUS_TRACKER[target_repo] = {"status": "Chờ xếp hàng đăng nhập... ⏳", "acc": found_acc["account_id"], "last_update": time.time()}
        PLAYWRIGHT_QUEUE.put({"type": "login", "acc": found_acc, "repo": found_repo, "chat_id": message.chat.id})
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

    for acc in filtered_accounts:
        Thread(target=clean_all_active_codespaces, args=(acc["github_token"],)).start()
    time.sleep(2)
    
    if target_bots:
        bot.send_message(message.chat.id, f"⚡ Đang phân bổ các bot `{', '.join(target_bots).upper()}` vào hàng đợi...", parse_mode="Markdown")
    else:
        bot.send_message(message.chat.id, "⚡ Đang phân bổ danh sách TÀI KHOẢN vào hàng đợi nạp phiên chạy...")
    
    for acc in filtered_accounts:
        for repo in acc["repos"]:
            repo_name = repo["name"]
            STATUS_TRACKER[repo_name] = {"status": "Chờ xếp hàng... ⏳", "acc": acc["account_id"], "last_update": time.time()}

    for acc in filtered_accounts:
        PLAYWRIGHT_QUEUE.put({"type": "account_batch", "acc": acc, "chat_id": message.chat.id})
            
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