import telebot
import requests
from telebot import types

# Токен бота
TOKEN = 'ВАШ_ТОКЕН_ТУТ'
bot = telebot.TeleBot(TOKEN)

def get_icing_emoji(t):
    return "⚠️" if -20 <= t <= 0 else "✅"

def estimate_temp(base_temp, height_m):
    return round(base_temp - (height_m / 100 * 0.65), 1)

@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(message, "Привіт! Надішли мені координати (широту, довготу) у форматі: 50.45, 30.52")

@bot.message_handler(func=lambda message: True)
def get_weather(message):
    try:
        lat, lon = map(float, message.text.split(','))
        url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&hourly=temperature_2m,relative_humidity_2m,pressure_msl,wind_speed_10m,wind_direction_10m&wind_speed_unit=ms"
        data = requests.get(url).json()
        
        idx = 0  # Поточний час
        temp = data['hourly']['temperature_2m'][idx]
        humidity = data['hourly']['relative_humidity_2m'][idx]
        pressure = data['hourly']['pressure_msl'][idx]
        w_speed_10 = data['hourly']['wind_speed_10m'][idx]
        w_dir_10 = data['hourly']['wind_direction_10m'][idx]
        
        # Спрощені розрахунки для висот (на основі вітру землі)
        h = [50, 100, 150, 300, 500, 540, 760, 980, 1450, 1500, 1950]
        
        report = f"✈️ **МЕТЕОЗВІТ**\n📍 {lat}, {lon}\n" \
                 f"🌍 Земля: {temp}°C | {humidity}% | {pressure} hPa\n" \
                 f"💨 Вітер (10м): {w_speed_10} м/с, {w_dir_10}°\n" \
                 f"────────────────────────\n" \
                 f"📈 **ЕШЕЛОНИ (Вітер | Зледеніння):**\n\n"

        for height in h:
            est_t = estimate_temp(temp, height)
            # Коефіцієнт швидкості вітру з висотою (спрощений)
            speed = round(w_speed_10 * (1 + height/1000), 1)
            report += f"{height} м: {speed} м/с | {get_icing_emoji(est_t)}\n"

        report += f"────────────────────────\n⚠️ - ризик в діапазоні 0..-20°C"
        bot.reply_to(message, report, parse_mode="Markdown")

    except Exception as e:
        bot.reply_to(message, f"Помилка: {e}")

if __name__ == '__main__':
    while True:
        try:
            bot.polling(none_stop=True)
        except Exception:
            import time
            time.sleep(5)
