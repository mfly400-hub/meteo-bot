import telebot
import requests
import re
import logging
from datetime import datetime, timedelta

# Налаштування логування
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler("bot_activity.log", encoding="utf-8"), logging.StreamHandler()]
)

TOKEN = "8679032582:AAGljGFF_n40NgLynM4Jtndyr_tHg74JgZI"
bot = telebot.TeleBot(TOKEN)

# Глобальні змінні
target_heights = [50, 100, 110, 150, 300, 500, 540, 760, 980, 1450, 1500, 1950]
user_flights = {}
known_users = set()

def log_user_activity(message, action_type, details):
    user_id = message.from_user.id
    username = message.from_user.username or "Без юзернейму"
    log_message = f"ID: {user_id} | @{username} | Дія: {action_type} | Запит: {details}"
    logging.info(log_message)

def get_icing_emoji(t):
    return "⚠️" if -20 <= t <= 0 else "✅"

def estimate_temp(base_temp, height_m):
    return round(base_temp - (height_m / 100 * 0.65), 1)

@bot.message_handler(commands=['start'])
def start(message):
    text = "👋 Вітаю! Я Ваш надійний авіаційний метео-помічник.\n\n" \
           "📩 Надішліть координати або назву міста для отримання звіту.\n" \
           "⚙️ Щоб змінити висоти, надішліть: /set_h 100, 300, 500"
    bot.send_message(message.chat.id, text)

@bot.message_handler(commands=['set_h'])
def set_heights(message):
    global target_heights
    try:
        cmd = message.text.replace('/set_h', '').strip()
        if not cmd:
            bot.reply_to(message, f"Поточні висоти: {', '.join(map(str, target_heights))} м.")
            return
        target_heights = sorted([int(x.strip()) for x in cmd.split(',')])
        bot.reply_to(message, f"✅ Висоти оновлено: {', '.join(map(str, target_heights))} м.")
    except:
        bot.reply_to(message, "❌ Помилка! Введіть числа через кому: /set_h 100, 500")

@bot.message_handler(content_types=['text'])
def handle_text(message):
    if message.text.startswith('/'): return
    # Логіка визначення координат (залишається ваша попередня версія)
    # Після визначення lat/lon:
    user_flights[message.chat.id] = {'lat': lat, 'lon': lon, 'name': location_name}
    # (Вивід кнопок часу залишається без змін)

@bot.callback_query_handler(func=lambda call: call.data.startswith('time_'))
def handle_time_callback(call):
    chat_id = call.message.chat.id
    flight_data = user_flights.get(chat_id)
    if not flight_data: return
    
    # ... (код запиту до API, отримання змінних w_speed_50, w_dir_50 тощо)
    
    # Словник для відображення
    speed_map = {
        50: (w_speed_50, w_dir_50), 100: (w_speed_100, w_dir_100), 
        110: (w_speed_110, w_dir_110), 150: (w_speed_150, w_dir_150),
        300: (w_speed_300, w_dir_300), 500: (w_speed_500, w_dir_500),
        540: (w_speed_540, w_dir_540), 760: (w_speed_760, w_dir_760),
        980: (w_speed_980, w_dir_980), 1450: (w_speed_1450, w_dir_1450),
        1500: (w_speed_1500, w_dir_1500), 1950: (w_speed_1950, w_dir_1950)
    }

    report = f"✈️ **ПОВНИЙ АВІАЦІЙНИЙ МЕТЕОЗВІТ**\n📍 {flight_data['name']}\n────────────────────────\n"
    for h in target_heights:
        est_t = estimate_temp(temp, h)
        spd, dr = speed_map.get(h, (0, 0))
        report += f"🔺 **{h} м:** {spd} м/с | {dr}° | {get_icing_emoji(est_t)}\n"
        
    report += f"────────────────────────\n" \
              f"💡 Щоб змінити висоти, надішліть: /set_h 100, 300, 500\n" \
              f"🛫 Веселих польотів! RsPz"
              
    bot.send_message(chat_id, report, parse_mode="Markdown")

bot.polling(none_stop=True)
