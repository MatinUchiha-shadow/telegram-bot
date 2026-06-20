import requests
import json
import os
import base64
from datetime import datetime

TELEGRAM_TOKEN = "8602655242:AAFufIU1Y3qbKjWdyKHDH3HkAYcPl2gVq-M"
GEMINI_API_KEY = "AQ.Ab8RN6IFiiv_1Nn_nzNe0P_D967-lk6QRdUiHxvizABOiA2HUw"
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"
TG_URL = "https://api.telegram.org/bot" + TELEGRAM_TOKEN
HISTORY_FILE = "histories.json"
USERS_FILE = "users.json"
ADMIN_ID = "7175294025"

SYSTEM = "تو یه دستیار هوشمند فارسی‌زبان هستی. اسم تو 'دستیار متین' هست. سازنده تو متین هست و هر وقت کسی پرسید کی تو رو ساخته یا چه کسی تو رو درست کرده، بگو که متین منو ساخته. همیشه به فارسی جواب بده مگه اینکه کاربر انگلیسی بنویسه."

# ───── ذخیره و بارگذاری ─────

def load_json(path):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

user_histories = load_json(HISTORY_FILE)
users_data = load_json(USERS_FILE)

# ───── ثبت کاربر ─────

def register_user(user_id, from_info):
    uid = str(user_id)
    if uid not in users_data:
        users_data[uid] = {
            "first_name": from_info.get("first_name", ""),
            "username": from_info.get("username", ""),
            "joined": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "message_count": 0,
            "blocked": False
        }
    else:
        users_data[uid]["first_name"] = from_info.get("first_name", "")
        users_data[uid]["username"] = from_info.get("username", "")
    save_json(USERS_FILE, users_data)

def increment_msg(user_id):
    uid = str(user_id)
    if uid in users_data:
        users_data[uid]["message_count"] = users_data[uid].get("message_count", 0) + 1
        save_json(USERS_FILE, users_data)

def is_blocked(user_id):
    return users_data.get(str(user_id), {}).get("blocked", False)

# ───── ارسال پیام ─────

def send(chat_id, text, reply_markup=None, parse_mode="Markdown"):
    chunks = [text[i:i+4096] for i in range(0, len(text), 4096)]
    for i, chunk in enumerate(chunks):
        payload = {"chat_id": chat_id, "text": chunk, "parse_mode": parse_mode}
        if reply_markup and i == len(chunks) - 1:
            payload["reply_markup"] = reply_markup
        requests.post(TG_URL + "/sendMessage", json=payload)

# ───── دانلود فایل از تلگرام ─────

def get_file_bytes(file_id):
    r = requests.get(TG_URL + f"/getFile?file_id={file_id}")
    file_path = r.json()["result"]["file_path"]
    file_url = f"https://api.telegram.org/file/bot{TELEGRAM_TOKEN}/{file_path}"
    return requests.get(file_url).content, file_path

# ───── هوش مصنوعی Gemini ─────

def ask_ai(user_id, text=None, image_data=None, image_mime=None, audio_data=None, audio_mime=None):
    uid = str(user_id)
    if uid not in user_histories:
        user_histories[uid] = []

    # ساخت پارت‌های پیام کاربر
    user_parts = []

    if image_data:
        user_parts.append({
            "inline_data": {
                "mime_type": image_mime,
                "data": base64.b64encode(image_data).decode()
            }
        })

    if audio_data:
        user_parts.append({
            "inline_data": {
                "mime_type": audio_mime,
                "data": base64.b64encode(audio_data).decode()
            }
        })

    if text:
        user_parts.append({"text": text})
    elif not image_data and not audio_data:
        user_parts.append({"text": ""})

    # اضافه کردن پیام کاربر به تاریخچه
    user_histories[uid].append({"role": "user", "parts": user_parts})

    # گرفتن ۲۰ پیام آخر
    history = user_histories[uid][-20:]

    payload = {
        "system_instruction": {"parts": [{"text": SYSTEM}]},
        "contents": history,
        "generationConfig": {"maxOutputTokens": 2048}
    }

    r = requests.post(GEMINI_URL, json=payload, headers={"x-goog-api-key": GEMINI_API_KEY, "Content-Type": "application/json"})
    result = r.json()

    reply = result["candidates"][0]["content"]["parts"][0]["text"]

    # ذخیره پاسخ در تاریخچه
    user_histories[uid].append({"role": "model", "parts": [{"text": reply}]})
    save_json(HISTORY_FILE, user_histories)
    return reply

