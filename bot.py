import telebot
import requests
import re
import logging
from datetime import datetime, timedelta

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s',
                    handlers=[logging.StreamHandler()])

TOKEN = "8679032582:AAGljGFF_n40NgLynM4Jtndyr_tHg74JgZI"
bot = telebot.TeleBot(TOKEN)

target_heights = [50, 100, 110, 150, 300, 500, 540, 760, 980, 1450, 1500, 1950]
user_flights = {}

def get_octants(percent):
    if percent == 0: return "NSC (Ясно)"
    if percent <= 25: return "FEW (Мала, 1-2 окт.)"
    if percent <= 50: return "SCT (Розсіяна, 3-4 окт.)"
    if percent <= 87: return "BKN (Хмарно, 5-7 окт.)"
    return "OVC (Суцільна, 8 окт.)"

@bot.message_handler(commands=['start'])
def start(message):
    bot.send_message(message.chat.id, "👋 Вітаю! Надішліть координати або місто.\n⚙️ Налаштувати висоти: /set_h 100, 500, 1000")

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
        bot.reply_to(message, "❌ Помилка! Введіть числа через кому.")

@bot.message_handler(content_types=['text'])
def handle_text(message):
    if message.text.startswith('/'): return
    # Логіка геокодингу (тут має бути ваш робочий код)
    # Після визначення lat/lon:
    user_flights[message.chat.id] = {'lat': lat, 'lon': lon, 'name': location_name}
    # (Вивід кнопок часу як у вас було)

@bot.callback_query_handler(func=lambda call: call.data.startswith('time_'))
def handle_time_callback(call):
    chat_id = call.message.chat.id
    flight_data = user_flights.get(chat_id)
    if not flight_data: return
    
    # ... (код запиту до API, отримання параметрів як у вас)
    
    # Розрахунок параметрів
    vis_km = round(hourly.get('visibility', [10000])[idx] / 1000, 1)
    vis_display = "10+ км" if vis_km >= 10 else f"{vis_km} км"
    clouds_octant = get_octants(hourly['cloudcover'][idx])
    
    # Словник висот (додайте всі свої 12 значень сюди)
    speed_map = { 50: (w_speed_50, w_dir_50), 100: (w_speed_100, w_dir_100), ... }

    report = f"✈️ **АВІАЦІЙНИЙ ЗВІТ**\n📍 {flight_data['name']}\n" \
             f"👁 **Видимість:** {vis_display}\n" \
             f"☁️ **Хмарність:** {clouds_octant} ({hourly['cloudcover'][idx]}%)\n" \
             f"────────────────────────\n"
    
    for h in target_heights:
        spd, dr = speed_map.get(h, (0, 0))
        report += f"🔺 **{h} м:** {spd} м/с | {dr}°\n"
        
    report += f"────────────────────────\n" \
              f"🌐 **Вінді:** [Переглянути](https://www.windy.com/?{flight_data['lat']},{flight_data['lon']},10)\n" \
              f"💡 /set_h 100, 300, 500\n🛫 Веселих польотів!"
              
    bot.send_message(chat_id, report, parse_mode="Markdown")

bot.polling(none_stop=True)
