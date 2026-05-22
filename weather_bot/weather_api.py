"""
Модуль работы с API погоды OpenWeatherMap
Предоставляет функции для получения текущей погоды и прогноза
"""

import aiohttp
from typing import Optional, Dict, Any, Tuple
from datetime import datetime


class WeatherAPI:
    """Класс для работы с OpenWeatherMap API"""
    
    def __init__(self, api_key: str):
        """
        Инициализация API клиента
        
        Args:
            api_key: API ключ от OpenWeatherMap
        """
        self.api_key = api_key
        self.base_url = "https://api.openweathermap.org/data/2.5"
    
    async def _make_request(self, endpoint: str, params: Dict[str, Any]) -> Optional[Dict]:
        """
        Выполнение HTTP запроса к API
        
        Args:
            endpoint: Конечная точка API
            params: Параметры запроса
            
        Returns:
            JSON ответ от API или None при ошибке
        """
        params['appid'] = self.api_key
        params['units'] = 'metric'  # Температура в Цельсиях
        
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(f"{self.base_url}/{endpoint}", params=params) as response:
                    if response.status == 200:
                        return await response.json()
                    else:
                        return None
            except Exception as e:
                print(f"Error making request to weather API: {e}")
                return None
    
    async def get_weather_by_coords(
        self,
        lat: float,
        lon: float,
        lang: str = 'ru'
    ) -> Optional[Dict[str, Any]]:
        """
        Получение текущей погоды по координатам
        
        Args:
            lat: Широта
            lon: Долгота
            lang: Язык ответа (ru, en, uk)
            
        Returns:
            Словарь с данными о погоде или None при ошибке
        """
        params = {
            'lat': lat,
            'lon': lon,
            'lang': lang,
            'exclude': 'minutely,hourly,alerts'  # Исключаем ненужные данные
        }
        
        result = await self._make_request('weather', params)
        
        if result:
            # Добавляем информацию о времени рассвета/заката в локальном времени
            if 'sys' in result and 'sunrise' in result['sys'] and 'timezone' in result:
                tz_offset = result['timezone']
                result['sys']['sunrise_local'] = datetime.fromtimestamp(
                    result['sys']['sunrise'] + tz_offset
                ).strftime('%H:%M')
                result['sys']['sunset_local'] = datetime.fromtimestamp(
                    result['sys']['sunset'] + tz_offset
                ).strftime('%H:%M')
        
        return result
    
    async def get_forecast_by_coords(
        self,
        lat: float,
        lon: float,
        lang: str = 'ru',
        days: int = 3
    ) -> Optional[Dict[str, Any]]:
        """
        Получение прогноза погоды на несколько дней по координатам
        
        Args:
            lat: Широта
            lon: Долгота
            lang: Язык ответа
            days: Количество дней для прогноза (максимум 5)
            
        Returns:
            Словарь с прогнозом погоды или None при ошибке
        """
        params = {
            'lat': lat,
            'lon': lon,
            'lang': lang,
            'cnt': days * 8  # 8 измерений в день (каждые 3 часа)
        }
        
        return await self._make_request('forecast', params)
    
    async def geocode_city(self, city_name: str, lang: str = 'ru') -> Optional[Tuple[float, float, str]]:
        """
        Геокодирование названия города в координаты
        
        Args:
            city_name: Название города
            lang: Язык поиска
            
        Returns:
            Кортеж (широта, долгота, название страны) или None если город не найден
        """
        params = {
            'q': city_name,
            'lang': lang,
            'limit': 1
        }
        
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(
                    "http://api.openweathermap.org/geo/1.0/direct",
                    params={**params, 'appid': self.api_key}
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data and len(data) > 0:
                            return (data[0]['lat'], data[0]['lon'], data[0].get('country', ''))
                    return None
            except Exception as e:
                print(f"Error geocoding city: {e}")
                return None
    
    @staticmethod
    def get_weather_emoji(weather_id: int) -> str:
        """
        Возвращает эмодзи для типа погоды
        
        Args:
            weather_id: ID типа погоды от OpenWeatherMap
            
        Returns:
            Строка с эмодзи
        """
        if 200 <= weather_id < 300:
            return "⛈️"  # Гроза
        elif 300 <= weather_id < 400:
            return "🌦️"  # Морось
        elif 400 <= weather_id < 500:
            return "🌧️"  # Дождь
        elif 500 <= weather_id < 600:
            return "🌧️"  # Ливень
        elif 600 <= weather_id < 700:
            return "❄️"  # Снег
        elif 700 <= weather_id < 800:
            return "🌫️"  # Атмосферные явления
        elif weather_id == 800:
            return "☀️"  # Ясно
        elif 801 <= weather_id < 900:
            return "⛅"  # Облачно
        else:
            return "🌡️"  # По умолчанию
    
    @staticmethod
    def get_wind_direction(degrees: int) -> str:
        """
        Определяет направление ветра по градусам
        
        Args:
            degrees: Направление ветра в градусах
            
        Returns:
            Строка с направлением ветра
        """
        directions = ['С', 'СВ', 'В', 'ЮВ', 'Ю', 'ЮЗ', 'З', 'СЗ']
        index = round(degrees / 45) % 8
        return directions[index]