# ───── منوها ─────

def main_menu():
    return {
        "inline_keyboard": [
            [
                {"text": "🆕 مکالمه جدید", "callback_data": "clear"},
                {"text": "ℹ️ درباره ربات", "callback_data": "about"}
            ],
            [{"text": "❓ راهنما", "callback_data": "help"}]
        ]
    }

def admin_menu():
    return {
        "inline_keyboard": [
            [
                {"text": "👥 لیست کاربران", "callback_data": "admin_userlist"},
                {"text": "📊 آمار کلی", "callback_data": "admin_stats"}
            ],
            [
                {"text": "📢 ارسال همگانی", "callback_data": "admin_broadcast"},
                {"text": "🔍 جستجوی کاربر", "callback_data": "admin_search"}
            ],
            [
                {"text": "🔴 بلاک کاربر", "callback_data": "admin_block"},
                {"text": "🟢 آنبلاک کاربر", "callback_data": "admin_unblock"}
            ],
            [{"text": "🗑️ پاک کردن حافظه کاربر", "callback_data": "admin_clearmem"}]
        ]
    }

# ───── حالت انتظار ادمین ─────

admin_state = {}

def handle_admin_input(chat_id, text):
    state = admin_state.get(ADMIN_ID, {})
    action = state.get("action")

    if action == "broadcast":
        total, success = 0, 0
        for uid in users_data:
            if not users_data[uid].get("blocked", False):
                total += 1
                try:
                    send(uid, f"📢 *پیام از ادمین:*\n\n{text}")
                    success += 1
                except:
                    pass
        send(chat_id, f"✅ پیام به *{success}* از *{total}* کاربر ارسال شد.", reply_markup=admin_menu())
        admin_state.pop(ADMIN_ID, None)
        return True

    elif action == "search":
        found = []
        query = text.lower()
        for uid, info in users_data.items():
            if (query in info.get("username", "").lower() or
                query in info.get("first_name", "").lower() or
                query == uid):
                found.append((uid, info))
        if found:
            msg = "🔍 *نتایج جستجو:*\n\n"
            for uid, info in found[:10]:
                status = "🔴 بلاک" if info.get("blocked") else "🟢 فعال"
                msg += (f"👤 *{info.get('first_name', 'بدون نام')}*\n"
                        f"🆔 آیدی: `{uid}`\n"
                        f"📛 یوزرنیم: @{info.get('username', '-')}\n"
                        f"💬 پیام: {info.get('message_count', 0)}\n"
                        f"📅 عضویت: {info.get('joined', '-')}\n"
                        f"وضعیت: {status}\n\n")
        else:
            msg = "❌ کاربری پیدا نشد."
        send(chat_id, msg, reply_markup=admin_menu())
        admin_state.pop(ADMIN_ID, None)
        return True

    elif action == "block":
        uid = text.strip()
        if uid in users_data:
            users_data[uid]["blocked"] = True
            save_json(USERS_FILE, users_data)
            send(chat_id, f"🔴 کاربر *{users_data[uid].get('first_name', uid)}* بلاک شد.", reply_markup=admin_menu())
        else:
            send(chat_id, "❌ کاربر پیدا نشد.", reply_markup=admin_menu())
        admin_state.pop(ADMIN_ID, None)
        return True

    elif action == "unblock":
        uid = text.strip()
        if uid in users_data:
            users_data[uid]["blocked"] = False
            save_json(USERS_FILE, users_data)
            send(chat_id, f"🟢 کاربر *{users_data[uid].get('first_name', uid)}* آنبلاک شد.", reply_markup=admin_menu())
        else:
            send(chat_id, "❌ کاربر پیدا نشد.", reply_markup=admin_menu())
        admin_state.pop(ADMIN_ID, None)
        return True

    elif action == "clearmem":
        uid = text.strip()
        if uid in user_histories:
            user_histories[uid] = []
            save_json(HISTORY_FILE, user_histories)
            send(chat_id, f"🗑️ حافظه کاربر `{uid}` پاک شد.", reply_markup=admin_menu())
        else:
            send(chat_id, "❌ کاربر یا حافظه‌ای پیدا نشد.", reply_markup=admin_menu())
        admin_state.pop(ADMIN_ID, None)
        return True

    return False

# ───── Callback ─────

def answer_callback(cid):
    requests.post(TG_URL + "/answerCallbackQuery", json={"callback_query_id": cid})

