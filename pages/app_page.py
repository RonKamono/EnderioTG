import flet as ft
from parsing.coin_price_parcing import get_bybit_futures_price
import threading
import time
import concurrent.futures
from typing import Dict, List

class AppWindow:
    def __init__(self, page, cl):
        self.page = page
        self.cl = cl
        self._stop_update = False

        # Создаем все текстовые поля с помощью вспомогательной функции
        self._create_text_fields()

        # Кнопки
        self._create_buttons()

        # Создаем 8 контейнеров для позиций
        self._create_position_containers()

        # Загружаем данные из БД при запуске
        self._load_positions_from_db()

        # Собираем представление
        self.app_page = self._build_app_view()

        # Запускаем автообновление
        self._start_auto_update()

    def _start_auto_update(self):
        """Запускает поток автоматического обновления каждые 30 секунд"""

        def update_loop():
            while not self._stop_update:
                time.sleep(5)
                if self._stop_update:
                    break

                # Обновляем данные
                if self.page:
                    self._load_positions_from_db()

        thread = threading.Thread(target=update_loop, daemon=True)
        thread.start()

    def stop_auto_update(self):
        """Останавливает автоматическое обновление"""
        self._stop_update = True

    def _create_text_field(self, **kwargs):
        """Создает стандартное текстовое поле"""
        defaults = {
            'height': 60,
            'width': 380,
            'value': '',
            'bgcolor': self.cl.color_bg,
            'border_radius': 16,
            'border_color': self.cl.secondary_bg,
            'text_align': ft.TextAlign.CENTER,
            'text_style': ft.TextStyle(
                color=self.cl.text_primary,
                size=16,
                weight=ft.FontWeight.W_500,
            ),
        }
        defaults.update(kwargs)
        return ft.TextField(**defaults)

    def _create_text_fields(self):
        """Создает все текстовые поля"""
        self.name_coin = self._create_text_field()
        self.percentage_balance = self._create_text_field()
        self.cross = self._create_text_field()
        self.take_profit = self._create_text_field()
        self.stop_loss = self._create_text_field()
        self.type = self._create_text_field()

    def _create_buttons(self):
        """Создает кнопки"""
        button_style = {
            'disabled': False,
            'color': self.cl.text_primary,
            'bgcolor': self.cl.surface,
            'width': 190,
            'height': 40,
        }

        self.confirm_button = ft.ElevatedButton(
            text='Send',
            tooltip='Enter details',
            on_click=self.create_new_position,
            **button_style
        )

        self.get_button = ft.ElevatedButton(
            text='Get Position',
            tooltip='Enter details',
            on_click=self.get_info_position,
            **button_style
        )

    def _create_position_containers(self):
        """Создает 8 контейнеров для позиций"""
        self.position_containers = []
        for i in range(8):
            container = ft.Container(
                width=250,
                height=150,
                bgcolor=self.cl.color_bg,
                border_radius=20,
                content=ft.Column(
                    controls=[
                        ft.Text(f'Позиция {i + 1}', color=self.cl.text_secondary),
                        ft.Text('Отсутствует', color=self.cl.text_secondary, size=12),
                    ],
                    alignment=ft.MainAxisAlignment.CENTER,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER
                )
            )
            self.position_containers.append(container)

    def _update_container_with_data_fast(self, index: int, position_data: Dict, last_price: str):
        """Быстрое обновление контейнера с данными"""
        id = position_data.get('id')
        name = position_data.get('name')
        pos_type = position_data.get('pos_type')
        cross = position_data.get('cross')
        tp = position_data.get('take_profit')
        sl = position_data.get('stop_loss')
        percent = position_data.get('percent')
        entry_price = position_data.get('entry_price')
        updated_at = position_data.get('updated_at')

        balance_percent = 0
        if entry_price and last_price and cross:
            try:
                entry = float(entry_price)
                current = float(last_price)
                leverage = float(cross)

                if pos_type == 'short':
                    direction_multiplier = -1
                else:  # long или по умолчанию
                    direction_multiplier = 1

                price_change_pct = ((current - entry) / entry) * 100 * direction_multiplier

                position_share = float(percent) / 100 if percent else 0.01
                balance_percent = round(price_change_pct * leverage * position_share, 2)

        # Обновляем контейнер
        self.position_containers[index].content = ft.Column(
            controls=[
                ft.Text(f'ID: {id} | Coin: {name.upper()}',
                        color=self.cl.text_primary,
                        size=16,
                        weight=ft.FontWeight.W_600),
                ft.Text(f'Last: {last_price} | Entry: {entry_price} | {balance_percent}%',
                        color=self.cl.text_primary,
                        size=12,
                        weight=ft.FontWeight.W_600),
                ft.Text(f"{pos_type.upper()} | cross: {cross}",
                        color=self.cl.text_primary,
                        weight=ft.FontWeight.W_600,
                        size=12),
                ft.Text(f'TP: {tp} | SL: {sl}',
                        color=self.cl.text_primary,
                        weight=ft.FontWeight.W_600,
                        size=12),
                ft.Text(f"Balance: {percent}% | Time {updated_at}",
                        color=self.cl.text_primary,
                        weight=ft.FontWeight.W_600,
                        size=12),
            ],
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=5
        )

    def _load_positions_from_db(self):
        """Загружает позиции из базы данных"""
        try:
            from utils.send_logic import TradingDB
            db = TradingDB()
            positions = db.get_all_positions()[:8]

            # Получаем цены для всех монет параллельно
            price_cache = self._get_prices_parallel(positions)

            # Сбрасываем все контейнеры
            for i in range(8):
                self.position_containers[i].content = ft.Column(
                    controls=[
                        ft.Text(f'Позиция {i + 1}', color=self.cl.text_secondary),
                        ft.Text('Отсутствует', color=self.cl.text_secondary, size=12),
                    ],
                    alignment=ft.MainAxisAlignment.CENTER,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER
                )

            # Заполняем данными с кэшированными ценами
            for i, pos in enumerate(positions):
                if i < len(self.position_containers):
                    name = pos.get('name')
                    last_price = price_cache.get(name, 'N/A')
                    self._update_container_with_data_fast(i, pos, last_price)

            # Обновляем всю страницу
            if self.page:
                self.page.update()

        except Exception as e:
            print(f"Ошибка загрузки позиций: {e}")

    def _get_prices_parallel(self, positions: List[Dict]) -> Dict[str, str]:
        """Получает цены для всех монет параллельно"""
        price_cache = {}

        # Создаем список уникальных монет
        unique_coins = list(set(pos.get('name') for pos in positions if pos.get('name')))

        if not unique_coins:
            return price_cache

        # Используем ThreadPoolExecutor для параллельных запросов
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            # Запускаем получение цен для каждой монеты
            future_to_coin = {
                executor.submit(get_bybit_futures_price, coin): coin
                for coin in unique_coins
            }

            # Обрабатываем результаты
            for future in concurrent.futures.as_completed(future_to_coin):
                coin = future_to_coin[future]
                try:
                    price_data = future.result()
                    if price_data['found']:
                        price_cache[coin] = price_data['last_price']
                    else:
                        price_cache[coin] = 'N/A'
                        print(price_data)
                except Exception:
                    price_cache[coin] = 'N/A'
                    print(price_data)


        return price_cache

    def _update_container_with_data(self, index, position_data):
        """Обновляет контейнер данными из БД"""
        # Форматируем данные
        id = position_data.get('id')
        name = position_data.get('name')
        pos_type = position_data.get('pos_type')
        cross = position_data.get('cross')
        tp = position_data.get('take_profit')
        sl = position_data.get('stop_loss')
        percent = position_data.get('percent')

        # Получаем актуальную цену
        actual_price = get_bybit_futures_price(coin=name)
        last_price = actual_price['last_price'] if actual_price['found'] else print(actual_price['found'])

        # Обновляем контейнер
        self.position_containers[index].content = ft.Column(
            controls=[
                ft.Text(f'ID: {id} | Coin: {name.upper()}',
                        color=self.cl.text_primary,
                        size=16,
                        weight=ft.FontWeight.W_600),
                ft.Text(f'Last Price: {last_price}',
                        color=self.cl.text_primary,
                        size=16,
                        weight=ft.FontWeight.W_600),
                ft.Text(f"{pos_type.upper()} | cross: {cross}",
                        color=self.cl.text_primary,
                        weight=ft.FontWeight.W_600,
                        size=16),
                ft.Text(f'TP: {tp} | SL: {sl}',
                        color=self.cl.text_primary,
                        weight=ft.FontWeight.W_600,
                        size=16),
                ft.Text(f"Balance: {percent}%",
                        color=self.cl.text_primary,
                        weight=ft.FontWeight.W_600,
                        size=16),
            ],
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=5
        )

    def _create_field_group(self, label, field):
        """Создает группу с меткой и полем ввода"""
        return ft.Container(
            ft.Column(
                controls=[
                    ft.Text(label, size=20, weight=ft.FontWeight.W_600, color=self.cl.text_primary),
                    field
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=10
            ),
            bgcolor=self.cl.surface,
            border_radius=30,
            width=400
        )

    def _build_app_view(self):
        """Собирает основное представление приложения"""
        # Первая колонка с полями ввода
        first_column = ft.Column(
            expand=4,
            controls=[
                self._create_field_group('Coin Name', self.name_coin),
                self._create_field_group('Long/Short', self.type),
                self._create_field_group('Cross', self.cross),
                self._create_field_group('Percent balance', self.percentage_balance),
                self._create_field_group('Take Profit', self.take_profit),
                self._create_field_group('Stop Loss', self.stop_loss),
                ft.Row(
                    controls=[self.confirm_button, self.get_button],
                    alignment=ft.MainAxisAlignment.CENTER,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER
                )
            ],
            spacing=20,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            alignment=ft.MainAxisAlignment.CENTER
        )

        # Вторая колонка с позициями (2 ряда по 3 контейнера)
        second_column = ft.Column(
            expand=5,
            controls=[
                ft.Container(
                    width=550,
                    height=760,
                    bgcolor=self.cl.secondary_bg,
                    border_radius=50,
                    padding=ft.padding.all(20),
                    content=ft.Column(
                        controls=[
                            ft.Text('Positions', size=32, weight=ft.FontWeight.W_600, color=self.cl.text_primary),
                            # Две колонки по вертикали
                            ft.Row(
                                controls=[
                                    # Первая вертикальная колонка (4 контейнера)
                                    ft.Column(
                                        controls=self.position_containers[:4],
                                        spacing=15,
                                        horizontal_alignment=ft.CrossAxisAlignment.CENTER
                                    ),
                                    # Вторая вертикальная колонка (4 контейнера)
                                    ft.Column(
                                        controls=self.position_containers[4:],
                                        spacing=15,
                                        horizontal_alignment=ft.CrossAxisAlignment.CENTER
                                    )
                                ],
                                spacing=20,
                                alignment=ft.MainAxisAlignment.CENTER,
                                vertical_alignment=ft.CrossAxisAlignment.START
                            )
                        ],
                        alignment=ft.MainAxisAlignment.START,
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=20
                    )
                )
            ],
            spacing=20,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            alignment=ft.MainAxisAlignment.CENTER
        )

        return ft.Row(
            expand=True,
            controls=[first_column, second_column]
        )

    def create_new_position(self, e):
        from utils.send_logic import TradingDB
        db = TradingDB()
        name = self.name_coin.value.strip()
        percent_str = self.percentage_balance.value.strip()
        cross_str = self.cross.value.strip()
        take_profit_str = self.take_profit.value.strip()
        stop_loss_str = self.stop_loss.value.strip()
        pos_type = self.type.value.strip().lower()
        actual_price = get_bybit_futures_price(coin=name)
        entry_price_srt = actual_price['last_price'] if actual_price['found'] else print(actual_price['found'])

        # Преобразование типов
        percent = int(percent_str)
        cross = int(cross_str)
        take_profit = float(take_profit_str.replace(',', '.'))
        stop_loss = float(stop_loss_str.replace(',', '.'))
        entry_price = float(entry_price_srt.replace(',', '.'))
        db.add_to_db(name, percent, cross, entry_price, take_profit, stop_loss, pos_type)

        # После отправки обновляем позиции
        self._load_positions_from_db()

    def get_info_position(self, e=None):
        self._load_positions_from_db()

    def _show_positions_simple(self):
        """Показать позиции в простом формате (без pandas)"""
        try:
            from utils.send_logic import TradingDB
            db = TradingDB()
            positions = db.get_all_positions()

            if not positions:
                print("📭 Нет активных позиций")
                return

            print("\n" + "=" * 60)
            print("СПИСОК ПОЗИЦИЙ")
            print("=" * 60)

            for i, pos in enumerate(positions, 1):
                status = "✅" if pos.get('is_active', True) else "⏸️"
                pos_type = "📈 LONG" if pos.get('pos_type') == 'long' else "📉 SHORT"
                print(f"{i}. {status} {pos['name']} | {pos_type}")
                print(
                    f"   %: {pos.get('percent', 'N/A')} | TP: {pos.get('take_profit', 'N/A')} | SL: {pos.get('stop_loss', 'N/A')}")

                # Форматируем дату
                created_at = pos.get('created_at', '')
                if created_at and '.' in created_at:
                    created_at = created_at.split('.')[0]
                print(f"   📅 Создана: {created_at if created_at else 'N/A'}")
                print("-" * 60)
        except Exception as e:
            print(f"❌ Ошибка при показе позиций: {e}")