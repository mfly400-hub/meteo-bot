import telebot
import requests
import re
import logging
from datetime import datetime, timedelta

# Налаштування логування: запис у файл bot_activity.log та вивід у консоль
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("bot_activity.log", encoding="utf-8"),
        logging.StreamHandler()
    ]
)

TOKEN = "8679032582:AAGljGFF_n40NgLynM4Jtndyr_tHg74JgZI"
bot = telebot.TeleBot(TOKEN)

user_flights = {}
known_users = set()

def log_user_activity(message, action_type, details):
    user_id = message.from_user.id
    username = message.from_user.username or "Без юзернейму"
    first_name = message.from_user.first_name or ""
    last_name = message.from_user.last_name or ""
    full_name = f"{first_name} {last_name}".strip()
    
    is_new = "НОВИЙ" if user_id not in known_users else "АКТИВНІСТЬ"
    known_users.add(user_id)
    
    log_message = f"[{is_new}] ID: {user_id} | @{username} ({full_name}) | Дія: {action_type} | Запит: {details}"
    logging.info(log_message)

@bot.message_handler(commands=['start'])
def start(message):
    log_user_activity(message, "Команда /start", "Запуск бота")
    text = "👋 Вітаю! Я твій авіаційний метео-помічник.\n\n" \
           "Надішли мені **координати**, **посилання на карту** або **назву міста**, щоб отримати повний звіт по всіх ешелонах висоти."
    bot.send_message(message.chat.id, text)

@bot.message_handler(content_types=['text'])
def handle_text(message):
    chat_id = message.chat.id
    text = message.text.strip()
    
    lat, lon, location_name = None, None, ""

    coord_match = re.search(r'(-?\d+[\.,]\d+)\s*,\s*(-?\d+[\.,]\d+)', text)
    
    if coord_match:
        lat = float(coord_match.group(1).replace(',', '.'))
        lon = float(coord_match.group(2).replace(',', '.'))
        location_name = f"Точка за координатами ({round(lat, 4)}, {round(lon, 4)})"
        log_user_activity(message, "Пошук за координатами", text)
    
    elif "maps" in text or "google" in text or text.startswith("http"):
        log_user_activity(message, "Надіслав посилання", text)
        bot.send_message(chat_id, "🔍 Обробляю посилання на карту...")
        try:
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
            response = requests.get(text, allow_redirects=True, headers=headers, timeout=7)
            final_url = response.url
            
            url_match = re.search(r'@(-?\d+\.\d+),(-?\d+\.\d+)', final_url)
            if not url_match:
                url_match = re.search(r'[?&]q=(-?\d+\.\d+),(-?\d+\.\d+)', final_url)
            if not url_match:
                url_match = re.search(r'!3d(-?\d+\.\d+)!4d(-?\d+\.\d+)', final_url)

            if url_match:
                lat = float(url_match.group(1))
                lon = float(url_match.group(2))
                location_name = f"Локація з мапи ({round(lat, 4)}, {round(lon, 4)})"
            else:
                bot.send_message(chat_id, "❌ Не вдалося знайти координати.")
                logging.warning(f"Не вдалося спарсити URL: {text}")
                return
        except Exception as e:
            bot.send_message(chat_id, "❌ Помилка зчитування посилання.")
            logging.error(f"Помилка при запиті URL: {e}")
            return
            
    else:
        log_user_activity(message, "Пошук за назвою міста", text)
        bot.send_message(chat_id, f"🔍 Шукаю місто {text}...")
        geo_url = f"https://geocoding-api.open-meteo.com/v1/search?name={text}&count=1&language=uk"
        try:
            geo_data = requests.get(geo_url).json()
            if not geo_data.get('results'):
                bot.send_message(chat_id, "❌ Місто не знайдено.")
                return
            res = geo_data['results'][0]
            lat = res['latitude']
            lon = res['longitude']
            
            country = res.get('country', '')
            if country.lower() in ["росія", "російська федерація", "russia"]:
                country = "росія"
                
            location_name = f"{res['name']} ({country})"
        except Exception as e:
            bot.send_message(chat_id, "❌ Помилка пошуку міста.")
            logging.error(f"Помилка геокодера: {e}")
            return

    if lat and lon:
        user_flights[chat_id] = {
            'lat': lat,
            'lon': lon,
            'name': location_name
        }
        
        keyboard = telebot.types.InlineKeyboardMarkup()
        now = datetime.now()
        
        btn_now = telebot.types.InlineKeyboardButton(text="⏱️ Зараз", callback_data=f"time_{now.strftime('%Y-%m-%dT%H:00')}")
        keyboard.add(btn_now)
        
        for hours in [3, 6, 12]:
            future_time = now + timedelta(hours=hours)
            btn = telebot.types.InlineKeyboardButton(
                text=f"⏳ Через {hours} год ({future_time.strftime('%H:00')})", 
                callback_data=f"time_{future_time.strftime('%Y-%m-%dT%H:00')}"
            )
            keyboard.add(btn)
            
        tomorrow = now + timedelta(days=1)
        btn_tomorrow = telebot.types.InlineKeyboardButton(text=f"📅 Завтра о 12:00", callback_data=f"time_{tomorrow.strftime('%Y-%m-%dT12:00')}")
        keyboard.add(btn_tomorrow)

        bot.send_message(chat_id, f"📍 Локацію визначено: {location_name}\n\nОберіть час для прогнозу:", reply_markup=keyboard)

