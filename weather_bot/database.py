"""
Модуль работы с базой данных SQLite
Хранит информацию о пользователях: ID, последняя локация, часовой пояс, язык
"""

import sqlite3
import json
from typing import Optional, Dict, Any
from pathlib import Path


class Database:
    """Класс для работы с SQLite базой данных пользователей"""
    
    def __init__(self, db_path: str = "users.db"):
        """
        Инициализация базы данных
        
        Args:
            db_path: Путь к файлу базы данных
        """
        self.db_path = Path(db_path)
        self._init_db()
    
    def _init_db(self):
        """Создание таблиц базы данных если они не существуют"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Таблица пользователей
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                last_lat REAL,
                last_lon REAL,
                last_city TEXT,
                timezone TEXT DEFAULT 'UTC',
                language TEXT DEFAULT 'ru',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Таблица для хранения истории запросов (метаданные для аналитики)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS weather_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                request_type TEXT,
                location TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """)
        
        conn.commit()
        conn.close()
    
    def get_user(self, user_id: int) -> Optional[Dict[str, Any]]:
        """
        Получение информации о пользователе
        
        Args:
            user_id: Telegram ID пользователя
            
        Returns:
            Словарь с данными пользователя или None если не найден
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return dict(row)
        return None
    
    def create_or_update_user(
        self,
        user_id: int,
        username: Optional[str] = None,
        lat: Optional[float] = None,
        lon: Optional[float] = None,
        city: Optional[str] = None,
        timezone: Optional[str] = None,
        language: Optional[str] = None
    ):
        """
        Создание нового пользователя или обновление существующего
        
        Args:
            user_id: Telegram ID пользователя
            username: Имя пользователя
            lat: Широта последней локации
            lon: Долгота последней локации
            city: Название последнего города
            timezone: Часовой пояс
            language: Предпочитаемый язык
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Проверяем существует ли пользователь
        cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
        exists = cursor.fetchone()
        
        if exists:
            # Обновляем существующего пользователя
            updates = []
            values = []
            
            if username is not None:
                updates.append("username = ?")
                values.append(username)
            if lat is not None:
                updates.append("last_lat = ?")
                values.append(lat)
            if lon is not None:
                updates.append("last_lon = ?")
                values.append(lon)
            if city is not None:
                updates.append("last_city = ?")
                values.append(city)
            if timezone is not None:
                updates.append("timezone = ?")
                values.append(timezone)
            if language is not None:
                updates.append("language = ?")
                values.append(language)
            
            if updates:
                updates.append("updated_at = CURRENT_TIMESTAMP")
                values.append(user_id)
                
                query = f"UPDATE users SET {', '.join(updates)} WHERE user_id = ?"
                cursor.execute(query, values)
        else:
            # Создаем нового пользователя
            cursor.execute("""
                INSERT INTO users (user_id, username, last_lat, last_lon, last_city, timezone, language)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (user_id, username, lat, lon, city, timezone or 'UTC', language or 'ru'))
        
        conn.commit()
        conn.close()
    
    def log_request(self, user_id: int, request_type: str, location: str):
        """
        Логирование запроса погоды для аналитики
        
        Args:
            user_id: Telegram ID пользователя
            request_type: Тип запроса (current, forecast, etc.)
            location: Локация запроса
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO weather_requests (user_id, request_type, location)
            VALUES (?, ?, ?)
        """, (user_id, request_type, location))
        
        conn.commit()
        conn.close()
    
    def get_all_users_for_export(self) -> list:
        """
        Получение всех пользователей для экспорта в Google Sheets
        
        Returns:
            Список словарей с данными пользователей
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM users ORDER BY created_at DESC")
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]
    
    def get_user_statistics(self) -> Dict[str, Any]:
        """
        Получение статистики по пользователям и запросам
        
        Returns:
            Словарь со статистикой
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        stats = {}
        
        # Общее количество пользователей
        cursor.execute("SELECT COUNT(*) FROM users")
        stats['total_users'] = cursor.fetchone()[0]
        
        # Количество запросов за сегодня
        cursor.execute("""
            SELECT COUNT(*) FROM weather_requests 
            WHERE date(timestamp) = date('now')
        """)
        stats['requests_today'] = cursor.fetchone()[0]
        
        # Топ городов
        cursor.execute("""
            SELECT last_city, COUNT(*) as count 
            FROM users 
            WHERE last_city IS NOT NULL 
            GROUP BY last_city 
            ORDER BY count DESC 
            LIMIT 10
        """)
        stats['top_cities'] = cursor.fetchall()
        
        conn.close()
        return stats
