import requests
import concurrent.futures
from typing import Dict, List, Optional
import threading

# Глобальная блокировка для потока безопасности
print_lock = threading.Lock()

class BybitFuturesAPI:
    """Класс для работы с API фьючерсов Bybit с многопоточностью"""

    def __init__(self, max_workers: int = 10):
        self.base_url = "https://api.bybit.com/v5"
        self.max_workers = max_workers
        self._session = None
        self._session_lock = threading.Lock()

    @property
    def session(self):
        """Ленивая инициализация сессии с thread-safety"""
        if self._session is None:
            with self._session_lock:
                if self._session is None:
                    self._session = requests.Session()
                    # Оптимизация таймаутов для фьючерсных запросов
                    adapter = requests.adapters.HTTPAdapter(
                        pool_connections=self.max_workers,
                        pool_maxsize=self.max_workers,
                        max_retries=2
                    )
                    self._session.mount('https://', adapter)
        return self._session

    def _make_request(self, endpoint: str, params: Dict = None, timeout: int = 5) -> Optional[Dict]:
        """Базовый метод для выполнения запросов"""
        url = f"{self.base_url}/{endpoint}"
        try:
            response = self.session.get(url, params=params, timeout=timeout)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return None

    def _fetch_category_instruments(self, category: str) -> List[Dict]:
        """Получение инструментов для категории"""
        data = self._make_request("market/instruments-info", {"category": category})
        if data and data.get("retCode") == 0:
            return data.get("result", {}).get("list", [])
        return []

    def _process_instrument(self, instrument: Dict, category: str, search_term: str) -> Optional[Dict]:
        """Обработка одного инструмента в потоке"""
        symbol = instrument.get("symbol", "")
        status = instrument.get("status", "")
        base_coin = instrument.get("baseCoin", "")

        # Пропускаем неактивные инструменты
        if status != "Trading":
            return None

        search_upper = search_term.upper()

        # 1. Точное совпадение с символом
        if search_upper == symbol:
            return self._get_ticker_data(category, symbol, instrument)

        # 2. Частичное совпадение в символе
        if search_upper in symbol:
            # Проверяем что это фьючерс
            if "PERP" in symbol or any(char.isdigit() for char in symbol) or "USDT" in symbol:
                return self._get_ticker_data(category, symbol, instrument)

        # 3. Поиск по baseCoin (убираем USDT из поиска)
        coin_name_only = search_upper.replace("USDT", "").replace("USD", "")
        if coin_name_only and coin_name_only == base_coin.upper():
            # Проверяем что это фьючерс
            if "PERP" in symbol or any(char.isdigit() for char in symbol):
                return self._get_ticker_data(category, symbol, instrument)

        return None

    def _get_ticker_data(self, category: str, symbol: str, instrument_info: Dict) -> Optional[Dict]:
        """Получение данных тикера для конкретного символа"""
        data = self._make_request("market/tickers", {"category": category, "symbol": symbol})

        if not data or data.get("retCode") != 0:
            return None

        ticker_list = data.get("result", {}).get("list", [])
        if not ticker_list:
            return None

        ticker = ticker_list[0]

        # Определяем тип контракта
        if "PERP" in symbol:
            contract_type = "perpetual"
        elif any(char.isdigit() for char in symbol):
            contract_type = "dated"
        else:
            contract_type = "quarterly"

        return {
            'found': True,
            'symbol': symbol,
            'category': category,
            'contract_type': contract_type,
            'last_price': ticker.get("lastPrice", "N/A"),
            'mark_price': ticker.get("markPrice", "N/A"),
            'index_price': ticker.get("indexPrice", "N/A"),
            '24h_change': ticker.get("price24hPcnt", "0"),
            '24h_high': ticker.get("highPrice24h", "N/A"),
            '24h_low': ticker.get("lowPrice24h", "N/A"),
            '24h_volume': ticker.get("volume24h", "N/A"),
            'open_interest': ticker.get("openInterest", "N/A"),
            'funding_rate': ticker.get("fundingRate", "N/A"),
            'next_funding': ticker.get("nextFundingTime", "N/A"),
            'base_coin': instrument_info.get("baseCoin", "N/A"),
            'quote_coin': instrument_info.get("quoteCoin", "N/A"),
            'expiry_time': instrument_info.get("expiryTime", "N/A"),
            'settle_coin': instrument_info.get("settleCoin", "N/A"),
            'source': 'bybit'
        }

    def search_futures(self, coin: str, categories: List[str] = None) -> Dict:
        """
        Многопоточный поиск фьючерсов на монету
        """
        if categories is None:
            categories = ["linear", "inverse"]

        search_term = coin.upper().strip()

        # Сначала попробуем прямой запрос для поиска символа
        for category in categories:
            # Пробуем разные варианты символа
            possible_symbols = [
                search_term,  # WIFUSDT
                f"{search_term}PERP",  # WIFUSDTPERP
                search_term.replace("USDT", "") + "USDT",  # Убедимся что есть USDT
                search_term + "USD"  # WIFUSD
            ]

            for symbol in possible_symbols:
                # Прямой запрос тикера
                data = self._make_request("market/tickers", {"category": category, "symbol": symbol})

                if data and data.get("retCode") == 0:
                    ticker_list = data.get("result", {}).get("list", [])
                    if ticker_list:
                        # Получаем информацию об инструменте
                        info_data = self._make_request("market/instruments-info",
                                                       {"category": category, "symbol": symbol})
                        instrument_info = {}
                        if info_data and info_data.get("retCode") == 0:
                            instruments = info_data.get("result", {}).get("list", [])
                            if instruments:
                                instrument_info = instruments[0]

                        ticker = ticker_list[0]

                        # Определяем тип контракта
                        if "PERP" in symbol:
                            contract_type = "perpetual"
                        elif any(char.isdigit() for char in symbol):
                            contract_type = "dated"
                        else:
                            contract_type = "quarterly"

                        return {
                            'found': True,
                            'symbol': symbol,
                            'category': category,
                            'contract_type': contract_type,
                            'last_price': ticker.get("lastPrice", "N/A"),
                            'mark_price': ticker.get("markPrice", "N/A"),
                            'index_price': ticker.get("indexPrice", "N/A"),
                            '24h_change': ticker.get("price24hPcnt", "0"),
                            '24h_high': ticker.get("highPrice24h", "N/A"),
                            '24h_low': ticker.get("lowPrice24h", "N/A"),
                            '24h_volume': ticker.get("volume24h", "N/A"),
                            'open_interest': ticker.get("openInterest", "N/A"),
                            'funding_rate': ticker.get("fundingRate", "N/A"),
                            'next_funding': ticker.get("nextFundingTime", "N/A"),
                            'base_coin': instrument_info.get("baseCoin", "N/A"),
                            'quote_coin': instrument_info.get("quoteCoin", "N/A"),
                            'expiry_time': instrument_info.get("expiryTime", "N/A"),
                            'settle_coin': instrument_info.get("settleCoin", "N/A"),
                            'source': 'bybit'
                        }

        # Если прямой поиск не сработал, ищем в списке всех инструментов
        for category in categories:
            instruments = self._fetch_category_instruments(category)

            for instrument in instruments:
                symbol = instrument.get("symbol", "")
                status = instrument.get("status", "")

                if status != "Trading":
                    continue

                # Проверяем различные варианты совпадения
                search_clean = search_term.replace("USDT", "").replace("USD", "")
                symbol_clean = symbol.replace("USDT", "").replace("USD", "").replace("PERP", "")

                # Ищем совпадение по очищенным названиям
                if search_clean in symbol_clean or search_term in symbol:
                    # Получаем данные тикера
                    return self._get_ticker_data(category, symbol, instrument)

        return {
            'found': False,
            'message': f'Фьючерсы на "{coin}" не найдены на Bybit.',
            'category': 'futures',
            'source': 'bybit'
        }

