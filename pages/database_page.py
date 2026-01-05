import flet as ft
import os
import asyncio

class DatabasePage:
    def __init__(self, page, cl, trading_bot=None):
        self.page = page
        self.cl = cl
        self.trading_bot = trading_bot
        self.db = None

        self.app_page = self._build_app_view()

    def _build_app_view(self):

        first_column = ft.Column(
            controls=[
                ft.Container(
                    width=450,
                    height=900,
                    bgcolor=self.cl.secondary_bg,
                    border_radius=50,
                    padding=ft.padding.all(20),
                    content=ft.Column(
                        controls=[
                            ft.Text(
                                'Text'
                            )
                        ]
                    )
                )
            ], alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.CENTER
        )

        second_column = ft.Column(
            controls=[
                ft.Container(
                    width=600,
                    height=900,
                    bgcolor=self.cl.secondary_bg,
                    border_radius=50,
                    padding=ft.padding.all(20),
                    content=ft.Column(
                        controls=[
                            ft.Text(
                                'Text'
                            )
                        ]
                    )
                )
            ], alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.CENTER
        )

        third_column = ft.Column(
            controls=[
                ft.Container(
                    width=450,
                    height=900,
                    bgcolor=self.cl.secondary_bg,
                    border_radius=50,
                    padding=ft.padding.all(20),
                    content=ft.Column(
                        controls=[
                            ft.Text(
                                'Text'
                            )
                        ]
                    )
                )
            ], alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.CENTER
        )

        return ft.Row(
            expand=True,
            controls=[ft.Container(
                expand=True,
                padding=ft.padding.all(20),
                content = ft.Row(
                   controls=[
                       first_column, second_column, third_column
                   ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN, spacing=50
                )
            )],
        alignment=ft.MainAxisAlignment.CENTER, vertical_alignment=ft.CrossAxisAlignment.CENTER,
        spacing=50,
        )