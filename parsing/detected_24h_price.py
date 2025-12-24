import requests
import json
import time
from typing import List, Dict, Optional
import threading
import queue
from datetime import datetime


class StakanScreener:
    def __init__(self, base_url: str = "https://stakan.io/api/screener"):
        self.base_url = base_url
        self._cached_data = None
        self._cache_time = 0
        self.cache_duration = 30
        self.request_timeout = 15
        self._update_queue = queue.Queue()
        self._stop_flag = False
        self._update_thread = None

    def fetch_data(self, use_cache: bool = True) -> Optional[Dict]:
        """Получает данные из API с кешированием"""
        current_time = time.time()

        if use_cache and self._cached_data and (current_time - self._cache_time) < self.cache_duration:
            return self._cached_data

        try:
            response = requests.get(self.base_url, timeout=self.request_timeout)
            response.raise_for_status()
            data = response.json()

            if use_cache:
                self._cached_data = data
                self._cache_time = current_time

            return data
        except requests.exceptions.RequestException as e:
            print(f"⚠️ [StakanScreener] Ошибка API: {e}")
            if self._cached_data:
                print("⚠️ [StakanScreener] Использую кешированные данные")
                return self._cached_data
            return None
        except json.JSONDecodeError as e:
            print(f"⚠️ [StakanScreener] Ошибка JSON: {e}")
            return None

    def get_usdt_pairs(self, min_change: float = 10.0, limit: int = 10) -> List[Dict]:
        """Основная функция: получает USDT пары с изменением ≥ min_change%"""
        data = self.fetch_data()
        if not data or 'result' not in data:
            return []

        result_data = data['result']
        if not isinstance(result_data, list):
            return []

        usdt_pairs = []
        seen_symbols = set()

        for item in result_data:
            if not isinstance(item, dict):
                continue

            symbol = item.get('symbol', {})
            if not isinstance(symbol, dict):
                continue

            exchange_code = symbol.get('exchangeCode', '')
            if not exchange_code.endswith('USDT'):
                continue

            if exchange_code in seen_symbols:
                continue
            seen_symbols.add(exchange_code)

            ticker = item.get('ticker', {})
            price_change = ticker.get('priceChangePercent', 0)

            if abs(price_change) >= min_change:
                usdt_pairs.append({
                    'symbol': exchange_code,
                    'price_change': price_change,
                    'price_usdt': item.get('priceInUSDT', 0),
                    'volume_usdt': item.get('volumeInUSDT', 0),
                    'base_asset': symbol.get('baseAsset', ''),
                    'last_updated': datetime.now().strftime('%H:%M:%S')
                })

        usdt_pairs.sort(key=lambda x: abs(x['price_change']), reverse=True)

        if limit and len(usdt_pairs) > limit:
            usdt_pairs = usdt_pairs[:limit]

        return usdt_pairs

    def start_periodic_updates(self, update_callback=None, interval: int = 30):
        """Запускает периодическое обновление в отдельном потоке"""
        if self._update_thread and self._update_thread.is_alive():
            return self._update_thread

        def update_loop():
            while not self._stop_flag:
                try:
                    # Получаем данные
                    pairs = self.get_usdt_pairs(min_change=10.0, limit=10)

                    if pairs:
                        # Добавляем в очередь
                        self._update_queue.put(pairs)

                        # Вызываем callback если он есть
                        if update_callback:
                            try:
                                update_callback(pairs)
                            except Exception as e:
                                print(f"⚠️ [StakanScreener] Ошибка в callback: {e}")

                    # Ждем интервал с проверкой флага остановки
                    for _ in range(interval * 2):
                        if self._stop_flag:
                            break
                        time.sleep(0.5)

                except Exception as e:
                    print(f"❌ [StakanScreener] Ошибка в update_loop: {e}")
                    import traceback
                    traceback.print_exc()
                    time.sleep(interval)

        self._stop_flag = False
        self._update_thread = threading.Thread(target=update_loop, daemon=True)
        self._update_thread.start()
        return self._update_thread

    def stop_updates(self):
        """Останавливает обновления"""
        self._stop_flag = True
        if self._update_thread:
            self._update_thread.join(timeout=2)
        print("⏹️ [StakanScreener] Обновления остановлены")

    def get_latest_pairs(self) -> Optional[List[Dict]]:
        """Получает последние данные из очереди"""
        try:
            return self._update_queue.get_nowait()
        except queue.Empty:
            return None


# Синглтон для глобального использования
_global_screener = None


def get_global_screener():
    """Возвращает глобальный экземпляр скринера"""
    global _global_screener
    if _global_screener is None:
        _global_screener = StakanScreener()
    return _global_screener


def get_volatile_usdt_pairs(min_change: float = 10.0, limit: int = 10) -> List[Dict]:
    """Быстрая функция для получения пар"""
    screener = get_global_screener()
    return screener.get_usdt_pairs(min_change=min_change, limit=limit)