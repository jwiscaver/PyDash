Arcade Runner — Project Skeleton (Arcade 3.x)

How to run:
1) python -m venv .venv
2) source .venv/bin/activate
3) pip install arcade
4) python main.py

Controls:
- ENTER: start from menu
- SPACE / UP / mouse: jump
- R: restart level
- ESC: pause (resume with ESC); press 'M' for menu

Project structure:
- main.py .................. App entry; shows MenuView
- menu_view.py ............. Title/menu screen
- game_view.py ............. Core runner game (JSON level loader)
- pause_view.py ............ Pause overlay using separate View
- level_loader.py .......... Loads and validates JSON levels
- settings.py .............. Tunables and colors
- level/level1.json ........ Sample level with gaps & widths

Level format (example):
{
  "scroll_speed": 360,
  "floor_y": 120,
  "player_x": 220,
  "default_obstacle_width": 30,
  "obstacles": [
    {"gap": 300, "width": 28},
    {"gap": 260, "width": 30}
  ]
}

Tips:
- Add more JSONs in /level and change GameView(level_path="level/your.json").
- Replace rectangular obstacles with sprite spikes and custom hitboxes next.
- For web export later: pip install pygbag && pygbag main.py
