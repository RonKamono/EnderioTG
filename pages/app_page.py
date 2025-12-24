import concurrent.futures
import webbrowser

import flet as ft
import threading, time
import utils.webbrowser_open as wbb
import sys
import os
from datetime import datetime
from parsing.coin_price_parcing import get_bybit_futures_price
from typing import Dict, List, Optional


class AppWindow:
    def __init__(self, page, cl, trading_bot=None):
        self.page = page
        self.cl = cl
        self.trading_bot = trading_bot
        self._stop_update = False
        self._stop_price_updates = False
        self.db = None

        # Для хранения данных о парах
        self.volatile_pairs = []
        self.pairs_update_lock = threading.Lock()

        # Режим удаления
        self.delete_mode = False

        # Инициализация БД
        self._init_database()

        # Создаем UI элементы
        self._create_text_fields()
        self._create_buttons()
        self._create_position_containers()
        self._create_change_price_containers()
        self._create_target_container()

        # Загружаем позиции из БД
        self._load_positions_from_db()

        # Собираем представление
        self.app_page = self._build_app_view()

        # Запускаем автообновление позиций
        self._start_auto_update()

        # Работа с потоками для ALERT
        self._stop_alerts = False
        self.alerts = []
        self.alerts_lock = threading.Lock()
        self._start_alert_checker()

        # Запускаем парсинг цен с небольшой задержкой
        threading.Timer(1.0, self._start_price_updates).start()

        # Делаем первоначальную загрузку данных
        threading.Timer(2.0, self._force_initial_price_update).start()

    def _start_auto_update(self):
        """Запускает поток автоматического обновления"""

        def update_loop():
            while not self._stop_update:
                time.sleep(2)
                if self._stop_update:
                    break
                # Обновляем данные
                if self.page and self.db:
                    self._load_positions_from_db()

        thread = threading.Thread(target=update_loop, daemon=True)
        thread.start()

    def _init_database(self):
        """Инициализация подключения к базе данных"""
        try:
            # Добавляем путь к utils
            utils_path = os.path.join(os.path.dirname(__file__), '..', 'utils')
            if utils_path not in sys.path:
                sys.path.append(utils_path)
            from utils.database_logic import TradingDB

            self.db = TradingDB()
            print("✅ База данных инициализирована в AppWindow")
        except Exception as e:
            print(f"❌ Ошибка инициализации БД: {e}")
            self.db = None

    def _load_positions_from_db(self):
        """Загружает позиции из базы данных"""
        if not self.db:
            print("❌ БД не инициализирована")
            return

        try:
            # Получаем все позиции
            positions = self.db.get_all_positions(active_only=False)
            # Получаем цены
            price_cache = self._get_prices_parallel(positions)

            # Обновляем контейнеры
            for i in range(8):
                if i < len(positions):
                    pos = positions[i]
                    name = pos.get('name')
                    last_price = price_cache.get(name, 'N/A')
                    self._update_container_with_data(i, pos, last_price)
                else:
                    # Очищаем контейнер если позиции нет
                    self.position_containers[i].content = ft.Column(
                        controls=[
                            ft.Text(f'Позиция {i + 1}', color=self.cl.text_secondary),
                            ft.Text('Отсутствует', color=self.cl.text_secondary, size=12),
                        ],
                        alignment=ft.MainAxisAlignment.CENTER,
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER
                    )
                    self.position_containers[i].bgcolor = self.cl.color_bg

            # Обновляем страницу
            if self.page:
                self.page.update()

        except Exception as e:
            print(f"❌ Ошибка загрузки позиций: {e}")
            import traceback
            traceback.print_exc()

    # Создание элементов
    def _create_text_field(self, **kwargs):
        """Создает стандартное текстовое поле"""
        defaults = {
            'height': 40,
            'width': 180,
            'value': '',
            'bgcolor': self.cl.color_bg,
            'border_radius': 16,
            'border_color': self.cl.secondary_bg,
            'text_align': ft.TextAlign.CENTER,
            'text_style': ft.TextStyle(
                color=self.cl.text_primary,
                size=14,
                weight=ft.FontWeight.W_500,
            ),
        }
        defaults.update(kwargs)
        return ft.TextField(**defaults)

    def _create_text_fields(self):
        """Создает все текстовые поля"""
        self.name_coin = self._create_text_field(value='')
        self.percentage_balance = self._create_text_field(value='10')
        self.cross = self._create_text_field(value='30')
        self.take_profit = self._create_text_field()
        self.stop_loss = self._create_text_field()
        self.type = self._create_text_field(value='')

        self.target_name = self._create_text_field(value='')
        self.target_price = self._create_text_field()

    def _create_buttons(self):
        """Создает кнопки"""
        button_style = {
            'disabled': False,
            'color': self.cl.text_primary,
            'bgcolor': self.cl.surface,
            'width': 200,
            'height': 40,
        }

        self.confirm_button = ft.ElevatedButton(
            text='Send Position',
            tooltip='Enter details',
            on_click=lambda e: self.create_new_position(e),
            **button_style
        )

        self.delete_position_button = ft.ElevatedButton(
            text='Delete Position',
            on_click=lambda e: self._toggle_delete_mode(e),
            **button_style
        )

        self.create_alert = ft.ElevatedButton(
            text='Set Alert',
            on_click=lambda e: self._set_alert_on_target(e),
            **button_style
        )

        self.remove_alert = ft.ElevatedButton(
            text='Delete Alert',
            on_click=lambda e: self._remove_alert(e),
            **button_style
        )

        # Кнопка отмены удаления (скрыта по умолчанию)
        self.cancel_delete_button = ft.ElevatedButton(
            text='Cancel Delete',
            on_click=lambda e: self._cancel_delete_mode(e),
            **button_style
        )
        self.cancel_delete_button.visible = False

    def _toggle_delete_mode(self, e):
        """Включает/выключает режим удаления позиций"""
        self.delete_mode = not self.delete_mode

        if self.delete_mode:
            print("🔴 РЕЖИМ УДАЛЕНИЯ АКТИВЕН: Нажмите на позицию для удаления")
            self.delete_position_button.text = "Cancel Delete"
            self.cancel_delete_button.visible = True

            # Показываем сообщение
            self._show_message("🔴 РЕЖИМ УДАЛЕНИЯ: Нажмите на позицию для удаления")

            # Включаем анимацию пульсации для контейнеров позиций
            for i, container in enumerate(self.position_containers):
                if container.content.controls and len(container.content.controls) > 0:
                    # Проверяем, есть ли реальная позиция
                    first_text = container.content.controls[0]
                    if isinstance(first_text, ft.Text) and "ID:" in first_text.value:
                        container.on_click = lambda e, idx=i: self._delete_selected_position(idx)
        else:
            print("✅ Режим удаления отключен")
            self.delete_position_button.text = "Delete Position"
            self.delete_position_button.bgcolor = self.cl.surface
            self.cancel_delete_button.visible = False

            # Сбрасываем стили контейнеров
            for container in self.position_containers:
                container.bgcolor = self.cl.color_bg
                container.border = None
                container.on_click = None

            self._show_message("✅ Режим удаления отключен")

        # Обновляем UI
        if self.page:
            self.page.update()

    def _cancel_delete_mode(self, e):
        """Отменяет режим удаления"""
        self.delete_mode = False
        self.delete_position_button.text = "Delete Position"
        self.delete_position_button.bgcolor = self.cl.surface
        self.cancel_delete_button.visible = False

        # Сбрасываем стили контейнеров
        for container in self.position_containers:
            container.bgcolor = self.cl.color_bg
            container.border = None
            container.on_click = None

        print("✅ Режим удаления отменен")
        self._show_message("✅ Режим удаления отменен")

        if self.page:
            self.page.update()

    def _delete_selected_position(self, index):
        """Удаляет выбранную позицию"""
        if not self.delete_mode:
            return

        try:
            # Получаем данные позиции
            positions = self.db.get_all_positions(active_only=False)
            if index >= len(positions):
                print("❌ Позиция не найдена")
                self._show_message("❌ Позиция не найдена", is_error=True)
                return

            position = positions[index]
            position_id = position.get('id')
            position_name = position.get('name')

            # Запрашиваем подтверждение
            self._show_delete_confirmation(position_id, position_name, index)

        except Exception as e:
            print(f"❌ Ошибка при удалении позиции: {e}")
            self._show_message(f"❌ Ошибка: {str(e)}", is_error=True)

    def _show_delete_confirmation(self, position_id, position_name, index):
        """Показывает диалог подтверждения удаления"""

        def confirm_delete(e):
            # Удаляем позицию из БД
            if self.db and hasattr(self.db, 'delete_position'):
                success = self.db.delete_position(position_id)
                if success:
                    print(f"✅ Позиция {position_name} (ID: {position_id}) удалена из БД")
                    self._show_message(f"✅ Позиция {position_name} удалена")

                    # Уведомляем TradingBot об удалении
                    if self.trading_bot and hasattr(self.trading_bot, 'remove_position'):
                        self.trading_bot.remove_position(position_id)

                    # Обновляем UI
                    self._load_positions_from_db()
                else:
                    print(f"❌ Не удалось удалить позицию {position_name}")
                    self._show_message("❌ Не удалось удалить позицию", is_error=True)
            else:
                print("❌ База данных не доступна")
                self._show_message("❌ База данных не доступна", is_error=True)

            # Закрываем диалог
            self.page.close(dlg)
            # Отключаем режим удаления
            self._cancel_delete_mode(None)

        def cancel_delete(e):
            self.page.close(dlg)

        # Создаем диалог подтверждения
        dlg = ft.AlertDialog(
            title=ft.Text("Подтверждение удаления"),
            content=ft.Column([
                ft.Text(f"Вы уверены, что хотите удалить позицию?", size=16),
                ft.Text(f"ID: {position_id} | {position_name}", size=18, weight=ft.FontWeight.BOLD),
                ft.Text("Это действие нельзя отменить!", size=14, color=ft.Colors.RED, weight=ft.FontWeight.W_500)
            ], tight=True),
            actions=[
                ft.TextButton("Удалить", on_click=confirm_delete, style=ft.ButtonStyle(color=ft.Colors.RED)),
                ft.TextButton("Отмена", on_click=cancel_delete),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )

        self.page.open(dlg)

    def _show_message(self, message: str, is_error: bool = False):
        """Показывает всплывающее сообщение"""
        self.page.snack_bar = ft.SnackBar(
            content=ft.Text(message),
            bgcolor=ft.Colors.RED_400 if is_error else self.cl.secondary_bg
        )
        self.page.snack_bar.open = True
        if self.page:
            self.page.update()

    def _create_position_containers(self):
        """Создает контейнеры для позиций"""
        self.position_containers = []
        for i in range(8):
            container = ft.Container(
                width=330,
                height=190,
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

    def _create_field_group(self, label, field):
        """Создает группу с меткой и полем ввода"""
        return ft.Container(
            ft.Column(
                controls=[
                    ft.Text(label, size=16, weight=ft.FontWeight.W_600, color=self.cl.text_primary),
                    field
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=10
            ),
            bgcolor=self.cl.surface,
            border_radius=30,
            height=80,
            width=200
        )

    def _create_change_price_containers(self):
        """Создает контейнеры для изменения цен"""
        self.change_price_containers = []
        for i in range(10):
            container = ft.Container(
                width=200,
                height=152,
                bgcolor=self.cl.color_bg,
                border_radius=20,
                padding=ft.padding.all(10),
                content=self._create_price_container_content(i)
            )
            self.change_price_containers.append(container)

    def _create_target_container(self):
        self.target_coin_container = []
        target_container = ft.Container(
            width=400,
            height=240,
            bgcolor=self.cl.color_bg,
            border_radius=20,
            content=ft.Column(
                controls=[
                    ft.Text(f'Позиция', color=self.cl.text_secondary),
                    ft.Text('Отсутствует', color=self.cl.text_secondary, size=14),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER
            )
        )
        self.target_coin_container.append(target_container)

    # Методы отвечающие за парсинг и изменение цен

    def _force_initial_price_update(self):
        try:
            from parsing.detected_24h_price import get_volatile_usdt_pairs

            pairs = get_volatile_usdt_pairs(min_change=10.0, limit=10)

            with self.pairs_update_lock:
                self.volatile_pairs = pairs

            # Обновляем UI
            self._update_price_containers()

        except Exception as e:
            print(f"❌ [AppWindow] Ошибка начальной загрузки: {e}")

    def _create_price_container_content(self, index: int):
        """Создает содержимое контейнера цены"""
        return ft.Column(
            controls=[
                ft.Text(f'Монета {index + 1}',
                        color=self.cl.text_secondary,
                        size=14,
                        weight=ft.FontWeight.W_600),
                ft.Text('Загрузка...',
                        color=self.cl.text_secondary,
                        size=12),
                ft.Text('0.00%',
                        color=self.cl.text_secondary,
                        size=18,
                        weight=ft.FontWeight.W_700),
                ft.Text('Объем: 0',
                        color=self.cl.text_secondary,
                        size=10),
                ft.Text('--:--:--',
                        color=self.cl.text_secondary,
                        size=10)
            ],
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=5
        )

    def _start_price_updates(self):
        """Запускает обновление цен в отдельном потоке"""

        def price_update_thread():
            try:
                from parsing.detected_24h_price import get_global_screener
            except ImportError as e:
                print(f"❌ [AppWindow] Ошибка импорта: {e}")
                return

            screener = get_global_screener()

            # Функция обратного вызова при получении новых данных
            def on_pairs_update(pairs):
                """Эта функция вызывается из потока скринера"""
                try:
                    # Сохраняем данные
                    with self.pairs_update_lock:
                        self.volatile_pairs = pairs

                    # Обновляем UI в основном потоке
                    if hasattr(self, 'page') and self.page:
                        try:
                            # Обновляем контейнеры синхронно
                            self._update_price_containers()
                        except Exception as e:
                            print(f"⚠️ [AppWindow] Ошибка обновления UI: {e}")

                except Exception as e:
                    print(f"❌ [AppWindow] Ошибка в on_pairs_update: {e}")
                    import traceback
                    traceback.print_exc()

            # Запускаем периодическое обновлениеЁ
            screener.start_periodic_updates(on_pairs_update, interval=10)

            # Держим поток живым
            while not self._stop_price_updates:
                time.sleep(1)

        # Запускаем поток
        thread = threading.Thread(target=price_update_thread, daemon=True)
        thread.start()
        print(f"✅ [AppWindow] Поток обновления цен запущен (ID: {thread.ident})")

    def _update_price_containers(self):
        """Обновляет контейнеры с ценами на основе полученных данных"""
        try:
            if not hasattr(self, 'volatile_pairs'):
                self.volatile_pairs = []

            if not self.volatile_pairs:
                # Если данных нет, показываем заглушки
                for i in range(10):
                    self._update_single_price_container(i, None)
                return

            # Обновляем первые N контейнеров данными
            for i in range(min(10, len(self.volatile_pairs))):
                self._update_single_price_container(i, self.volatile_pairs[i])

            # Остальные контейнеры очищаем
            for i in range(len(self.volatile_pairs), 10):
                self._update_single_price_container(i, None)

            # Обновляем страницу
            if hasattr(self, 'page') and self.page:
                try:
                    self.page.update()
                except Exception as e:
                    print(f"⚠️ [AppWindow] Ошибка обновления страницы: {e}")
        except Exception as e:
            print(f"❌ [AppWindow] Ошибка в _update_price_containers: {e}")
            import traceback
            traceback.print_exc()

    def stop_all_updates(self):
        """Останавливает все обновления"""
        self._stop_update = True
        self._stop_alerts = True
        self._stop_price_updates = True

        # Останавливаем скринер
        try:
            from parsing.detected_24h_price import get_global_screener
            screener = get_global_screener()
            screener.stop_updates()
        except:
            pass

    def _force_price_update(self):
        """Принудительное обновление цен"""
        from parsing.detected_24h_price import get_volatile_usdt_pairs

        try:
            pairs = get_volatile_usdt_pairs(min_change=10.0, limit=10)
            with self.pairs_update_lock:
                self.volatile_pairs = pairs

            self._update_price_containers()

            # Показываем уведомление
            if self.page:
                self.page.snack_bar = ft.SnackBar(
                    content=ft.Text("✅ Цены обновлены!"),
                    bgcolor=ft.Colors.GREEN_400
                )
                self.page.snack_bar.open = True
                self.page.update()
        except Exception as e:
            print(f"❌ Ошибка принудительного обновления: {e}")

    def _show_top_pairs(self):
        """Показывает топ пар в диалоге"""
        if not self.volatile_pairs:
            return

        pairs_list = []
        for i, pair in enumerate(self.volatile_pairs[:10], 1):
            change = pair.get('price_change', 0)
            color = ft.Colors.GREEN_400 if change > 0 else ft.Colors.RED_400

            pairs_list.append(
                ft.ListTile(
                    leading=ft.Text(f"{i}.", size=16),
                    title=ft.Text(pair.get('symbol', 'N/A'), size=16),
                    subtitle=ft.Text(f"{pair.get('base_asset', '').upper()} | ${pair.get('price_usdt', 0):.4f}"),
                    trailing=ft.Text(
                        f"{'+' if change > 0 else ''}{change:.2f}%",
                        color=color,
                        size=16,
                        weight=ft.FontWeight.W_700
                    )
                )
            )

    # Методы отвечающие за Alert Target

    def _start_alert_checker(self):
        """Запускает поток проверки алертов"""

        def alert_checker_loop():
            while not self._stop_alerts:
                try:
                    # Проверяем алерты каждые 5 секунд
                    time.sleep(5)

                    # Если нет алертов - пропускаем
                    with self.alerts_lock:
                        if not self.alerts:
                            continue

                    # Проверяем каждый алерт
                    self._check_all_alerts()

                except Exception as e:
                    print(f"❌ Ошибка в потоке алертов: {e}")
                    import traceback
                    traceback.print_exc()

        # Создаем и запускаем поток
        thread = threading.Thread(target=alert_checker_loop, daemon=True, name="alert_checker")
        thread.start()
        print(f"✅ Запущен поток проверки алертов (ID: {thread.ident})")

    def _check_all_alerts(self):
        """Проверяет все активные алерты"""
        from parsing.coin_price_parcing import get_bybit_futures_price

        # Создаем копию алертов для безопасной работы
        alerts_to_check = []
        with self.alerts_lock:
            alerts_to_check = self.alerts.copy()

        for alert in alerts_to_check:
            try:
                if not alert.get('active', True):
                    continue

                # Получаем текущую цену
                price_data = get_bybit_futures_price(coin=alert['name'])

                if not price_data['found']:
                    continue

                current_price = float(price_data['last_price'])
                target_price = alert['target_price']
                condition = alert.get('condition', 'above')

                # Обновляем текущую цену в алерте
                alert['current_price'] = current_price

                # Обновляем UI с новой ценой
                self._update_alert_container(alert)

                # Проверяем в зависимости от условия
                triggered = False

                if condition == 'above':
                    # Алерт "выше": текущая цена должна быть >= целевой
                    triggered = current_price >= target_price
                    status = "выше"
                else:  # condition == 'below'
                    # Алерт "ниже": текущая цена должна быть <= целевой
                    triggered = current_price <= target_price
                    status = "ниже"

                # Если сработал - выполняем действие
                if triggered:
                    print(f"🎯 АЛЕРТ СРАБОТАЛ: {alert['name']} ${current_price:.4f} {status} ${target_price:.4f}")
                    self._handle_alert_triggered(alert, current_price, condition)

                    # Удаляем алерт
                    with self.alerts_lock:
                        self.alerts = []

            except Exception as e:
                print(f"❌ Ошибка проверки алерта {alert.get('name')}: {e}")

        # Обновляем страницу после всех проверок
        if self.page:
            self.page.update()

    def _handle_alert_triggered(self, alert, current_price, condition):
        """Обрабатывает срабатывание алерта"""
        self._send_alert_to_telegram(alert, current_price, condition)

    def _update_alert_container(self, alert):
        """Обновляет контейнер алерта"""
        # Рассчитываем разницу
        current_price = alert['current_price']
        target_price = alert['target_price']
        price_diff = current_price - target_price
        price_diff_percent = (price_diff / target_price) * 100

        # Определяем цвет для разницы
        if price_diff >= 0:
            diff_sign = "+"
        else:
            diff_sign = ""

        self.target_coin_container[0].content = ft.Column(
            controls=[
                ft.Text(f"{alert['name']}", size=24, weight=ft.FontWeight.W_700, color=self.cl.text_primary),
                ft.Text(f"Target Price: ${target_price:.4f}", weight=ft.FontWeight.W_600, size=14,
                        color=self.cl.text_primary),
                ft.Text(f"Current Price: ${current_price:.4f}", weight=ft.FontWeight.W_600, size=14,
                        color=self.cl.text_primary),
                ft.Text(
                    f"Difference: {diff_sign}{price_diff:.4f}$ ({diff_sign}{price_diff_percent:.2f}%)",
                    size=14,
                    color=self.cl.text_primary,
                    weight=ft.FontWeight.W_600
                ),
                ft.Text(f"Update: {datetime.now().strftime('%H:%M:%S')}", size=12, weight=ft.FontWeight.W_500,
                        color=self.cl.text_secondary),
            ],
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=10
        )

    def _update_alert_current_price(self):
        """Обновляет текущую цену в контейнере алерта"""
        if not self.alerts:
            return

        try:
            from parsing.coin_price_parcing import get_bybit_futures_price

            with self.alerts_lock:
                alerts_copy = self.alerts.copy()

            for alert in alerts_copy:
                if not alert.get('active', True):
                    continue

                # Получаем текущую цену
                price_data = get_bybit_futures_price(coin=alert['name'])

                if not price_data['found']:
                    continue

                # Обновляем текущую цену в алерте
                alert['current_price'] = float(price_data['last_price'])

                # Обновляем UI
                self._update_alert_container(alert)

            # Обновляем страницу
            if self.page:
                self.page.update()

        except Exception as e:
            print(f"❌ Ошибка обновления цены алерта: {e}")

    def _remove_alert(self, e):
        """Удаляет алерт по ID"""
        try:
            with self.alerts_lock:
                self.alerts = []

            # Сбрасываем контейнер к состоянию по умолчанию
            self._reset_alert_container()

            print(f"✅ Алерт удален")

        except Exception as e:
            print(f"❌ Ошибка удаления алерта: {e}")

    def _set_alert_on_target(self, e):
        """Устанавливает алерт на целевую цену"""
        try:
            target_name = self.target_name.value.strip().upper()
            target_price = float(self.target_price.value.replace(',', '.'))

            if not target_name or not target_price:
                print("❌ Заполните все поля алерта")
                return

            # Получаем текущую цену для сравнения
            from parsing.coin_price_parcing import get_bybit_futures_price
            price_data = get_bybit_futures_price(coin=target_name)

            if not price_data['found']:
                print(f"❌ Не удалось получить цену для {target_name}")
                return

            current_price = float(price_data['last_price'])

            # Определяем условие (выше или ниже текущей цены)
            # Если целевая цена выше текущей - ждем когда цена ВЫШЕ цели
            # Если целевая цена ниже текущей - ждем когда цена НИЖЕ цели
            condition = 'above' if target_price > current_price else 'below'

            print(f"📊 Текущая цена {target_name}: ${current_price:.4f}")
            print(f"🔔 Устанавливаю алерт: {condition} ${target_price:.4f}")

            # Создаем алерт
            alert = {
                'id': len(self.alerts) + 1,
                'name': target_name,
                'target_price': target_price,
                'current_price': current_price,
                'condition': condition,  # 'above' или 'below'
                'created_at': datetime.now().strftime('%H:%M:%S'),
                'active': True
            }

            # Добавляем в список алертов
            with self.alerts_lock:
                self.alerts.clear()  # Очищаем старые (если нужен только один алерт)
                self.alerts.append(alert)

            # Обновляем UI
            self._update_alert_container(alert)

            # Очищаем поля
            self.target_name.value = ''
            self.target_price.value = ''

            # Показываем уведомление
            if self.page:
                self.page.snack_bar = ft.SnackBar(
                    content=ft.Text(f"✅ Алерт для {target_name} установлен ({condition} ${target_price:.4f})"),
                    bgcolor=ft.Colors.GREEN_400
                )
                self.page.snack_bar.open = True
                self.page.update()

        except Exception as ex:
            print(f"❌ Ошибка установки алерта: {ex}")

    def _reset_alert_container(self):
        """Сбрасывает контейнер алерта к состоянию по умолчанию"""
        if hasattr(self, 'target_coin_container') and self.target_coin_container:
            # target_coin_container[0] - это Container, у него есть content
            self.target_coin_container[0].content = ft.Column(
                controls=[
                    ft.Text('Позиция', color=self.cl.text_secondary),
                    ft.Text('Отсутствует', color=self.cl.text_secondary, size=14),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER
            )
            # Обновляем страницу
            if self.page:
                self.page.update()

    def _send_alert_to_telegram(self, alert, current_price, condition):
        """Отправляет алерт в Telegram через TradingBot"""
        try:
            if self.trading_bot:
                condition_text = "выше" if condition == 'above' else "ниже"
                price_diff = current_price - alert['target_price']
                price_diff_percent = (price_diff / alert['target_price']) * 100

                diff_sign = "+" if price_diff >= 0 else ""

                message = (
                    "<b>Trigger price</b>\n\n"
                    f"<b>{alert['name']}</b>\n"
                    f"Trigger price: {alert['current_price']}\n"
                    f"Time:: {datetime.now().strftime('%H:%M:%S')}\n\n"
                    f"<a href='https://www.bybit.com/trade/usdt/{alert['name']}'>Open Bybit</a>\n"
                    f"<a href='https://www.binance.com/en/trade/{alert['name'].replace('USDT', '_USDT')}'>Open Binance</a>"
                )

                import threading

                def send_in_thread():
                    """Отправка в отдельном потоке"""
                    import asyncio

                    # Создаем новый event loop для этого потока
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)

                    try:
                        # Запускаем асинхронную отправку
                        loop.run_until_complete(self.trading_bot.send_to_all_users(message))
                        print(f"✅ Уведомление об алерте {alert['name']} отправлено")
                    except Exception as e:
                        print(f"❌ Ошибка отправки в Telegram: {e}")
                    finally:
                        loop.close()

                # Запускаем отправку в отдельном потоке
                thread = threading.Thread(target=send_in_thread, daemon=True)
                thread.start()

            else:
                print("⚠️ TradingBot не инициализирован или нет метода send_to_all_users")

        except Exception as e:
            print(f"❌ Ошибка отправки в Telegram: {e}")

    # Отрисовка
    def _build_app_view(self):
        # Первая колонка с полями ввода
        first_column = ft.Column(
            expand=2,
            controls=[
                ft.Container(
                    height=425,
                    width=440,
                    bgcolor=self.cl.secondary_bg,
                    border_radius=50,
                    content=ft.Column(
                        controls=[
                            ft.Container(
                                content=ft.Text('Create Position',
                                                size=32,
                                                weight=ft.FontWeight.W_600,
                                                color=self.cl.text_primary),
                                alignment=ft.alignment.center
                            ),
                            ft.Row(
                                controls=[
                                    ft.Column(
                                        controls=[
                                            self._create_field_group('Coin Name', self.name_coin),
                                            self._create_field_group('Percent balance', self.percentage_balance),
                                            self._create_field_group('Cross', self.cross)
                                        ]
                                    ),
                                    ft.Column(
                                        controls=[
                                            self._create_field_group('Long/Short', self.type),
                                            self._create_field_group('Stop Loss', self.stop_loss),
                                            self._create_field_group('Take Profit', self.take_profit)
                                        ]
                                    )
                                ], alignment=ft.MainAxisAlignment.CENTER,
                                vertical_alignment=ft.CrossAxisAlignment.CENTER
                            ),

                            ft.Row(
                                controls=[
                                    self.confirm_button,
                                    self.delete_position_button,
                                ],
                                alignment=ft.MainAxisAlignment.CENTER,
                            )
                        ],
                        spacing=25,
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        alignment=ft.MainAxisAlignment.CENTER
                    )
                ),
                ft.Container(
                    width=450,
                    height=460,
                    bgcolor=self.cl.secondary_bg,
                    border_radius=50,
                    content=ft.Column(
                        controls=[
                            ft.Container(
                                content=ft.Text('Alert Trigger',
                                                size=32,
                                                weight=ft.FontWeight.W_600,
                                                color=self.cl.text_primary),
                                alignment=ft.alignment.center
                            ),
                            ft.Column(
                                controls=self.target_coin_container,
                                spacing=15,
                                horizontal_alignment=ft.CrossAxisAlignment.CENTER
                            ),
                            ft.Row(
                                controls=[
                                    self._create_field_group('Coin Name', self.target_name),
                                    self._create_field_group('Target price', self.target_price),
                                ], alignment=ft.MainAxisAlignment.CENTER
                            ),
                            ft.Row(
                                controls=[self.create_alert, self.remove_alert],
                                alignment=ft.MainAxisAlignment.CENTER,
                            ),
                        ], alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.CENTER
                    )
                )

            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            alignment=ft.MainAxisAlignment.CENTER
        )

        # Вторая колонка с позициями
        second_column = ft.Column(
            expand=3,
            controls=[
                ft.Container(
                    width=750,
                    height=900,
                    bgcolor=self.cl.secondary_bg,
                    border_radius=50,
                    padding=ft.padding.all(10),
                    content=ft.Column(
                        controls=[
                            # Центрируем заголовок
                            ft.Container(
                                content=ft.Text('Positions',
                                                size=32,
                                                weight=ft.FontWeight.W_600,
                                                color=self.cl.text_primary),
                                alignment=ft.alignment.center
                            ),
                            ft.Row(
                                controls=[
                                    ft.Column(
                                        controls=self.position_containers[:4],
                                        spacing=15,
                                        horizontal_alignment=ft.CrossAxisAlignment.CENTER
                                    ),
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
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=20
                    )
                )
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            alignment=ft.MainAxisAlignment.CENTER
        )
        # Третья колонка с изменением цен
        third_column = ft.Column(
            expand=2,
            controls=[
                ft.Container(
                    width=450,
                    height=900,
                    bgcolor=self.cl.secondary_bg,
                    border_radius=50,
                    padding=ft.padding.all(20),
                    content=ft.Column(
                        controls=[
                            ft.Container(
                                content=ft.Row(
                                    controls=[
                                        ft.Text('Change Price',
                                                size=32,
                                                weight=ft.FontWeight.W_600,
                                                color=self.cl.text_primary),
                                    ],
                                    alignment=ft.MainAxisAlignment.CENTER,
                                    spacing=10
                                ),
                                alignment=ft.alignment.center
                            ),
                            ft.Row(
                                controls=[
                                    ft.Column(
                                        controls=self.change_price_containers[:5],
                                        spacing=10,
                                        alignment=ft.MainAxisAlignment.CENTER,
                                        horizontal_alignment=ft.CrossAxisAlignment.CENTER
                                    ),
                                    ft.Column(
                                        controls=self.change_price_containers[5:],
                                        spacing=10,
                                        alignment=ft.MainAxisAlignment.CENTER,
                                        horizontal_alignment=ft.CrossAxisAlignment.CENTER
                                    ),
                                ],
                                alignment=ft.MainAxisAlignment.CENTER,
                                spacing=15,
                            ),
                        ],
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=15
                    )
                )
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            alignment=ft.MainAxisAlignment.CENTER
        )

        return ft.Row(
            expand=True,
            controls=[first_column, second_column, third_column],
        )

    def _update_container_with_data(self, index: int, position_data: Dict, last_price: str):
        """Обновляет контейнер с данными с проверкой TP/SL"""
        try:
            from utils.database_logic import TradingDB
            from utils.telegram_notifier import send_close_notification

            id = position_data.get('id')
            name = position_data.get('name')
            pos_type = position_data.get('pos_type')
            cross = position_data.get('cross')
            tp = position_data.get('take_profit')
            sl = position_data.get('stop_loss')
            percent = position_data.get('percent')
            entry_price = position_data.get('entry_price')
            is_active = position_data.get('is_active', True)
            close_reason = position_data.get('close_reason')

            # Работа с %
            balance_percent = 0
            if entry_price and last_price and cross and last_price != 'N/A':
                try:
                    entry = float(entry_price)
                    current = float(last_price)
                    leverage = float(cross)
                    if pos_type == 'short':
                        direction_multiplier = -1
                    else:
                        direction_multiplier = 1

                    price_change_pct = ((current - entry) / entry) * 100 * direction_multiplier

                    position_share = float(percent) / 100 if percent else 0.01
                    balance_percent = round(price_change_pct * leverage * position_share, 2)
                except Exception as e:
                    print(f"Ошибка расчёта: {e}")
                    balance_percent = 0

            # Проверяем TP/SL
            tp_hit = False
            sl_hit = False

            if is_active and last_price != 'N/A':
                try:
                    last_price_float = float(last_price)
                    tp_float = float(tp) if tp else None
                    sl_float = float(sl) if sl else None

                    if pos_type == "short":
                        tp_hit = tp_float and last_price_float <= tp_float
                        sl_hit = sl_float and last_price_float >= sl_float
                    else:  # long
                        tp_hit = tp_float and last_price_float >= tp_float
                        sl_hit = sl_float and last_price_float <= sl_float
                except Exception as e:
                    print(f"Ошибка проверки TP/SL: {e}")

            # Если сработал TP/SL - сохраняем в БД
            if is_active and (tp_hit or sl_hit):
                db = TradingDB()

                if tp_hit:
                    print(f'{id} - TP hit! Сохраняю в БД...')
                    new_close_reason = 'tp'

                else:
                    print(f'{id} - SL hit! Сохраняю в БД...')
                    new_close_reason = 'sl'

                # Сохраняем в БД
                try:
                    db.update_position(
                        position_id=id,
                        is_active=False,
                        close_reason=new_close_reason,
                        closed_at=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        final_pnl=balance_percent
                    )
                    print(f"✅ Позиция {id} сохранена в БД как неактивная")
                    is_active = False
                    close_reason = new_close_reason  # Обновляем причину закрытия

                    # Отправляем уведомление в Telegram
                    try:
                        close_data = {
                            'id': id,
                            'name': name,
                            'pos_type': pos_type,
                            'entry_price': entry_price,
                            'take_profit': tp,
                            'stop_loss': sl,
                            'close_reason': new_close_reason,
                            'final_pnl': balance_percent,
                            'closed_at': datetime.now().strftime('%m-%d %H:%M')
                        }
                        send_close_notification(close_data)
                        print(f"📢 Уведомление о закрытии {name} отправлено")
                    except Exception as e:
                        print(f"⚠️ Ошибка отправки уведомления: {e}")

                    # Уведомляем TradingBot о закрытии
                    if self.trading_bot and hasattr(self.trading_bot, 'remove_position'):
                        self.trading_bot.remove_position(id)

                except Exception as e:
                    print(f"❌ Ошибка сохранения в БД: {e}")

            # Определяем цвет и статус
            if not is_active:
                # Безопасная проверка close_reason
                if close_reason and 'tp' in str(close_reason).lower():
                    status = "TP HIT"
                    text_color = ft.Colors.GREEN_400
                elif close_reason and 'sl' in str(close_reason).lower():
                    status = "SL HIT"
                    text_color = ft.Colors.RED_400
                else:
                    status = "CLOSED"
                    text_color = ft.Colors.GREY_400
            else:
                if balance_percent > 0:
                    status = f"+{balance_percent}%"
                    text_color = ft.Colors.GREEN_400
                else:
                    status = f"{balance_percent}%"
                    text_color = ft.Colors.RED_400

            # Форматируем цены
            entry_display = str(entry_price) if entry_price else "N/A"
            current_display = last_price if last_price != 'N/A' else "N/A"
            tp_display = str(tp) if tp else "N/A"
            sl_display = str(sl) if sl else "N/A"

            # Работа с цветом для | pos_type
            type_color = ft.Colors.RED_400
            if pos_type.upper() == "LONG":
                type_color = ft.Colors.GREEN_400

            # Update container positions
            container_content = ft.Column(
                controls=[
                    ft.Text(f"ID: {id} | {name.upper()}", color=self.cl.text_primary, size=16,
                            weight=ft.FontWeight.W_600),
                    ft.Row(controls=[
                        ft.Text(f"{pos_type.upper()}", color=type_color, size=15, weight=ft.FontWeight.W_600),
                        ft.Text(f'| CROSS: {cross} | PERCENT: {percent}%', color=self.cl.text_primary,
                                size=15, weight=ft.FontWeight.W_600)
                    ], alignment=ft.MainAxisAlignment.CENTER),
                    ft.Text(f"Entry: {entry_display}$ | Current: {current_display}$", color=self.cl.text_primary,
                            size=14, weight=ft.FontWeight.W_600),
                    ft.Text(f"TP: {tp_display} | SL: {sl_display}", color=self.cl.text_primary, size=13,
                            weight=ft.FontWeight.W_600),
                    ft.Text(f"{status}", color=text_color, size=14, weight=ft.FontWeight.W_700),
                    ft.Row(controls=[
                        ft.ElevatedButton(
                            text='Bybit',
                            color=self.cl.text_primary,
                            width=70,
                            bgcolor=self.cl.secondary_bg,
                            on_click=lambda e: wbb.bybit_open(name)
                        ),
                        ft.ElevatedButton(
                            text='Binance',
                            color=self.cl.text_primary,
                            width=70,
                            bgcolor=self.cl.secondary_bg,
                            on_click=lambda e: wbb.binance_open(name)
                        ),
                        ft.ElevatedButton(
                            text='BingX',
                            color=self.cl.text_primary,
                            width=70,
                            bgcolor=self.cl.secondary_bg,
                            on_click=lambda e: wbb.binx_open(name)
                        ),
                        ft.ElevatedButton(
                            text='Mexc',
                            color=self.cl.text_primary,
                            width=70,
                            bgcolor=self.cl.secondary_bg,
                            on_click=lambda e: wbb.mexc_open(name)
                        )
                    ], alignment=ft.MainAxisAlignment.CENTER)
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=5
            )

            # Назначаем обработчик клика в зависимости от режима
            if self.delete_mode:
                self.position_containers[index].on_click = lambda e, idx=index: self._delete_selected_position(idx)
                # Добавляем визуальный индикатор режима удаления
                self.position_containers[index].border = ft.border.all(2, ft.Colors.RED_400)
            else:
                self.position_containers[index].on_click = None
                self.position_containers[index].bgcolor = self.cl.color_bg
                self.position_containers[index].border = None

            self.position_containers[index].content = container_content

        except Exception as e:
            print(f"❌ Ошибка обновления контейнера {index}: {e}")
            import traceback
            traceback.print_exc()
            self.position_containers[index].content = ft.Column(
                controls=[
                    ft.Text(f"Позиция {index + 1}", color=self.cl.text_secondary),
                    ft.Text('Ошибка загрузки', color=self.cl.text_secondary, size=12),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER
            )

    def _update_single_price_container(self, index: int, pair_data: Optional[Dict]):
        """Обновляет один контейнер с ценой"""
        container = self.change_price_containers[index]

        if not pair_data:
            # Нет данных - показываем заглушки
            container.content = ft.Column(
                controls=[
                    ft.Text(f'Монета {index + 1}',
                            color=self.cl.text_secondary,
                            size=14),
                    ft.Text('Нет данных',
                            color=self.cl.text_secondary,
                            size=12),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER
            )
            return

        try:
            symbol = pair_data.get('symbol', 'N/A')
            price_change = pair_data.get('price_change', 0)
            price_usdt = pair_data.get('price_usdt', 0)
            volume = pair_data.get('volume_usdt', 0)
            base_asset = pair_data.get('base_asset', '')
            last_updated = pair_data.get('last_updated', '--:--:--')

            # Форматируем объем (миллионы)
            volume_millions = volume / 1_000_000
            volume_text = f"{volume_millions:.1f}M" if volume_millions >= 1 else f"{volume:,.0f}"

            # Определяем цвет текста для процента
            text_color = ft.Colors.GREEN_400 if price_change > 0 else ft.Colors.RED_400

            # Знак процента
            change_sign = "+" if price_change > 0 else ""

            # Форматируем цену
            price_text = f"${price_usdt:.4f}"

            container.content = ft.Column(
                controls=[
                    ft.Text(
                        symbol,
                        size=24,
                        weight=ft.FontWeight.W_600,
                        color=self.cl.text_primary
                    ),
                    ft.Text(
                        f"{change_sign}{price_change:.2f}%",
                        size=20,
                        weight=ft.FontWeight.W_600,
                        color=text_color
                    ),
                    ft.Text(
                        price_text,
                        size=14,
                        weight=ft.FontWeight.W_600,
                        color=self.cl.text_primary
                    ),

                    # Объем
                    ft.Text(
                        f"Volume: {volume_text}",
                        size=13,
                        color=self.cl.text_secondary
                    ),

                    # Время обновления
                    ft.Text(
                        f" {last_updated}",
                        size=12,
                        color=self.cl.text_primary
                    )
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=2
            )
            container.on_click = lambda e: webbrowser.open(f'https://www.bybit.com/trade/usdt/{symbol}')

        except Exception as e:
            print(f"❌ Ошибка обновления контейнера {index}: {e}")
            container.content = ft.Column(
                controls=[
                    ft.Text(f'Ошибка', color=ft.Colors.RED, size=14),
                    ft.Text(str(e)[:30], color=self.cl.text_secondary, size=10),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER
            )

    # Функции
    def _get_prices_parallel(self, positions: List[Dict]) -> Dict[str, str]:
        """Получает цены для всех монет параллельно"""
        price_cache = {}
        unique_coins = list(set(pos.get('name') for pos in positions if pos.get('name')))

        if not unique_coins:
            return price_cache

        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            future_to_coin = {
                executor.submit(get_bybit_futures_price, coin): coin
                for coin in unique_coins
            }

            for future in concurrent.futures.as_completed(future_to_coin):
                coin = future_to_coin[future]
                try:
                    price_data = future.result()
                    if price_data['found']:
                        price_cache[coin] = price_data['last_price']
                    else:
                        price_cache[coin] = 'N/A'
                except:
                    price_cache[coin] = 'N/A'

        return price_cache

    def _load_parsing_change(self):
        from parsing.detected_24h_price import StakanScreener
        ss = StakanScreener()
        ss.get_usdt_pairs(15, 10)

    def create_new_position(self, e):
        """Создает новую позицию"""
        if not self.db:
            print("❌ БД не инициализирована")
            return

        try:
            name = self.name_coin.value.strip().upper()
            percent = int(self.percentage_balance.value)
            cross = int(self.cross.value)
            tp = float(self.take_profit.value.replace(',', '.')) if self.take_profit.value else 0
            sl = float(self.stop_loss.value.replace(',', '.')) if self.stop_loss.value else 0
            pos_type = self.type.value.strip().lower()

            # Получаем текущую цену
            price_data = get_bybit_futures_price(coin=name)
            if not price_data['found']:
                print(f"❌ Не удалось получить цену для {name}")
                return

            entry_price = float(price_data['last_price'])

            # Добавляем в БД
            position_id = self.db.add_to_db(name, percent, cross, entry_price, tp, sl, pos_type)
            print(f"✅ Позиция {name} добавлена в БД (ID: {position_id})")

            # Обновляем UI
            self._load_positions_from_db()

            # Очищаем поля
            self.name_coin.value = ''
            self.take_profit.value = ''
            self.stop_loss.value = ''

            if self.page:
                self.page.update()

        except Exception as ex:
            print(f"❌ Ошибка создания позиции: {ex}")

    def close_position(self, name):
        """Закрывает позицию и отправляет уведомление"""
        print(f"🔔 Закрытие позиции: {name}")

        try:
            from utils.telegram_notifier import send_close_notification

            if not self.db:
                print("❌ БД не инициализирована")
                return

            # Находим активную позицию по имени
            positions = self.db.get_all_positions(active_only=True)
            position_to_close = None

            for pos in positions:
                if pos.get('name') == name:
                    position_to_close = pos
                    break

            if not position_to_close:
                print(f"⚠️ Активная позиция {name} не найдена")
                return

            # Формируем данные для закрытия
            close_data = {
                'id': position_to_close.get('id'),
                'name': name,
                'pos_type': position_to_close.get('pos_type'),
                'entry_price': position_to_close.get('entry_price'),
                'take_profit': position_to_close.get('take_profit'),
                'stop_loss': position_to_close.get('stop_loss'),
                'close_reason': 'manual',  # или 'tp', 'sl' в зависимости от ситуации
                'final_pnl': 0,  # можно рассчитать
                'closed_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }

            # Отправляем уведомление
            send_close_notification(close_data)
            print(f"📢 Уведомление о закрытии {name} отправлено")

        except Exception as e:
            print(f"⚠️ Ошибка закрытия позиции: {e}")