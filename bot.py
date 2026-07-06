import telebot, requests, re, logging
from datetime import datetime, timedelta

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
TOKEN = "8679032582:AAGljGFF_n40NgLynM4Jtndyr_tHg74JgZI"
bot = telebot.TeleBot(TOKEN)

target_heights = [50, 100, 110, 150, 300, 500, 540, 760, 980, 1450, 1500, 1950]
user_flights = {}

def get_octants(p):
    if p == 0: return "NSC (Ясно)"
    if p <= 25: return "FEW (1-2 окт.)"
    if p <= 50: return "SCT (3-4 окт.)"
    if p <= 87: return "BKN (5-7 окт.)"
    return "OVC (8 окт.)"

@bot.message_handler(commands=['start'])
def start(message):
    bot.send_message(message.chat.id, "👋 Надішли **координати**, **посилання** або **місто**.\n⚙️ Висоти: /set_h 100, 300")

@bot.message_handler(commands=['set_h'])
def set_heights(message):
    global target_heights
    try:
        cmd = message.text.replace('/set_h', '').strip()
        if not cmd:
            bot.reply_to(message, f"Поточні: {target_heights} м.")
            return
        target_heights = sorted([int(x.strip()) for x in cmd.split(',')])
        bot.reply_to(message, f"✅ Оновлено: {target_heights} м.")
    except:
        bot.reply_to(message, "❌ Помилка. Приклад: /set_h 100, 500")

@bot.message_handler(content_types=['text'])
def handle_text(message):
    if message.text.startswith('/'): return
    chat_id, text = message.chat.id, message.text.strip()
    lat, lon, name = None, None, ""

    coord_match = re.search(r'(-?\d+[\.,]\d+)\s*,\s*(-?\d+[\.,]\d+)', text)
    if coord_match:
        lat = float(coord_match.group(1).replace(',', '.'))
        lon = float(coord_match.group(2).replace(',', '.'))
        name = f"Точка ({round(lat,4)}, {round(lon,4)})"
    elif "maps" in text or "google" in text or text.startswith("http"):
        try:
            url = requests.get(text, allow_redirects=True, headers={'User-Agent': 'Mozilla'}, timeout=5).url
            m = re.search(r'@(-?\d+\.\d+),(-?\d+\.\d+)', url) or re.search(r'[?&]q=(-?\d+\.\d+),(-?\d+\.\d+)', url)
            lat, lon = float(m.group(1)), float(m.group(2))
            name = f"Мапа ({round(lat,4)}, {round(lon,4)})"
        except:
            return bot.send_message(chat_id, "❌ Не зчитав посилання.")
    else:
        try:
            res = requests.get(f"https://geocoding-api.open-meteo.com/v1/search?name={text}&count=1").json()['results'][0]
            lat, lon, name = res['latitude'], res['longitude'], f"{res['name']} ({res.get('country', '')})"
        except:
            return bot.send_message(chat_id, "❌ Місто не знайдено.")

    if lat and lon:
        user_flights[chat_id] = {'lat': lat, 'lon': lon, 'name': name}
        kb = telebot.types.InlineKeyboardMarkup()
        now = datetime.now()
        kb.add(telebot.types.InlineKeyboardButton("⏱️ Зараз", callback_data=f"time_{now.strftime('%Y-%m-%dT%H:00')}"))
        for h in [3, 6, 12]:
            f = now + timedelta(hours=h)
            kb.add(telebot.types.InlineKeyboardButton(f"⏳ +{h} год", callback_data=f"time_{f.strftime('%Y-%m-%dT%H:00')}"))
        bot.send_message(chat_id, f"📍 {name}\nОберіть час:", reply_markup=kb)

