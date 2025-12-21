import sqlite3
import os

from typing import List, Dict, Optional
from datetime import datetime

class TradingDB:
    def __init__(self, db_name: str = 'trading.db'):
        self.db_path = os.path.join('C:\\DataBase', db_name)
        os.makedirs('C:\\DataBase', exist_ok=True)
        self.create_table()

    def create_table(self):
        """Создание таблицы"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            cursor.execute('''
            CREATE TABLE IF NOT EXISTS positions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                percent INTEGER CHECK(percent >= 1 AND percent <= 100),
                cross INTEGER,
                entry_price REAL NOT NULL,
                take_profit REAL NOT NULL,
                stop_loss REAL NOT NULL,
                pos_type TEXT CHECK(pos_type IN ('long', 'short')) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_active BOOLEAN DEFAULT 1,
                
                -- Проверки для логики
                CHECK(stop_loss >= 0),
                CHECK(take_profit >= 0),
                CHECK(stop_loss != take_profit)
            )
            ''')

            # Таблица для истории изменений
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS position_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                position_id INTEGER,
                name TEXT,
                percent INTEGER,
                cross INTEGER,
                entry_price REAL,
                take_profit REAL,
                stop_loss REAL,
                pos_type TEXT,
                changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (position_id) REFERENCES positions (id)
            )
            ''')

            # Таблица для логов операций
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS position_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                position_id INTEGER,
                action TEXT,
                details TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (position_id) REFERENCES positions (id)
            )
            ''')

            conn.commit()

    def add_to_db(self, name: str, percent: int, cross: Optional[int],
                  entry_price: float, take_profit: float, stop_loss: float, pos_type: str) -> Optional[int]:
        """
        Добавляет новую позицию в базу данных и отправляет уведомление в Telegram
        """
        try:
            # Валидация входных данных
            if not 1 <= percent <= 100:
                raise ValueError(f"Percent must be between 1 and 100, got {percent}")

            if pos_type not in ['long', 'short']:
                raise ValueError(f"pos_type must be 'long' or 'short', got {pos_type}")

            if stop_loss == take_profit:
                raise ValueError("stop_loss and take_profit must be different")

            if stop_loss < 0 or take_profit < 0:
                raise ValueError("stop_loss and take_profit must be non-negative")

            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                # Вставляем новую позицию - ИСПРАВЛЕНО: 8 значений для 8 колонок
                cursor.execute('''
                INSERT INTO positions (name, percent, cross, entry_price, take_profit, stop_loss, pos_type, is_active)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (name, percent, cross, entry_price, take_profit, stop_loss, pos_type, True))

                position_id = cursor.lastrowid

                # Добавляем запись в историю изменений (создание позиции)
                cursor.execute('''
                INSERT INTO position_history (position_id, name, percent, cross, entry_price, take_profit, stop_loss, pos_type)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (position_id, name, percent, cross, entry_price, take_profit, stop_loss, pos_type))

                # Логируем операцию создания
                cursor.execute('''
                INSERT INTO position_logs (position_id, action, details)
                VALUES (?, ?, ?)
                ''', (position_id, 'CREATE',
                      f"Created position: {name}, type: {pos_type}, entry: {entry_price}, TP: {take_profit}, SL: {stop_loss}"))

                conn.commit()

                print(f"✅ Position '{name}' (ID: {position_id}) successfully added to database")

                # Отправляем уведомление в Telegram
                self._send_telegram_notification(
                    name=name,
                    percent=percent,
                    cross=cross,
                    entry_price=entry_price,
                    take_profit=take_profit,
                    stop_loss=stop_loss,
                    pos_type=pos_type
                )

                return position_id

        except sqlite3.Error as e:
            print(f"❌ Database error: {e}")
            return None
        except ValueError as e:
            print(f"❌ Validation error: {e}")
            return None
        except Exception as e:
            print(f"❌ Unexpected error: {e}")
            return None

    def _send_telegram_notification(self, name: str, percent: int, cross: Optional[int],
                                    entry_price: float,
                                    take_profit: float, stop_loss: float, pos_type: str):
        """
        Отправляет уведомление о новой позиции в Telegram бот

        Args:
            name: Название позиции
            percent: Процент
            cross: Пересечение
            take_profit: Уровень TP
            stop_loss: Уровень SL
            pos_type: Тип позиции
        """
        try:
            # Импортируем модуль для отправки уведомлений
            from utils.telegram_notifier import send_position_notification

            # Формируем данные позиции
            position_data = {
                'name': name,
                'percent': percent,
                'cross': cross,
                'entry_price': entry_price,
                'take_profit': take_profit,
                'stop_loss': stop_loss,
                'pos_type': pos_type,
                'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }

            # Отправляем уведомление
            send_position_notification(position_data)

            print("📢 Уведомление отправлено в Telegram")

        except ImportError as e:
            print(f"⚠️ Telegram notifier not available: {e}")
        except Exception as e:
            print(f"⚠️ Failed to send Telegram notification: {e}")

    def get_all_positions(self, active_only: bool = True) -> List[Dict]:
        """Получить все позиции с преобразованием типов данных"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()

                query = '''
                SELECT 
                    id,
                    name,
                    percent,
                    cross,
                    entry_price,
                    take_profit,
                    stop_loss,
                    pos_type,
                    is_active,
                    created_at,
                    updated_at
                FROM positions 
                WHERE is_active = ?
                ORDER BY created_at DESC
                ''' if active_only else '''
                SELECT 
                    id,
                    name,
                    percent,
                    cross,
                    entry_price,
                    take_profit,
                    stop_loss,
                    pos_type,
                    is_active,
                    created_at,
                    updated_at
                FROM positions 
                ORDER BY created_at DESC
                '''

                cursor.execute(query, (True,) if active_only else ())
                rows = cursor.fetchall()

                # Преобразуем строки в словари с правильными типами данных
                positions = []
                for row in rows:
                    pos_dict = dict(row)

                    # Приводим типы данных к более удобным
                    pos_dict['percent'] = int(pos_dict['percent']) if pos_dict['percent'] is not None else None
                    pos_dict['cross'] = int(pos_dict['cross']) if pos_dict['cross'] is not None else None
                    pos_dict['entry_price'] = float(pos_dict['entry_price']) if pos_dict['entry_price'] is not None else None
                    pos_dict['take_profit'] = float(pos_dict['take_profit']) if pos_dict['take_profit'] is not None else None
                    pos_dict['stop_loss'] = float(pos_dict['stop_loss']) if pos_dict['stop_loss'] is not None else None
                    pos_dict['is_active'] = bool(pos_dict['is_active'])

                    # Преобразуем даты в строки (если нужно для Pandas)
                    if pos_dict['created_at']:
                        # Убираем миллисекунды, если они есть
                        if '.' in pos_dict['created_at']:
                            pos_dict['created_at'] = pos_dict['created_at'].split('.')[0]

                    if pos_dict['updated_at'] and '.' in pos_dict['updated_at']:
                        pos_dict['updated_at'] = pos_dict['updated_at'].split('.')[0]

                    positions.append(pos_dict)

                return positions

        except sqlite3.Error as e:
            print(f"❌ Ошибка при получении позиций: {e}")
            return []

        except sqlite3.Error as e:
            print(f"❌ Ошибка при получении позиций: {e}")
            return []