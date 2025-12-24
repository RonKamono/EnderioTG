"""
Модуль для работы с реестром Windows
"""

import winreg
import json
from typing import Any, Dict


class RegistryConfig:
    """Класс для работы с настройками в реестре Windows"""

    def __init__(self, company_name: str = "Enderio", app_name: str = "Trading Panel"):
        self.company_name = company_name
        self.app_name = app_name
        self.base_key = f"Software\\{company_name}\\{app_name}"

    def _ensure_key_exists(self):
        """Убедиться, что ключ реестра существует"""
        try:
            winreg.OpenKey(winreg.HKEY_CURRENT_USER, self.base_key, 0, winreg.KEY_READ)
        except FileNotFoundError:
            # Создаем ключ и подразделы
            winreg.CreateKey(winreg.HKEY_CURRENT_USER, self.base_key)

    def set_value(self, name: str, value: Any) -> bool:
        """Установить значение в реестре"""
        try:
            self._ensure_key_exists()

            # Открываем ключ для записи
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                self.base_key,
                0,
                winreg.KEY_WRITE
            )

            # Определяем тип значения
            if isinstance(value, str):
                value_type = winreg.REG_SZ
            elif isinstance(value, int):
                value_type = winreg.REG_DWORD
            elif isinstance(value, bool):
                value = 1 if value else 0
                value_type = winreg.REG_DWORD
            elif isinstance(value, (list, dict)):
                value = json.dumps(value, ensure_ascii=False)
                value_type = winreg.REG_SZ
            else:
                value = str(value)
                value_type = winreg.REG_SZ

            winreg.SetValueEx(key, name, 0, value_type, value)
            winreg.CloseKey(key)
            return True

        except Exception as e:
            print(f"Ошибка записи в реестр: {e}")
            return False

    def get_value(self, name: str, default: Any = None) -> Any:
        """Получить значение из реестра"""
        try:
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                self.base_key,
                0,
                winreg.KEY_READ
            )

            value, value_type = winreg.QueryValueEx(key, name)
            winreg.CloseKey(key)

            # Восстанавливаем типы данных
            if value_type == winreg.REG_SZ and isinstance(value, str):
                try:
                    # Пробуем декодировать JSON
                    if value.startswith('[') or value.startswith('{'):
                        return json.loads(value)
                except:
                    pass
                return value
            elif value_type == winreg.REG_DWORD:
                return int(value)

            return value

        except (FileNotFoundError, OSError):
            return default

    def get_all_values(self) -> Dict[str, Any]:
        """Получить все значения из ключа"""
        values = {}
        try:
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                self.base_key,
                0,
                winreg.KEY_READ
            )

            i = 0
            while True:
                try:
                    name, value, value_type = winreg.EnumValue(key, i)

                    # Восстанавливаем типы данных
                    if value_type == winreg.REG_SZ and isinstance(value, str):
                        try:
                            if value.startswith('[') or value.startswith('{'):
                                value = json.loads(value)
                        except:
                            pass
                    elif value_type == winreg.REG_DWORD:
                        value = int(value)

                    values[name] = value
                    i += 1
                except OSError:
                    break

            winreg.CloseKey(key)
        except FileNotFoundError:
            pass

        return values

    def delete_value(self, name: str) -> bool:
        """Удалить значение из реестра"""
        try:
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                self.base_key,
                0,
                winreg.KEY_WRITE
            )
            winreg.DeleteValue(key, name)
            winreg.CloseKey(key)
            return True
        except:
            return False

    def clear_all(self) -> bool:
        """Удалить все значения из реестра"""
        try:
            # Удаляем весь ключ
            winreg.DeleteKey(winreg.HKEY_CURRENT_USER, self.base_key)
            return True
        except:
            return False