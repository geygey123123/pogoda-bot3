"""
Модуль для синхронизации данных с Google Sheets
Опциональный модуль для экспорта метаданных пользователей
"""

import json
from typing import Optional, List, Dict, Any
from datetime import datetime


class GoogleSheetsSync:
    """Класс для синхронизации данных с Google Таблицами"""
    
    def __init__(self, credentials_json: str, sheet_name: str = "weather_bot_users"):
        """
        Инициализация клиента Google Sheets
        
        Args:
            credentials_json: JSON строка с учетными данными Google Service Account
            sheet_name: Название таблицы для синхронизации
        """
        self.credentials_json = credentials_json
        self.sheet_name = sheet_name
        self._client = None
        self._sheet = None
    
    def _init_client(self):
        """Инициализация клиента gspread при первом использовании"""
        if self._client is None and self.credentials_json:
            try:
                import gspread
                from google.oauth2.service_account import Credentials
                
                # Парсим учетные данные
                credentials_info = json.loads(self.credentials_json)
                
                # Создаем учетные данные
                scopes = [
                    'https://www.googleapis.com/auth/spreadsheets',
                    'https://www.googleapis.com/auth/drive'
                ]
                credentials = Credentials.from_service_account_info(
                    credentials_info,
                    scopes=scopes
                )
                
                # Создаем клиент
                self._client = gspread.authorize(credentials)
                
                # Открываем или создаем таблицу
                try:
                    spreadsheet = self._client.open(self.sheet_name)
                except gspread.exceptions.SpreadsheetNotFound:
                    # Создаем новую таблицу если не найдена
                    spreadsheet = self._client.create(self.sheet_name)
                
                # Получаем первый лист
                self._sheet = spreadsheet.get_worksheet(0)
                
                # Инициализируем заголовки если лист пустой
                if self._sheet.row_values(1) == []:
                    headers = [
                        'User ID',
                        'Username',
                        'Latitude',
                        'Longitude',
                        'City',
                        'Timezone',
                        'Language',
                        'Created At',
                        'Updated At'
                    ]
                    self._sheet.append_row(headers)
                    
            except ImportError:
                print("gspread or google-auth not installed. Install with: pip install gspread google-auth")
                self._client = None
            except Exception as e:
                print(f"Error initializing Google Sheets client: {e}")
                self._client = None
    
    def sync_users(self, users: List[Dict[str, Any]]) -> bool:
        """
        Синхронизация данных пользователей с Google Таблицей
        
        Args:
            users: Список словарей с данными пользователей
            
        Returns:
            True если синхронизация успешна, False иначе
        """
        if not self.credentials_json:
            return False
        
        self._init_client()
        
        if self._client is None or self._sheet is None:
            return False
        
        try:
            # Очищаем все данные кроме заголовков
            all_values = self._sheet.get_all_values()
            if len(all_values) > 1:
                self._sheet.batch_clear([f"A2:I{len(all_values)}"])
            
            # Подготавливаем данные для записи
            rows_to_add = []
            for user in users:
                row = [
                    user.get('user_id', ''),
                    user.get('username', ''),
                    user.get('last_lat', ''),
                    user.get('last_lon', ''),
                    user.get('last_city', ''),
                    user.get('timezone', ''),
                    user.get('language', ''),
                    user.get('created_at', ''),
                    user.get('updated_at', '')
                ]
                rows_to_add.append(row)
            
            # Добавляем все строки
            if rows_to_add:
                self._sheet.append_rows(rows_to_add)
            
            return True
            
        except Exception as e:
            print(f"Error syncing users to Google Sheets: {e}")
            return False
    
    def add_user_row(self, user: Dict[str, Any]) -> bool:
        """
        Добавление одной строки с данными пользователя
        
        Args:
            user: Словарь с данными пользователя
            
        Returns:
            True если успешно, False иначе
        """
        if not self.credentials_json:
            return False
        
        self._init_client()
        
        if self._client is None or self._sheet is None:
            return False
        
        try:
            row = [
                user.get('user_id', ''),
                user.get('username', ''),
                user.get('last_lat', ''),
                user.get('last_lon', ''),
                user.get('last_city', ''),
                user.get('timezone', ''),
                user.get('language', ''),
                user.get('created_at', ''),
                user.get('updated_at', '')
            ]
            self._sheet.append_row(row)
            return True
        except Exception as e:
            print(f"Error adding user row to Google Sheets: {e}")
            return False
    
    def get_sheet_url(self) -> Optional[str]:
        """
        Получение URL таблицы
        
        Returns:
            URL таблицы или None если клиент не инициализирован
        """
        if self._sheet:
            return self._sheet.spreadsheet.url
        return None
