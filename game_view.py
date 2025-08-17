# game_view.py
from __future__ import annotations
import random
from pathlib import Path
import arcade

from settings import (
    WIDTH, HEIGHT, TITLE,
    DEFAULT_SCROLL_SPEED, FLOOR_Y, PLAYER_SIZE, PLAYER_X,
    GRAVITY, JUMP_VEL, COYOTE_TIME, JUMP_BUFFER,
    BG, GROUND, PLAYER_COLOR, OBST, PARA_BACK, PARA_MID,
    WHITE, PINK, GRAY, GOLD, COIN_SIZE
)
from level_loader import load_level
from pause_view import PauseView

SPAWN_START = WIDTH + 80
OB_H = 36

class GameView(arcade.View):
    def __init__(self, level_path: str | None = None):
        super().__init__()
        self.level_path = level_path or (Path(__file__).parent / "level" / "level1.json")
        self.scroll_speed = DEFAULT_SCROLL_SPEED

        # Sprite containers
        self.ground_list = arcade.SpriteList(use_spatial_hash=True)
        self.obstacles = arcade.SpriteList(use_spatial_hash=True)
        self.player_list = arcade.SpriteList(use_spatial_hash=False)

        # NEW: coins & portals
        self.coins = arcade.SpriteList(use_spatial_hash=True)
        self.portals = arcade.SpriteList(use_spatial_hash=True)

        # Parallax strips (dicts with left/bottom/w/h/color)
        self.parallax_back = []
        self.parallax_mid = []

        # Player + physics
        self.player: arcade.SpriteSolidColor | None = None
        self.vel_y = 0.0
        self.on_ground = False
        self.coyote_timer = 0.0
        self.jump_buffer_timer = 0.0

        # Game state
        self.alive = True
        self.time_alive = 0.0
        self.next_spawn_x = SPAWN_START
        self.score = 0                     # NEW: score includes coins

        # Text
        self.score_text = arcade.Text("", 16, HEIGHT - 36, WHITE, 18)
        self.dead_text = arcade.Text("You Died  -  Press R to Restart",
                                     WIDTH / 2, HEIGHT / 2 + 40, PINK, 28, anchor_x="center")
        self.help_text = arcade.Text("SPACE/Click = Jump   ESC = Pause   M = Menu",
                                     WIDTH / 2, HEIGHT / 2 - 6, GRAY, 18, anchor_x="center")

        # Level data
        self.level_data = None
        self.obstacle_plan = []  # list of (gap, width)
        self.coin_plan = []      # list of (x, y)
        self.portal_plan = []    # list of (x, speed)

        self.setup()

    def on_show_view(self):
        # Arcade 3.x: no viewport setting needed
        pass

    def setup(self):
        # Load level JSON
        self.level_data = load_level(self.level_path)
        self.scroll_speed = float(self.level_data.get("scroll_speed", DEFAULT_SCROLL_SPEED))
        floor_y = int(self.level_data.get("floor_y", FLOOR_Y))
        player_x = int(self.level_data.get("player_x", PLAYER_X))

        # Obstacles -> (gap, width)
        self.obstacle_plan = []
        default_w = int(self.level_data.get("default_obstacle_width", 30))
        for item in self.level_data["obstacles"]:
            if isinstance(item, dict):
                gap = int(item.get("gap", 240)); w = int(item.get("width", default_w))
            else:
                gap = int(item); w = default_w
            self.obstacle_plan.append((gap, w))

        # NEW: coins & portals
        self.coin_plan = []
        for c in self.level_data.get("coins", []):
            self.coin_plan.append((int(c["x"]), int(c["y"])))
        self.portal_plan = []
        for p in self.level_data.get("speed_portals", []):
            self.portal_plan.append((int(p["x"]), float(p["speed"])))

        # Reset world
        self.ground_list = arcade.SpriteList(use_spatial_hash=True)
        self.obstacles = arcade.SpriteList(use_spatial_hash=True)
        self.player_list = arcade.SpriteList(use_spatial_hash=False)
        self.coins = arcade.SpriteList(use_spatial_hash=True)
        self.portals = arcade.SpriteList(use_spatial_hash=True)
        self.parallax_back = []
        self.parallax_mid = []

        # Ground
        ground_h = 40
        ground = arcade.SpriteSolidColor(WIDTH * 4, ground_h, GROUND)
        ground.center_x = WIDTH * 2
        ground.center_y = floor_y - ground_h / 2
        self.ground_list.append(ground)

        # Player
        self.player = arcade.SpriteSolidColor(PLAYER_SIZE, PLAYER_SIZE, PLAYER_COLOR)
        self.player.center_x = player_x + PLAYER_SIZE / 2
        self.player.center_y = floor_y + PLAYER_SIZE / 2
        self.player_list.append(self.player)

        # State
        self.vel_y = 0.0
        self.on_ground = True
        self.coyote_timer = 0.0
        self.jump_buffer_timer = 0.0
        self.alive = True
        self.time_alive = 0.0
        self.score = 0

        # Parallax strips
        self._build_parallax(floor_y)

        # Obstacles from plan
        self.obstacles.clear()
        x = SPAWN_START
        for gap, w in self.obstacle_plan:
            self._create_obstacle(x, w, floor_y)
            x += gap
        self.next_spawn_x = x

        # NEW: build coins & portals (as sprites that scroll left)
        for cx, cy in self.coin_plan:
            s = arcade.SpriteSolidColor(COIN_SIZE//2, COIN_SIZE//2, (0, 0, 0, 0))  # invisible hitbox
            s.center_x = cx
            s.center_y = cy
            self.coins.append(s)

        for px, spd in self.portal_plan:
            # thin, tall invisible trigger the player collides with
            trig = arcade.SpriteSolidColor(8, int(PLAYER_SIZE*2), (0, 0, 0, 0))
            trig.center_x = px
            trig.center_y = floor_y + PLAYER_SIZE
            trig.properties = {"speed": spd}
            self.portals.append(trig)

    def _build_parallax(self, floor_y: int):
        # Back layer
        h = 110
        bottom_back = floor_y + 20 - h / 2
        for i in range(3):
            left = i * WIDTH
            self.parallax_back.append({"left": left, "bottom": bottom_back, "w": WIDTH, "h": h, "color": PARA_BACK})
        # Mid layer
        h2 = 70
        bottom_mid = floor_y + 10 - h2 / 2
        for i in range(3):
            left = i * WIDTH
            self.parallax_mid.append({"left": left, "bottom": bottom_mid, "w": WIDTH, "h": h2, "color": PARA_MID})

    def _create_obstacle(self, x, w, floor_y):
        ob = arcade.SpriteSolidColor(w, OB_H, OBST)
        ob.center_x = x + w / 2
        ob.center_y = floor_y + OB_H / 2
        self.obstacles.append(ob)

    # -------------- Input --------------
    def _queue_jump(self):
        if not self.alive:
            return
        self.jump_buffer_timer = JUMP_BUFFER
        if self.on_ground or self.coyote_timer > 0.0:
            self._do_jump()

    def _do_jump(self):
        self.vel_y = JUMP_VEL
        self.on_ground = False
        self.coyote_timer = 0.0
        self.jump_buffer_timer = 0.0

    def on_key_press(self, symbol: int, modifiers: int):
        if symbol in (arcade.key.SPACE, arcade.key.UP):
            self._queue_jump()
        elif symbol == arcade.key.R:
            self.setup()
        elif symbol == arcade.key.ESCAPE:
            self.window.show_view(PauseView(self))
        elif symbol in (arcade.key.M,):
            from menu_view import MenuView
            self.window.show_view(MenuView())

    def on_mouse_press(self, x: float, y: float, button: int, modifiers: int):
        self._queue_jump()

    # -------------- Update --------------
    def on_update(self, dt: float):
        if not self.alive:
            return

        self.time_alive += dt

        # Parallax scroll
        self._scroll_parallax(dt)

        # Scroll world left
        dx = self.scroll_speed * dt
        for s in self.ground_list:
            s.center_x -= dx
        for s in self.obstacles:
            s.center_x -= dx
        for s in self.coins:
            s.center_x -= dx
        for s in self.portals:
            s.center_x -= dx

        # Extend ground forward
        ground = self.ground_list[0]
        if ground.right < WIDTH * 2:
            ground.width += int(WIDTH)

        # Prune far-left sprites
        for lst in (self.obstacles, self.coins, self.portals):
            for s in list(lst):
                if s.right < -200:
                    s.remove_from_sprite_lists()

        # Gravity and vertical motion
        self.vel_y -= GRAVITY * dt
        self.player.center_y += self.vel_y * dt

        # Ground collision (clamp)
        self.on_ground = False
        hits = arcade.check_for_collision_with_list(self.player, self.ground_list)
        if hits and self.vel_y <= 0:
            top = max(h.top for h in hits)
            self.player.center_y = top + PLAYER_SIZE / 2
            self.vel_y = 0.0
            self.on_ground = True

        # Coyote / buffer
        if self.on_ground:
            self.coyote_timer = COYOTE_TIME
        else:
            self.coyote_timer = max(0.0, self.coyote_timer - dt)

        if self.jump_buffer_timer > 0.0:
            if self.on_ground or self.coyote_timer > 0.0:
                self._do_jump()
            else:
                self.jump_buffer_timer -= dt

        # Coin pickups (remove & score)
        for coin in arcade.check_for_collision_with_list(self.player, self.coins):
            coin.remove_from_sprite_lists()
            self.score += 10

        # Speed portals (touch to change speed)
        for portal in arcade.check_for_collision_with_list(self.player, self.portals):
            new_speed = float(getattr(portal, "properties", {}).get("speed", self.scroll_speed))
            self.scroll_speed = new_speed
            portal.remove_from_sprite_lists()

        # Death
        if arcade.check_for_collision_with_list(self.player, self.obstacles) or self.player.center_y < -200:
            self.alive = False

    def _scroll_parallax(self, dt: float):
        move1 = 60.0 * dt
        for strip in self.parallax_back:
            strip["left"] -= move1
            if strip["left"] + strip["w"] < 0:
                strip["left"] += WIDTH * 3
        move2 = 120.0 * dt
        for strip in self.parallax_mid:
            strip["left"] -= move2
            if strip["left"] + strip["w"] < 0:
                strip["left"] += WIDTH * 3

    # -------------- Draw --------------
    def on_draw(self):
        self.clear()

        # Parallax
        for strip in self.parallax_back:
            arcade.draw_lbwh_rectangle_filled(strip["left"], strip["bottom"], strip["w"], strip["h"], strip["color"])
        for strip in self.parallax_mid:
            arcade.draw_lbwh_rectangle_filled(strip["left"], strip["bottom"], strip["w"], strip["h"], strip["color"])

        # World & obstacles
        self.ground_list.draw()
        self.obstacles.draw()

        # NEW: draw spikes visually as triangles sitting on each obstacle
        for ob in self.obstacles:
            left = ob.left
            right = ob.right
            top = ob.top
            bottom = ob.bottom
            # triangle base spans the top of the block, pointing upward
            mid_x = (left + right) / 2
            arcade.draw_triangle_filled(left, top, right, top, mid_x, top + OB_H * 0.9, OBST)

        # Player & coins
        self.player_list.draw()

        # Draw coins as circles at their sprite centers
        for c in self.coins:
            arcade.draw_circle_filled(c.center_x, c.center_y, COIN_SIZE / 2, GOLD)
            arcade.draw_circle_outline(c.center_x, c.center_y, COIN_SIZE / 2, (255, 255, 255, 180), 2)

        # UI
        live_score = int(self.time_alive * 10) + self.score
        self.score_text.text = f"Score: {live_score}"
        self.score_text.draw()
        if not self.alive:
            self.dead_text.draw()
            self.help_text.draw()
