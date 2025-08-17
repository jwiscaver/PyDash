# game_view.py
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import random
import math
import arcade

from settings import (
    WIDTH, HEIGHT,
    DEFAULT_SCROLL_SPEED, FLOOR_Y, PLAYER_SIZE, PLAYER_X,
    GRAVITY, JUMP_VEL, COYOTE_TIME, JUMP_BUFFER,
    GROUND, PLAYER_COLOR, OBST,  # kept for collision strip & fallback
    WHITE, PINK, GRAY, GOLD, COIN_SIZE
)
from level_loader import load_level
from pause_view import PauseView

SPAWN_START = WIDTH + 80
OB_H = 36
ASSETS_DIR = Path(__file__).parent / "assets"


# -------------------------------
# Lightweight particle system
# -------------------------------
@dataclass
class Particle:
    x: float
    y: float
    vx: float
    vy: float
    life: float         # remaining seconds
    start_life: float   # initial life (for fade)
    radius: float
    color: tuple[int, int, int, int]

    def update(self, dt: float, gravity: float = 0.0):
        self.life -= dt
        self.vy += gravity * dt
        self.x += self.vx * dt
        self.y += self.vy * dt

    @property
    def alive(self) -> bool:
        return self.life > 0

    def draw(self, dx: float = 0.0, dy: float = 0.0):
        # Fade alpha as life decreases
        t = max(0.0, min(1.0, self.life / self.start_life))
        r, g, b, a = self.color
        arcade.draw_circle_filled(self.x + dx, self.y + dy, self.radius, (r, g, b, int(a * t)))