def handle_callback(callback):
    cid = callback["id"]
    chat_id = callback["message"]["chat"]["id"]
    user_id = str(callback["from"]["id"])
    data = callback.get("data", "")
    answer_callback(cid)

    if data == "clear":
        user_histories[user_id] = []
        save_json(HISTORY_FILE, user_histories)
        send(chat_id, "✅ حافظه پاک شد! مکالمه جدید شروع شد.", reply_markup=main_menu())
        return
    if data == "about":
        send(chat_id, "🤖 *دستیار متین*\n\nاین ربات توسط *متین* ساخته شده.\nهر سوالی داری بپرس! 😊", reply_markup=main_menu())
        return
    if data == "help":
        send(chat_id,
             "📖 *راهنمای دستیار متین*\n\n"
             "🔹 متن بفرست تا جواب بگیری\n"
             "🖼️ عکس بفرست تا تحلیل بشه\n"
             "🎤 ویس بفرست تا پردازش بشه\n\n"
             "🔹 /start — شروع و منوی اصلی\n"
             "🔹 /clear — پاک کردن حافظه\n"
             "🔹 /about — درباره ربات\n"
             "🔹 /help — راهنما",
             reply_markup=main_menu())
        return

    if user_id != ADMIN_ID:
        return

    if data == "admin_stats":
        total = len(users_data)
        blocked = sum(1 for u in users_data.values() if u.get("blocked"))
        total_msgs = sum(u.get("message_count", 0) for u in users_data.values())
        send(chat_id,
             f"📊 *آمار کلی ربات*\n\n"
             f"👥 کل کاربران: *{total}*\n"
             f"🟢 فعال: *{total - blocked}*\n"
             f"🔴 بلاک: *{blocked}*\n"
             f"💬 کل پیام‌ها: *{total_msgs}*",
             reply_markup=admin_menu())

    elif data == "admin_userlist":
        if not users_data:
            send(chat_id, "❌ هیچ کاربری ثبت نشده.", reply_markup=admin_menu())
            return
        msg = "👥 *لیست کاربران:*\n\n"
        for uid, info in list(users_data.items())[:20]:
            status = "🔴" if info.get("blocked") else "🟢"
            msg += f"{status} *{info.get('first_name', 'بدون نام')}* | `{uid}` | 💬{info.get('message_count', 0)} | 📅{info.get('joined', '-')}\n"
        if len(users_data) > 20:
            msg += f"\n_... و {len(users_data)-20} کاربر دیگه_"
        send(chat_id, msg, reply_markup=admin_menu())

    elif data == "admin_broadcast":
        admin_state[ADMIN_ID] = {"action": "broadcast"}
        send(chat_id, "📢 متن پیام همگانی رو بفرست:", reply_markup={"inline_keyboard": [[{"text": "❌ لغو", "callback_data": "admin_cancel"}]]})

    elif data == "admin_search":
        admin_state[ADMIN_ID] = {"action": "search"}
        send(chat_id, "🔍 نام، یوزرنیم یا آیدی کاربر رو بفرست:", reply_markup={"inline_keyboard": [[{"text": "❌ لغو", "callback_data": "admin_cancel"}]]})

    elif data == "admin_block":
        admin_state[ADMIN_ID] = {"action": "block"}
        send(chat_id, "🔴 آیدی عددی کاربر رو بفرست:", reply_markup={"inline_keyboard": [[{"text": "❌ لغو", "callback_data": "admin_cancel"}]]})

    elif data == "admin_unblock":
        admin_state[ADMIN_ID] = {"action": "unblock"}
        send(chat_id, "🟢 آیدی عددی کاربر رو بفرست:", reply_markup={"inline_keyboard": [[{"text": "❌ لغو", "callback_data": "admin_cancel"}]]})

    elif data == "admin_clearmem":
        admin_state[ADMIN_ID] = {"action": "clearmem"}
        send(chat_id, "🗑️ آیدی عددی کاربر رو بفرست:", reply_markup={"inline_keyboard": [[{"text": "❌ لغو", "callback_data": "admin_cancel"}]]})

    elif data == "admin_cancel":
        admin_state.pop(ADMIN_ID, None)
        send(chat_id, "❌ عملیات لغو شد.", reply_markup=admin_menu())

# ───── پردازش پیام ─────