@bot.callback_query_handler(func=lambda call: call.data.startswith('time_'))
def handle_time_callback(call):
    chat_id = call.message.chat.id
    formatted_hour = call.data.split('_')[1]
    
    if chat_id not in user_flights:
        bot.send_message(chat_id, "❌ Сесія застаріла.")
        return
        
    flight_data = user_flights[chat_id]
    lat, lon = flight_data['lat'], flight_data['lon']
    
    bot.edit_message_reply_markup(chat_id, call.message.message_id, reply_markup=None)
    bot.send_message(chat_id, "⏳ Розраховую розширений авіаційний звіт...")
    
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
            
            # --- ПАРАМЕТРИ ЗЕМЛІ ---
            temp = hourly['temperature_2m'][idx]
            humidity = hourly['relativehumidity_2m'][idx]
            dew_point = hourly['dewpoint_2m'][idx]
            pressure = int(hourly['pressure_msl'][idx])
            clouds = hourly['cloudcover'][idx]
            
            vis_m = hourly.get('visibility', [10000])[idx]
            visibility_km = round(vis_m / 1000, 1) if vis_m else "N/A"
            
            w_speed_10 = round(hourly['windspeed_10m'][idx] / 3.6, 1)
            w_dir_10 = hourly['winddirection_10m'][idx]
            w_gusts = round(hourly['windgusts_10m'][idx] / 3.6, 1)
            
            # --- ВІТЕР ЗА ЕШЕЛОНАМИ ---
            w_speed_50 = round(((hourly['windspeed_10m'][idx] + hourly['windspeed_80m'][idx]) / 2) / 3.6, 1)
            w_dir_50 = int((hourly['winddirection_10m'][idx] + hourly['winddirection_80m'][idx]) / 2)
            
            w_speed_100 = round(hourly['windspeed_120m'][idx] / 3.6, 1)
            w_dir_100 = hourly['winddirection_120m'][idx]
            
            w_speed_110 = round(hourly['windspeed_120m'][idx] / 3.6, 1)
            w_dir_110 = hourly['winddirection_120m'][idx]
            
            w_speed_150 = round(hourly['windspeed_180m'][idx] / 3.6, 1)
            w_dir_150 = hourly['winddirection_180m'][idx]
            
            w_speed_300 = round(((hourly['windspeed_180m'][idx] + hourly['windspeed_950hPa'][idx]) / 2) / 3.6, 1)
            w_dir_300 = int((hourly['winddirection_180m'][idx] + hourly['winddirection_950hPa'][idx]) / 2)
            
            w_speed_500 = round(hourly['windspeed_950hPa'][idx] / 3.6, 1)
            w_dir_500 = hourly['winddirection_950hPa'][idx]
            
            w_speed_540 = round(hourly['windspeed_950hPa'][idx] / 3.6, 1)
            w_dir_540 = hourly['winddirection_950hPa'][idx]
            
            w_speed_760 = round(hourly['windspeed_925hPa'][idx] / 3.6, 1)
            w_dir_760 = hourly['winddirection_925hPa'][idx]
            
            w_speed_980 = round(hourly['windspeed_900hPa'][idx] / 3.6, 1)
            w_dir_980 = hourly['winddirection_900hPa'][idx]
            
            w_speed_1450 = round(hourly['windspeed_850hPa'][idx] / 3.6, 1)
            w_dir_1450 = hourly['winddirection_850hPa'][idx]
            
            w_speed_1500 = round(hourly['windspeed_850hPa'][idx] / 3.6, 1)
            w_dir_1500 = hourly['winddirection_850hPa'][idx]
            
            w_speed_1950 = round(hourly['windspeed_800hPa'][idx] / 3.6, 1)
            w_dir_1950 = hourly['winddirection_800hPa'][idx]
            
            display_time = datetime.strptime(formatted_hour, "%Y-%m-%dT%H:00").strftime("%d.%m.%Y %H:00")
            
            report = f"✈️ **ПОВНИЙ АВІАЦІЙНИЙ МЕТЕОЗВІТ**\n" \
                     f"📍 Локація: {flight_data['name']}\n" \
                     f"📅 Час: {display_time}\n" \
                     f"────────────────────────\n" \
                     f"🌍 **МЕТЕО ПАРАМЕТРИ ЗЕМЛІ (10 м):**\n" \
                     f"🌡 **Температура:** {temp}°C\n" \
                     f"💧 **Відносна вологість:** {humidity}%\n" \
                     f"🌱 **Точка роси:** {dew_point}°C\n" \
                     f"📉 **Тиск (MSLP):** {pressure} hPa\n" \
                     f"☁️ **Загальна хмарність:** {clouds}%\n" \
                     f"👁 **Видимість:** {visibility_km} км\n" \
                     f"💨 **Вітер біля землі:** {w_speed_10} м/с | Пориви: {w_gusts} м/с | Напрямок: {w_dir_10}°\n" \
                     f"────────────────────────\n" \
                     f"📈 **ВІТЕР ЗА ВСІМА ЕШЕЛОНАМИ:**\n\n" \
                     f"🔺 **50 м:** {w_speed_50} м/с | Напрямок: {w_dir_50}°\n" \
                     f"🔺 **100 м:** {w_speed_100} м/с | Напрямок: {w_dir_100}°\n" \
                     f"🔺 **110 м:** {w_speed_110} м/с | Напрямок: {w_dir_110}°\n" \
                     f"🔺 **150 м:** {w_speed_150} м/с | Напрямок: {w_dir_150}°\n" \
                     f"🔺 **300 м:** {w_speed_300} м/с | Напрямок: {w_dir_300}°\n" \
                     f"🔺 **500 м:** {w_speed_500} м/с | Напрямок: {w_dir_500}°\n" \
                     f"🔺 **540 м:** {w_speed_540} м/с | Напрямок: {w_dir_540}°\n" \
                     f"🔺 **760 м:** {w_speed_760} м/с | Напрямок: {w_dir_760}°\n" \
                     f"🔺 **980 м:** {w_speed_980} м/с | Напрямок: {w_dir_980}°\n" \
                     f"🔺 **1450 м:** {w_speed_1450} м/с | Напрямок: {w_dir_1450}°\n" \
                     f"🔺 **1500 м:** {w_speed_1500} м/с | Напрямок: {w_dir_1500}°\n" \
                     f"🔺 **1950 м:** {w_speed_1950} м/с | Напрямок: {w_dir_1950}°\n" \
                     f"────────────────────────\n" \
                     f"🛫 Безпечних польотів!RsPz"
                     
            bot.send_message(chat_id, report, parse_mode="Markdown")
            log_user_activity(call, "Отримав повний звіт (всі ешелони)", flight_data['name'])
            del user_flights[chat_id]
        else:
            bot.send_message(chat_id, "❌ Дані на цей час відсутні.")
            
    except Exception as e:
        bot.send_message(chat_id, "❌ Помилка розрахунку метеоданих.")
        logging.error(f"Помилка отримання погоди: {e}")

logging.info("Бот запускається. Логи тепер паралельно пишуться у файл bot_activity.log")
bot.polling(none_stop=True)