# Функция для обратной совместимости
def get_bybit_futures_price(coin: str, max_workers: int = 10) -> Dict:
    """
    Оптимизированная многопоточная функция для поиска цены монеты во фьючерсах на Bybit

    Args:
        coin: Название монеты
        max_workers: Максимальное количество потоков

    Returns:
        dict: Результат поиска
    """
    api = BybitFuturesAPI(max_workers=max_workers)
    return api.search_futures(coin)

# Многопоточный поиск для нескольких монет одновременно
def search_multiple_coins(coins: List[str], max_workers_per_search: int = 5) -> Dict[str, Dict]:
    """
    Поиск фьючерсов для нескольких монет одновременно

    Args:
        coins: Список названий монет
        max_workers_per_search: Количество потоков на один поиск

    Returns:
        Dict: Словарь с результатами для каждой монеты
    """
    results = {}

    with concurrent.futures.ThreadPoolExecutor(max_workers=len(coins)) as executor:
        # Создаем футуры для каждой монеты
        future_to_coin = {
            executor.submit(get_bybit_futures_price, coin, max_workers_per_search): coin
            for coin in coins
        }

        # Обрабатываем результаты
        for future in concurrent.futures.as_completed(future_to_coin):
            coin = future_to_coin[future]
            try:
                results[coin] = future.result()
            except Exception as e:
                results[coin] = {
                    'found': False,
                    'message': f'Ошибка при поиске: {str(e)}',
                    'source': 'bybit'
                }

    return results

# Примеры использования - В КОНЦЕ ФАЙЛА
if __name__ == "__main__":
    import time

    # Тест одиночного поиска
    print("🔍 Тест одиночного поиска:")
    start_time = time.time()

    result = get_bybit_futures_price("WIF", max_workers=8)

    if result['found']:
        with print_lock:
            print(f"✅ НАЙДЕНО: {result['symbol']}")
            print(f"   Тип: {result['category']} | {result['contract_type']}")
            print(f"   Цена: ${result['last_price']}")
            print(f"   Изменение 24ч: {float(result['24h_change']) * 100:.2f}%")
    else:
        print(f"❌ {result['message']}")

    print(f"⏱️ Время выполнения: {time.time() - start_time:.2f} секунд")

    # Тест многопоточного поиска нескольких монет
    print("\n🔍 Тест поиска нескольких монет:")
    coins_to_search = ["BTC", "ETH", "SOL", "ADA", "DOGE", "XRP", "DOT", "AVAX"]

    start_time = time.time()
    all_results = search_multiple_coins(coins_to_search, max_workers_per_search=4)

    with print_lock:
        for coin, result in all_results.items():
            if result['found']:
                print(f"{coin}: {result}")
                print(f"{coin} | Last_price: {result['last_price']}$ | 24H Change: {float(result['24h_change']) * 100:.2f}% | 24h HIGH: {float(result['24h_high'])}$ | 24h LOW: {float(result['24h_low'])}$")
            else:
                print(f"❌ {coin}: {result['message']}")

    print(f"⏱️ Общее время поиска {len(coins_to_search)} монет: {time.time() - start_time:.2f} секунд")