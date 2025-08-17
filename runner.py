# runner.py
# Geometry-Dash style starter for Arcade 3.x (Linux-friendly)
#
# Controls:
#   SPACE / UP / Left Mouse  -> Jump
#   R                         -> Restart
#
# Requires: pip install arcade

import random
import arcade

# -----------------------------
# Tunables
# -----------------------------
WIDTH, HEIGHT = 960, 540
TITLE = "Arcade Runner Starter"

GRAVITY = 1800.0           # px/s^2 downward
JUMP_VEL = 820.0           # px/s upward
SCROLL_SPEED = 360.0       # px/s world scroll left
FLOOR_Y = 120              # y of the floor surface
PLAYER_SIZE = 48           # player square size
PLAYER_X = 220             # fixed x for the player
SPAWN_X = WIDTH + 80       # where obstacles begin spawning

# Input forgiveness
COYOTE_TIME = 0.08         # seconds allowed to jump after leaving ground
JUMP_BUFFER = 0.10         # seconds to buffer a jump press before grounded

# Obstacle sizes and spacing
OB_MIN_W, OB_MAX_W = 26, 42
OB_H = 36
GAP_MIN, GAP_MAX = 180, 340

# Parallax speeds
PARALLAX1_SPEED = 60.0
PARALLAX2_SPEED = 120.0

# Colors (RGBA)
BG = (22, 22, 28, 255)
GROUND = (90, 90, 110, 255)
PLAYER_COLOR = (120, 220, 255, 255)
OBST = (230, 70, 70, 255)
PARA_BACK = (40, 40, 64, 255)
PARA_MID = (58, 58, 86, 255)
WHITE = (220, 220, 220, 255)
PINK = (255, 220, 220, 255)
GRAY = (210, 210, 210, 255)


