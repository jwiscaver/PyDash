# settings.py
WIDTH, HEIGHT = 960, 540
TITLE = "Py Dash"

DEFAULT_SCROLL_SPEED = 360.0
FLOOR_Y = 120
PLAYER_SIZE = 48
PLAYER_X = 220
GRAVITY = 1800.0
JUMP_VEL = 820.0
COYOTE_TIME = 0.08
JUMP_BUFFER = 0.10

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
GOLD = (255, 205, 0, 255)     # NEW: coin color

# Coin visuals/physics
COIN_SIZE = 16                # NEW: diameter (px) for drawn coin; hitbox is a small square sprite
