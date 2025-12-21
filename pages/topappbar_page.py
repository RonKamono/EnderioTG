import flet as ft
from flet.core.types import MainAxisAlignment

import settings
import utils.window_functions

window_size = settings.WindowSettings()
functions = utils.window_functions.WindowFunctions()

class AppBarTop:
    def __init__(self, page, cl):
        self.page = page
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
                                ft.Container(ft.Icon(ft.Icons.TELEGRAM, color=cl.text_primary)),
                            ], alignment=MainAxisAlignment.START, expand=1),
                            ft.Row(controls=[
                                ft.Container(ft.Text('Telegram Signal', weight=ft.FontWeight.W_600, size=24,
                                                     color=cl.text_primary))
                            ],alignment=MainAxisAlignment.CENTER, expand=1),
                            ft.Row(controls=[
                                ft.Container(
                                    ft.IconButton(icon=ft.Icons.SETTINGS,
                                                  icon_size=24,
                                                  hover_color=cl.secondary_bg,
                                                  icon_color=cl.text_primary,
                                                  on_click=lambda e: None)
                                ),
                                ft.Container(
                                    ft.IconButton(icon=ft.Icons.CLOSE_ROUNDED,
                                                  icon_size=24,
                                                  hover_color=cl.secondary_bg,
                                                  icon_color=cl.text_primary,
                                                  on_click=lambda e: functions.close_window(e))
                                )
                            ],expand=1, alignment=MainAxisAlignment.END)
                        ], alignment=MainAxisAlignment.CENTER
                    )
                ), expand=True, maximizable= False
            )
        ]
    )