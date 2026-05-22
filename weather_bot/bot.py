"""
Основной модуль Telegram-бота
Обрабатывает сообщения пользователей и взаимодействует с API погоды
"""

import asyncio
import logging
from typing import Optional
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from dotenv import load_dotenv
import os

from database import Database
from weather_api import WeatherAPI
from formatter import WeatherFormatter
from google_sync import GoogleSheetsSync

# Загружаем переменные окружения из .env файла
load_dotenv()

# Настраиваем логирование
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class WeatherStates(StatesGroup):
    """Машина состояний для обработки ввода города"""
    waiting_for_city = State()


class WeatherBot:
    """Основной класс Telegram-бота"""
    
    def __init__(self):
        """Инициализация бота и всех сервисов"""
        # Получаем токены из переменных окружения
        self.telegram_token = os.getenv('TELEGRAM_BOT_TOKEN')
        self.weather_api_key = os.getenv('OPENWEATHER_API_KEY')
        
        if not self.telegram_token or not self.weather_api_key:
            raise ValueError("Необходимо установить TELEGRAM_BOT_TOKEN и OPENWEATHER_API_KEY в .env файле")
        
        # Инициализируем сервисы
        self.bot = Bot(token=self.telegram_token)
        self.dp = Dispatcher()
        self.db = Database(os.getenv('DATABASE_PATH', 'users.db'))
        self.weather_api = WeatherAPI(self.weather_api_key)
        
        # Опциональная синхронизация с Google Sheets
        google_credentials = os.getenv('GOOGLE_CREDENTIALS_JSON', '')
        google_sheet_name = os.getenv('GOOGLE_SHEET_NAME', 'weather_bot_users')
        self.google_sync = GoogleSheetsSync(google_credentials, google_sheet_name) if google_credentials else None
        
        # Регистрируем обработчики
        self._register_handlers()
    
    def _get_main_keyboard(self) -> ReplyKeyboardMarkup:
        """
        Создание главного меню с кнопками
        
        Returns:
            ReplyKeyboardMarkup с основными кнопками
        """
        keyboard = ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="🌤 Погода сейчас")],
                [KeyboardButton(text="📅 Прогноз на 3 дня")],
                [KeyboardButton(text="⚙ Настройки"), KeyboardButton(text="📍 Поделиться геопозицией")]
            ],
            resize_keyboard=True,
            one_time_keyboard=False
        )
        return keyboard
    
    def _register_handlers(self):
        """Регистрация всех обработчиков сообщений"""
        
        # Команда /start
        @self.dp.message(CommandStart())
        async def cmd_start(message: types.Message):
            """Обработчик команды /start"""
            user_id = message.from_user.id
            username = message.from_user.username
            
            # Сохраняем пользователя в базу
            self.db.create_or_update_user(
                user_id=user_id,
                username=username
            )
            
            welcome_text = f"""
👋 Привет, {message.from_user.first_name}!

Я погодный бот 🌤️. Я могу показать тебе подробную погоду в любой точке мира!

<b>Как пользоваться:</b>
• Нажми «📍 Поделиться геопозицией» чтобы отправить свои координаты
• Или введи название города текстом (например: Киев, Москва, London)
• Используй кнопки меню для быстрого доступа

Выбери город и узнай погоду! ☀️🌧️❄️
"""
            
            await message.answer(
                welcome_text,
                reply_markup=self._get_main_keyboard(),
                parse_mode='HTML'
            )
        
        # Обработка команды /help
        @self.dp.message(Command("help"))
        async def cmd_help(message: types.Message):
            """Обработчик команды /help"""
            help_text = """
ℹ️ <b>Помощь по боту</b>

<b>Основные команды:</b>
/start - Запустить бота
/help - Показать эту справку

<b>Как получить погоду:</b>
1. Отправьте геопозицию через кнопку «📍 Поделиться геопозицией»
2. Или введите название города текстом
3. Используйте кнопки меню:
   • 🌤 Погода сейчас - текущая погода
   • 📅 Прогноз на 3 дня - прогноз на ближайшие дни
   • ⚙ Настройки - настройки бота

Поддерживаются города на русском, украинском и английском языках! 🌍
"""
            await message.answer(help_text, parse_mode='HTML')
        
        # Обработка кнопки "Поделиться геопозицией"
        @self.dp.message(F.text == "📍 Поделиться геопозицией")
        async def request_location(message: types.Message):
            """Запрос геопозиции у пользователя"""
            await message.answer(
                "📍 Пожалуйста, отправьте вашу геопозицию!\n\n"
                "Нажмите на значок 📎 (скрепка) → Геопозиция → Отправить",
                reply_markup=types.ReplyKeyboardRemove()
            )
        
        # Обработка полученной геопозиции
        @self.dp.message(F.location)
        async def handle_location(message: types.Message):
            """Обработка полученной геопозиции"""
            user_id = message.from_user.id
            lat = message.location.latitude
            lon = message.location.longitude
            
            # Сохраняем локацию в базу
            self.db.create_or_update_user(
                user_id=user_id,
                lat=lat,
                lon=lon
            )
            
            # Логгируем запрос
            self.db.log_request(user_id, 'location', f'{lat},{lon}')
            
            await message.answer(
                f"✅ Геопозиция получена!\n📍 Координаты: {lat:.4f}, {lon:.4f}\n\n"
                f"Теперь выберите в меню:\n• 🌤 Погода сейчас\n• 📅 Прогноз на 3 дня",
                reply_markup=self._get_main_keyboard()
            )
        
        # Обработка кнопки "Погода сейчас"
        @self.dp.message(F.text == "🌤 Погода сейчас")
        async def current_weather_button(message: types.Message):
            """Обработка запроса текущей погоды через кнопку"""
            await self._show_current_weather(message)
        
        # Обработка кнопки "Прогноз на 3 дня"
        @self.dp.message(F.text == "📅 Прогноз на 3 дня")
        async def forecast_button(message: types.Message):
            """Обработка запроса прогноза через кнопку"""
            await self._show_forecast(message)
        
        # Обработка кнопки "Настройки"
        @self.dp.message(F.text == "⚙ Настройки")
        async def settings_button(message: types.Message):
            """Обработка кнопки настроек"""
            user_id = message.from_user.id
            user_data = self.db.get_user(user_id)
            
            settings_text = "⚙️ <b>Настройки</b>\n\n"
            
            if user_data and user_data.get('last_city'):
                settings_text += f"🏙️ Последний город: <b>{user_data['last_city']}</b>\n"
            elif user_data and user_data.get('last_lat') and user_data.get('last_lon'):
                settings_text += f"📍 Последняя локация: <b>{user_data['last_lat']:.4f}, {user_data['last_lon']:.4f}</b>\n"
            else:
                settings_text += "📍 Локация не установлена\n"
            
            settings_text += f"\n🌐 Язык: <b>Русский</b>\n"
            settings_text += f"🕐 Часовой пояс: <b>Авто</b>\n\n"
            settings_text += "<i>Локация определяется по вашим координатам или названию города</i>"
            
            await message.answer(settings_text, parse_mode='HTML')
        
        # Обработка текстовых сообщений (название города)
        @self.dp.message(~F.location)
        async def handle_city_input(message: types.Message):
            """Обработка ввода названия города"""
            city_name = message.text.strip()
            
            if not city_name:
                await message.answer(WeatherFormatter.format_error_message('invalid_input'))
                return
            
            user_id = message.from_user.id
            
            # Геокодируем город
            coords = await self.weather_api.geocode_city(city_name, lang='ru')
            
            if not coords:
                # Пробуем на английском если не нашли
                coords = await self.weather_api.geocode_city(city_name, lang='en')
            
            if not coords:
                await message.answer(WeatherFormatter.format_error_message('city_not_found'))
                return
            
            lat, lon, country = coords
            
            # Сохраняем город в базу
            self.db.create_or_update_user(
                user_id=user_id,
                lat=lat,
                lon=lon,
                city=city_name
            )
            
            # Логгируем запрос
            self.db.log_request(user_id, 'city_search', city_name)
            
            await message.answer(
                f"✅ Город найден: <b>{city_name}, {country}</b>\n\n"
                f"Теперь выберите:\n• 🌤 Погода сейчас\n• 📅 Прогноз на 3 дня",
                reply_markup=self._get_main_keyboard(),
                parse_mode='HTML'
            )
    
    async def _show_current_weather(self, message: types.Message):
        """
        Показ текущей погоды для пользователя
        
        Args:
            message: Сообщение от пользователя
        """
        user_id = message.from_user.id
        user_data = self.db.get_user(user_id)
        
        if not user_data or (not user_data.get('last_lat') and not user_data.get('last_city')):
            await message.answer(
                WeatherFormatter.format_error_message('no_location') + "\n\n"
                "Отправьте геопозицию или введите название города."
            )
            return
        
        # Определяем язык пользователя (по умолчанию русский)
        lang = user_data.get('language', 'ru')
        
        # Получаем погоду
        if user_data.get('last_lat') and user_data.get('last_lon'):
            # Используем координаты
            weather_data = await self.weather_api.get_weather_by_coords(
                user_data['last_lat'],
                user_data['last_lon'],
                lang=lang
            )
            location_name = user_data.get('last_city', 'По координатам')
        elif user_data.get('last_city'):
            # Сначала геокодируем город
            coords = await self.weather_api.geocode_city(user_data['last_city'], lang=lang)
            if not coords:
                await message.answer(WeatherFormatter.format_error_message('city_not_found'))
                return
            
            lat, lon, _ = coords
            weather_data = await self.weather_api.get_weather_by_coords(lat, lon, lang=lang)
            location_name = user_data['last_city']
        else:
            await message.answer(WeatherFormatter.format_error_message('no_location'))
            return
        
        if not weather_data:
            await message.answer(WeatherFormatter.format_error_message('api_error'))
            return
        
        # Форматируем и отправляем сообщение
        formatted_weather = WeatherFormatter.format_current_weather(weather_data, location_name)
        await message.answer(formatted_weather, parse_mode='HTML')
        
        # Логгируем запрос
        self.db.log_request(user_id, 'current_weather', location_name)
    
    async def _show_forecast(self, message: types.Message):
        """
        Показ прогноза погоды для пользователя
        
        Args:
            message: Сообщение от пользователя
        """
        user_id = message.from_user.id
        user_data = self.db.get_user(user_id)
        
        if not user_data or (not user_data.get('last_lat') and not user_data.get('last_city')):
            await message.answer(
                WeatherFormatter.format_error_message('no_location') + "\n\n"
                "Отправьте геопозицию или введите название города."
            )
            return
        
        lang = user_data.get('language', 'ru')
        
        # Получаем прогноз
        if user_data.get('last_lat') and user_data.get('last_lon'):
            forecast_data = await self.weather_api.get_forecast_by_coords(
                user_data['last_lat'],
                user_data['last_lon'],
                lang=lang,
                days=3
            )
        elif user_data.get('last_city'):
            coords = await self.weather_api.geocode_city(user_data['last_city'], lang=lang)
            if not coords:
                await message.answer(WeatherFormatter.format_error_message('city_not_found'))
                return
            
            lat, lon, _ = coords
            forecast_data = await self.weather_api.get_forecast_by_coords(lat, lon, lang=lang, days=3)
        else:
            await message.answer(WeatherFormatter.format_error_message('no_location'))
            return
        
        if not forecast_data:
            await message.answer(WeatherFormatter.format_error_message('api_error'))
            return
        
        # Форматируем и отправляем сообщение
        formatted_forecast = WeatherFormatter.format_forecast(forecast_data, days=3)
        await message.answer(formatted_forecast, parse_mode='HTML')
        
        # Логгируем запрос
        location_name = user_data.get('last_city', 'По координатам')
        self.db.log_request(user_id, 'forecast', location_name)
    
    async def start(self):
        """Запуск бота"""
        logger.info("Бот запускается...")
        try:
            await self.dp.start_polling(self.bot)
        except Exception as e:
            logger.error(f"Ошибка при запуске бота: {e}")
        finally:
            await self.bot.session.close()
    
    async def export_to_google_sheets(self):
        """Экспорт данных пользователей в Google Sheets"""
        if not self.google_sync:
            logger.warning("Google Sheets синхронизация не настроена")
            return False
        
        users = self.db.get_all_users_for_export()
        success = self.google_sync.sync_users(users)
        
        if success:
            sheet_url = self.google_sync.get_sheet_url()
            logger.info(f"Данные экспортированы в Google Sheets: {sheet_url}")
            return True
        else:
            logger.error("Не удалось экспортировать данные в Google Sheets")
            return False


async def main():
    """Точка входа для запуска бота"""
    try:
        bot = WeatherBot()
        await bot.start()
    except ValueError as e:
        print(f"Ошибка конфигурации: {e}")
        print("Убедитесь, что файл .env содержит необходимые токены.")
    except KeyboardInterrupt:
        print("\nБот остановлен пользователем")


if __name__ == "__main__":
    asyncio.run(main())
