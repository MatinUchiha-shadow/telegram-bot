import requests

TELEGRAM_TOKEN = "8602655242:AAEHikXtfhrs-6yqbU-ygTaFmvwBBeKgG-M"
COHERE_API_KEY = "KrDOjWoGuBZvvTQRj8D5YqjDKU6dA5nkiyJBMPoj"
COHERE_URL = "https://api.cohere.com/v2/chat"
TG_URL = "https://api.telegram.org/bot" + TELEGRAM_TOKEN

user_histories = {}
SYSTEM = """تو یه دستیار هوشمند فارسی‌زبان هستی. همیشه به فارسی جواب بده مگه اینکه کاربر انگلیسی بنویسه.
اسم تو «دست یار شخصی متین» هست. اگه کسی پرسید اسمت چیه یا چی هستی، بگو: من دست یار شخصی متین هستم.
سازنده تو Matin_Uchiha هست. اگه کسی پرسید سازنده‌ات کیه یا چه کسی تو رو ساخته، بگو: سازنده من Matin_Uchiha هست."""

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
        "model": "command-r-plus",
        "messages": [{"role": "system", "content": SYSTEM}] + history
    }
    r = requests.post(COHERE_URL, headers=headers, json=data)
    result = r.json()
    print("Cohere response:", result)
    reply = result["message"]["content"][0]["text"]
    user_histories[user_id].append({"role": "assistant", "content": reply})
    return reply

def send(chat_id, text):
    requests.post(TG_URL + "/sendMessage", json={"chat_id": chat_id, "text": text[:4096]})

def main():
    print("ربات شروع به کار کرد!")
    offset = None
    while True:
        try:
            r = requests.get(TG_URL + "/getUpdates", params={"timeout": 30, "offset": offset}, timeout=35)
            updates = r.json()
            for update in updates.get("result", []):
                offset = update["update_id"] + 1
                msg = update.get("message", {})
                if not msg:
                    continue
                chat_id = msg["chat"]["id"]
                user_id = str(msg["from"]["id"])
                text = msg.get("text", "")
                if not text:
                    continue
                if text == "/start":
                    send(chat_id, "سلام! هر سوالی داری بپرس.")
                    continue
                if text == "/clear":
                    user_histories[user_id] = []
                    send(chat_id, "حافظه پاک شد!")
                    continue
                requests.post(TG_URL + "/sendChatAction", json={"chat_id": chat_id, "action": "typing"})
                try:
                    reply = ask_ai(user_id, text)
                    send(chat_id, reply)
                except Exception as e:
                    print("خطا ask_ai: " + str(e))
                    send(chat_id, "خطایی رخ داد. دوباره امتحان کن.")
        except Exception as e:
            print("خطا: " + str(e))

main()