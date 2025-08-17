# pause_view.py
import arcade
from settings import WIDTH, HEIGHT, WHITE, GRAY

class PauseView(arcade.View):
    def __init__(self, game_view: arcade.View):
        super().__init__()
        self.game_view = game_view
        self.title = arcade.Text("Paused", WIDTH/2, HEIGHT/2 + 30, WHITE, 28, anchor_x="center")
        self.hint = arcade.Text("ESC = Resume    M = Menu", WIDTH/2, HEIGHT/2 - 10, GRAY, 16, anchor_x="center")

    def on_draw(self):
        # Draw game behind dim overlay
        self.game_view.on_draw()
        # overlay
        arcade.draw_rectangle_filled(WIDTH/2, HEIGHT/2, WIDTH, HEIGHT, (0,0,0,140))
        self.title.draw()
        self.hint.draw()

    def on_key_press(self, symbol: int, modifiers: int):
        if symbol == arcade.key.ESCAPE:
            self.window.show_view(self.game_view)
        elif symbol in (arcade.key.M,):
            from menu_view import MenuView
            self.window.show_view(MenuView())