class GameView(arcade.View):
    def __init__(self, level_path: str | None = None):
        super().__init__()
        self.level_path = level_path or (Path(__file__).parent / "level" / "level1.json")
        self.scroll_speed = DEFAULT_SCROLL_SPEED

        # --- Sprite containers ---
        self.bg_list = arcade.SpriteList(use_spatial_hash=False)
        self.ground_tiles = arcade.SpriteList(use_spatial_hash=False)
        self.ground_collision = arcade.SpriteList(use_spatial_hash=True)
        self.obstacles = arcade.SpriteList(use_spatial_hash=True)
        self.spikes = arcade.SpriteList(use_spatial_hash=False)
        self.player_list = arcade.SpriteList(use_spatial_hash=False)
        self.coins = arcade.SpriteList(use_spatial_hash=True)
        self.portals = arcade.SpriteList(use_spatial_hash=True)

        # --- Player / physics ---
        self.player: arcade.Sprite | None = None
        self.vel_y = 0.0
        self.on_ground = False
        self.coyote_timer = 0.0
        self.jump_buffer_timer = 0.0

        # --- Game state ---
        self.alive = True
        self.time_alive = 0.0
        self.score = 0
        self.next_spawn_x = SPAWN_START

        # --- Text ---
        self.score_text = arcade.Text("", 16, HEIGHT - 36, WHITE, 18)
        self.dead_text = arcade.Text("You Died  -  Press R to Restart",
                                     WIDTH / 2, HEIGHT / 2 + 40, PINK, 28, anchor_x="center")
        self.help_text = arcade.Text("SPACE/Click = Jump   ESC = Pause   M = Menu",
                                     WIDTH / 2, HEIGHT / 2 - 6, GRAY, 18, anchor_x="center")

        # --- Level data ---
        self.level_data = None
        self.obstacle_plan: list[tuple[int, int]] = []
        self.coin_plan: list[tuple[int, int]] = []
        self.portal_plan: list[tuple[int, float]] = []

        # --- Textures ---
        self.tex_bg = arcade.load_texture(str(ASSETS_DIR / "background.png"))
        self.tex_ground = arcade.load_texture(str(ASSETS_DIR / "ground.png"))
        self.tex_spike = arcade.load_texture(str(ASSETS_DIR / "spike.png"))
        self.tex_coin = [
            arcade.load_texture(str(ASSETS_DIR / "coin1.png")),
            arcade.load_texture(str(ASSETS_DIR / "coin2.png")),
        ]
        self.tex_player_idle = arcade.load_texture(str(ASSETS_DIR / "player.png"))
        self.tex_player_run = [
            arcade.load_texture(str(ASSETS_DIR / "player_run1.png")),
            arcade.load_texture(str(ASSETS_DIR / "player_run2.png")),
        ]

        # --- Animation timers ---
        self.coin_anim_t = 0.0
        self.player_anim_t = 0.0

        # --- Particles & screen shake ---
        self.dust_particles: list[Particle] = []
        self.sparkle_particles: list[Particle] = []
        self.death_particles: list[Particle] = []
        self._dust_accum = 0.0
        self.shake_time = 0.0         # remaining shake time
        self.shake_intensity = 0.0    # px amplitude

        self.setup()

    def on_show_view(self):
        # Arcade 3.x: nothing needed here
        pass

    def setup(self):
        # ----- Load level -----
        self.level_data = load_level(self.level_path)
        self.scroll_speed = float(self.level_data.get("scroll_speed", DEFAULT_SCROLL_SPEED))
        floor_y = int(self.level_data.get("floor_y", FLOOR_Y))
        player_x = int(self.level_data.get("player_x", PLAYER_X))

        self.obstacle_plan.clear()
        default_w = int(self.level_data.get("default_obstacle_width", 30))
        for item in self.level_data["obstacles"]:
            if isinstance(item, dict):
                gap = int(item.get("gap", 240)); w = int(item.get("width", default_w))
            else:
                gap = int(item); w = default_w
            self.obstacle_plan.append((gap, w))

        self.coin_plan = [(int(c["x"]), int(c["y"])) for c in self.level_data.get("coins", [])]
        self.portal_plan = [(int(p["x"]), float(p["speed"])) for p in self.level_data.get("speed_portals", [])]

        # ----- Reset containers -----
        self.bg_list = arcade.SpriteList()
        self.ground_tiles = arcade.SpriteList()
        self.ground_collision = arcade.SpriteList(use_spatial_hash=True)
        self.obstacles = arcade.SpriteList(use_spatial_hash=True)
        self.spikes = arcade.SpriteList()
        self.player_list = arcade.SpriteList()
        self.coins = arcade.SpriteList(use_spatial_hash=True)
        self.portals = arcade.SpriteList(use_spatial_hash=True)

        # Reset particles & shake
        self.dust_particles.clear()
        self.sparkle_particles.clear()
        self.death_particles.clear()
        self._dust_accum = 0.0
        self.shake_time = 0.0
        self.shake_intensity = 0.0

        # ----- Background (two sprites that scroll & wrap) -----
        bg_scale = HEIGHT / self.tex_bg.height
        bg_w = self.tex_bg.width * bg_scale
        for i in range(2):
            s = arcade.Sprite()
            s.texture = self.tex_bg
            s.scale = bg_scale
            s.center_x = i * bg_w + bg_w / 2
            s.center_y = HEIGHT / 2
            self.bg_list.append(s)

        # ----- Ground collision (one long strip) -----
        ground_h = 40
        g = arcade.SpriteSolidColor(WIDTH * 4, ground_h, GROUND)
        g.center_x = WIDTH * 2
        g.center_y = floor_y - ground_h / 2
        self.ground_collision.append(g)

        # ----- Decorative ground tiles -----
        tile_w = self.tex_ground.width
        tile_h = self.tex_ground.height
        scale = 1.0
        span_w = WIDTH * 4 + tile_w
        x = 0
        while x < span_w:
            s = arcade.Sprite()
            s.texture = self.tex_ground
            s.scale = scale
            s.left = x
            s.bottom = floor_y - tile_h * scale
            self.ground_tiles.append(s)
            x += tile_w * scale

        # ----- Player -----
        self.player = arcade.Sprite()
        self.player.texture = self.tex_player_idle
        self.player.width = PLAYER_SIZE
        self.player.height = PLAYER_SIZE
        self.player.center_x = player_x + PLAYER_SIZE / 2
        self.player.center_y = floor_y + PLAYER_SIZE / 2
        self.player_list.append(self.player)

        self.vel_y = 0.0
        self.on_ground = True
        self.coyote_timer = 0.0
        self.jump_buffer_timer = 0.0
        self.alive = True
        self.time_alive = 0.0
        self.score = 0
        self.coin_anim_t = 0.0
        self.player_anim_t = 0.0

        # ----- Obstacles, spikes, coins, portals -----
        x = SPAWN_START
        for gap, w in self.obstacle_plan:
            ob = self._create_obstacle(x, w, floor_y)
            self._create_spikes_for_obstacle(ob)
            x += gap
        self.next_spawn_x = x

        for cx, cy in self.coin_plan:
            c = arcade.Sprite()
            c.texture = self.tex_coin[0]
            c.center_x = cx; c.center_y = cy
            c.width = COIN_SIZE; c.height = COIN_SIZE
            self.coins.append(c)

        for px, spd in self.portal_plan:
            trig = arcade.SpriteSolidColor(8, int(PLAYER_SIZE * 2), (0, 0, 0, 0))
            trig.center_x = px
            trig.center_y = floor_y + PLAYER_SIZE
            trig.properties = {"speed": spd}
            self.portals.append(trig)

    # ---------- Helpers ----------
    def _create_obstacle(self, x, w, floor_y) -> arcade.Sprite:
        ob = arcade.SpriteSolidColor(w, OB_H, OBST)
        ob.center_x = x + w / 2
        ob.center_y = floor_y + OB_H / 2
        self.obstacles.append(ob)
        return ob

    def _create_spikes_for_obstacle(self, ob: arcade.Sprite):
        count = max(1, int(round(ob.width / self.tex_spike.width)))
        pitch = ob.width / count
        for i in range(count):
            s = arcade.Sprite()
            s.texture = self.tex_spike
            s.center_x = ob.left + pitch * (i + 0.5)
            s.bottom = ob.top
            self.spikes.append(s)

    def _emit_dust(self, dt: float):
        """Spawn small dust puffs when grounded and the world is scrolling."""
        self._dust_accum += dt
        if not self.on_ground:
            return
        # spawn ~ every 0.04s
        while self._dust_accum >= 0.04:
            self._dust_accum -= 0.04
            px = self.player.center_x - self.player.width * 0.45
            py = self.player.center_y - self.player.height * 0.5
            # random little puffs drifting left/up
            for _ in range(2):
                vx = -80 - random.random() * 80
                vy = 60 + random.random() * 40
                life = 0.35 + random.random() * 0.15
                r = 2 + random.random() * 2
                col = (200, 200, 220, 180)
                self.dust_particles.append(Particle(px, py, vx, vy, life, life, r, col))

    def _emit_coin_sparkles(self, x: float, y: float):
        for _ in range(12):
            ang = random.random() * math.tau
            spd = 120 + random.random() * 120
            vx = math.cos(ang) * spd
            vy = math.sin(ang) * spd
            life = 0.4 + random.random() * 0.2
            r = 2 + random.random() * 1.5
            col = (255, 215, 80, 255)
            self.sparkle_particles.append(Particle(x, y, vx, vy, life, life, r, col))

    def _emit_death_burst(self, x: float, y: float):
        for _ in range(40):
            ang = random.random() * math.tau
            spd = 150 + random.random() * 250
            vx = math.cos(ang) * spd
            vy = math.sin(ang) * spd
            life = 0.6 + random.random() * 0.4
            r = 2 + random.random() * 3
            col = random.choice([(240, 80, 80, 240), (255, 255, 255, 220)])
            self.death_particles.append(Particle(x, y, vx, vy, life, life, r, col))
        self.shake_time = 0.35
        self.shake_intensity = 6.0

    # ---------- Input ----------
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

    # ---------- Update ----------
    def on_update(self, dt: float):
        if not self.alive:
            # still animate death particles & shake so the effect plays out
            self._update_particles(dt)
            self._update_shake(dt)
            return

        self.time_alive += dt
        self.coin_anim_t += dt
        self.player_anim_t += dt

        # Background scroll
        bg_speed = 30.0
        dx_bg = bg_speed * dt
        for s in self.bg_list:
            s.center_x -= dx_bg
        if self.bg_list:
            bg_w = self.bg_list[0].width
            for s in self.bg_list:
                if s.right < 0:
                    s.left += bg_w * 2

        # Scroll world left
        dx = self.scroll_speed * dt
        for lst in (self.ground_collision, self.obstacles, self.spikes, self.coins, self.portals, self.ground_tiles):
            for s in lst:
                s.center_x -= dx

        # Extend ground collision forward
        ground = self.ground_collision[0]
        if ground.right < WIDTH * 2:
            ground.width += int(WIDTH)

        # Recycle ground tiles
        for t in self.ground_tiles:
            if t.right < -64:
                t.left += WIDTH * 4 + 64

        # Prune far-left sprites
        for lst in (self.obstacles, self.spikes, self.coins, self.portals):
            for s in list(lst):
                if s.right < -200:
                    s.remove_from_sprite_lists()

        # Gravity & vertical motion
        self.vel_y -= GRAVITY * dt
        self.player.center_y += self.vel_y * dt

        # Ground collision (clamp)
        self.on_ground = False
        hits = arcade.check_for_collision_with_list(self.player, self.ground_collision)
        if hits and self.vel_y <= 0:
            top = max(h.top for h in hits)
            self.player.center_y = top + self.player.height / 2
            self.vel_y = 0.0
            self.on_ground = True

        # Coyote & buffered jump
        if self.on_ground:
            self.coyote_timer = COYOTE_TIME
        else:
            self.coyote_timer = max(0.0, self.coyote_timer - dt)

        if self.jump_buffer_timer > 0.0:
            if self.on_ground or self.coyote_timer > 0.0:
                self._do_jump()
            else:
                self.jump_buffer_timer -= dt

        # Emit running dust
        self._emit_dust(dt)

        # Animate coins
        coin_frame = 0 if int(self.coin_anim_t * 6) % 2 == 0 else 1
        for c in self.coins:
            c.texture = self.tex_coin[coin_frame]

        # Animate player
        if self.on_ground:
            run_frame = 0 if int(self.player_anim_t * 8) % 2 == 0 else 1
            self.player.texture = self.tex_player_run[run_frame]
        else:
            self.player.texture = self.tex_player_idle

        # Coin pickups -> sparkles + score
        for coin in arcade.check_for_collision_with_list(self.player, self.coins):
            self._emit_coin_sparkles(coin.center_x, coin.center_y)
            coin.remove_from_sprite_lists()
            self.score += 10

        # Speed portals
        for portal in arcade.check_for_collision_with_list(self.player, self.portals):
            self.scroll_speed = float(getattr(portal, "properties", {}).get("speed", self.scroll_speed))
            portal.remove_from_sprite_lists()

        # Death
        if arcade.check_for_collision_with_list(self.player, self.obstacles) or self.player.center_y < -200:
            self.alive = False
            self._emit_death_burst(self.player.center_x, self.player.center_y)

        # Update particles & shake
        self._update_particles(dt)
        self._update_shake(dt)

    def _update_particles(self, dt: float):
        # Dust (slight downward gravity)
        for p in list(self.dust_particles):
            p.update(dt, gravity=-400.0)   # negative so they fall down
            if not p.alive:
                self.dust_particles.remove(p)
        # Sparkles (no gravity)
        for p in list(self.sparkle_particles):
            p.update(dt, gravity=0.0)
            if not p.alive:
                self.sparkle_particles.remove(p)
        # Death burst (mild downward gravity)
        for p in list(self.death_particles):
            p.update(dt, gravity=-300.0)
            if not p.alive:
                self.death_particles.remove(p)

    def _update_shake(self, dt: float):
        if self.shake_time > 0:
            self.shake_time = max(0.0, self.shake_time - dt)

    # ---------- Draw ----------
    def on_draw(self):
        self.clear()

        # Compute shake offset (apply to world sprites & particles; UI stays stable)
        dx = dy = 0.0
        if self.shake_time > 0.0:
            # decay intensity slightly over remaining time
            amp = self.shake_intensity * (self.shake_time / 0.35)
            dx = random.uniform(-amp, amp)
            dy = random.uniform(-amp, amp)

        # Draw everything with temporary offset (cheap & safe for our sizes)
        self._apply_offset(dx, dy)
        try:
            self.bg_list.draw()
            self.ground_tiles.draw()
            # ground_collision is invisible, but draw() is harmless; skip to reduce overdraw
            self.obstacles.draw()
            self.spikes.draw()
            self.player_list.draw()
            self.coins.draw()

            # Particles
            for p in self.dust_particles: p.draw(dx, dy)
            for p in self.sparkle_particles: p.draw(dx, dy)
            for p in self.death_particles: p.draw(dx, dy)
        finally:
            # always restore positions
            self._apply_offset(-dx, -dy)

        # UI (no shake)
        live_score = int(self.time_alive * 10) + self.score
        self.score_text.text = f"Score: {live_score}"
        self.score_text.draw()
        if not self.alive:
            self.dead_text.draw()
            self.help_text.draw()

    def _apply_offset(self, dx: float, dy: float):
        """Temporarily offset sprites by (dx,dy) for screen shake."""
        if dx == 0 and dy == 0:
            return
        for lst in (self.bg_list, self.ground_tiles, self.ground_collision,
                    self.obstacles, self.spikes, self.player_list,
                    self.coins, self.portals):
            for s in lst:
                s.center_x += dx
                s.center_y += dy