@bot.callback_query_handler(func=lambda call: call.data.startswith('time_'))
def handle_time_callback(call):
    chat_id = call.message.chat.id
    if chat_id not in user_flights:
        return bot.answer_callback_query(call.id, "❌ Сесія застаріла.")
        
    bot.answer_callback_query(call.id, "⏳ Рахую...")
    f_data = user_flights[chat_id]
    lat, lon, target_time = f_data['lat'], f_data['lon'], call.data.split('_')[1]
    
    bot.edit_message_reply_markup(chat_id, call.message.message_id, reply_markup=None)
    
    url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}" \
          f"&hourly=temperature_2m,relativehumidity_2m,dewpoint_2m,visibility,pressure_msl,cloudcover,windspeed_10m,winddirection_10m,windgusts_10m," \
          f"windspeed_80m,winddirection_80m,windspeed_120m,winddirection_120m,windspeed_180m,winddirection_180m," \
          f"windspeed_950hPa,winddirection_950hPa,windspeed_925hPa,winddirection_925hPa," \
          f"windspeed_900hPa,winddirection_900hPa,windspeed_850hPa,winddirection_850hPa,windspeed_800hPa,winddirection_800hPa"

    try:
        hr = requests.get(url).json()['hourly']
        if target_time not in hr['time']: return
        idx = hr['time'].index(target_time)
        
        vis = hr.get('visibility', [10000])[idx]
        vis_txt = "10+ км" if vis >= 10000 else f"{round(vis/1000, 1)} км"
        w_gust = round(hr['windgusts_10m'][idx] / 3.6, 1)

        # Компактний збір базових рівнів вітру (переводимо в м/с)
        levels = ['10m', '80m', '120m', '180m', '950hPa', '925hPa', '900hPa', '850hPa', '800hPa']
        s = {k: hr[f'windspeed_{k}'][idx] / 3.6 for k in levels}
        d = {k: hr[f'winddirection_{k}'][idx] for k in levels}

        # Динамічна карта висот
        speed_map = {
            50:   (round((s['10m'] + s['80m'])/2, 1), int((d['10m'] + d['80m'])/2)),
            100:  (round(s['120m'], 1), d['120m']), 110: (round(s['120m'], 1), d['120m']),
            150:  (round(s['180m'], 1), d['180m']),
            300:  (round((s['180m'] + s['950hPa'])/2, 1), int((d['180m'] + d['950hPa'])/2)),
            500:  (round(s['950hPa'], 1), d['950hPa']), 540: (round(s['950hPa'], 1), d['950hPa']),
            760:  (round(s['925hPa'], 1), d['925hPa']), 980: (round(s['900hPa'], 1), d['900hPa']),
            1450: (round(s['850hPa'], 1), d['850hPa']), 1500: (round(s['850hPa'], 1), d['850hPa']),
            1950: (round(s['800hPa'], 1), d['800hPa'])
        }

        t_print = datetime.strptime(target_time, "%Y-%m-%dT%H:00").strftime("%d.%m.%Y %H:00")
        
        rep = f"✈️ **МЕТЕОЗВІТ**\n📍 {f_data['name']}\n📅 {t_print}\n" \
              f"────────────────────────\n" \
              f"🌍 **ЗЕМЛЯ:**\n" \
              f"🌡️ {hr['temperature_2m'][idx]}°C | 💧 {hr['relativehumidity_2m'][idx]}% | 🌱 Роса: {hr['dewpoint_2m'][idx]}°C\n" \
              f"📉 Тиск: {int(hr['pressure_msl'][idx])} hPa | 👁️ Видимість: {vis_txt}\n" \
              f"☁️ Хмарність: {get_octants(hr['cloudcover'][idx])} ({hr['cloudcover'][idx]}%)\n" \
              f"💨 Вітер: {round(s['10m'],1)} м/с (пор. {w_gust}) | {d['10m']}°\n" \
              f"────────────────────────\n" \
              f"📈 **ВІТЕР ЗА ЕШЕЛОНАМИ:**\n"
              
        for h in target_heights:
            spd, dr = speed_map.get(h, (0, 0))
            rep += f"🔺 **{h} м:** {spd} м/с | {dr}°\n"
            
        rep += f"────────────────────────\n🌐 [Windy](https://www.windy.com/?{lat},{lon},10) | /set_h"
        bot.send_message(chat_id, rep, parse_mode="Markdown", disable_web_page_preview=True)
    except:
        bot.send_message(chat_id, "❌ Помилка API.")

bot.polling(none_stop=True)
