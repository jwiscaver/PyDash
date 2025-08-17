# menu_view.py
import arcade
from settings import WIDTH, HEIGHT, TITLE, WHITE, GRAY
from game_view import GameView

class MenuView(arcade.View):
    def __init__(self):
        super().__init__()
        self.title_text = arcade.Text(TITLE, WIDTH/2, HEIGHT*0.62, WHITE, 36, anchor_x="center")
        self.sub_text = arcade.Text("Press ENTER to Play", WIDTH/2, HEIGHT*0.48, WHITE, 20, anchor_x="center")
        self.help_text = arcade.Text("SPACE/Click = Jump    ESC = Pause    R = Restart",
                                     WIDTH/2, HEIGHT*0.36, GRAY, 16, anchor_x="center")

    def on_show_view(self):
         arcade.set_background_color(arcade.color.BLACK)

    def on_draw(self):
        self.clear()
        self.title_text.draw()
        self.sub_text.draw()
        self.help_text.draw()

    def on_key_press(self, symbol: int, modifiers: int):
        if symbol in (arcade.key.ENTER, arcade.key.RETURN):
            self.window.show_view(GameView(level_path=None))  # default level1
