
### Import libs
import flet as ft

import pages
### import func/my libs
from settings import *

### MAIN function
def main(page: ft.Page):
    #usage ws/cl
    ws = WindowSettings()
    cl = Colors()
    #import pages
    app_view = pages.AppWindow(page ,cl)
    app_bar = pages.AppBarTop(page, cl)

    #page settings
    page.window.height = ws.height
    page.window.width = ws.width
    page.padding = 0
    page.window.center()
    page.window.frameless = True
    page.bgcolor = cl.color_bg

    #page preview
    main_container = app_view.app_page
    top_appbar = app_bar.top_appbar

    page.add(
        ft.Column(
            expand=True,
            controls=[
                top_appbar,
                main_container
            ],  alignment=ft.MainAxisAlignment.START, horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=40
        )
    )


ft.app(main)