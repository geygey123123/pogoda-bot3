"""
Модуль форматирования сообщений о погоде
Создает красивые и информативные сообщения с использованием эмодзи
"""

from typing import Dict, Any, Optional
from datetime import datetime
from weather_api import WeatherAPI


class WeatherFormatter:
    """Класс для красивого форматирования данных о погоде"""
    
    @staticmethod
    def format_current_weather(data: Dict[str, Any], location_name: str = "") -> str:
        """
        Форматирование текущей погоды в красивое сообщение
        
        Args:
            data: Данные о погоде от API
            location_name: Название локации (город или координаты)
            
        Returns:
            Отформатированная строка с информацией о погоде
        """
        if not data:
            return "❌ Не удалось получить данные о погоде"
        
        # Основная информация
        temp = data['main']['temp']
        feels_like = data['main']['feels_like']
        weather_id = data['weather'][0]['id']
        weather_desc = data['weather'][0]['description'].capitalize()
        weather_icon = WeatherAPI.get_weather_emoji(weather_id)
        
        # Ветер
        wind_speed = data['wind']['speed']
        wind_deg = data['wind'].get('deg', 0)
        wind_dir = WeatherAPI.get_wind_direction(wind_deg)
        
        # Влажность и давление
        humidity = data['main']['humidity']
        pressure = round(data['main']['pressure'] * 0.750062)  # Конвертация в мм рт. ст.
        
        # Рассвет и закат
        sunrise = data['sys'].get('sunrise_local', 'N/A')
        sunset = data['sys'].get('sunset_local', 'N/A')
        
        # Формируем сообщение
        message = f"""
{weather_icon} <b>Погода сейчас</b> {weather_icon}

📍 <b>Локация:</b> {location_name or data.get('name', 'Неизвестно')}

🌡️ <b>Температура:</b>
   • Фактическая: <b>{temp:+.1f}°C</b>
   • Ощущается как: <b>{feels_like:+.1f}°C</b>

☁️ <b>Описание:</b> {weather_desc}

💧 <b>Влажность:</b> {humidity}%
📊 <b>Давление:</b> {pressure} мм рт. ст.

💨 <b>Ветер:</b> {wind_speed:.1f} м/с ({wind_dir})

🌅 <b>Рассвет:</b> {sunrise}
🌇 <b>Закат:</b> {sunset}

<i>Данные предоставлены OpenWeatherMap</i>
"""
        return message.strip()
    
    @staticmethod
    def format_forecast(data: Dict[str, Any], days: int = 3) -> str:
        """
        Форматирование прогноза погоды на несколько дней
        
        Args:
            data: Данные прогноза от API
            days: Количество дней для отображения
            
        Returns:
            Отформатированная строка с прогнозом
        """
        if not data or 'list' not in data:
            return "❌ Не удалось получить прогноз погоды"
        
        location_name = data.get('city', {}).get('name', 'Неизвестно')
        country = data.get('city', {}).get('country', '')
        timezone_offset = data.get('city', {}).get('timezone', 0)
        
        message = f"""📅 <b>Прогноз погоды на {days} дня(ей)</b> 📅

📍 {location_name}, {country}

"""
        
        # Группируем данные по дням
        daily_data = {}
        for item in data['list']:
            dt = datetime.fromtimestamp(item['dt'] + timezone_offset)
            date_str = dt.strftime('%Y-%m-%d')
            
            if date_str not in daily_data:
                daily_data[date_str] = {
                    'temps': [],
                    'weather_ids': [],
                    'descriptions': [],
                    'date_obj': dt
                }
            
            daily_data[date_str]['temps'].append(item['main']['temp'])
            daily_data[date_str]['weather_ids'].append(item['weather'][0]['id'])
            daily_data[date_str]['descriptions'].append(item['weather'][0]['description'])
        
        # Форматируем каждый день
        day_names = {
            0: 'Понедельник',
            1: 'Вторник',
            2: 'Среда',
            3: 'Четверг',
            4: 'Пятница',
            5: 'Суббота',
            6: 'Воскресенье'
        }
        
        for i, (date_str, day_info) in enumerate(sorted(daily_data.items())[:days]):
            date_obj = day_info['date_obj']
            day_name = day_names.get(date_obj.weekday(), 'День')
            date_formatted = date_obj.strftime('%d.%m')
            
            # Минимальная и максимальная температура
            min_temp = min(day_info['temps'])
            max_temp = max(day_info['temps'])
            
            # Преобладающая погода (наиболее частый weather_id)
            most_common_weather_id = max(set(day_info['weather_ids']), key=day_info['weather_ids'].count)
            weather_icon = WeatherAPI.get_weather_emoji(most_common_weather_id)
            
            # Преобладающее описание
            most_common_desc = max(set(day_info['descriptions']), key=day_info['descriptions'].count)
            
            message += f"""<b>{day_name}, {date_formatted}</b>
{weather_icon} {most_common_desc.capitalize()}
🌡️ {min_temp:+.0f}°C ... {max_temp:+.0f}°C

"""
        
        message += "<i>Прогноз обновляется каждые 3 часа</i>"
        
        return message.strip()
    
    @staticmethod
    def format_error_message(error_type: str) -> str:
        """
        Форматирование сообщения об ошибке
        
        Args:
            error_type: Тип ошибки
            
        Returns:
            Отформатированное сообщение об ошибке
        """
        errors = {
            'city_not_found': "❌ Город не найден. Пожалуйста, проверьте правильность названия или попробуйте отправить геопозицию.",
            'api_error': "⚠️ Временно недоступен сервис погоды. Попробуйте позже.",
            'no_location': "📍 Пожалуйста, отправьте геопозицию или введите название города.",
            'invalid_input': "❌ Некорректный ввод. Пожалуйста, введите название города или используйте кнопку «Поделиться геопозицией»."
        }
        
        return errors.get(error_type, "❌ Произошла неизвестная ошибка. Попробуйте позже.")