def handle_message(msg):
    chat_id = msg["chat"]["id"]
    user_id = str(msg["from"]["id"])
    first_name = msg["from"].get("first_name", "دوست عزیز")
    text = msg.get("text", "")
    caption = msg.get("caption", "")

    register_user(user_id, msg["from"])

    # ── دستور /admin ──
    if text == "/admin" and user_id != ADMIN_ID:
        send(chat_id, "⛔ این دستور فقط برای ادمین هست.")
        return

    if text == "/admin" and user_id == ADMIN_ID:
        total = len(users_data)
        blocked = sum(1 for u in users_data.values() if u.get("blocked"))
        total_msgs = sum(u.get("message_count", 0) for u in users_data.values())
        send(chat_id,
             f"👑 *پنل ادمین - دستیار متین*\n\n"
             f"👥 کاربران: *{total}* | 🔴 بلاک: *{blocked}*\n"
             f"💬 کل پیام‌ها: *{total_msgs}*\n\n"
             f"یه گزینه رو انتخاب کن:",
             reply_markup=admin_menu())
        return

    # ── ادمین در حالت انتظار ──
    if user_id == ADMIN_ID and ADMIN_ID in admin_state and text:
        if handle_admin_input(chat_id, text):
            return

    # ── بررسی بلاک ──
    if is_blocked(user_id):
        send(chat_id, "⛔ دسترسی شما مسدود شده.")
        return

    # ── دستورات عمومی ──
    if text == "/start":
        send(chat_id,
             f"سلام {first_name} عزیز! 👋\n\n"
             "من *دستیار متین* هستم، ساخته شده توسط *متین*.\n"
             "میتونی متن، عکس یا ویس بفرستی 😊",
             reply_markup=main_menu())
        return

    if text == "/clear":
        user_histories[user_id] = []
        save_json(HISTORY_FILE, user_histories)
        send(chat_id, "✅ حافظه پاک شد!", reply_markup=main_menu())
        return

    if text == "/about":
        send(chat_id, "🤖 *دستیار متین*\n\nاین ربات توسط *متین* ساخته شده.\nهر سوالی داری بپرس! 😊", reply_markup=main_menu())
        return

    if text == "/help":
        send(chat_id,
             "📖 *راهنمای دستیار متین*\n\n"
             "🔹 متن بفرست تا جواب بگیری\n"
             "🖼️ عکس بفرست تا تحلیل بشه\n"
             "🎤 ویس بفرست تا پردازش بشه\n\n"
             "🔹 /start — شروع و منوی اصلی\n"
             "🔹 /clear — پاک کردن حافظه\n"
             "🔹 /about — درباره ربات\n"
             "🔹 /help — راهنما",
             reply_markup=main_menu())
        return

    requests.post(TG_URL + "/sendChatAction", json={"chat_id": chat_id, "action": "typing"})

    try:
        increment_msg(user_id)

        # ── عکس ──
        if "photo" in msg:
            file_id = msg["photo"][-1]["file_id"]
            img_bytes, _ = get_file_bytes(file_id)
            reply = ask_ai(user_id, text=caption or "این عکس رو توضیح بده", image_data=img_bytes, image_mime="image/jpeg")
            send(chat_id, reply)
            return

        # ── ویس / صدا ──
        if "voice" in msg or "audio" in msg:
            file_id = msg.get("voice", msg.get("audio", {})).get("file_id")
            audio_bytes, file_path = get_file_bytes(file_id)
            mime = "audio/ogg" if "voice" in msg else "audio/mpeg"
            reply = ask_ai(user_id, text=caption or "این صدا رو پردازش کن و محتواش رو بگو", audio_data=audio_bytes, audio_mime=mime)
            send(chat_id, reply)
            return

        # ── متن ──
        if text:
            reply = ask_ai(user_id, text=text)
            send(chat_id, reply)
        else:
            send(chat_id, "⚠️ لطفاً متن، عکس یا ویس بفرست.")

    except Exception as e:
        print("خطا:", str(e))
        send(chat_id, "⚠️ خطایی رخ داد. دوباره امتحان کن.")

# ───── حلقه اصلی ─────

def main():
    print("ربات شروع به کار کرد! (Gemini 2.5 Flash)")
    offset = None
    while True:
        try:
            r = requests.get(TG_URL + "/getUpdates", params={"timeout": 30, "offset": offset}, timeout=35)
            updates = r.json()
            for update in updates.get("result", []):
                offset = update["update_id"] + 1
                if "callback_query" in update:
                    handle_callback(update["callback_query"])
                    continue
                msg = update.get("message", {})
                if msg:
                    handle_message(msg)
        except Exception as e:
            print("خطا:", str(e))

main()