class Runner(arcade.Window):
    def __init__(self):
        super().__init__(WIDTH, HEIGHT, TITLE, resizable=False)
        arcade.set_background_color(BG)

        # Sprite containers
        self.ground_list = arcade.SpriteList(use_spatial_hash=True)
        self.obstacles = arcade.SpriteList(use_spatial_hash=True)
        self.player_list = arcade.SpriteList(use_spatial_hash=False)

        # Parallax layers (lists of dicts with left/bottom/width/height/color)
        self.parallax_back = []
        self.parallax_mid = []

        # Player sprite/state
        self.player: arcade.SpriteSolidColor | None = None
        self.vel_y = 0.0
        self.on_ground = False
        self.coyote_timer = 0.0
        self.jump_buffer_timer = 0.0

        # Game state
        self.alive = True
        self.time_alive = 0.0
        self.next_spawn_x = SPAWN_X

        # Text objects (fast in Arcade 3.x)
        self.score_text = arcade.Text("", 16, HEIGHT - 36, WHITE, 18)
        self.dead_text = arcade.Text("You Died  -  Press R to Restart",
                                     WIDTH / 2, HEIGHT / 2 + 40, PINK, 28, anchor_x="center")
        self.help_text = arcade.Text("SPACE/Click = Jump",
                                     WIDTH / 2, HEIGHT / 2 - 6, GRAY, 18, anchor_x="center")

        self.setup()

    # -----------------------------
    # Game setup / reset
    # -----------------------------
    def setup(self):
        self.ground_list = arcade.SpriteList(use_spatial_hash=True)
        self.obstacles = arcade.SpriteList(use_spatial_hash=True)
        self.player_list = arcade.SpriteList(use_spatial_hash=False)
        self.parallax_back = []
        self.parallax_mid = []

        # Ground: one very wide strip under the player (top at FLOOR_Y)
        ground_h = 40
        ground = arcade.SpriteSolidColor(WIDTH * 4, ground_h, GROUND)
        ground.center_x = WIDTH * 2
        ground.center_y = FLOOR_Y - ground_h / 2
        self.ground_list.append(ground)

        # Player (placed by centers)
        self.player = arcade.SpriteSolidColor(PLAYER_SIZE, PLAYER_SIZE, PLAYER_COLOR)
        self.player.center_x = PLAYER_X + PLAYER_SIZE / 2
        self.player.center_y = FLOOR_Y + PLAYER_SIZE / 2
        self.player_list.append(self.player)

        self.vel_y = 0.0
        self.on_ground = True
        self.coyote_timer = 0.0
        self.jump_buffer_timer = 0.0

        # Parallax strips
        self._build_parallax()

        # Obstacles
        self.obstacles.clear()
        self._spawn_initial_pack()

        # Game flags
        self.alive = True
        self.time_alive = 0.0

    def _build_parallax(self):
        # Back layer: 3 wide bars that cycle (center-y at FLOOR_Y+20, height h)
        h = 110
        bottom_back = FLOOR_Y + 20 - h / 2
        for i in range(3):
            left = i * WIDTH
            self.parallax_back.append(
                {"left": left, "bottom": bottom_back, "w": WIDTH, "h": h, "color": PARA_BACK}
            )
        # Mid layer: 3 bars closer to the floor (center-y at FLOOR_Y+10, height h2)
        h2 = 70
        bottom_mid = FLOOR_Y + 10 - h2 / 2
        for i in range(3):
            left = i * WIDTH
            self.parallax_mid.append(
                {"left": left, "bottom": bottom_mid, "w": WIDTH, "h": h2, "color": PARA_MID}
            )

    def _spawn_initial_pack(self):
        """Create a row of obstacles starting off-screen to the right."""
        x = SPAWN_X
        for _ in range(8):
            w = random.randint(OB_MIN_W, OB_MAX_W)
            self._create_obstacle(x, w)
            x += random.randint(GAP_MIN, GAP_MAX)
        self.next_spawn_x = x

    def _create_obstacle(self, x, w):
        ob = arcade.SpriteSolidColor(w, OB_H, OBST)
        ob.center_x = x + w / 2
        ob.center_y = FLOOR_Y + OB_H / 2   # so its bottom sits on FLOOR_Y
        self.obstacles.append(ob)

    # -----------------------------
    # Input
    # -----------------------------
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

    def on_mouse_press(self, x: float, y: float, button: int, modifiers: int):
        self._queue_jump()

    # -----------------------------
    # Update
    # -----------------------------
    def on_update(self, dt: float):
        if not self.alive:
            return

        # Score
        self.time_alive += dt

        # Parallax motion
        self._scroll_parallax(dt)

        # Scroll world left
        dx = SCROLL_SPEED * dt
        for s in self.ground_list:
            s.center_x -= dx
        for s in self.obstacles:
            s.center_x -= dx

        # Keep a long ground ahead
        ground = self.ground_list[0]
        if ground.right < WIDTH * 2:
            ground.width += int(WIDTH)

        # Spawn new obstacles as needed
        while self.next_spawn_x - dx < SPAWN_X:
            w = random.randint(OB_MIN_W, OB_MAX_W)
            self._create_obstacle(self.next_spawn_x, w)
            self.next_spawn_x += random.randint(GAP_MIN, GAP_MAX)

        # Prune obstacles off-screen
        for s in list(self.obstacles):
            if s.right < -200:
                s.remove_from_sprite_lists()

        # Gravity & vertical motion
        self.vel_y -= GRAVITY * dt
        self.player.center_y += self.vel_y * dt

        # Ground collision (simple clamp)
        self.on_ground = False
        hits = arcade.check_for_collision_with_list(self.player, self.ground_list)
        if hits and self.vel_y <= 0:
            top = max(h.top for h in hits)
            self.player.center_y = top + PLAYER_SIZE / 2
            self.vel_y = 0.0
            self.on_ground = True

        # Coyote time & jump buffer
        if self.on_ground:
            self.coyote_timer = COYOTE_TIME
        else:
            self.coyote_timer = max(0.0, self.coyote_timer - dt)

        if self.jump_buffer_timer > 0.0:
            if self.on_ground or self.coyote_timer > 0.0:
                self._do_jump()
            else:
                self.jump_buffer_timer -= dt

        # Death on obstacle collision or falling
        if arcade.check_for_collision_with_list(self.player, self.obstacles) or self.player.center_y < -200:
            self.alive = False

    def _scroll_parallax(self, dt: float):
        # Move left and wrap when fully off-screen
        move1 = PARALLAX1_SPEED * dt
        for strip in self.parallax_back:
            strip["left"] -= move1
            if strip["left"] + strip["w"] < 0:
                strip["left"] += WIDTH * 3

        move2 = PARALLAX2_SPEED * dt
        for strip in self.parallax_mid:
            strip["left"] -= move2
            if strip["left"] + strip["w"] < 0:
                strip["left"] += WIDTH * 3

    # -----------------------------
    # Draw
    # -----------------------------
    def on_draw(self):
        # Arcade 3.x: use clear(), not start_render()
        self.clear()

        # Parallax
        for strip in self.parallax_back:
            arcade.draw_lbwh_rectangle_filled(strip["left"], strip["bottom"], strip["w"], strip["h"], strip["color"])
        for strip in self.parallax_mid:
            arcade.draw_lbwh_rectangle_filled(strip["left"], strip["bottom"], strip["w"], strip["h"], strip["color"])

        # World
        self.ground_list.draw()
        self.obstacles.draw()
        self.player_list.draw()

        # UI (Text objects)
        self.score_text.text = f"Score: {int(self.time_alive * 10)}"
        self.score_text.draw()

        if not self.alive:
            self.dead_text.draw()
            self.help_text.draw()


if __name__ == "__main__":
    Runner()
    arcade.run()
