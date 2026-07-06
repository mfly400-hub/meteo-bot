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
    if message.text.startswith('/'): 
        return
        
    chat_id = message.chat.id
    text = message.text.strip()
    
    lat, lon, location_name = None, None, ""

    # 1. Спроба знайти координати (числа через кому)
    coord_match = re.search(r'(-?\d+[\.,]\d+)\s*,\s*(-?\d+[\.,]\d+)', text)
    
    # 2. Спроба обробити посилання або назву
    if coord_match:
        lat = float(coord_match.group(1).replace(',', '.'))
        lon = float(coord_match.group(2).replace(',', '.'))
        location_name = f"Точка ({round(lat, 4)}, {round(lon, 4)})"
        
    elif "maps" in text or "google" in text or text.startswith("http"):
        bot.send_message(chat_id, "🔍 Аналізую посилання...")
        try:
            headers = {'User-Agent': 'Mozilla/5.0'}
            response = requests.get(text, allow_redirects=True, headers=headers, timeout=7)
            final_url = response.url
            
            # Шукаємо координати в посиланні
            url_match = re.search(r'@(-?\d+\.\d+),(-?\d+\.\d+)', final_url) or \
                        re.search(r'[?&]q=(-?\d+\.\d+),(-?\d+\.\d+)', final_url) or \
                        re.search(r'!3d(-?\d+\.\d+)!4d(-?\d+\.\d+)', final_url)
            
            if url_match:
                lat, lon = float(url_match.group(1)), float(url_match.group(2))
                location_name = f"Локація з мапи ({round(lat, 4)}, {round(lon, 4)})"
            else:
                bot.send_message(chat_id, "❌ Не знайшов координати в посиланні.")
                return
        except Exception as e:
            bot.send_message(chat_id, "❌ Помилка зчитування посилання.")
            return
            
    else:
        # 3. Пошук за назвою міста
        bot.send_message(chat_id, f"🔍 Шукаю: {text}...")
        geo_url = f"https://geocoding-api.open-meteo.com/v1/search?name={text}&count=1&language=uk"
        try:
            geo_data = requests.get(geo_url).json()
            if geo_data.get('results'):
                res = geo_data['results'][0]
                lat, lon = res['latitude'], res['longitude']
                location_name = f"{res['name']} ({res.get('country', '')})"
            else:
                bot.send_message(chat_id, "❌ Місто не знайдено.")
                return
        except:
            bot.send_message(chat_id, "❌ Помилка пошуку.")
            return

    # Якщо координати знайдені — створюємо кнопки
    if lat is not None and lon is not None:
        user_flights[chat_id] = {'lat': lat, 'lon': lon, 'name': location_name}
        
        keyboard = telebot.types.InlineKeyboardMarkup()
        now = datetime.now()
        keyboard.add(telebot.types.InlineKeyboardButton("⏱️ Зараз", callback_data=f"time_{now.strftime('%Y-%m-%dT%H:00')}"))
        for hours in [3, 6, 12]:
            future = now + timedelta(hours=hours)
            keyboard.add(telebot.types.InlineKeyboardButton(f"⏳ Через {hours} год", callback_data=f"time_{future.strftime('%Y-%m-%dT%H:00')}"))
        
        bot.send_message(chat_id, f"📍 {location_name}\nОберіть час:", reply_markup=keyboard)
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
   # Словник з усіма вашими висотами та змінними
    speed_map = {
        50: (w_speed_50, w_dir_50),
        100: (w_speed_100, w_dir_100),
        110: (w_speed_110, w_dir_110),
        150: (w_speed_150, w_dir_150),
        300: (w_speed_300, w_dir_300),
        500: (w_speed_500, w_dir_500),
        540: (w_speed_540, w_dir_540),
        760: (w_speed_760, w_dir_760),
        980: (w_speed_980, w_dir_980),
        1450: (w_speed_1450, w_dir_1450),
        1500: (w_speed_1500, w_dir_1500),
        1950: (w_speed_1950, w_dir_1950)
    }

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
