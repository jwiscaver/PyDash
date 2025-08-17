# menu_view.py
from pathlib import Path
import arcade
from settings import WIDTH, HEIGHT, TITLE, WHITE, GRAY

ASSETS_DIR = Path(__file__).parent / "assets"

class MenuView(arcade.View):
    def __init__(self):
        super().__init__()
        # Background (two scrolling sprites)
        self.bg_list = arcade.SpriteList()
        self.bg_tex = arcade.load_texture(str(ASSETS_DIR / "background.png"))
        scale = HEIGHT / self.bg_tex.height
        w = self.bg_tex.width * scale
        for i in range(2):
            s = arcade.Sprite(str(ASSETS_DIR / "background.png"), scale=scale)
            s.center_x = i * w + w / 2
            s.center_y = HEIGHT / 2
            self.bg_list.append(s)

        # Title text
        self.title_text = arcade.Text(TITLE, WIDTH/2, HEIGHT*0.62, WHITE, 36, anchor_x="center")
        self.sub_text = arcade.Text("Press ENTER to Play", WIDTH/2, HEIGHT*0.48, WHITE, 20, anchor_x="center")
        self.help_text = arcade.Text("SPACE/Click = Jump    ESC = Pause    R = Restart",
                                     WIDTH/2, HEIGHT*0.36, GRAY, 16, anchor_x="center")

    def on_show_view(self):
        pass  # no viewport call in Arcade 3.x

    def on_update(self, dt: float):
        # Slow background drift
        speed = 20.0
        dx = speed * dt
        for s in self.bg_list:
            s.center_x -= dx
        if self.bg_list:
            w = self.bg_list[0].width
            for s in self.bg_list:
                if s.right < 0:
                    s.left += w * 2

    def on_draw(self):
        self.clear()
        self.bg_list.draw()
        self.title_text.draw()
        self.sub_text.draw()
        self.help_text.draw()

    def on_key_press(self, symbol: int, modifiers: int):
        if symbol in (arcade.key.ENTER, arcade.key.RETURN):
            from game_view import GameView
            self.window.show_view(GameView(level_path=None))  # default level1
