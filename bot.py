import telebot
import requests
import re
import logging
from datetime import datetime, timedelta

# Логування лише в консоль (на серверах Railway лог-файли створювати не потрібно)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

TOKEN = "8679032582:AAGljGFF_n40NgLynM4Jtndyr_tHg74JgZI"
bot = telebot.TeleBot(TOKEN)

target_heights = [50, 100, 110, 150, 300, 500, 540, 760, 980, 1450, 1500, 1950]
user_flights = {}
known_users = set()

def get_octants(percent):
    if percent == 0: return "NSC (Ясно)"
    if percent <= 25: return "FEW (Мала, 1-2 окт.)"
    if percent <= 50: return "SCT (Розсіяна, 3-4 окт.)"
    if percent <= 87: return "BKN (Хмарно, 5-7 окт.)"
    return "OVC (Суцільна, 8 окт.)"

def log_user_activity(message, action_type, details):
    user_id = message.from_user.id
    username = message.from_user.username or "Без юзернейму"
    first_name = message.from_user.first_name or ""
    last_name = message.from_user.last_name or ""
    full_name = f"{first_name} {last_name}".strip()
    
    is_new = "НОВИЙ" if user_id not in known_users else "АКТИВНІСТЬ"
    known_users.add(user_id)
    
    logging.info(f"[{is_new}] ID: {user_id} | @{username} ({full_name}) | Дія: {action_type} | Запит: {details}")

@bot.message_handler(commands=['start'])
def start(message):
    log_user_activity(message, "Команда /start", "Запуск бота")
    text = "👋 Вітаю! Я твій авіаційний метео-помічник.\n\n" \
           "Надішли мені **координати**, **посилання на карту** або **назву міста**.\n" \
           "⚙️ Змінити висоти: /set_h 100, 300, 500"
    bot.send_message(message.chat.id, text)

@bot.message_handler(commands=['set_h'])
def set_heights(message):
    global target_heights
    try:
        cmd = message.text.replace('/set_h', '').strip()
        if not cmd:
            bot.reply_to(message, f"Поточні висоти: {', '.join(map(str, target_heights))} м.\nЩоб змінити, напишіть: /set_h 100, 500")
            return
        target_heights = sorted([int(x.strip()) for x in cmd.split(',')])
        bot.reply_to(message, f"✅ Висоти оновлено: {', '.join(map(str, target_heights))} м.")
    except:
        bot.reply_to(message, "❌ Помилка! Введіть числа через кому: /set_h 100, 500")

