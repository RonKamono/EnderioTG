import sqlite3
import os

from typing import List, Dict, Optional
from datetime import datetime

class TradingDB:
    def __init__(self, db_name: str = 'trading.db'):
        self.db_path = os.path.join('C:\\DataBase', db_name)
        os.makedirs('C:\\DataBase', exist_ok=True)
        self.create_table()
        print(f"🔍 DEBUG TradingDB инициализирован, путь к БД: {self.db_path}")

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
                take_profit REAL NOT NULL,
                stop_loss REAL NOT NULL,
                pos_type TEXT CHECK(pos_type IN ('long', 'short')) NOT NULL,
                entry_price REAL,
                is_active BOOLEAN DEFAULT 1,
                close_reason TEXT,
                closed_at TIMESTAMP,
                final_pnl REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

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
        """
        print(f"🔍 DEBUG _send_telegram_notification: Начало метода")

        try:
            # Импортируем модуль для отправки уведомлений
            print(f"🔍 DEBUG: Пытаюсь импортировать telegram_notifier")
            from utils.telegram_notifier import send_position_notification

            # Формируем данные позиции - УБРАН is_active!
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

            print(f"🔍 DEBUG: Данные сформированы: {position_data}")

            # Отправляем уведомление
            print(f"🔍 DEBUG: Вызываю send_position_notification")
            send_position_notification(position_data)

            print("📢 Уведомление отправлено в Telegram")

        except ImportError as e:
            print(f"⚠️ Telegram notifier not available: {e}")
        except Exception as e:
            print(f"⚠️ Failed to send Telegram notification: {e}")
            import traceback
            traceback.print_exc()

    def update_position(self, position_id: int, **kwargs) -> bool:
        """Обновить позицию с новыми полями - УПРОЩЕННЫЙ"""
        try:
            allowed_fields = ['name', 'percent', 'cross', 'take_profit', 'stop_loss',
                              'pos_type', 'is_active', 'close_reason', 'closed_at', 'final_pnl']

            updates = {k: v for k, v in kwargs.items() if k in allowed_fields}

            if not updates:
                print("Нет полей для обновления")
                return False

            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                set_clause = ', '.join([f"{k} = ?" for k in updates.keys()])
                set_clause += ', updated_at = CURRENT_TIMESTAMP'

                query = f"UPDATE positions SET {set_clause} WHERE id = ?"
                values = list(updates.values()) + [position_id]

                cursor.execute(query, values)

                # Простое логирование
                cursor.execute('''
                INSERT INTO position_logs (position_id, action, details)
                VALUES (?, ?, ?)
                ''', (position_id, 'UPDATE', f"Fields: {', '.join(updates.keys())}"))

                conn.commit()

                print(f"✅ Позиция {position_id} обновлена")
                return True

        except sqlite3.Error as e:
            print(f"❌ Ошибка БД: {e}")
            return False

    def get_all_positions(self, active_only: bool = True) -> List[Dict]:
        """Получить все позиции"""
        try:
            print(f"🔍 DEBUG get_all_positions: active_only={active_only}")
            print(f"🔍 DEBUG: db_path={self.db_path}")

            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()

                print("🔍 DEBUG: Выполняю SQL запрос...")

                if active_only:
                    cursor.execute('''
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
                        close_reason,
                        closed_at,
                        final_pnl,
                        created_at,
                        updated_at
                    FROM positions 
                    WHERE is_active = 1
                    ORDER BY created_at DESC
                    ''')
                    print("🔍 DEBUG: Выполнен запрос для активных позиций")
                else:
                    cursor.execute('''
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
                        close_reason,
                        closed_at,
                        final_pnl,
                        created_at,
                        updated_at
                    FROM positions 
                    ORDER BY is_active DESC, created_at DESC
                    ''')
                    print("🔍 DEBUG: Выполнен запрос для всех позиций")

                rows = cursor.fetchall()
                print(f"🔍 DEBUG: Получено строк: {len(rows)}")

                positions = []
                for row in rows:
                    try:
                        # 🔴 ВОТ ЗДЕСЬ МОЖЕТ БЫТЬ ПРОБЛЕМА
                        pos_dict = dict(row)
                        print(f"🔍 DEBUG: Обрабатываю позицию ID={pos_dict.get('id')}")

                        # Конвертируем типы данных с проверкой на None
                        if pos_dict.get('percent') is not None:
                            try:
                                pos_dict['percent'] = int(pos_dict['percent'])
                            except:
                                pos_dict['percent'] = None

                        if pos_dict.get('cross') is not None:
                            try:
                                pos_dict['cross'] = int(pos_dict['cross'])
                            except:
                                pos_dict['cross'] = None

                        if pos_dict.get('entry_price') is not None:
                            try:
                                pos_dict['entry_price'] = float(pos_dict['entry_price'])
                            except:
                                pos_dict['entry_price'] = None

                        if pos_dict.get('take_profit') is not None:
                            try:
                                pos_dict['take_profit'] = float(pos_dict['take_profit'])
                            except:
                                pos_dict['take_profit'] = None

                        if pos_dict.get('stop_loss') is not None:
                            try:
                                pos_dict['stop_loss'] = float(pos_dict['stop_loss'])
                            except:
                                pos_dict['stop_loss'] = None

                        if pos_dict.get('final_pnl') is not None:
                            try:
                                pos_dict['final_pnl'] = float(pos_dict['final_pnl'])
                            except:
                                pos_dict['final_pnl'] = None

                        # Преобразуем is_active в bool
                        if 'is_active' in pos_dict:
                            pos_dict['is_active'] = bool(pos_dict['is_active'])

                        # Убираем миллисекунды из дат
                        for date_field in ['created_at', 'updated_at', 'closed_at']:
                            if pos_dict.get(date_field):
                                date_str = str(pos_dict[date_field])
                                if '.' in date_str:
                                    pos_dict[date_field] = date_str.split('.')[0]

                        positions.append(pos_dict)
                        print(f"🔍 DEBUG: Позиция ID={pos_dict.get('id')} добавлена")

                    except Exception as e:
                        print(f"❌ Ошибка обработки строки: {e}")
                        print(f"❌ Строка: {row}")
                        import traceback
                        traceback.print_exc()

                print(f"🔍 DEBUG: Всего обработано позиций: {len(positions)}")
                return positions

        except Exception as e:
            print(f"❌ Ошибка при получении позиций: {e}")
            import traceback
            traceback.print_exc()
            return []

    def _send_close_notification(self, position_data: Dict, close_reason: str, final_pnl: float):
        """
        Отправляет уведомление о закрытии позиции в Telegram

        Args:
            position_data: Данные позиции
            close_reason: Причина закрытия ('tp' или 'sl')
            final_pnl: Финальный P/L в процентах
        """
        try:
            from utils.telegram_notifier import send_close_notification

            notification_data = {
                'id': position_data.get('id'),
                'name': position_data.get('name'),
                'pos_type': position_data.get('pos_type'),
                'entry_price': position_data.get('entry_price'),
                'take_profit': position_data.get('take_profit'),
                'stop_loss': position_data.get('stop_loss'),
                'close_reason': close_reason,
                'final_pnl': final_pnl,
                'closed_at': datetime.now().strftime('%m-%d %H:%M')
            }

            send_close_notification(notification_data)
            print(f"📢 Уведомление о закрытии позиции {position_data.get('id')} отправлено")

        except ImportError as e:
            print(f"⚠️ Telegram notifier not available: {e}")
        except Exception as e:
            print(f"⚠️ Failed to send close notification: {e}")