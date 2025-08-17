import arcade
W, H = 800, 600
class App(arcade.Window):
    def __init__(self):
        super().__init__(W, H, "Hello Arcade"); arcade.set_background_color((135,206,235))
    def on_draw(self):
        arcade.start_render(); arcade.draw_text("Hello, Arcade!", 280, 300, (0,0,0), 24)
App(); arcade.run()