@bot.message_handler(content_types=['text'])
def handle_text(message):
    if message.text.startswith('/'): return
    
    chat_id = message.chat.id
    text = message.text.strip()
    lat, lon, location_name = None, None, ""

    coord_match = re.search(r'(-?\d+[\.,]\d+)\s*,\s*(-?\d+[\.,]\d+)', text)
    
    if coord_match:
        lat = float(coord_match.group(1).replace(',', '.'))
        lon = float(coord_match.group(2).replace(',', '.'))
        location_name = f"Точка ({round(lat, 4)}, {round(lon, 4)})"
        log_user_activity(message, "Пошук за координатами", text)
        
    elif "maps" in text or "google" in text or text.startswith("http"):
        log_user_activity(message, "Надіслав посилання", text)
        bot.send_message(chat_id, "🔍 Обробляю посилання...")
        try:
            headers = {'User-Agent': 'Mozilla/5.0'}
            response = requests.get(text, allow_redirects=True, headers=headers, timeout=7)
            final_url = response.url
            url_match = re.search(r'@(-?\d+\.\d+),(-?\d+\.\d+)', final_url) or \
                        re.search(r'[?&]q=(-?\d+\.\d+),(-?\d+\.\d+)', final_url) or \
                        re.search(r'!3d(-?\d+\.\d+)!4d(-?\d+\.\d+)', final_url)
            if url_match:
                lat, lon = float(url_match.group(1)), float(url_match.group(2))
                location_name = f"Локація з мапи ({round(lat, 4)}, {round(lon, 4)})"
            else:
                bot.send_message(chat_id, "❌ Не знайдено координати в посиланні.")
                return
        except Exception as e:
            bot.send_message(chat_id, "❌ Помилка зчитування посилання.")
            logging.error(f"Помилка URL: {e}")
            return
            
    else:
        log_user_activity(message, "Пошук за назвою", text)
        bot.send_message(chat_id, f"🔍 Шукаю {text}...")
        try:
            geo_url = f"https://geocoding-api.open-meteo.com/v1/search?name={text}&count=1&language=uk"
            geo_data = requests.get(geo_url).json()
            if not geo_data.get('results'):
                bot.send_message(chat_id, "❌ Місто не знайдено.")
                return
            res = geo_data['results'][0]
            lat, lon = res['latitude'], res['longitude']
            location_name = f"{res['name']} ({res.get('country', '')})"
        except Exception as e:
            bot.send_message(chat_id, "❌ Помилка пошуку.")
            logging.error(f"Помилка геокодера: {e}")
            return

        # Захист від пустих значень
        if lat is None or lon is None:
            return

    if lat is not None and lon is not None:
        user_flights[chat_id] = {'lat': lat, 'lon': lon, 'name': location_name}
        
        keyboard = telebot.types.InlineKeyboardMarkup()
        now = datetime.now()
        keyboard.add(telebot.types.InlineKeyboardButton("⏱️ Зараз", callback_data=f"time_{now.strftime('%Y-%m-%dT%H:00')}"))
        for hours in [3, 6, 12]:
            future = now + timedelta(hours=hours)
            keyboard.add(telebot.types.InlineKeyboardButton(f"⏳ Через {hours} год", callback_data=f"time_{future.strftime('%Y-%m-%dT%H:00')}"))
            
        bot.send_message(chat_id, f"📍 Локацію визначено: {location_name}\nОберіть час для прогнозу:", reply_markup=keyboard)

