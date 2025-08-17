# main.py
import arcade
from settings import WIDTH, HEIGHT, BG, TITLE
from menu_view import MenuView

def main():
    window = arcade.Window(WIDTH, HEIGHT, TITLE, resizable=False)
    arcade.set_background_color(BG)
    window.show_view(MenuView())
    arcade.run()

if __name__ == "__main__":
    main()
