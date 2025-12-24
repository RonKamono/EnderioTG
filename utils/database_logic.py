import sqlite3
import os
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime


class TradingDB:
    def __init__(self, db_name: str = 'trading.db'):
        # Получаем путь к базе данных из настроек реестра
        self.db_path = self._get_db_path(db_name)
        # Создаем папку, если она не существует
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self.create_table()

    def _get_db_path(self, db_name: str) -> str:
        """Получить путь к базе данных из настроек реестра"""
        try:
            # Пытаемся импортировать конфиг
            from utils import config
            # Используем путь из конфига, если он задан
            if hasattr(config, 'DB_PATH') and config.DB_PATH:
                db_path = config.DB_PATH
                print(f"📁 Использую путь к БД из настроек: {db_path}")
                return db_path
        except ImportError as e:
            print(f"⚠️ Не удалось импортировать config: {e}")
        except Exception as e:
            print(f"⚠️ Ошибка при получении пути к БД: {e}")

        # Fallback: путь по умолчанию в AppData/Local
        return self._get_default_db_path(db_name)

    def _get_default_db_path(self, db_name: str) -> str:
        """Получить путь по умолчанию в AppData/Local"""
        local_appdata = os.getenv('LOCALAPPDATA')
        if not local_appdata:
            local_appdata = os.path.join(os.path.expanduser('~'), 'AppData', 'Local')

        # Создаем путь в AppData/Local/EnderioTG/TradingBot/
        app_folder = Path(local_appdata) / 'EnderioTG' / 'TradingBot'
        app_folder.mkdir(parents=True, exist_ok=True)

        db_path = str(app_folder / db_name)
        print(f"📁 Использую путь к БД по умолчанию: {db_path}")
        return db_path

    def show_db_info(self):
        """Показать информацию о базе данных"""
        print(f"📊 Информация о базе данных:")
        print(f"   Путь: {self.db_path}")
        print(f"   Существует: {'✅' if os.path.exists(self.db_path) else '❌'}")
        print(f"   Размер: {os.path.getsize(self.db_path) if os.path.exists(self.db_path) else 0} байт")

        if os.path.exists(self.db_path):
            try:
                with sqlite3.connect(self.db_path) as conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT COUNT(*) FROM positions")
                    count = cursor.fetchone()[0]
                    print(f"   Количество записей: {count}")
            except:
                print(f"   Количество записей: не удалось определить")

    def create_table(self):
        """Создание таблицы"""
        try:
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
                print(f"✅ Таблицы созданы/проверены в базе: {self.db_path}")

        except Exception as e:
            print(f"❌ Ошибка при создании таблиц: {e}")
            raise

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
        try:
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
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()

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

                rows = cursor.fetchall()

                positions = []
                for row in rows:
                    try:
                        # 🔴 ВОТ ЗДЕСЬ МОЖЕТ БЫТЬ ПРОБЛЕМА
                        pos_dict = dict(row)

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
                    except Exception as e:
                        print(f"❌ Ошибка обработки строки: {e}")
                        print(f"❌ Строка: {row}")
                        import traceback
                        traceback.print_exc()

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

    def close_position(self, position_id: int, close_reason: str, final_pnl: float) -> bool:
        """Закрыть позицию"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                # Получаем данные позиции перед закрытием
                cursor.execute('SELECT * FROM positions WHERE id = ?', (position_id,))
                position_data = dict(cursor.fetchone())

                # Закрываем позицию
                cursor.execute('''
                UPDATE positions 
                SET is_active = 0, 
                    close_reason = ?,
                    closed_at = CURRENT_TIMESTAMP,
                    final_pnl = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                ''', (close_reason, final_pnl, position_id))

                # Логируем операцию закрытия
                cursor.execute('''
                INSERT INTO position_logs (position_id, action, details)
                VALUES (?, ?, ?)
                ''', (position_id, 'CLOSE',
                      f"Closed with reason: {close_reason}, PnL: {final_pnl}%"))

                conn.commit()

                # Отправляем уведомление о закрытии
                self._send_close_notification(position_data, close_reason, final_pnl)

                print(f"✅ Позиция {position_id} закрыта ({close_reason}), PnL: {final_pnl}%")
                return True

        except Exception as e:
            print(f"❌ Ошибка при закрытии позиции: {e}")
            return False

    def delete_position(self, position_id: int) -> bool:
        """Удалить позицию"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                # Удаляем связанные записи из истории и логов
                cursor.execute('DELETE FROM position_history WHERE position_id = ?', (position_id,))
                cursor.execute('DELETE FROM position_logs WHERE position_id = ?', (position_id,))

                # Удаляем саму позицию
                cursor.execute('DELETE FROM positions WHERE id = ?', (position_id,))

                conn.commit()

                print(f"✅ Позиция {position_id} удалена")
                return True

        except Exception as e:
            print(f"❌ Ошибка при удалении позиции: {e}")
            return False

    def get_position_by_id(self, position_id: int) -> Optional[Dict]:
        """Получить позицию по ID"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()

                cursor.execute('SELECT * FROM positions WHERE id = ?', (position_id,))
                row = cursor.fetchone()

                if row:
                    return dict(row)
                return None

        except Exception as e:
            print(f"❌ Ошибка при получении позиции: {e}")
            return None

    def cleanup_old_positions(self, days_old: int = 30) -> int:
        """Очистить старые закрытые позиции"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                cursor.execute('''
                SELECT id FROM positions 
                WHERE is_active = 0 
                AND closed_at <= datetime('now', ?)
                ''', (f'-{days_old} days',))

                old_positions = cursor.fetchall()

                deleted_count = 0
                for pos_id in old_positions:
                    if self.delete_position(pos_id[0]):
                        deleted_count += 1

                print(f"✅ Удалено {deleted_count} старых позиций (старше {days_old} дней)")
                return deleted_count

        except Exception as e:
            print(f"❌ Ошибка при очистке старых позиций: {e}")
            return 0


# Для обратной совместимости со старым кодом
def get_database():
    """Создать и вернуть экземпляр TradingDB"""
    return TradingDB()