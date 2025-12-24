import flet as ft
from flet.core.types import MainAxisAlignment

import settings
import utils.window_functions

window_size = settings.WindowSettings()
functions = utils.window_functions.WindowFunctions()


class AppBarTop:
    def __init__(self, page, cl):
        self.page = page
        self.cl = cl
        self.top_appbar = ft.Row(
            [
                ft.WindowDragArea(
                    ft.Container(
                        bgcolor=cl.secondary_bg,
                        width=window_size.width,
                        height=50,
                        padding=ft.padding.symmetric(0, 10),
                        content=ft.Row(
                            expand=True,
                            controls=[
                                ft.Row(controls=[
                                    ft.Container(ft.Icon(ft.Icons.TERMINAL, color=cl.text_primary, size=40)),
                                ], alignment=MainAxisAlignment.START, expand=1),
                                ft.Row(controls=[
                                    ft.Container(ft.Text('Trade Panel v0.1', weight=ft.FontWeight.W_600, size=36,
                                                         color=cl.text_primary))
                                ], alignment=MainAxisAlignment.CENTER, expand=1),
                                ft.Row(controls=[
                                    ft.Container(
                                        ft.IconButton(icon=ft.Icons.TELEGRAM,
                                                      icon_size=24,
                                                      hover_color=cl.secondary_bg,
                                                      icon_color=cl.text_primary,
                                                      on_click=lambda e: self._open_settings(e))
                                    ),
                                    ft.Container(
                                        ft.IconButton(icon=ft.Icons.SETTINGS,
                                                      icon_size=24,
                                                      hover_color=cl.secondary_bg,
                                                      icon_color=cl.text_primary,
                                                      on_click=lambda e: self._open_settings(e))
                                    ),
                                    ft.Container(
                                        ft.IconButton(icon=ft.Icons.CLOSE_ROUNDED,
                                                      icon_size=24,
                                                      hover_color=cl.secondary_bg,
                                                      icon_color=cl.text_primary,
                                                      on_click=lambda e: functions.close_window(e))
                                    )
                                ], expand=1, alignment=MainAxisAlignment.END)
                            ], alignment=MainAxisAlignment.CENTER
                        )
                    ), expand=True, maximizable=False
                )
            ]
        )

    # Create elements TEXTFIELD
    def _create_text_field(self, **kwargs):
        defaults = {
            'height': 50,
            'width': 350,
            'value': '',
            'bgcolor': self.cl.color_bg,
            'border_radius': 20,
            'cursor_color': self.cl.text_primary,
            'focused_border_color': self.cl.text_primary,
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
        """Создает текстовые поля с загрузкой значений из реестра"""
        try:
            from utils import config

            bot_token = config.TELEGRAM_BOT_TOKEN
            self.bot_token = self._create_text_field(
                value=bot_token if bot_token else "",
                hint_text="Введите токен бота от @BotFather",
                password=True,
                can_reveal_password=True
            )

            # Загружаем ID администраторов из реестра
            admin_ids = config.ADMIN_IDS
            if admin_ids:
                # Если это список, преобразуем в строку через запятую
                if isinstance(admin_ids, list):
                    admin_ids_str = ','.join(str(id) for id in admin_ids)
                else:
                    admin_ids_str = str(admin_ids)
            else:
                admin_ids_str = ""

            self.admin_id = self._create_text_field(
                value=admin_ids_str,
                hint_text="Введите ID администраторов (через запятую)"
            )

        except ImportError:
            print("⚠️ Не удалось загрузить настройки из реестра")
            # Создаем пустые поля
            self.bot_token = self._create_text_field(
                value="",
                hint_text="Введите токен бота",
                password=True,
                can_reveal_password=True
            )
            self.admin_id = self._create_text_field(
                value="",
                hint_text="Введите ID администраторов"
            )

    # Create elements Container
    def _create_container(self, name, text_field_name):
        return ft.Container(
            width=400,
            height=120,
            border_radius=30,
            bgcolor=self.cl.secondary_bg,
            padding=ft.padding.all(10),
            content=ft.Column(
                controls=[
                    ft.Text(f'{name}', size=20, weight=ft.FontWeight.W_600, color=self.cl.text_primary),
                    text_field_name
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=10
            )
        )

    def _create_containers(self):
        self.bot_token_container = self._create_container('TOKEN BOT', self.bot_token)
        self.admin_id_container = self._create_container('ID ADMIN', self.admin_id)


    # Open settings
    def _open_settings(self, e):
        """Открывает диалог настроек"""
        self._create_text_fields()
        self._create_containers()

        self.dlg = ft.AlertDialog(
            bgcolor=self.cl.color_bg,
            content=ft.Container(
                width=400,
                height=450,
                bgcolor=self.cl.color_bg,
                content=ft.Column(
                    controls=[
                        # Заголовок
                        ft.Container(
                            width=400,
                            height=60,
                            border_radius=30,
                            bgcolor=self.cl.secondary_bg,
                            content=ft.Row(
                                controls=[
                                    ft.Text('Settings', size=32, weight=ft.FontWeight.W_600,
                                            color=self.cl.text_primary),
                                ],
                                alignment=ft.MainAxisAlignment.CENTER,
                                vertical_alignment=ft.CrossAxisAlignment.CENTER
                            )
                        ),
                        # Текстовые поля
                        ft.Column(
                            controls=[
                                self.bot_token_container,
                                self.admin_id_container,
                            ],
                            spacing=10,
                            horizontal_alignment=ft.CrossAxisAlignment.CENTER
                        ),

                        # Кнопки
                        ft.Row(
                            controls=[
                                ft.Container(
                                    width=180,
                                    height=50,
                                    border_radius=30,
                                    bgcolor=self.cl.secondary_bg,
                                    content=ft.ElevatedButton(
                                        bgcolor=self.cl.secondary_bg,
                                        text="Save settings",
                                        color=self.cl.text_primary,
                                        on_click=self._save_settings
                                    )
                                ),
                                ft.Container(
                                    width=180,
                                    height=50,
                                    border_radius=30,
                                    bgcolor=self.cl.secondary_bg,
                                    content=ft.ElevatedButton(
                                        bgcolor=self.cl.secondary_bg,
                                        text="Close",
                                        color=self.cl.text_primary,
                                        on_click=lambda e: self.page.close(self.dlg)
                                    )
                                )
                            ],
                            alignment=ft.MainAxisAlignment.SPACE_EVENLY
                        )
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    spacing=15
                )
            ),
            alignment=ft.alignment.center,
        )

        self.page.open(self.dlg)

    # Save settings
    def _save_settings(self, e):
        """Сохраняет настройки в реестр"""
        try:
            from utils import config

            # Получаем значения из полей
            new_bot_token = self.bot_token.value.strip()
            new_admin_ids_str = self.admin_id.value.strip()

            # Валидация токена
            if not new_bot_token:
                print("⚠️ Токен бота не указан")
                return

            # Проверяем формат токена (примерная проверка)
            if ':' not in new_bot_token:
                print("⚠️ Неверный формат токена бота")
                return

            # Обрабатываем ID администраторов
            new_admin_ids = []
            if new_admin_ids_str:
                try:
                    # Разделяем по запятой, убираем пробелы
                    id_strings = [id_str.strip() for id_str in new_admin_ids_str.split(',') if id_str.strip()]
                    # Конвертируем в целые числа
                    new_admin_ids = [int(id_str) for id_str in id_strings]
                    print(f"✅ ID администраторов преобразованы: {new_admin_ids}")
                except ValueError as e:
                    print(f"❌ Ошибка преобразования ID: {e}")
                    return

            if not new_admin_ids:
                print("⚠️ ID администраторов не указаны")

            # Сохраняем в реестр
            success_token = config.update_setting('telegram_bot_token', new_bot_token)
            success_ids = config.update_setting('admin_ids', new_admin_ids)

            if success_token and success_ids:
                print("✅ Настройки успешно сохранены в реестре")
                print(f"   Токен: {new_bot_token[:10]}...")
                print(f"   Админы: {new_admin_ids}")

                # Закрываем диалог
                self.page.close(self.dlg)

                # Перезагружаем страницу для применения настроек
                self.page.update()
            else:
                print("❌ Не удалось сохранить настройки в реестре")

        except Exception as ex:
            print(f"❌ Ошибка сохранения настроек: {ex}")
            import traceback
            traceback.print_exc()