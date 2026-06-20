import requests
import json
import os

TELEGRAM_TOKEN = "8602655242:AAFufIU1Y3qbKjWdyKHDH3HkAYcPl2gVq-M"
COHERE_API_KEY = "KrDOjWoGuBZvvTQRj8D5YqjDKU6dA5nkiyJBMPoj"
COHERE_URL = "https://api.cohere.com/v2/chat"
TG_URL = "https://api.telegram.org/bot" + TELEGRAM_TOKEN
HISTORY_FILE = "histories.json"

SYSTEM = "تو یه دستیار هوشمند فارسی‌زبان هستی. اسم تو 'دستیار متین' هست. سازنده تو متین هست و هر وقت کسی پرسید کی تو رو ساخته یا چه کسی تو رو درست کرده، بگو که متین منو ساخته. همیشه به فارسی جواب بده مگه اینکه کاربر انگلیسی بنویسه."

# ───── ذخیره و بارگذاری تاریخچه ─────

def load_histories():
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_histories(histories):
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(histories, f, ensure_ascii=False, indent=2)

user_histories = load_histories()

# ───── ارسال پیام (با پشتیبانی از پیام‌های طولانی) ─────

def send(chat_id, text, reply_markup=None):
    chunks = [text[i:i+4096] for i in range(0, len(text), 4096)]
    for i, chunk in enumerate(chunks):
        payload = {"chat_id": chat_id, "text": chunk}
        if reply_markup and i == len(chunks) - 1:
            payload["reply_markup"] = reply_markup
        requests.post(TG_URL + "/sendMessage", json=payload)

# ───── منوی اصلی (دکمه‌های شیشه‌ای) ─────

def main_menu():
    return {
        "inline_keyboard": [
            [
                {"text": "🆕 شروع مکالمه جدید", "callback_data": "clear"},
                {"text": "ℹ️ درباره ربات", "callback_data": "about"}
            ],
            [
                {"text": "❓ راهنما", "callback_data": "help"}
            ]
        ]
    }

# ───── هوش مصنوعی ─────

def ask_ai(user_id, text):
    if user_id not in user_histories:
        user_histories[user_id] = []
    user_histories[user_id].append({"role": "user", "content": text})
    history = user_histories[user_id][-20:]
    headers = {
        "Authorization": "Bearer " + COHERE_API_KEY,
        "Content-Type": "application/json"
    }
    data = {
        "model": "command-r7b-12-2024",
        "messages": [{"role": "system", "content": SYSTEM}] + history
    }
    r = requests.post(COHERE_URL, headers=headers, json=data)
    result = r.json()
    print("Cohere response:", result)
    reply = result["message"]["content"][0]["text"]
    user_histories[user_id].append({"role": "assistant", "content": reply})
    save_histories(user_histories)
    return reply

# ───── پاسخ به Callback (دکمه‌ها) ─────

def answer_callback(callback_query_id):
    requests.post(TG_URL + "/answerCallbackQuery", json={"callback_query_id": callback_query_id})

def handle_callback(callback):
    cid = callback["id"]
    chat_id = callback["message"]["chat"]["id"]
    user_id = str(callback["from"]["id"])
    data = callback.get("data", "")
    answer_callback(cid)

    if data == "clear":
        user_histories[user_id] = []
        save_histories(user_histories)
        send(chat_id, "✅ حافظه پاک شد! مکالمه جدید شروع شد.", reply_markup=main_menu())

    elif data == "about":
        send(chat_id,
             "🤖 *دستیار متین*\n\n"
             "این ربات توسط *متین* ساخته شده.\n"
             "هر سوالی داری بپرس، خوشحال میشم کمک کنم! 😊",
             reply_markup=main_menu())

    elif data == "help":
        send(chat_id,
             "📖 *راهنمای دستیار متین*\n\n"
             "🔹 کافیه پیامت رو بفرستی تا جواب بگیری.\n"
             "🔹 /start — شروع و منوی اصلی\n"
             "🔹 /clear — پاک کردن حافظه مکالمه\n"
             "🔹 /about — درباره ربات\n"
             "🔹 /help — نمایش این راهنما\n\n"
             "💡 ربات تاریخچه مکالمه رو حتی بعد از ری‌استارت هم به خاطر میاره!",
             reply_markup=main_menu())

# ───── پردازش پیام‌های متنی ─────

def handle_message(msg):
    chat_id = msg["chat"]["id"]
    user_id = str(msg["from"]["id"])
    first_name = msg["from"].get("first_name", "دوست عزیز")
    text = msg.get("text", "")

    if not text:
        send(chat_id, "⚠️ فقط پیام متنی پشتیبانی میشه.")
        return

    if text == "/start":
        send(chat_id,
             f"سلام {first_name} عزیز! 👋\n\n"
             "من *دستیار متین* هستم، ساخته شده توسط *متین*.\n"
             "هر سوالی داری بپرس، اینجام! 😊",
             reply_markup=main_menu())
        return

    if text == "/clear":
        user_histories[user_id] = []
        save_histories(user_histories)
        send(chat_id, "✅ حافظه پاک شد! مکالمه جدید شروع شد.", reply_markup=main_menu())
        return

    if text == "/about":
        send(chat_id,
             "🤖 *دستیار متین*\n\n"
             "این ربات توسط *متین* ساخته شده.\n"
             "هر سوالی داری بپرس، خوشحال میشم کمک کنم! 😊",
             reply_markup=main_menu())
        return

    if text == "/help":
        send(chat_id,
             "📖 *راهنمای دستیار متین*\n\n"
             "🔹 کافیه پیامت رو بفرستی تا جواب بگیری.\n"
             "🔹 /start — شروع و منوی اصلی\n"
             "🔹 /clear — پاک کردن حافظه مکالمه\n"
             "🔹 /about — درباره ربات\n"
             "🔹 /help — نمایش این راهنما\n\n"
             "💡 ربات تاریخچه مکالمه رو حتی بعد از ری‌استارت هم به خاطر میاره!",
             reply_markup=main_menu())
        return

    requests.post(TG_URL + "/sendChatAction", json={"chat_id": chat_id, "action": "typing"})
    try:
        reply = ask_ai(user_id, text)
        send(chat_id, reply)
    except Exception as e:
        print("خطا ask_ai: " + str(e))
        send(chat_id, "⚠️ خطایی رخ داد. دوباره امتحان کن.")

# ───── حلقه اصلی ─────

def main():
    print("ربات شروع به کار کرد!")
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
            print("خطا: " + str(e))

main()