@bot.callback_query_handler(func=lambda call: call.data.startswith('time_'))
def handle_time_callback(call):
    chat_id = call.message.chat.id
    
    if chat_id not in user_flights:
        bot.answer_callback_query(call.id, "❌ Сесія застаріла. Надішліть координати знову.")
        bot.send_message(chat_id, "⏳ Сесія застаріла. Будь ласка, надішліть локацію заново.")
        return
        
    bot.answer_callback_query(call.id, "⏳ Розраховую звіт...")
    
    flight_data = user_flights[chat_id]
    lat, lon = flight_data['lat'], flight_data['lon']
    formatted_hour = call.data.split('_')[1]
    
    bot.edit_message_reply_markup(chat_id, call.message.message_id, reply_markup=None)
    bot.send_message(chat_id, "⏳ Отримую авіаційні метеодані...")
    
    url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}" \
          f"&hourly=temperature_2m,relativehumidity_2m,dewpoint_2m,visibility,pressure_msl,cloudcover,windspeed_10m,winddirection_10m,windgusts_10m," \
          f"windspeed_80m,winddirection_80m,windspeed_120m,winddirection_120m,windspeed_180m,winddirection_180m," \
          f"windspeed_950hPa,winddirection_950hPa,windspeed_925hPa,winddirection_925hPa," \
          f"windspeed_900hPa,winddirection_900hPa,windspeed_850hPa,winddirection_850hPa,windspeed_800hPa,winddirection_800hPa"
          
    try:
        data = requests.get(url).json()
        hourly = data['hourly']
        
        if formatted_hour in hourly['time']:
            idx = hourly['time'].index(formatted_hour)
            
            temp = hourly['temperature_2m'][idx]
            humidity = hourly['relativehumidity_2m'][idx]
            dew_point = hourly['dewpoint_2m'][idx]
            pressure = int(hourly['pressure_msl'][idx])
            
            vis_m = hourly.get('visibility', [10000])[idx]
            vis_km = round(vis_m / 1000, 1) if vis_m else 0
            vis_display = "10+ км" if vis_km >= 10 else f"{vis_km} км"
            
            clouds_octant = get_octants(hourly['cloudcover'][idx])
            
            w_speed_10 = round(hourly['windspeed_10m'][idx] / 3.6, 1)
            w_dir_10 = hourly['winddirection_10m'][idx]
            w_gusts = round(hourly['windgusts_10m'][idx] / 3.6, 1)
            
            w_speed_50 = round(((hourly['windspeed_10m'][idx] + hourly['windspeed_80m'][idx]) / 2) / 3.6, 1)
            w_dir_50 = int((hourly['winddirection_10m'][idx] + hourly['winddirection_80m'][idx]) / 2)
            w_speed_100 = round(hourly['windspeed_120m'][idx] / 3.6, 1)
            w_dir_100 = hourly['winddirection_120m'][idx]
            w_speed_110 = w_speed_100
            w_dir_110 = w_dir_100
            w_speed_150 = round(hourly['windspeed_180m'][idx] / 3.6, 1)
            w_dir_150 = hourly['winddirection_180m'][idx]
            w_speed_300 = round(((hourly['windspeed_180m'][idx] + hourly['windspeed_950hPa'][idx]) / 2) / 3.6, 1)
            w_dir_300 = int((hourly['winddirection_180m'][idx] + hourly['winddirection_950hPa'][idx]) / 2)
            w_speed_500 = round(hourly['windspeed_950hPa'][idx] / 3.6, 1)
            w_dir_500 = hourly['winddirection_950hPa'][idx]
            w_speed_540 = w_speed_500
            w_dir_540 = w_dir_500
            w_speed_760 = round(hourly['windspeed_925hPa'][idx] / 3.6, 1)
            w_dir_760 = hourly['winddirection_925hPa'][idx]
            w_speed_980 = round(hourly['windspeed_900hPa'][idx] / 3.6, 1)
            w_dir_980 = hourly['winddirection_900hPa'][idx]
            w_speed_1450 = round(hourly['windspeed_850hPa'][idx] / 3.6, 1)
            w_dir_1450 = hourly['winddirection_850hPa'][idx]
            w_speed_1500 = w_speed_1450
            w_dir_1500 = w_dir_1450
            w_speed_1950 = round(hourly['windspeed_800hPa'][idx] / 3.6, 1)
            w_dir_1950 = hourly['winddirection_800hPa'][idx]
            
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
            
            display_time = datetime.strptime(formatted_hour, "%Y-%m-%dT%H:00").strftime("%d.%m.%Y %H:00")
            
            report = f"✈️ **АВІАЦІЙНИЙ МЕТЕОЗВІТ**\n" \
                     f"📍 Локація: {flight_data['name']}\n" \
                     f"📅 Час: {display_time}\n" \
                     f"────────────────────────\n" \
                     f"🌍 **ЗЕМЛЯ (10 м):**\n" \
                     f"🌡 Темп: {temp}°C | 💧 Вол: {humidity}% | 🌱 Роса: {dew_point}°C\n" \
                     f"📉 Тиск (MSLP): {pressure} hPa\n" \
                     f"👁 **Видимість:** {vis_display}\n" \
                     f"☁️ **Хмарність:** {clouds_octant} ({hourly['cloudcover'][idx]}%)\n" \
                     f"💨 **Вітер:** {w_speed_10} м/с (пориви {w_gusts}) | {w_dir_10}°\n" \
                     f"────────────────────────\n" \
                     f"📈 **ВІТЕР ЗА ЕШЕЛОНАМИ:**\n\n"
            
            for h in target_heights:
                spd, dr = speed_map.get(h, (0, 0))
                report += f"🔺 **{h} м:** {spd} м/с | Напрямок: {dr}°\n"
                
            report += f"────────────────────────\n" \
                      f"🌐 **Вінді (Карта вітрів):** [Відкрити](https://www.windy.com/?{lat},{lon},10)\n" \
                      f"💡 Змінити висоти: /set_h 100, 300, 500\n" \
                      f"🛫 Безпечних польотів! RsPz"
            
            bot.send_message(chat_id, report, parse_mode="Markdown", disable_web_page_preview=True)
            log_user_activity(call, "Видав звіт", flight_data['name'])
            
        else:
            bot.send_message(chat_id, "❌ Дані на цей час відсутні.")
            
    except Exception as e:
        bot.send_message(chat_id, "❌ Помилка розрахунку.")
        logging.error(f"Помилка погоди: {e}")

bot.polling(none_stop=True)
