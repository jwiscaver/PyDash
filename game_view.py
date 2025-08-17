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
    GROUND, PLAYER_COLOR, OBST,
    WHITE, PINK, GRAY, GOLD, COIN_SIZE
)
from level_loader import load_level
from pause_view import PauseView

SPAWN_START = WIDTH + 80
OB_H = 36
ASSETS_DIR = Path(__file__).parent / "assets"

@dataclass
class Particle:
    x: float; y: float; vx: float; vy: float
    life: float; start_life: float; radius: float
    color: tuple[int, int, int, int]
    def update(self, dt: float, gravity: float = 0.0):
        self.life -= dt
        self.vy += gravity * dt
        self.x += self.vx * dt
        self.y += self.vy * dt
    @property
    def alive(self) -> bool: return self.life > 0
    def draw(self, dx: float = 0.0, dy: float = 0.0):
        t = max(0.0, min(1.0, self.life / self.start_life))
        r,g,b,a = self.color
        arcade.draw_circle_filled(self.x + dx, self.y + dy, self.radius, (r, g, b, int(a * t)))

class GameView(arcade.View):
    def __init__(self, level_path: str | None = None):
        super().__init__()
        self.level_path = level_path or (Path(__file__).parent / "level" / "level1.json")
        self.scroll_speed = DEFAULT_SCROLL_SPEED

        # Sprite containers
        self.bg_list = arcade.SpriteList(False)
        self.ground_tiles = arcade.SpriteList(False)
        self.ground_collision = arcade.SpriteList(True)
        self.ceiling_collision = arcade.SpriteList(True)     # for inverted gravity
        self.obstacles = arcade.SpriteList(True)
        self.spikes = arcade.SpriteList(False)
        self.player_list = arcade.SpriteList(False)
        self.coins = arcade.SpriteList(True)
        self.portals = arcade.SpriteList(True)               # speed portals (visible now)
        self.gravity_portals = arcade.SpriteList(True)       # gravity portals (visible)
        self.jump_pads = arcade.SpriteList(True)             # jump pads (visible)

        # Player / physics
        self.player: arcade.Sprite | None = None
        self.vel_y = 0.0
        self.gravity_dir = 1  # +1 normal, -1 inverted
        self.on_ground = False
        self.coyote_timer = 0.0
        self.jump_buffer_timer = 0.0

        # Game state
        self.alive = True
        self.time_alive = 0.0
        self.score = 0
        self.next_spawn_x = SPAWN_START

        # UI text
        self.score_text = arcade.Text("", 16, HEIGHT - 36, WHITE, 18)
        self.dead_text = arcade.Text("You Died  -  Press R to Restart",
                                     WIDTH / 2, HEIGHT / 2 + 40, PINK, 28, anchor_x="center")
        self.help_text = arcade.Text("SPACE/Click = Jump   ESC = Pause   M = Menu",
                                     WIDTH / 2, HEIGHT / 2 - 6, GRAY, 18, anchor_x="center")

        # Level data
        self.level_data = None
        self.obstacle_plan: list[tuple[int, int]] = []
        self.coin_plan: list[tuple[int, int]] = []
        self.portal_plan: list[tuple[int, float]] = []        # speed portals
        self.gravity_plan: list[tuple[int, int]] = []         # (x, dir)
        self.jump_pad_plan: list[tuple[int, float]] = []      # (x, strength)

        # Textures
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

        # NEW textures for triggers
        # If you put my generated PNGs into your assets/ folder, these paths will work.
        # Otherwise, update the paths to wherever you saved them.
        self.tex_portal_speed = arcade.load_texture(str(ASSETS_DIR / "portal_speed.png"))
        self.tex_portal_gravity = arcade.load_texture(str(ASSETS_DIR / "portal_gravity.png"))
        self.tex_pad_jump = arcade.load_texture(str(ASSETS_DIR / "pad_jump.png"))

        # Animation timers
        self.coin_anim_t = 0.0
        self.player_anim_t = 0.0

        # Particles & camera shake
        self.dust_particles: list[Particle] = []
        self.sparkle_particles: list[Particle] = []
        self.death_particles: list[Particle] = []
        self._dust_accum = 0.0
        self.shake_time = 0.0
        self.shake_intensity = 0.0

        self.setup()

    def on_show_view(self): pass

    def setup(self):
        data = load_level(self.level_path)
        self.level_data = data
        self.scroll_speed = float(data.get("scroll_speed", DEFAULT_SCROLL_SPEED))
        floor_y = int(data.get("floor_y", FLOOR_Y))
        player_x = int(data.get("player_x", PLAYER_X))

        self.obstacle_plan.clear()
        default_w = int(data.get("default_obstacle_width", 30))
        for item in data["obstacles"]:
            if isinstance(item, dict):
                gap = int(item.get("gap", 240)); w = int(item.get("width", default_w))
            else:
                gap = int(item); w = default_w
            self.obstacle_plan.append((gap, w))

        self.coin_plan = [(int(c["x"]), int(c["y"])) for c in data.get("coins", [])]
        self.portal_plan = [(int(p["x"]), float(p["speed"])) for p in data.get("speed_portals", [])]
        self.gravity_plan = [(int(p["x"]), int(p.get("dir", -1))) for p in data.get("gravity_portals", [])]
        self.jump_pad_plan = [(int(p["x"]), float(p.get("strength", 1.0))) for p in data.get("jump_pads", [])]

        # Reset lists
        self.bg_list = arcade.SpriteList()
        self.ground_tiles = arcade.SpriteList()
        self.ground_collision = arcade.SpriteList(use_spatial_hash=True)
        self.ceiling_collision = arcade.SpriteList(use_spatial_hash=True)
        self.obstacles = arcade.SpriteList(use_spatial_hash=True)
        self.spikes = arcade.SpriteList()
        self.player_list = arcade.SpriteList()
        self.coins = arcade.SpriteList(use_spatial_hash=True)
        self.portals = arcade.SpriteList(use_spatial_hash=True)
        self.gravity_portals = arcade.SpriteList(use_spatial_hash=True)
        self.jump_pads = arcade.SpriteList(use_spatial_hash=True)

        self.dust_particles.clear(); self.sparkle_particles.clear(); self.death_particles.clear()
        self._dust_accum = 0.0; self.shake_time = 0.0; self.shake_intensity = 0.0

        # Background (two tiles)
        bg_scale = HEIGHT / self.tex_bg.height
        bg_w = self.tex_bg.width * bg_scale
        for i in range(2):
            s = arcade.Sprite()
            s.texture = self.tex_bg
            s.scale = bg_scale
            s.center_x = i * bg_w + bg_w / 2
            s.center_y = HEIGHT / 2
            self.bg_list.append(s)

        # Ground & ceiling colliders
        ground_h = 40
        g = arcade.SpriteSolidColor(WIDTH * 4, ground_h, GROUND)
        g.center_x = WIDTH * 2
        g.center_y = floor_y - ground_h / 2
        self.ground_collision.append(g)

        c = arcade.SpriteSolidColor(WIDTH * 4, ground_h, (0, 0, 0, 0))
        c.center_x = WIDTH * 2
        c.center_y = (HEIGHT - floor_y) + ground_h / 2
        self.ceiling_collision.append(c)

        # Decorative ground tiles
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

        # Player
        self.player = arcade.Sprite()
        self.player.texture = self.tex_player_idle
        self.player.width = PLAYER_SIZE
        self.player.height = PLAYER_SIZE
        self.player.center_x = player_x + PLAYER_SIZE / 2
        self.player.center_y = floor_y + PLAYER_SIZE / 2
        self.player_list.append(self.player)

        self.vel_y = 0.0
        self.gravity_dir = 1
        self.on_ground = True
        self.coyote_timer = 0.0
        self.jump_buffer_timer = 0.0
        self.alive = True
        self.time_alive = 0.0
        self.score = 0
        self.coin_anim_t = 0.0
        self.player_anim_t = 0.0
        self.player.angle = 0

        # Obstacles & spikes
        x = SPAWN_START
        for gap, w in self.obstacle_plan:
            ob = self._create_obstacle(x, w, floor_y)
            self._create_spikes_for_obstacle(ob)
            x += gap
        self.next_spawn_x = x

        # Coins
        for cx, cy in self.coin_plan:
            ccoin = arcade.Sprite()
            ccoin.texture = self.tex_coin[0]
            ccoin.center_x = cx; ccoin.center_y = cy
            ccoin.width = COIN_SIZE; ccoin.height = COIN_SIZE
            self.coins.append(ccoin)

        # Visible speed portals
        for px, spd in self.portal_plan:
            s = arcade.Sprite()
            s.texture = self.tex_portal_speed
            s.center_x = px
            # straddle floor for visibility
            s.center_y = floor_y + self.tex_portal_speed.height * 0.5
            s.scale = 1.0
            # collider roughly matches
            s.properties = {"speed": spd}
            self.portals.append(s)

        # Visible gravity portals
        for px, d in self.gravity_plan:
            s = arcade.Sprite()
            s.texture = self.tex_portal_gravity
            s.center_x = px
            s.center_y = floor_y + self.tex_portal_gravity.height * 0.5
            s.scale = 1.0
            s.properties = {"dir": 1 if d >= 0 else -1}
            self.gravity_portals.append(s)

        # Visible jump pads (thin)
        for px, strength in self.jump_pad_plan:
            s = arcade.Sprite()
            s.texture = self.tex_pad_jump
            s.center_x = px
            s.center_y = floor_y + self.tex_pad_jump.height * 0.5
            s.scale = 1.0
            s.properties = {"strength": max(0.2, float(strength))}
            self.jump_pads.append(s)

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
        self._dust_accum += dt
        if not self.on_ground:
            return
        while self._dust_accum >= 0.04:
            self._dust_accum -= 0.04
            px = self.player.center_x - self.player.width * 0.45
            py = self.player.center_y - self.player.height * 0.5 * self.gravity_dir
            for _ in range(2):
                vx = -80 - random.random() * 80
                vy = 60 + random.random() * 40
                life = 0.35 + random.random() * 0.15
                r = 2 + random.random() * 2
                col = (200, 200, 220, 180)
                self.dust_particles.append(Particle(px, py, vx, vy * self.gravity_dir, life, life, r, col))

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

    def _queue_jump(self):
        if not self.alive: return
        self.jump_buffer_timer = JUMP_BUFFER
        if self.on_ground or self.coyote_timer > 0.0:
            self._do_jump()

    def _do_jump(self):
        self.vel_y = JUMP_VEL * self.gravity_dir
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

    def on_update(self, dt: float):
        if not self.alive:
            self._update_particles(dt); self._update_shake(dt); return

        self.time_alive += dt
        self.coin_anim_t += dt
        self.player_anim_t += dt

        # Background parallax
        bg_speed = 30.0
        dx_bg = bg_speed * dt
        for s in self.bg_list:
            s.center_x -= dx_bg
        if self.bg_list:
            bg_w = self.bg_list[0].width
            for s in self.bg_list:
                if s.right < 0:
                    s.left += bg_w * 2

        # World scroll
        dx = self.scroll_speed * dt
        for lst in (self.ground_collision, self.ceiling_collision, self.obstacles, self.spikes,
                    self.coins, self.portals, self.gravity_portals, self.jump_pads, self.ground_tiles):
            for s in lst:
                s.center_x -= dx

        # Extend colliders
        ground = self.ground_collision[0]
        ceiling = self.ceiling_collision[0]
        if ground.right < WIDTH * 2:
            ground.width += int(WIDTH)
            ceiling.width += int(WIDTH)

        # Recycle ground tiles
        for t in self.ground_tiles:
            if t.right < -64:
                t.left += WIDTH * 4 + 64

        # Prune off-screen
        for lst in (self.obstacles, self.spikes, self.coins, self.portals, self.gravity_portals, self.jump_pads):
            for s in list(lst):
                if s.right < -200:
                    s.remove_from_sprite_lists()

        # Vertical physics with gravity sign
        self.vel_y += (-GRAVITY * self.gravity_dir) * dt
        self.player.center_y += self.vel_y * dt

        # Ground/Ceiling contacts
        self.on_ground = False
        if self.gravity_dir > 0:
            hits = arcade.check_for_collision_with_list(self.player, self.ground_collision)
            if hits and self.vel_y <= 0:
                top = max(h.top for h in hits)
                self.player.center_y = top + self.player.height / 2
                self.vel_y = 0.0
                self.on_ground = True
        else:
            hits = arcade.check_for_collision_with_list(self.player, self.ceiling_collision)
            if hits and self.vel_y >= 0:
                bottom = min(h.bottom for h in hits)
                self.player.center_y = bottom - self.player.height / 2
                self.vel_y = 0.0
                self.on_ground = True

        # Jump grace & buffer
        if self.on_ground:
            self.coyote_timer = COYOTE_TIME
        else:
            self.coyote_timer = max(0.0, self.coyote_timer - dt)
        if self.jump_buffer_timer > 0.0:
            if self.on_ground or self.coyote_timer > 0.0:
                self._do_jump()
            else:
                self.jump_buffer_timer -= dt

        # Dust & animations
        self._emit_dust(dt)
        coin_frame = 0 if int(self.coin_anim_t * 6) % 2 == 0 else 1
        for c in self.coins:
            c.texture = self.tex_coin[coin_frame]
        if self.on_ground:
            run_frame = 0 if int(self.player_anim_t * 8) % 2 == 0 else 1
            self.player.texture = self.tex_player_run[run_frame]
        else:
            self.player.texture = self.tex_player_idle
        self.player.angle = 180 if self.gravity_dir < 0 else 0

        # Coins
        for coin in arcade.check_for_collision_with_list(self.player, self.coins):
            self._emit_coin_sparkles(coin.center_x, coin.center_y)
            coin.remove_from_sprite_lists()
            self.score += 10

        # Speed portals
        for portal in arcade.check_for_collision_with_list(self.player, self.portals):
            self.scroll_speed = float(getattr(portal, "properties", {}).get("speed", self.scroll_speed))
            portal.remove_from_sprite_lists()

        # Gravity portals
        for gport in arcade.check_for_collision_with_list(self.player, self.gravity_portals):
            new_dir = int(getattr(gport, "properties", {}).get("dir", -self.gravity_dir))
            if new_dir not in (1, -1):
                new_dir = -self.gravity_dir
            if new_dir != self.gravity_dir:
                self.gravity_dir = new_dir
                self.vel_y = 0.0
            gport.remove_from_sprite_lists()

        # Jump pads
        for pad in arcade.check_for_collision_with_list(self.player, self.jump_pads):
            strength = float(getattr(pad, "properties", {}).get("strength", 1.0))
            target_v = JUMP_VEL * self.gravity_dir * strength
            if (self.gravity_dir > 0 and self.vel_y < target_v) or (self.gravity_dir < 0 and self.vel_y > target_v):
                self.vel_y = target_v
            self.on_ground = False
            self.coyote_timer = 0.0
            pad.remove_from_sprite_lists()

        # Death / OOB
        if (arcade.check_for_collision_with_list(self.player, self.obstacles)
            or self.player.center_y < -200 or self.player.center_y > HEIGHT + 200):
            self.alive = False
            self._emit_death_burst(self.player.center_x, self.player.center_y)

        self._update_particles(dt)
        self._update_shake(dt)

    def _update_particles(self, dt: float):
        for lst, g in ((self.dust_particles, -400.0),
                       (self.sparkle_particles, 0.0),
                       (self.death_particles, -300.0)):
            for p in list(lst):
                p.update(dt, gravity=g)
                if not p.alive:
                    lst.remove(p)

    def _update_shake(self, dt: float):
        if self.shake_time > 0:
            self.shake_time = max(0.0, self.shake_time - dt)

    def on_draw(self):
        self.clear()
        dx = dy = 0.0
        if self.shake_time > 0.0:
            amp = self.shake_intensity * (self.shake_time / 0.35)
            dx = random.uniform(-amp, amp); dy = random.uniform(-amp, amp)

        self._apply_offset(dx, dy)
        try:
            # background and ground
            self.bg_list.draw()
            self.ground_tiles.draw()

            # world objects behind player
            self.portals.draw()
            self.gravity_portals.draw()
            self.jump_pads.draw()

            # obstacles, spikes, coins, player
            self.obstacles.draw()
            self.spikes.draw()
            self.coins.draw()
            self.player_list.draw()

            # particles
            for p in self.dust_particles: p.draw(dx, dy)
            for p in self.sparkle_particles: p.draw(dx, dy)
            for p in self.death_particles: p.draw(dx, dy)
        finally:
            self._apply_offset(-dx, -dy)

        live_score = int(self.time_alive * 10) + self.score
        self.score_text.text = f"Score: {live_score}"
        self.score_text.draw()
        if not self.alive:
            self.dead_text.draw()
            self.help_text.draw()

    def _apply_offset(self, dx: float, dy: float):
        if dx == 0 and dy == 0: return
        for lst in (self.bg_list, self.ground_tiles, self.ground_collision, self.ceiling_collision,
                    self.obstacles, self.spikes, self.player_list,
                    self.coins, self.portals, self.gravity_portals, self.jump_pads):
            for s in lst:
                s.center_x += dx; s.center_y += dy
