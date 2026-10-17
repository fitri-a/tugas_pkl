import logging
import flet as ft
from app.config import APP_NAME, COLORS, WINDOW_WIDTH, WINDOW_HEIGHT
from app.config import LOG_PATH
from app.database.migrations import run_migrations
from app.views.app_shell import AppShell


def main(page: ft.Page):
    run_migrations()
    page.title = APP_NAME
    page.window.width = WINDOW_WIDTH
    page.window.height = WINDOW_HEIGHT
    page.bgcolor = COLORS['surface']
    page.padding = 0
    page.theme_mode = ft.ThemeMode.LIGHT
    page.add(AppShell(page).build())


if __name__ == '__main__':
    logging.basicConfig(filename=LOG_PATH, level=logging.INFO, format='%(asctime)s %(levelname)s %(name)s: %(message)s')
    ft.app(target=main)
