#importing packages

import csv
import random
import json
import os
import stat
import hashlib
import pandas as pd
import pygame

from qooty import match_settings
from qooty.team_selection import _agent_log, load_roster, DuplicatePlayerNameError
from qooty.team_setup import TeamSetup, SetupClosed
from qooty.match_state import MatchState
from qooty.player_attributes import SkillAllocationError
from qooty.reports import (format_team_lineup, write_player_stat_exports, TextCSVWriter,
    TextCSVDictWriter, write_dataframe_csv)

state = MatchState()
selected_roster = None

pygame.init()

from qooty.constants import (
	CANVAS_WIDTH as CanvasWidth,
	CANVAS_HEIGHT as CanvasHeight,
	WINDOW_SCALE as WindowScale,
	WINDOW_WIDTH as WindowWidth,
	WINDOW_HEIGHT as WindowHeight,
	BLUEY_GREEN as Bluey_Green,
	LIGHT_GREEN as Light_Green,
	GREEN as Green,
	WHITE as White,
	RED as Red,
	SOFT_RED as Soft_Red,
	BLUE as Blue,
	SOFT_BLUE as Soft_Blue,
	LIGHT_GREY as Light_Grey,
	DARK_GREY as Dark_Grey,
	BLACK as Black,
)

# For all internal UI geometry and surface layouts, keep ScreenWidth/ScreenHeight at native canvas resolution (640x400)
ScreenWidth = CanvasWidth
ScreenHeight = CanvasHeight

# Real display window (1280x800: double size with identical 16:10 aspect ratio)
display_win = pygame.display.set_mode((WindowWidth, WindowHeight))

# Virtual surface where all screens, backgrounds, and simulation render (640x400)
win = pygame.Surface((CanvasWidth, CanvasHeight))

pygame.display.set_caption("Couch Footy")

# Hook pygame.display.update and flip so any update call automatically upscales win to display_win
_orig_display_update = pygame.display.update
_orig_display_flip = pygame.display.flip

def _refresh_display(*args, **kwargs):
	pygame.transform.smoothscale(win, (WindowWidth, WindowHeight), display_win)
	_orig_display_update()

pygame.display.update = _refresh_display
pygame.display.flip = _refresh_display

# Scale mouse coordinates so mouse positions map 1:1 onto the 640x400 virtual canvas
_orig_mouse_get_pos = pygame.mouse.get_pos

def _scaled_mouse_get_pos():
	raw_x, raw_y = _orig_mouse_get_pos()
	return (int(raw_x / WindowScale), int(raw_y / WindowScale))

pygame.mouse.get_pos = _scaled_mouse_get_pos

# Defining the variables that load the various background images for screens using absolute paths
from qooty.paths import get_output_path, get_resource_path

start_bg = pygame.image.load(str(get_resource_path('start.png')))
game_bg = pygame.image.load(str(get_resource_path('gamescreen.png')))

# Load commentary data from JSON
with open(get_resource_path('qooty/commentary.json'), 'r', encoding='utf-8') as f:
    COMMENTARY_DATA = json.load(f)

#defining variables that set the fonts and respective sizes
myfont_main = pygame.font.SysFont("Verdana", 20)
myfont_game = pygame.font.SysFont("Verdana", 28)
myfont_comm = pygame.font.SysFont("Consolas", 16)
myfont_playLbl = pygame.font.SysFont("Consolas", 12)
myfont_selectTitle = pygame.font.SysFont("Verdana", 36)

# ── Couch Footy menu palette ──────────────────────────────────────────────────
# Warm amber/pixel-art palette matching the uploaded logo branding
MENU_AMBER        = (255, 210,  50)   # golden yellow – primary label colour
MENU_AMBER_BRIGHT = (255, 240, 120)   # hover highlight
MENU_OLIVE        = ( 72,  80,  40)   # dark olive – button fill (matches logo border)
MENU_OLIVE_HOVER  = ( 95, 105,  52)   # slightly lighter on hover
MENU_BORDER       = (200, 170,  20)   # amber border
MENU_SHADOW       = (  0,   0,   0, 160)  # semi-transparent drop shadow
MENU_TAGLINE      = (210, 200, 170)   # warm off-white for subtitle text

# Button geometry – centred horizontally (screen is 640px wide)
_BTN_W     = 220   # button width
_BTN_H     =  44   # button height
_BTN_X     = (ScreenWidth - _BTN_W) // 2   # horizontal centre
_BTN_Y1    = 272   # "Play Footy" top edge
_BTN_Y2    = 316   # "How to Play" top edge
_BTN_Y3    = 360   # "Settings" top edge
_BTN_RADII = 6     # corner radius (drawn with rects + circles for pixel feel)

myfont_menu_btn  = pygame.font.SysFont("Verdana", 18, bold=True)
myfont_menu_tag  = pygame.font.SysFont("Consolas", 13)

# ── 8-Bit Retro Fonts & Colors for Game Interface ─────────────────────────────
myfont_score_num   = pygame.font.SysFont("Consolas", 18, bold=True)
myfont_score_team  = pygame.font.SysFont("Verdana", 11, bold=True)
myfont_leaders     = pygame.font.SysFont("Consolas", 11, bold=True)
myfont_comm_text   = pygame.font.SysFont("Consolas", 12, bold=True)
myfont_badge       = pygame.font.SysFont("Consolas", 10, bold=True)

RETRO_GOLD         = (255, 215,  50)
RETRO_WHITE        = (245, 245, 235)
FLASH_GOLD         = (255, 230,  45)

def draw_match_leaders(surface):
	"""Draw running top disposals and top goal kickers in the Match Leaders frame."""
	all_players = []
	if hasattr(state, 'home') and hasattr(state.home, 'stats'):
		h_short = state.home.name[:3].upper()
		for p, s in state.home.stats.items():
			all_players.append((p, s.get('D', 0), s.get('G', 0), h_short, "Home"))
	if hasattr(state, 'away') and hasattr(state.away, 'stats'):
		a_short = state.away.name[:3].upper()
		for p, s in state.away.stats.items():
			all_players.append((p, s.get('D', 0), s.get('G', 0), a_short, "Away"))

	# Top disposals (up to 4)
	disp_leaders = sorted([p for p in all_players if p[1] > 0], key=lambda x: x[1], reverse=True)[:4]
	# Top goal kickers (up to 4)
	goal_leaders = sorted([p for p in all_players if p[2] > 0], key=lambda x: x[2], reverse=True)[:4]

	# Render Disposals Column (x: 20..155, y: 222..320)
	dy = 222
	if not disp_leaders:
		lbl = myfont_leaders.render("- None yet -", 1, (140, 145, 120))
		surface.blit(lbl, (24, dy))
	else:
		for i, (name, d, g, team, side) in enumerate(disp_leaders):
			color = (130, 180, 255) if side == "Home" else (255, 140, 140)
			short_name = name[:7]
			line_str = f"{i+1}. {short_name}"
			cnt_str = f"{d}d"
			lbl = myfont_leaders.render(line_str, 1, color)
			cnt_lbl = myfont_leaders.render(cnt_str, 1, RETRO_GOLD)
			surface.blit(lbl, (20, dy))
			surface.blit(cnt_lbl, (116, dy))
			dy += 26

	# Render Goals Column (x: 172..310, y: 222..320)
	gy = 222
	if not goal_leaders:
		lbl = myfont_leaders.render("- None yet -", 1, (140, 145, 120))
		surface.blit(lbl, (176, gy))
	else:
		for i, (name, d, g, team, side) in enumerate(goal_leaders):
			color = (130, 180, 255) if side == "Home" else (255, 140, 140)
			short_name = name[:7]
			line_str = f"{i+1}. {short_name}"
			cnt_str = f"{g}g"
			lbl = myfont_leaders.render(line_str, 1, color)
			cnt_lbl = myfont_leaders.render(cnt_str, 1, RETRO_GOLD)
			surface.blit(lbl, (172, gy))
			surface.blit(cnt_lbl, (272, gy))
			gy += 26

clock = pygame.time.Clock()

# ── Helper: draw a rounded-rectangle button ───────────────────────────────────
def _draw_menu_button(surface, rect, fill_colour, border_colour, border_width=2):
	"""Draw a simple rounded-rect button (pygame <2.0 compatible)."""
	x, y, w, h = rect
	r = _BTN_RADII
	# Main fill
	pygame.draw.rect(surface, fill_colour, (x + r, y, w - 2*r, h))
	pygame.draw.rect(surface, fill_colour, (x, y + r, w, h - 2*r))
	for cx, cy in [(x+r, y+r), (x+w-r-1, y+r), (x+r, y+h-r-1), (x+w-r-1, y+h-r-1)]:
		pygame.draw.circle(surface, fill_colour, (cx, cy), r)
	# Border
	pygame.draw.rect(surface, border_colour, (x + r, y, w - 2*r, border_width))
	pygame.draw.rect(surface, border_colour, (x + r, y+h-border_width, w - 2*r, border_width))
	pygame.draw.rect(surface, border_colour, (x, y + r, border_width, h - 2*r))
	pygame.draw.rect(surface, border_colour, (x+w-border_width, y + r, border_width, h - 2*r))
	for cx, cy in [(x+r, y+r), (x+w-r-1, y+r), (x+r, y+h-r-1), (x+w-r-1, y+h-r-1)]:
		pygame.draw.circle(surface, border_colour, (cx, cy), r, border_width)

# defined under this function is everything to do with the main menu screen
def main_menu():
	win.blit(start_bg, (0, 0))

	global on_main_menu
	global playing_match
	global settings
	global instructions
	global selected_roster, run

	mx, my = mouse

	# ── Tagline ──────────────────────────────────────────────────────────────
	tagline = myfont_menu_tag.render("Quick Footy Action — Made with PyGame", 1, MENU_TAGLINE)
	tag_x = (ScreenWidth - tagline.get_width()) // 2
	win.blit(tagline, (tag_x, 250))

	# ── Button 1: Play Footy ─────────────────────────────────────────────────
	btn1_rect = (_BTN_X, _BTN_Y1, _BTN_W, 36)
	btn1_hover = _BTN_X + _BTN_W > mx > _BTN_X and _BTN_Y1 + 36 > my > _BTN_Y1

	fill1   = MENU_OLIVE_HOVER if btn1_hover else MENU_OLIVE
	label1_colour = MENU_AMBER_BRIGHT if btn1_hover else MENU_AMBER
	_draw_menu_button(win, btn1_rect, fill1, MENU_BORDER)

	label1 = myfont_menu_btn.render(">  Play Footy", 1, label1_colour)
	lx1 = _BTN_X + (_BTN_W - label1.get_width()) // 2
	ly1 = _BTN_Y1 + (36 - label1.get_height()) // 2
	win.blit(label1, (lx1, ly1))

	if btn1_hover and click[0] == 1:
		try:
			selected_roster = TeamSetup(win).run()
		except SetupClosed:
			run = False
			return
		on_main_menu = selected_roster is None
		playing_match = selected_roster is not None
		settings = False
		instructions = False
		pygame.time.delay(200)

	# ── Button 2: How to Play ────────────────────────────────────────────────
	btn2_rect = (_BTN_X, _BTN_Y2, _BTN_W, 36)
	btn2_hover = _BTN_X + _BTN_W > mx > _BTN_X and _BTN_Y2 + 36 > my > _BTN_Y2

	fill2   = MENU_OLIVE_HOVER if btn2_hover else MENU_OLIVE
	label2_colour = MENU_AMBER_BRIGHT if btn2_hover else MENU_AMBER
	_draw_menu_button(win, btn2_rect, fill2, MENU_BORDER)

	label2 = myfont_menu_btn.render("?  How to Play", 1, label2_colour)
	lx2 = _BTN_X + (_BTN_W - label2.get_width()) // 2
	ly2 = _BTN_Y2 + (36 - label2.get_height()) // 2
	win.blit(label2, (lx2, ly2))

	if btn2_hover and click[0] == 1:
		on_main_menu = False
		playing_match = False
		settings = False
		instructions = True
		pygame.time.delay(80)

	# ── Button 3: Settings ───────────────────────────────────────────────────
	btn3_rect = (_BTN_X, _BTN_Y3, _BTN_W, 36)
	btn3_hover = _BTN_X + _BTN_W > mx > _BTN_X and _BTN_Y3 + 36 > my > _BTN_Y3
	fill3 = MENU_OLIVE_HOVER if btn3_hover else MENU_OLIVE
	label3_colour = MENU_AMBER_BRIGHT if btn3_hover else MENU_AMBER
	_draw_menu_button(win, btn3_rect, fill3, MENU_BORDER)
	label3 = myfont_menu_btn.render("*  Settings", 1, label3_colour)
	win.blit(label3, (_BTN_X + (_BTN_W - label3.get_width()) // 2,
	                  _BTN_Y3 + (36 - label3.get_height()) // 2))
	if btn3_hover and click[0] == 1:
		on_main_menu = False
		playing_match = False
		settings = True
		instructions = False
		pygame.time.delay(80)

	# ── Refresh display ──────────────────────────────────────────────────────
	pygame.display.update()


def open_instructions():
	"""Draw the branded, single-page match guide available from the main menu."""
	global on_main_menu, instructions, instructions_page, run

	if instructions_page == 2:
		open_stats_guide()
		return

	win.blit(start_bg, (0, 0))
	panel = pygame.Surface((ScreenWidth, ScreenHeight), pygame.SRCALPHA)
	panel.fill((8, 10, 5, 225))
	win.blit(panel, (0, 0))

	mx, my = mouse
	title_font = pygame.font.SysFont("Verdana", 30, bold=True)
	section_font = pygame.font.SysFont("Verdana", 14, bold=True)
	body_font = pygame.font.SysFont("Consolas", 11, bold=True)
	small_font = pygame.font.SysFont("Consolas", 10)

	title = title_font.render("HOW TO PLAY", 1, MENU_AMBER)
	win.blit(title, (18, 12))
	subtitle = myfont_menu_tag.render("Your quick guide to match day", 1, MENU_TAGLINE)
	win.blit(subtitle, (20, 46))
	pygame.draw.line(win, MENU_BORDER, (18, 66), (622, 66), 2)

	def _guide_card(x, y, w, h, number, heading, lines, accent=MENU_AMBER):
		pygame.draw.rect(win, (22, 25, 14), (x, y, w, h))
		pygame.draw.rect(win, (86, 91, 48), (x, y, w, h), 1)
		pygame.draw.rect(win, MENU_OLIVE, (x, y, w, 27))
		pygame.draw.rect(win, MENU_BORDER, (x, y, w, 27), 1)
		pygame.draw.circle(win, accent, (x + 16, y + 13), 9)
		num = small_font.render(str(number), 1, (25, 27, 14))
		win.blit(num, (x + 16 - num.get_width() // 2, y + 13 - num.get_height() // 2))
		hdr = section_font.render(heading, 1, MENU_AMBER_BRIGHT)
		win.blit(hdr, (x + 31, y + 5))
		for i, line in enumerate(lines):
			win.blit(body_font.render(line, 1, RETRO_WHITE), (x + 10, y + 37 + i * 17))

	_guide_card(18, 78, 194, 128, 1, "SET THE MATCH", [
		"Choose Settings to tune:",
		"- Weather & sim speed",
		"- Home-ground advantage",
		"- Competition mode",
		"Use CSV or saved teams.",
	])
	_guide_card(223, 78, 194, 128, 2, "WATCH IT UNFOLD", [
		"Select Play Footy.",
		"The match sim runs itself:",
		"contests, marks, tackles,",
		"kicks and handballs play out",
		"through live commentary.",
	], (120, 190, 255))
	_guide_card(428, 78, 194, 128, 3, "READ THE GAME", [
		"Track the score and clock,",
		"ball position, possession,",
		"match leaders and momentum.",
		"Player ratings shape how",
		"each contest is resolved.",
	], (255, 135, 110))

	pygame.draw.rect(win, (36, 31, 10), (18, 218, 604, 58))
	pygame.draw.rect(win, MENU_BORDER, (18, 218, 604, 58), 2)
	win.blit(section_font.render("SCORING", 1, MENU_AMBER_BRIGHT), (30, 226))
	win.blit(body_font.render("GOAL", 1, RETRO_WHITE), (145, 226))
	win.blit(myfont_score_num.render("6", 1, RETRO_GOLD), (191, 222))
	win.blit(body_font.render("points", 1, MENU_TAGLINE), (210, 226))
	win.blit(body_font.render("BEHIND", 1, RETRO_WHITE), (315, 226))
	win.blit(myfont_score_num.render("1", 1, RETRO_GOLD), (374, 222))
	win.blit(body_font.render("point", 1, MENU_TAGLINE), (393, 226))
	example = body_font.render("Example:  12 goals 8 behinds  =  12.8 (80)", 1, MENU_TAGLINE)
	win.blit(example, ((ScreenWidth - example.get_width()) // 2, 251))

	pygame.draw.rect(win, (18, 21, 12), (18, 288, 604, 49))
	pygame.draw.rect(win, (86, 91, 48), (18, 288, 604, 49), 1)
	win.blit(section_font.render("MATCH-DAY TIP", 1, MENU_AMBER), (30, 296))
	tip = body_font.render("Weather changes the pace of play. Fast sim speed is best for quick results.", 1, RETRO_WHITE)
	win.blit(tip, (30, 316))

	back_rect = (110, 351, 200, 38)
	back_hover = back_rect[0] + back_rect[2] > mx > back_rect[0] and back_rect[1] + back_rect[3] > my > back_rect[1]
	_draw_menu_button(win, back_rect,
	                  MENU_OLIVE_HOVER if back_hover else MENU_OLIVE, MENU_BORDER)
	back_label = myfont_menu_btn.render("< Back to Menu", 1,
	                                    MENU_AMBER_BRIGHT if back_hover else MENU_AMBER)
	win.blit(back_label, (back_rect[0] + (back_rect[2] - back_label.get_width()) // 2,
	                      back_rect[1] + (back_rect[3] - back_label.get_height()) // 2))

	if back_hover and click[0] == 1:
		instructions = False
		on_main_menu = True
		pygame.time.delay(200)

	next_rect = (330, 351, 200, 38)
	next_hover = next_rect[0] + next_rect[2] > mx > next_rect[0] and next_rect[1] + next_rect[3] > my > next_rect[1]
	_draw_menu_button(win, next_rect,
	                  MENU_OLIVE_HOVER if next_hover else MENU_OLIVE, MENU_BORDER)
	next_label = myfont_menu_btn.render("Stat Guide  >", 1,
	                                    MENU_AMBER_BRIGHT if next_hover else MENU_AMBER)
	win.blit(next_label, (next_rect[0] + (next_rect[2] - next_label.get_width()) // 2,
	                      next_rect[1] + (next_rect[3] - next_label.get_height()) // 2))
	if next_hover and click[0] == 1:
		instructions_page = 2
		pygame.time.delay(200)

	for event in pygame.event.get():
		if event.type == pygame.QUIT:
			run = False
		if event.type == pygame.KEYDOWN and event.key in (pygame.K_ESCAPE, pygame.K_RETURN):
			instructions = False
			on_main_menu = True

	pygame.display.update()


def open_stats_guide():
	"""Draw page two of the guide: match stats and player skill allocations."""
	global on_main_menu, instructions, instructions_page, run

	win.blit(start_bg, (0, 0))
	panel = pygame.Surface((ScreenWidth, ScreenHeight), pygame.SRCALPHA)
	panel.fill((8, 10, 5, 232))
	win.blit(panel, (0, 0))
	mx, my = mouse

	title_font = pygame.font.SysFont("Verdana", 27, bold=True)
	heading_font = pygame.font.SysFont("Verdana", 12, bold=True)
	text_font = pygame.font.SysFont("Consolas", 10)
	text_bold = pygame.font.SysFont("Consolas", 10, bold=True)

	win.blit(title_font.render("STATS & PLAYER SKILLS", 1, MENU_AMBER), (18, 9))
	win.blit(myfont_menu_tag.render("The numbers behind every performance", 1, MENU_TAGLINE), (20, 42))
	pygame.draw.line(win, MENU_BORDER, (18, 60), (622, 60), 2)

	def _glossary_card(x, y, w, h, heading, entries):
		pygame.draw.rect(win, (19, 22, 12), (x, y, w, h))
		pygame.draw.rect(win, (86, 91, 48), (x, y, w, h), 1)
		pygame.draw.rect(win, MENU_OLIVE, (x, y, w, 23))
		pygame.draw.rect(win, MENU_BORDER, (x, y, w, 23), 1)
		win.blit(heading_font.render(heading, 1, MENU_AMBER_BRIGHT), (x + 8, y + 4))
		for i, (abbr, meaning) in enumerate(entries):
			ty = y + 29 + i * 14
			win.blit(text_bold.render(abbr, 1, MENU_AMBER), (x + 8, ty))
			win.blit(text_font.render(meaning, 1, RETRO_WHITE), (x + 39, ty))

	basic_stats = [
		("HO", "Hitouts"), ("K", "Kicks"), ("M", "Marks"),
		("HB", "Handballs"), ("T", "Tackles"), ("FF", "Free kicks for"),
		("FA", "Free kicks against"), ("G", "Goals (6 points)"),
		("B", "Behinds (1 point)"), ("D", "Disposals (K + HB)"),
		("DT", "Fantasy score*"),
	]
	advanced_one = [
		("SI", "Score involvements"), ("INT", "Intercepts"),
		("TO", "Turnovers"), ("CW", "Contest wins"),
		("CL", "Contest losses"), ("R50", "Rebound 50s"),
		("I50", "Inside 50s"), ("BNC", "Running bounces"),
	]
	advanced_two = [
		("CP", "Contested possessions"), ("UP", "Uncontested possessions"),
		("CM", "Contested marks"), ("UM", "Uncontested marks"),
		("T50", "Tackles inside 50"), ("SPO", "Spoils"),
		("SMO", "Smothers"),
	]
	_glossary_card(18, 70, 194, 187, "BASIC MATCH STATS", basic_stats)
	_glossary_card(223, 70, 194, 187, "ADVANCED STATS  A-M", advanced_one)
	_glossary_card(428, 70, 194, 187, "ADVANCED STATS  N-Z", advanced_two)

	# Skill allocation card. The descriptions mirror player_attributes.py and
	# the contest pairings used by the simulation engine.
	pygame.draw.rect(win, (27, 28, 13), (18, 266, 604, 84))
	pygame.draw.rect(win, MENU_BORDER, (18, 266, 604, 84), 1)
	win.blit(heading_font.render("PLAYER SKILL ALLOCATION", 1, MENU_AMBER_BRIGHT), (28, 273))
	win.blit(text_font.render("Spend up to 100 points across 7 skills (no negatives). Default: 15 each + 10 Aura.", 1, RETRO_WHITE), (28, 291))

	left_skills = "STR  physical contests/rucks   SPD  separation/runs   AGI  evade & break pressure"
	right_skills = "SKL  disposal/goal accuracy   END  fatigue/subs   PRS  tackles/smothers   AUR  clutch play"
	win.blit(text_font.render(left_skills, 1, MENU_TAGLINE), (28, 308))
	win.blit(text_font.render(right_skills, 1, MENU_TAGLINE), (28, 323))
	win.blit(text_font.render("Contest odds compare players and stay within 30-70%. Skill success ranges 50-65%.", 1, MENU_AMBER), (28, 338))

	# DT scoring note sits under its glossary column without crowding definitions.
	dt_note = text_font.render("* DT: K 3, HB 2, M 3, T 4, FF 1, FA -3, G 6, B 1", 1, (170, 165, 125))
	win.blit(dt_note, (224, 248))

	guide_rect = (110, 358, 200, 34)
	menu_rect = (330, 358, 200, 34)
	guide_hover = guide_rect[0] + guide_rect[2] > mx > guide_rect[0] and guide_rect[1] + guide_rect[3] > my > guide_rect[1]
	menu_hover = menu_rect[0] + menu_rect[2] > mx > menu_rect[0] and menu_rect[1] + menu_rect[3] > my > menu_rect[1]
	_draw_menu_button(win, guide_rect, MENU_OLIVE_HOVER if guide_hover else MENU_OLIVE, MENU_BORDER)
	_draw_menu_button(win, menu_rect, MENU_OLIVE_HOVER if menu_hover else MENU_OLIVE, MENU_BORDER)
	guide_label = myfont_menu_btn.render("< Game Guide", 1, MENU_AMBER_BRIGHT if guide_hover else MENU_AMBER)
	menu_label = myfont_menu_btn.render("Main Menu", 1, MENU_AMBER_BRIGHT if menu_hover else MENU_AMBER)
	win.blit(guide_label, (guide_rect[0] + (guide_rect[2] - guide_label.get_width()) // 2,
	                       guide_rect[1] + (guide_rect[3] - guide_label.get_height()) // 2))
	win.blit(menu_label, (menu_rect[0] + (menu_rect[2] - menu_label.get_width()) // 2,
	                      menu_rect[1] + (menu_rect[3] - menu_label.get_height()) // 2))

	if guide_hover and click[0] == 1:
		instructions_page = 1
		pygame.time.delay(200)
	if menu_hover and click[0] == 1:
		instructions_page = 1
		instructions = False
		on_main_menu = True
		pygame.time.delay(200)

	for event in pygame.event.get():
		if event.type == pygame.QUIT:
			run = False
		if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
			instructions_page = 1

	pygame.display.update()

def ShowPostMatchScreen():
	global on_main_menu
	global post_match

	# ── Curated stat columns that fit in a 308px-wide card ────────────────────
	_PM_COLS   = ["HO", "K", "M", "HB", "T", "FF", "FA", "G", "B", "D", "DT"]
	_COL_W     = 22   # pixels per stat column (11 cols — slightly tighter)
	_NAME_W    = 56   # pixels for player name column
	_ROW_H     = 12   # compact enough to show the complete 20-player roster

	# ── Background: Couch Footy photo + dark frosted overlay ─────────────────
	win.blit(start_bg, (0, 0))
	panel = pygame.Surface((ScreenWidth, ScreenHeight), pygame.SRCALPHA)
	panel.fill((8, 10, 5, 210))
	win.blit(panel, (0, 0))

	# ── Helper: 8-bit beveled card border ─────────────────────────────────────
	def _card(rect, fill, border=(200, 170, 20), bw=2):
		x, y, w, h = rect
		pygame.draw.rect(win, fill, rect)
		pygame.draw.rect(win, border, rect, bw)
		# bevel highlight (top-left)
		hl = tuple(min(255, c + 40) for c in fill)
		pygame.draw.line(win, hl, (x+bw, y+bw), (x+w-bw-1, y+bw))
		pygame.draw.line(win, hl, (x+bw, y+bw), (x+bw, y+h-bw-1))

	# ── Compute scores ────────────────────────────────────────────────────────
	def _score(team):
		g = sum(s.get("G", 0) for s in team.stats.values())
		b = sum(s.get("B", 0) for s in team.stats.values())
		return g, b, g * 6 + b

	hg, hb, ht = _score(state.home)
	ag, ab, at_ = _score(state.away)

	# ── Header card: final score ──────────────────────────────────────────────
	_card((4, 4, 632, 52), (30, 28, 10), MENU_BORDER, 2)
	# title line
	report_title_font = pygame.font.SysFont("Consolas", 9, bold=True)
	title_lbl = report_title_font.render("POST-MATCH REPORT", 1, MENU_AMBER)
	win.blit(title_lbl, ((ScreenWidth - title_lbl.get_width()) // 2, 8))
	# score line
	home_total = f"{state.home.name}  {hg}.{hb} ({ht})"
	away_total = f"{state.away.name}  {ag}.{ab} ({at_})"
	sep        = "  def.  " if ht >= at_ else "  lost to  "
	winner_col = RETRO_GOLD
	loser_col  = (180, 175, 155)
	# Long team names can make the result headline wider than the 640px canvas.
	# Start smaller than the in-game score font and shrink only as far as needed.
	result_font_size = 16
	while True:
		result_font = pygame.font.SysFont("Consolas", result_font_size, bold=True)
		score_lbl_h = result_font.render(home_total, 1, winner_col if ht >= at_ else loser_col)
		score_lbl_s = result_font.render(sep, 1, RETRO_WHITE)
		score_lbl_a = result_font.render(away_total, 1, winner_col if at_ > ht else loser_col)
		total_w = score_lbl_h.get_width() + score_lbl_s.get_width() + score_lbl_a.get_width()
		if total_w <= ScreenWidth - 16 or result_font_size == 9:
			break
		result_font_size -= 1
	sx = (ScreenWidth - total_w) // 2
	sy = 26
	win.blit(score_lbl_h, (sx, sy))
	win.blit(score_lbl_s, (sx + score_lbl_h.get_width(), sy))
	win.blit(score_lbl_a, (sx + score_lbl_h.get_width() + score_lbl_s.get_width(), sy))

	# ── Home stat card (left: x 4..316) ──────────────────────────────────────
	CARD_Y    = 60
	CARD_H    = 292
	HOME_X    = 4
	AWAY_X    = 320
	CARD_W    = 312

	_card((HOME_X, CARD_Y, CARD_W, CARD_H), (12, 18, 38), MENU_BORDER, 2)
	# team header banner
	pygame.draw.rect(win, (30, 60, 120), (HOME_X, CARD_Y, CARD_W, 18))
	pygame.draw.rect(win, MENU_BORDER,   (HOME_X, CARD_Y, CARD_W, 18), 1)
	home_hdr = myfont_badge.render(
		f"{state.home.name[:20]}   {hg}.{hb} ({ht})", 1, RETRO_GOLD)
	win.blit(home_hdr, (HOME_X + 4, CARD_Y + 4))

	# column headers
	hdr_y = CARD_Y + 22
	name_hdr = myfont_badge.render("NAME", 1, MENU_AMBER)
	win.blit(name_hdr, (HOME_X + 4, hdr_y))
	cx = HOME_X + 4 + _NAME_W
	for col in _PM_COLS:
		lbl = myfont_badge.render(col, 1, MENU_AMBER)
		win.blit(lbl, (cx, hdr_y))
		cx += _COL_W

	# player rows
	row_y = CARD_Y + 35
	ROW_FILL_ALT = (20, 30, 55)
	for i, pos in enumerate(state.home.pos_index):
		p_name = state.home.pos_players[pos]
		if i % 2 == 1:
			pygame.draw.rect(win, ROW_FILL_ALT, (HOME_X + 2, row_y - 1, CARD_W - 4, _ROW_H))
		name_s = myfont_badge.render(p_name[:8], 1, RETRO_WHITE)
		win.blit(name_s, (HOME_X + 4, row_y))
		cx = HOME_X + 4 + _NAME_W
		pstats = state.home.stats.get(p_name, {})
		for col in _PM_COLS:
			val = pstats.get(col, 0)
			v_lbl = myfont_badge.render(str(val), 1, RETRO_WHITE)
			win.blit(v_lbl, (cx, row_y))
			cx += _COL_W
		row_y += _ROW_H

	# ── Away stat card (right: x 320..632) ───────────────────────────────────
	_card((AWAY_X, CARD_Y, CARD_W, CARD_H), (38, 12, 12), MENU_BORDER, 2)
	pygame.draw.rect(win, (110, 30, 30), (AWAY_X, CARD_Y, CARD_W, 18))
	pygame.draw.rect(win, MENU_BORDER,   (AWAY_X, CARD_Y, CARD_W, 18), 1)
	away_hdr = myfont_badge.render(
		f"{state.away.name[:20]}   {ag}.{ab} ({at_})", 1, RETRO_GOLD)
	win.blit(away_hdr, (AWAY_X + 4, CARD_Y + 4))

	# column headers
	win.blit(myfont_badge.render("NAME", 1, MENU_AMBER), (AWAY_X + 4, hdr_y))
	cx = AWAY_X + 4 + _NAME_W
	for col in _PM_COLS:
		lbl = myfont_badge.render(col, 1, MENU_AMBER)
		win.blit(lbl, (cx, hdr_y))
		cx += _COL_W

	# player rows
	row_y = CARD_Y + 35
	ROW_FILL_ALT_A = (55, 18, 18)
	for i, pos in enumerate(state.away.pos_index):
		p_name = state.away.pos_players[pos]
		if i % 2 == 1:
			pygame.draw.rect(win, ROW_FILL_ALT_A, (AWAY_X + 2, row_y - 1, CARD_W - 4, _ROW_H))
		name_s = myfont_badge.render(p_name[:8], 1, RETRO_WHITE)
		win.blit(name_s, (AWAY_X + 4, row_y))
		cx = AWAY_X + 4 + _NAME_W
		pstats = state.away.stats.get(p_name, {})
		for col in _PM_COLS:
			val = pstats.get(col, 0)
			v_lbl = myfont_badge.render(str(val), 1, RETRO_WHITE)
			win.blit(v_lbl, (cx, row_y))
			cx += _COL_W
		row_y += _ROW_H

	# ── Back to Main Menu button ──────────────────────────────────────────────
	mx, my = mouse
	BACK_W, BACK_H = 200, 34
	BACK_X = (ScreenWidth - BACK_W) // 2
	BACK_Y = CARD_Y + CARD_H + 6   # just below cards (~358)
	back_hover = BACK_X + BACK_W > mx > BACK_X and BACK_Y + BACK_H > my > BACK_Y
	_draw_menu_button(
		win, (BACK_X, BACK_Y, BACK_W, BACK_H),
		MENU_OLIVE_HOVER if back_hover else MENU_OLIVE,
		MENU_BORDER
	)
	back_lbl = myfont_menu_btn.render("< Back to Menu", 1,
	                                  MENU_AMBER_BRIGHT if back_hover else MENU_AMBER)
	win.blit(back_lbl, (BACK_X + (BACK_W - back_lbl.get_width()) // 2,
	                    BACK_Y  + (BACK_H - back_lbl.get_height()) // 2))

	# ── Event handling ────────────────────────────────────────────────────────
	events = pygame.event.get()
	for event in events:
		if event.type == pygame.KEYDOWN:
			if event.key == pygame.K_TAB:
				post_match = False
				on_main_menu = True

	if back_hover and click[0] == 1:
		post_match = False
		on_main_menu = True
		pygame.time.delay(200)

	pygame.display.update()

''' The following relates the 'settings' screen where you can toggle a variety of options in the app '''
def open_settings():
	# ── Background: Couch Footy photo with a dark frosted panel overlay ───────
	win.blit(start_bg, (0, 0))

	# Semi-transparent dark panel covering the full screen for legibility
	panel = pygame.Surface((ScreenWidth, ScreenHeight), pygame.SRCALPHA)
	panel.fill((10, 12, 6, 195))   # very dark olive-black, ~76% opaque
	win.blit(panel, (0, 0))

	mx, my = mouse

	# ── Title ─────────────────────────────────────────────────────────────────
	title_surf = myfont_selectTitle.render("Settings", 1, MENU_AMBER)
	win.blit(title_surf, (20, 14))

	# Amber divider line under title
	pygame.draw.line(win, MENU_BORDER, (20, 55), (620, 55), 2)

	# ── Helper colours ────────────────────────────────────────────────────────
	PILL_ON     = MENU_OLIVE_HOVER   # selected option fill
	PILL_OFF    = (30, 33, 18)       # unselected option fill (very dark)
	PILL_BORDER_ON  = MENU_BORDER
	PILL_BORDER_OFF = (80, 85, 50)
	TXT_ON   = MENU_AMBER_BRIGHT
	TXT_OFF  = (140, 140, 100)
	LABEL_COL = (210, 200, 160)      # row-label colour

	# ── Row layout constants ──────────────────────────────────────────────────
	LABEL_X = 18          # left edge of row labels
	ROW_H   = 32          # pill height
	ROW_TXT = myfont_comm # font for pill labels

	def _pill(label, x, y, w, active):
		"""Draw a small pill toggle button; return its rect."""
		fill   = PILL_ON  if active else PILL_OFF
		border = PILL_BORDER_ON if active else PILL_BORDER_OFF
		tc     = TXT_ON   if active else TXT_OFF
		_draw_menu_button(win, (x, y, w, ROW_H), fill, border)
		surf = ROW_TXT.render(label, 1, tc)
		win.blit(surf, (x + (w - surf.get_width()) // 2,
		                y + (ROW_H - surf.get_height()) // 2))
		return (x, y, w, ROW_H)

	def _pill_click(rect, value, setter):
		x, y, w, h = rect
		if x + w > mx > x and y + h > my > y and click[0] == 1:
			setter(value)
			pygame.time.delay(50)

	# ── Section: Weather ──────────────────────────────────────────────────────
	WY = 72
	win.blit(myfont_menu_tag.render("Weather", 1, LABEL_COL), (LABEL_X, WY))
	weather_opts = [("Random", 150), ("Rainy", 232), ("Warm", 314),
	                ("Cloudy", 396), ("Fine", 478)]
	PW = 74
	for label, px in weather_opts:
		r = _pill(label, px, WY + 18, PW, match_settings.weather == label)
		_pill_click(r, label, lambda v: setattr(match_settings, "weather", v))
		# inline click (lambda captures wrong 'label' at runtime so do it directly)
	# Direct click handlers to avoid closure capture issues
	for label, px in weather_opts:
		rx = (px, WY + 18, PW, ROW_H)
		if rx[0] + rx[2] > mx > rx[0] and rx[1] + rx[3] > my > rx[1] and click[0] == 1:
			match_settings.weather = label
			pygame.time.delay(50)

	# Separator
	pygame.draw.line(win, PILL_BORDER_OFF, (LABEL_X, WY + 60), (620, WY + 60), 1)

	# ── Section: Sim Speed ────────────────────────────────────────────────────
	SY = 148
	win.blit(myfont_menu_tag.render("Sim Speed", 1, LABEL_COL), (LABEL_X, SY))
	speed_opts = [("Slow", 150), ("Normal", 232), ("Fast", 314)]
	SW = 74
	for label, px in speed_opts:
		_pill(label, px, SY + 18, SW, match_settings.sim_speed == label)
	for label, px in speed_opts:
		rx = (px, SY + 18, SW, ROW_H)
		if rx[0] + rx[2] > mx > rx[0] and rx[1] + rx[3] > my > rx[1] and click[0] == 1:
			match_settings.sim_speed = label
			pygame.time.delay(50)

	pygame.draw.line(win, PILL_BORDER_OFF, (LABEL_X, SY + 60), (620, SY + 60), 1)

	# ── Section: Home Ground Advantage ───────────────────────────────────────
	HY = 224
	win.blit(myfont_menu_tag.render("Home Ground Advantage", 1, LABEL_COL), (LABEL_X, HY))
	TW = 62
	_pill("ON",  400, HY + 18, TW, match_settings.home_ground_advantage)
	_pill("OFF", 470, HY + 18, TW, not match_settings.home_ground_advantage)
	if 400 + TW > mx > 400 and HY + 18 + ROW_H > my > HY + 18 and click[0] == 1:
		match_settings.home_ground_advantage = True;  pygame.time.delay(50)
	if 470 + TW > mx > 470 and HY + 18 + ROW_H > my > HY + 18 and click[0] == 1:
		match_settings.home_ground_advantage = False; pygame.time.delay(50)

	pygame.draw.line(win, PILL_BORDER_OFF, (LABEL_X, HY + 60), (620, HY + 60), 1)

	# ── Section: Competition Mode ─────────────────────────────────────────────
	CY = 300
	win.blit(myfont_menu_tag.render("Competition Mode", 1, LABEL_COL), (LABEL_X, CY))
	_pill("ON",  400, CY + 18, TW, match_settings.competition_mode)
	_pill("OFF", 470, CY + 18, TW, not match_settings.competition_mode)
	if 400 + TW > mx > 400 and CY + 18 + ROW_H > my > CY + 18 and click[0] == 1:
		match_settings.competition_mode = True;  pygame.time.delay(50)
	if 470 + TW > mx > 470 and CY + 18 + ROW_H > my > CY + 18 and click[0] == 1:
		match_settings.competition_mode = False; pygame.time.delay(50)

	# ── Back button ───────────────────────────────────────────────────────────
	global on_main_menu
	global settings

	BACK_W, BACK_H = 200, 38
	BACK_X = (ScreenWidth - BACK_W) // 2
	BACK_Y = 352
	back_hover = BACK_X + BACK_W > mx > BACK_X and BACK_Y + BACK_H > my > BACK_Y

	back_fill   = MENU_OLIVE_HOVER if back_hover else MENU_OLIVE
	back_colour = MENU_AMBER_BRIGHT if back_hover else MENU_AMBER
	_draw_menu_button(win, (BACK_X, BACK_Y, BACK_W, BACK_H), back_fill, MENU_BORDER)
	back_lbl = myfont_menu_btn.render("< Back to Menu", 1, back_colour)
	win.blit(back_lbl, (BACK_X + (BACK_W - back_lbl.get_width()) // 2,
	                    BACK_Y + (BACK_H - back_lbl.get_height()) // 2))

	if back_hover and click[0] == 1:
		on_main_menu = True
		settings = False
		pygame.time.delay(250)

	pygame.display.update()
	for event in pygame.event.get():
		if event.type == pygame.QUIT:
			pygame.quit()

############### player identification starts here

class Player(object):
	homeTeam = ''
	awayTeam = ''
	homePlayers = []
	awayPlayers = []
	homeNumbers = []
	awayNumbers = []
	homeGenders = []
	awayGenders = []
	homePosIndex = []
	awayPosIndex = []
	stat_categories = ["HO", "K", "M", "HB", "T", "FF", "FA", "G", "B", "D", "DT"]
	
	homeStats = {}
	awayStats = {}
	RevDict_FieldPosition = {}
	Dict_FieldPosition = {}

	
	homePos_Players = {}
	awayPos_Players = {}
	homePos_Oppo = {}
	awayPos_Oppo = {}
	
	Current_Player = ''
	Current_Oppo = ''
	Prev_Player = ''

	scoreboardLog = []

	H2H = []
	H2H_data = {}
	H2H_extraFields = ["Start", "End", "Outcome"]

	FollowWithBall = False

	def Initiate():
		# region agent log
		_agent_log("engine.Player.Initiate", "enter", {}, "H2")
		# endregion
		try:
			r = selected_roster if selected_roster is not None else load_roster()
			state.scoreboard_log = []
			state.load_from_roster(r)
			
			# Sync to match_settings if present in roster
			if r.season: match_settings.season_number = r.season
			if r.round: match_settings.round_number = r.round
			if r.match_id: match_settings.match_id = r.match_id
			
			if match_settings.competition_mode:
				import hashlib
				# Use synced values from match_settings
				s = match_settings.season_number
				rd = match_settings.round_number
				
				# Generate a "Roster Fingerprint" to bake the lineups into the seed
				# Left positions (_l): Name Length | Home: Penultimate char | Away: First char
				home_chars = []
				for pos, name in state.home.pos_players.items():
					if not name: continue
					if "_l" in pos.lower():
						home_chars.append(str(len(name)))
					else:
						home_chars.append(name[-2] if len(name) > 1 else name[0])
				
				away_chars = []
				for pos, name in state.away.pos_players.items():
					if not name: continue
					if "_l" in pos.lower():
						away_chars.append(str(len(name)))
					else:
						away_chars.append(name[0])
				
				roster_hash = "".join(home_chars) + "_" + "".join(away_chars)
				
				# Use synced match_id from match_settings
				m_id = match_settings.match_id
				seed_str = f"{s}_{rd}_{state.home.name}_{state.away.name}_{m_id}_{roster_hash}"
				seed_int = int(hashlib.sha256(seed_str.encode()).hexdigest(), 16)
				random.seed(seed_int)
				
				# Store a short version of the roster hash for the commentary receipt
				state.roster_fingerprint = hashlib.md5(roster_hash.encode()).hexdigest()[:8].upper()
			else:
				# Reset competition mode settings if mode is OFF
				match_settings.season_number = "0"
				match_settings.round_number = "0"
				match_settings.match_id = "0"
				state.season = "0"
				state.round = "0"
				state.match_id = "0"
				random.seed() # Revert to normal randomness
				
			Player.Assign_MatchUps()
			Player.Possession_Index()
			# region agent log
			_agent_log(
				"engine.Player.Initiate",
				"complete",
				{"home_players": len(state.home.players), "pos_keys": len(state.home.pos_index)},
				"H2",
			)
			# endregion
		except Exception as e:
			# region agent log
			_agent_log(
				"engine.Player.Initiate",
				"exception",
				{"type": type(e).__name__, "msg": str(e)[:800]},
				"H2",
			)
			# endregion
			raise

		# assign genders — TBA

	def _write_interchange_comm(pos_players, key_on, key_off, team_name, other_bench_key):
		"""Write interchange commentary to Commentary.txt using a safe 'with' block."""
		on_name = pos_players[key_on]
		off_name = pos_players[key_off]
		other_name = pos_players[other_bench_key]
		colour = "[COLOR=rgb(209, 72, 65)]"
		end_colour = "[/COLOR]"
		if on_name == off_name:
			msg = f"<<< Meanwhile over on the bench {on_name} is getting some treatment >>>"
		elif off_name == other_name:
			msg = f"<<< They're playing musical chairs on the {team_name} bench as {on_name} and {off_name} switch seats>>>"
		else:
			msg = f"<<<ON: {on_name} | OFF: {off_name}>>>"
		with open(get_output_path("Commentary.txt"), "a") as f:
			f.write(colour + msg + end_colour + '\n')

	def Interchange():
		SubstitutionEvent = random.randint(1,40)
		if SubstitutionEvent == 1:
			global KeyON
			global KeyOFF
			WhichBench = random.randint(1,2)
			if state.possession == "Home":
				# Weight field players by inverse endurance (lower endurance -> higher chance to be subbed off)
				field_keys = [k for k in state.home.pos_players if "INT" not in k]
				weights = [state.get_player_stats(state.home.pos_players[k]).interchange_weight() for k in field_keys]
				if WhichBench == 1:
					KeyON = "h_INT1"
					KeyOFF = random.choices(field_keys, weights=weights, k=1)[0]
					Player._write_interchange_comm(state.home.pos_players, KeyON, KeyOFF, state.home.name, "h_INT2")
					if state.home.pos_players[KeyON] != state.home.pos_players[KeyOFF] and state.home.pos_players[KeyOFF] != state.home.pos_players["h_INT2"]:
						Player.Interchange_WriteInfo()
						Player.Updating_H2H()
					state.home.pos_players[KeyON], state.home.pos_players[KeyOFF] = state.home.pos_players[KeyOFF], state.home.pos_players[KeyON]
				elif WhichBench == 2:
					KeyON = "h_INT2"
					KeyOFF = random.choices(field_keys, weights=weights, k=1)[0]
					Player._write_interchange_comm(state.home.pos_players, KeyON, KeyOFF, state.home.name, "h_INT1")
					if state.home.pos_players[KeyON] != state.home.pos_players[KeyOFF] and state.home.pos_players[KeyOFF] != state.home.pos_players["h_INT1"]:
						Player.Interchange_WriteInfo()
						Player.Updating_H2H()
					state.home.pos_players[KeyON], state.home.pos_players[KeyOFF] = state.home.pos_players[KeyOFF], state.home.pos_players[KeyON]

			elif state.possession == "Away":
				field_keys = [k for k in state.away.pos_players if "INT" not in k]
				weights = [state.get_player_stats(state.away.pos_players[k]).interchange_weight() for k in field_keys]
				if WhichBench == 1:
					KeyON = "a_INT1"
					KeyOFF = random.choices(field_keys, weights=weights, k=1)[0]
					Player._write_interchange_comm(state.away.pos_players, KeyON, KeyOFF, state.away.name, "a_INT2")
					if state.away.pos_players[KeyON] != state.away.pos_players[KeyOFF] and state.away.pos_players[KeyOFF] != state.away.pos_players["a_INT2"]:
						Player.Interchange_WriteInfo()
						Player.Updating_H2H()
					state.away.pos_players[KeyON], state.away.pos_players[KeyOFF] = state.away.pos_players[KeyOFF], state.away.pos_players[KeyON]
				elif WhichBench == 2:
					KeyON = "a_INT2"
					KeyOFF = random.choices(field_keys, weights=weights, k=1)[0]
					Player._write_interchange_comm(state.away.pos_players, KeyON, KeyOFF, state.away.name, "a_INT1")
					if state.away.pos_players[KeyON] != state.away.pos_players[KeyOFF] and state.away.pos_players[KeyOFF] != state.away.pos_players["a_INT1"]:
						Player.Interchange_WriteInfo()
						Player.Updating_H2H()
					state.away.pos_players[KeyON], state.away.pos_players[KeyOFF] = state.away.pos_players[KeyOFF], state.away.pos_players[KeyON]

	
	def StartIntLog():
		with open(get_output_path('InterchangeLog.csv'), 'w', newline = '\n') as Int_CSV:
			fieldnames = ['QTR', 'TIME', 'PLAYER'] + Player.stat_categories + ['TEAM', 'POSITION']
			writer = TextCSVDictWriter(Int_CSV, fieldnames=fieldnames)
			writer.writeheader()
	
	def Interchange_WriteInfo():
		with open(get_output_path('InterchangeLog.csv'), 'a', newline = '\n') as Int_CSV:
			fieldnames = ['QTR', 'TIME', 'PLAYER'] + Player.stat_categories + ['TEAM', 'POSITION']
			Int_writer = TextCSVDictWriter(Int_CSV, fieldnames = fieldnames)
			if state.possession == "Home":
				On_Player = state.home.pos_players[KeyON]
				Off_Player = state.home.pos_players[KeyOFF]
				
				row_dict = {'QTR':str(state.qtr), 'TIME' : displayTime, 'PLAYER' : "ON: " + str(state.home.pos_players[KeyON]), 'TEAM': state.home.name, 'POSITION': KeyON}
				for stat in Player.stat_categories:
					row_dict[stat] = str(state.home.stats[On_Player][stat])
				Int_writer.writerow(row_dict)

				row_dict = {'QTR':str(state.qtr), 'TIME' : displayTime, 'PLAYER' : "OFF: " + str(state.home.pos_players[KeyOFF]), 'TEAM': state.home.name, 'POSITION': KeyOFF}
				for stat in Player.stat_categories:
					row_dict[stat] = str(state.home.stats[Off_Player][stat])
				Int_writer.writerow(row_dict)
				
			elif state.possession == "Away":
				On_Player = state.away.pos_players[KeyON]
				Off_Player = state.away.pos_players[KeyOFF]
				row_dict = {'QTR':str(state.qtr), 'TIME' : displayTime, 'PLAYER' : "ON: " + str(state.away.pos_players[KeyON]), 'TEAM': state.away.name, 'POSITION': KeyON}
				for stat in Player.stat_categories:
					row_dict[stat] = str(state.away.stats[On_Player][stat])
				Int_writer.writerow(row_dict)

				row_dict = {'QTR':str(state.qtr), 'TIME' : displayTime, 'PLAYER' : "OFF: " + str(state.away.pos_players[KeyOFF]), 'TEAM': state.away.name, 'POSITION': KeyOFF}
				for stat in Player.stat_categories:
					row_dict[stat] = str(state.away.stats[Off_Player][stat])
				Int_writer.writerow(row_dict)


	def Assign_MatchUps():
		Player.homePos_Oppo = {'h_rBP':'a_lFP','h_FB':'a_FF','h_lBP':'a_rFP','h_rHBF':'a_lHFF','h_CHB':'a_CHF','h_lHBF':'a_rHFF', \
		'h_rW':'a_lW','h_C':'a_C','h_lW':'a_rW','h_rHFF':'a_lHBF','h_CHF':'a_CHB','h_lHFF':'a_rHBF', 'h_rFP':'a_lBP','h_FF':'a_FB', \
		'h_lFP':'a_rBP','h_RUCK':'a_RUCK','h_RR':'a_RR','h_R':'a_R'}
		Player.awayPos_Oppo = {value : key for (key, value) in Player.homePos_Oppo.items()}
		
		#for i in Player.homePos_Oppo:
		#	print(Player.homePos_Oppo[i])
		#for i in Player.awayPos_Oppo:
		#	print(Player.awayPos_Oppo[i])
	
	def PlayerStatSheet():
		for i in state.home.players:
			state.home.stats[i] = dict.fromkeys(Player.stat_categories, 0)
			

		#print(state.home.stats['Blacky']['HO'])
		for j in state.away.players:
			state.away.stats[j] = dict.fromkeys(Player.stat_categories, 0)

		#print(state.away.stats['Tom Papley']['HO'])
	
	def Possession_Index():
		Player.RevDict_FieldPosition = {'a_rBP' : ((-1,2), "Away"), 'h_lFP' : ((-1,2), "Home"), 'a_FB' : ((0,2), "Away"), \
		'h_FF' : ((0,2), "Home"), 'a_lBP' : ((1,2), "Away"), 'h_rFP' : ((1,2), "Home"), 'a_rHBF' : ((-1,1), "Away"), \
		'h_lHFF' : ((-1,1), "Home"), 'a_CHB' : ((0,1), "Away"), 'h_CHF' : ((0,1), "Home"), 'a_lHBF' : ((1,1), "Away"), \
		'h_rHFF' : ((1,1), "Home"), 'a_rW' : ((-1,0), "Away"), 'h_lW' : ((-1,0), "Home"), 'a_C' : ((0,0), "Away"), \
		'h_C' : ((0,0), "Home"), 'a_lW' : ((1,0), "Away"), 'h_rW' :((1,0), "Home"), 'a_rHFF' : ((-1,-1), "Away"), \
		'h_lHBF' : ((-1,-1), "Home"), 'a_CHF' : ((0,-1), "Away"), 'h_CHB' : ((0,-1), "Home"), 'a_lHFF' : ((1,-1), "Away"), \
		'h_rHBF' : ((1,-1), "Home"), 'a_rFP' : ((-1,-2), "Away"), 'h_lBP' : ((-1,-2), "Home"), 'a_FF' : ((0,-2), "Away"), \
		'h_FB' : ((0,-2), "Home"), 'a_lFP' : ((1,-2), "Away"), 'h_rBP' : ((1,-2), "Home")}
		
		#print(Player.RevDict_FieldPosition['a_CHB'])
		
		Player.Dict_FieldPosition = {value : key for (key, value) in Player.RevDict_FieldPosition.items()}
		#print(Player.Dict_FieldPosition[((0,-2), "Home")])
		
		#print('pos index check!')
	def Start_Track_MatchUps():
		for p in state.home.pos_index[:18]:
			i = state.home.pos_players[p]
			OppoLookup = Player.homePos_Oppo[p]
			j = state.away.pos_players[OppoLookup]
			matchup = (i,j)
			state.h2h.append(matchup)
		for m in state.h2h:
			state.h2h_data[m] = dict.fromkeys(Player.H2H_extraFields, 0)
		print(state.h2h_data)
	
	def Updating_H2H():
		
		if state.possession == "Home":
			x = state.home.pos_players[KeyOFF]
			OppoLookup = Player.homePos_Oppo[KeyOFF]
			y = state.away.pos_players[OppoLookup]
			H2H_ended = (x,y)
			state.h2h_data[H2H_ended]["End"] = state.game_minutes + state.q_lengths[0] + state.q_lengths[1] + state.q_lengths[2] + state.q_lengths[3]
			#print(state.h2h_data[H2H_ended])

			z = state.home.pos_players[KeyON]
			H2H_started = (z,y)
			state.h2h_data[H2H_started] = dict.fromkeys(Player.H2H_extraFields, 0)
			state.h2h_data[H2H_started]["Start"] = state.game_minutes + state.q_lengths[0] + state.q_lengths[1] + state.q_lengths[2] + state.q_lengths[3]
			#print(state.h2h_data[H2H_started], " home")
		elif state.possession == "Away":
			x = state.away.pos_players[KeyOFF]
			OppoLookup = Player.awayPos_Oppo[KeyOFF]
			y = state.home.pos_players[OppoLookup]
			H2H_ended = (y,x)
			state.h2h_data[H2H_ended]["End"] = state.game_minutes + state.q_lengths[0] + state.q_lengths[1] + state.q_lengths[2] + state.q_lengths[3]
			#print(state.h2h_data[H2H_ended])

			z = state.away.pos_players[KeyON]
			H2H_started = (y,z)
			state.h2h_data[H2H_started] = dict.fromkeys(Player.H2H_extraFields, 0)
			state.h2h_data[H2H_started]["Start"] = state.game_minutes + state.q_lengths[0] + state.q_lengths[1] + state.q_lengths[2] + state.q_lengths[3]
			#print(state.h2h_data[H2H_started], " away")

	def H2H_Contests_WL(player, oppo):
		if state.possession == "Home":
			H2H_Current = (player, oppo)
			state.h2h_data[H2H_Current]["Outcome"] += 1
		elif state.possession == "Away":
			H2H_Current = (oppo, player)
			state.h2h_data[H2H_Current]["Outcome"] -= 1

	def recording_H2H():
		for MU in state.h2h_data:
			if state.h2h_data[MU]["End"] == 0:
				state.h2h_data[MU]["End"] = state.q_lengths[0] + state.q_lengths[1] + state.q_lengths[2] + state.q_lengths[3]
			else:
				continue
		
		with open(get_output_path("Commentary.txt"), "a") as WriteH2H:
			WriteH2H.write("\n" + "\n" + "\n" + "Match-Ups" + "\n")
			for MU in state.h2h_data:
				if state.h2h_data[MU]["Outcome"] >= -2 and state.h2h_data[MU]["Outcome"] <= 2:
					OutcomeComment = "In a tough battle, " + str(MU[0]) + " and " + str(MU[1]) + " were more or less evenly matched."
				elif state.h2h_data[MU]["Outcome"] >= 3 and state.h2h_data[MU]["Outcome"] <= 5:
					OutcomeComment = "In an enthralling match up, " + str(MU[0]) + " has prevailed over " + str(MU[1])
				elif state.h2h_data[MU]["Outcome"] >= 6 and state.h2h_data[MU]["Outcome"] <= 8:
					OutcomeComment = "No ambiguity on who won this matchup, " + str(MU[0]) + " well and truly has " + str(MU[1]) + "'s measure."
				elif state.h2h_data[MU]["Outcome"] >= 9:
					OutcomeComment = "It's been The " + str(MU[0]) + " Show today as the superstar made " + str(MU[1]) + " look like an insignificant speck of dust."
				elif state.h2h_data[MU]["Outcome"] <= -3 and state.h2h_data[MU]["Outcome"] >= -5:
					OutcomeComment = "In an enthralling match up, " + str(MU[1]) + " has prevailed over " + str(MU[0])
				elif state.h2h_data[MU]["Outcome"] <= -6 and state.h2h_data[MU]["Outcome"] >= -8:
					OutcomeComment = "No ambiguity on who won this matchup, " + str(MU[1]) + " well and truly has " + str(MU[0]) + "'s measure."
				elif state.h2h_data[MU]["Outcome"] <= -9:
					OutcomeComment = "It's been The " + str(MU[1]) + " Show today as the superstar made " + str(MU[0]) + " look like an insignificant speck of dust."
				WriteH2H.write(str(MU) + "; " + str(state.h2h_data[MU]["Start"]) + " to " + str(state.h2h_data[MU]["End"]) + "; " + OutcomeComment + "\n")

	def RuckContest():
		#print(state.action_type)
			#print(state.possession)
		if state.possession == "Home":
			state.prev_player = state.current_player
			state.current_player = state.home.pos_players['h_RUCK']
			state.current_oppo = state.away.pos_players['a_RUCK']
			
		elif state.possession == "Away":
			state.prev_player = state.current_player
			state.current_player = state.away.pos_players['a_RUCK']
			state.current_oppo = state.home.pos_players['h_RUCK']
			
		state.action_type = "Rucking"
			#print(state.action_type)
		state.comm_type = "Ruck Contest"
		if state.center_bounce:
			CB_RoverRoll = random.randint(-1,1)
			state.play_pos_col = CB_RoverRoll
			state.center_bounce = False
	
	def Follower():
		if state.possession in ["Home", "Away"] and state.action_type != "Tackle":
			if state.possession == "Home":
				player_dict = state.home.pos_players
				oppo_dict = state.away.pos_players
				p_prefix = "h_"
				o_prefix = "a_"
			else:
				player_dict = state.away.pos_players
				oppo_dict = state.home.pos_players
				p_prefix = "a_"
				o_prefix = "h_"

			PLAYER_Roll = random.randint(1,10)
			if PLAYER_Roll <= 2:
				state.current_player = player_dict[p_prefix + 'RUCK']
				state.current_oppo = oppo_dict[o_prefix + 'RUCK']
				if state.current_player == state.prev_player:
					state.current_player = player_dict[p_prefix + 'RR']
					state.current_oppo = oppo_dict[o_prefix + 'RR']
				state.follow_with_ball = True
			elif 2 < PLAYER_Roll <= 6:
				state.current_player = player_dict[p_prefix + 'RR']
				state.current_oppo = oppo_dict[o_prefix + 'RR']
				if state.current_player == state.prev_player:
					state.current_player = player_dict[p_prefix + 'R']
					state.current_oppo = oppo_dict[o_prefix + 'R']
				state.follow_with_ball = True
			elif 6 < PLAYER_Roll <= 10:
				state.current_player = player_dict[p_prefix + 'R']
				state.current_oppo = oppo_dict[o_prefix + 'R']
				if state.current_player == state.prev_player:
					state.current_player = player_dict[p_prefix + 'RUCK']
					state.current_oppo = oppo_dict[o_prefix + 'RUCK']
				state.follow_with_ball = True
		else:
			PossessionRoll = random.randint(1,2)
			if PossessionRoll == 1:
				state.possession = "Home"
			else:
				state.possession = "Away"
			Player.UpdatePlayerInPossession()
			Player.UpdateOpponent()

	def UpdatePlayerInPossession():
		Pos_Lookup = ((state.play_pos_col, state.play_pos_line), state.possession)
		state.prev_player = state.current_player
		if -1 <= state.play_pos_col <= 1 and -2 <= state.play_pos_line <= 2 and state.possession != "None":
			Current_Pos = Player.Dict_FieldPosition[Pos_Lookup]
			if state.possession == "Home":
				try:
					state.current_player = state.home.pos_players[Current_Pos]
					#state.home.stats[state.current_player]['HO'] += 1
					#print(state.home.stats[state.current_player]['HO'])
				except KeyError:
					#state.current_player = state.away.pos_players[Current_Pos]
					
					state.possession = "Away"
					Player.UpdatePlayerInPossession()
			elif state.possession == "Away":
				try:
					state.current_player = state.away.pos_players[Current_Pos]
					#state.away.stats[state.current_player]['HO'] += 1
					#print(state.away.stats[state.current_player]['HO'])
				except KeyError:
					#state.current_player = state.home.pos_players[Current_Pos]
					
					state.possession = "Home"
					Player.UpdatePlayerInPossession()
			#print(Pos_Lookup, state.current_player)
		else:
			Player.Follower()
	
	def UpdateOpponent():
		
		Pos_Lookup = ((state.play_pos_col, state.play_pos_line), state.possession)
		Current_Pos = Player.Dict_FieldPosition[Pos_Lookup]
		if state.possession == "Home":
			OppoLookup = Player.homePos_Oppo[Current_Pos]
			state.current_oppo = state.away.pos_players[OppoLookup]
		elif state.possession == "Away":
			OppoLookup = Player.awayPos_Oppo[Current_Pos]
			state.current_oppo = state.home.pos_players[OppoLookup]
		

	def updatePlayerStats(teamWithBall, action, playerWithBall, opponent=None):
		# teamWithBall is often misleading (e.g. defending player makes tackle)
		# So we dynamically locate the player's team dictionary.
		if playerWithBall in state.home.stats:
			player_team = "Home"
			player_stats = state.home.stats[playerWithBall]
		elif playerWithBall in state.away.stats:
			player_team = "Away"
			player_stats = state.away.stats[playerWithBall]
		else:
			return
		stat_opponent = state.current_oppo if opponent is None else opponent

		stat_key = None
		dt_pts = 0
		if action == "Rucking":
			stat_key = "HO"
			dt_pts = 1
		elif action in ("Kick", "EffectiveKick"):
			stat_key = "K"
			dt_pts = 3
			player_stats['D'] += 1
		elif action == "Handball":
			stat_key = "HB"
			dt_pts = 2
			player_stats['D'] += 1
		elif action == "Mark":
			stat_key = "M"
			dt_pts = 3
		elif action == "Tackle":
			stat_key = "T"
			dt_pts = 4
		elif action == "Free Kick":
			stat_key = "FF"
			dt_pts = 1
		elif action == "Free Against":
			stat_key = "FA"
			dt_pts = -3
		elif action == "Goal":
			stat_key = "G"
			dt_pts = 6
		elif action == "Behind":
			stat_key = "B"
			dt_pts = 1

		if stat_key:
			player_stats[stat_key] += 1
		player_stats['DT'] += dt_pts

		# Special handling for Free Kick / Free Against to credit the opponent
		oppo_stats_dict = None
		if stat_opponent:
			if player_team == "Home":
				oppo_stats_dict = state.away.stats
			else:
				oppo_stats_dict = state.home.stats

		if action in ("Free Kick", "Free Against"):
			if oppo_stats_dict and stat_opponent in oppo_stats_dict:
				if action == "Free Kick":
					# Player gets FF, Opponent gets FA
					oppo_stats_dict[stat_opponent]['FA'] += 1
					oppo_stats_dict[stat_opponent]['DT'] -= 3
				else:
					# Player gets FA, Opponent gets FF
					oppo_stats_dict[stat_opponent]['FF'] += 1
					oppo_stats_dict[stat_opponent]['DT'] += 1

		# ==========================================
		# ADVANCED STATS TRACKING
		# ==========================================

		# --- Contested / Uncontested Possessions ---
		if action == "BallGet":
			if state.comm_type in ("Hard Ball Get", "Loose Ball Get"):
				player_stats['CP'] += 1
			elif state.comm_type == "Loose Ball Get" and state.congestion_limiter == 0:
				player_stats['UP'] += 1
		elif action == "Mark":
			if state.comm_type == "Contested Mark Taken":
				player_stats['CP'] += 1
				player_stats['CM'] += 1
			elif state.comm_type == "Uncontested Mark Taken":
				player_stats['UP'] += 1
				player_stats['UM'] += 1
		elif action == "Free Kick":
			player_stats['CP'] += 1
		elif action == "HandballReceive":
			player_stats['UP'] += 1
		elif action == "Rucking":
			player_stats['CP'] += 1

		# --- Tackles Inside 50 ---
		if action == "Tackle":
			# Home attacks towards positive line numbers
			if player_team == "Home" and state.play_pos_line >= 1:
				player_stats['T50'] += 1
			# Away attacks towards negative line numbers
			elif player_team == "Away" and state.play_pos_line <= -1:
				player_stats['T50'] += 1

		# --- Running Bounces ---
		if action == "Run":
			player_stats['BNC'] += 1

		# --- Inside 50s (coordinate-based) ---
		if action in ("Kick", "EffectiveKick", "Handball", "Run"):
			prev_line = state.last_play_pos_line
			curr_line = state.play_pos_line
			if player_team == "Home":
				# Home attacks towards positive: entered forward zone if prev < 1 and now >= 1
				if prev_line < 1 and curr_line >= 1:
					player_stats['I50'] += 1
			elif player_team == "Away":
				# Away attacks towards negative: entered forward zone if prev > -1 and now <= -1
				if prev_line > -1 and curr_line <= -1:
					player_stats['I50'] += 1

		# --- Rebound 50s (coordinate-based, replaces position-based check) ---
		if action in ("Kick", "EffectiveKick", "Handball", "Run"):
			prev_line = state.last_play_pos_line
			curr_line = state.play_pos_line
			if player_team == "Home":
				# Home defends negative: rebound if started at <= -1 and moved to >= 0
				if prev_line <= -1 and curr_line >= 0:
					player_stats['R50'] += 1
			elif player_team == "Away":
				# Away defends positive: rebound if started at >= 1 and moved to <= 0
				if prev_line >= 1 and curr_line <= 0:
					player_stats['R50'] += 1

		# ==========================================
		# CHAIN LOGIC & MODERN STATS (BOG Rebuild)
		# ==========================================
		
		# Helper for turnovers
		def apply_turnover_to_chain():
			if state.current_chain:
				last_p = state.current_chain[-1]
				if last_p in state.home.stats:
					state.home.stats[last_p]['TO'] += 1
				elif last_p in state.away.stats:
					state.away.stats[last_p]['TO'] += 1

		# 1. Chain Addition
		if action in ("EffectiveKick", "Handball", "Mark", "Kick", "BallGet", "Run"):
			if playerWithBall not in state.current_chain:
				state.current_chain.append(playerWithBall)
			if action == "BallGet" or (action == "Mark" and state.comm_type == "Contested Mark Taken"):
				if oppo_stats_dict and stat_opponent in oppo_stats_dict:
					player_stats['CW'] += 1
					oppo_stats_dict[stat_opponent]['CL'] += 1

		# 2. Free Kicks
		elif action == "Free Kick":
			if player_team == state.possession:
				# Attacking free kick: continue chain
				if playerWithBall not in state.current_chain:
					state.current_chain.append(playerWithBall)
			else:
				# Defensive free kick: turnover for the other team
				apply_turnover_to_chain()
				state.current_chain = [playerWithBall]
				player_stats['INT'] += 1
				if oppo_stats_dict and stat_opponent in oppo_stats_dict:
					player_stats['CW'] += 1
					oppo_stats_dict[stat_opponent]['CL'] += 1

		elif action == "Free Against":
			# Player gave away a free: turnover
			apply_turnover_to_chain()
			if stat_opponent and oppo_stats_dict:
				state.current_chain = [stat_opponent]
				if stat_opponent in oppo_stats_dict:
					oppo_stats_dict[stat_opponent]['CW'] += 1
					oppo_stats_dict[stat_opponent]['INT'] += 1
					player_stats['CL'] += 1
			else:
				state.current_chain = []

		# 3. Turnovers and Tackles
		elif action in ("Tackle", "Dispossession", "Out on the Full", "Spoil", "Lose Ball"):
			apply_turnover_to_chain()
			
			if action in ("Tackle", "Spoil", "Dispossession"):
				if oppo_stats_dict and stat_opponent in oppo_stats_dict:
					player_stats['CW'] += 1
					oppo_stats_dict[stat_opponent]['CL'] += 1
				if action == "Tackle":
					state.current_chain = [playerWithBall]
				else:
					state.current_chain = []
			else:
				state.current_chain = []

		# 4. Score Involvements
		elif action in ("Goal", "Behind"):
			if playerWithBall not in state.current_chain:
				state.current_chain.append(playerWithBall)
				
			for p in state.current_chain:
				if player_team == "Home" and p in state.home.stats:
					state.home.stats[p]['SI'] += 1
				elif player_team == "Away" and p in state.away.stats:
					state.away.stats[p]['SI'] += 1
			# Chain resets after a score
			state.current_chain = []
	
	def WriteScore():
		if state.possession == "Home":
			TEAM = state.home.name
		elif state.possession == "Away":
			TEAM = state.away.name

		if state.home_score > state.away_score:
			LEAD = state.home.name
			c = " lead by "
			MARGIN = state.home_score - state.away_score
		elif state.away_score > state.home_score:
			LEAD = state.away.name
			c = " lead by "
			MARGIN = state.away_score - state.home_score
		else:
			LEAD = ""
			c = "Scores level"
			MARGIN = ""

		scoreEvent = "QTR " + str(state.qtr) + " | " + displayTime + " - " + state.action_type + " to " + state.current_player + " (" + TEAM + ")" + " - " + str(LEAD) + c + str(MARGIN)
		state.scoreboard_log.append(scoreEvent)
		print(scoreEvent)

############### player identification ends here

#this code collates the formula to calcuate the best on ground for each match.
class BestOnGround(object):
	homePlayer_Form = {}
	awayPlayer_Form = {}
	
	def MakeLists():
		
		state.home.player_form = dict.fromkeys(state.home.players, 0)
		state.away.player_form = dict.fromkeys(state.away.players, 0)
		
		#there's a problem here in that there may only be a single dictionary that changes keys from these dictionaries
	def TrackForm(player, oppo):
		# Form is now calculated dynamically at the end of the match.
		# This function just records Head-to-Head wins for the Match-Up report.
		try:
			if state.possession not in ["Home", "Away"]:
				return
			
			valid_actions = ("Rucking", "Mark", "Free Kick", "Run", "Goal", "EffectiveKick", "Kick", "Handball")
			if state.action_type in valid_actions:
				Player.H2H_Contests_WL(player, oppo)
		except KeyError:
			pass

#the main function that creates a simulation of the game. Still missing individual identifiable players, a prompt back to main menu and stats summary post-game.
class sim_game(object):
	game_minutes = 0
	game_seconds = 0
	QTR = 1
	Q1_Len = 0
	Q2_Len = 0
	Q3_Len = 0
	Q4_Len = 0
	stoppage_time = 5
	speed = 4
	home_goals = 0
	home_behinds = 0
	home_score = 0
	away_goals = 0
	away_behinds = 0
	away_score = 0
	play_posLine = 0
	play_posCol = 0
	congestionLimiter = 0

	areaOfGround = "Contest"
	possession = "None"
	transType = "Contest"
	ActionType = "Ball Up"
	CommType = "Ruck Contest"

	left_throwIn = False
	right_throwIn = False
	play_restart = True
	BoundaryThrowIn = False
	CenterBounce = False
	
	sim_running = False

	simRunSpeedDelay = 40

	@staticmethod
	def reset_state_for_new_match():
		"""Reset state between runs (avoids QTR=5 / Finished leaking into the next Play Footy)."""
		global state
		state = MatchState()

	def GetRunSpeed():
		if match_settings.sim_speed == "Slow":
			sim_game.simRunSpeedDelay = 200
		elif match_settings.sim_speed == "Normal":
			sim_game.simRunSpeedDelay = 80
		elif match_settings.sim_speed == "Fast":
			sim_game.simRunSpeedDelay = 3

	def BallPosition():
		if state.possession != "None":
			sim_game.areaOfGround = Player.Dict_FieldPosition[((state.play_pos_col, state.play_pos_line), state.possession)]
		else:
			sim_game.areaOfGround = "Contest"

	def EndOfQuarterScore():
		with open(get_output_path('PlayerStats.csv'), 'a', newline= '\n') as RecordQTRscore:
			Q_scoreWriter = TextCSVWriter(RecordQTRscore)
			if state.qtr - 1 == 1:
				Q_scoreWriter.writerow(['QTR',state.home.name + ' G',state.home.name + ' B',state.home.name + ' S',state.away.name + ' G',state.away.name + ' B',state.away.name + ' S'])
			Q_scoreWriter.writerow([state.qtr-1,str(state.home_goals),str(state.home_behinds),str(state.home_score),str(state.away_goals),str(state.away_behinds),str(state.away_score)])
			if state.qtr - 1 == 4:
				Q_scoreWriter.writerow(['\n'])

	def EndOfQuarterComm():
		with open(get_output_path("Commentary.txt"), "a") as EndOfQuarterScore:
			homeScoreline = state.home.name + ": " + str(state.home_goals) + "." + str(state.home_behinds) + "." + str(state.home_score)
			awayScoreline = state.away.name + ": " + str(state.away_goals) + "." + str(state.away_behinds) + "." + str(state.away_score)
			EndOfQuarterScore.write("[COLOR=rgb(61, 142, 185)]" +"====================" + '\n' + "END OF QUARTER " + str(state.qtr - 1) + '\n' + homeScoreline + '\n' + awayScoreline + '\n' + "====================" + "[/COLOR]" + '\n')
		sim_game.EndOfQuarterScore()

	def ScoreUpdateComm():
		with open(get_output_path("Commentary.txt"), "a") as Commentary_UpdateScore:
			homeScoreline = state.home.name + ": " + str(state.home_goals) + "." + str(state.home_behinds) + "." + str(state.home_score)
			awayScoreline = state.away.name + ": " + str(state.away_goals) + "." + str(state.away_behinds) + "." + str(state.away_score)
			Commentary_UpdateScore.write("[COLOR=rgb(61, 142, 185)]" + "--------------------" + '\n' + homeScoreline + '\n' + awayScoreline + '\n' + "--------------------" + "[/COLOR]" + '\n')
	
	def RandomWeather():
		if match_settings.weather == "Random":
			if match_settings.competition_mode:
				# Derive weather deterministically from match identity so
				# re-simulating with the same inputs always produces the same conditions.
				weather_key = (
					f"{match_settings.season_number}_"
					f"{match_settings.round_number}_"
					f"{state.home.name}_{state.away.name}_"
					f"{match_settings.match_id}_"
					f"hga={match_settings.home_ground_advantage}_weather"
				)
				weather_hash = int(hashlib.sha256(weather_key.encode()).hexdigest(), 16)
				options = ["Fine", "Cloudy", "Warm", "Rainy"]
				match_settings.weather = options[weather_hash % len(options)]
			else:
				i = random.randint(1, 4)
				if i == 1:
					match_settings.weather = "Fine"
				elif i == 2:
					match_settings.weather = "Cloudy"
				elif i == 3:
					match_settings.weather = "Warm"
				elif i == 4:
					match_settings.weather = "Rainy"
		print(match_settings.weather)
		weatherComm = open(get_output_path("Commentary.txt"), "a")
		weatherComm.write("Conditions: " + str(match_settings.weather) + '\n')
		weatherComm.close()

	def GetConditions(MatchWeather, Transaction):
		if MatchWeather == "Fine":
			if Transaction == "Contest":
				state.speed = 4
			elif Transaction == "Defending":
				state.speed = 3
			elif Transaction == "Carrying":
				state.speed = 6
		elif MatchWeather == "Warm":
			if Transaction == "Contest":
				state.speed = 4
			elif Transaction == "Defending":
				state.speed = 3
			elif Transaction == "Carrying":
				state.speed = 7
		elif MatchWeather == "Cloudy":
			if Transaction == "Contest":
				state.speed = 5
			elif Transaction == "Defending":
				state.speed = 4
			elif Transaction == "Carrying":
				state.speed = 7
		elif MatchWeather == "Rainy":
			if Transaction == "Contest":
				state.speed = 6
			elif Transaction == "Defending":
				state.speed = 5
			elif Transaction == "Carrying":
				state.speed = 7
	
	def GenerateStatReports():
		write_player_stat_exports(state)
#player statistics
		FullStats = {**state.home.stats, **state.away.stats}
		df = pd.DataFrame(FullStats)
		df = df.transpose()
		
		# Add Team column
		team_mapping = {p: state.home.name for p in state.home.players}
		team_mapping.update({p: state.away.name for p in state.away.players})
		df['TEAM'] = df.index.map(team_mapping)
		
		# Reorder columns to put TEAM at the front
		cols = ['TEAM'] + [c for c in df.columns if c != 'TEAM']
		df = df[cols]
		
		write_dataframe_csv(df, get_output_path('PlayerStats.csv'), mode = 'a')

#team stats
		df_home = df.iloc[0:20].drop(columns=['TEAM'])
		HomeTeamTotal = df_home.sum()
		df_away = df.iloc[20:40].drop(columns=['TEAM'])
		AwayTeamTotal = df_away.sum()
		Join_df = [HomeTeamTotal, AwayTeamTotal]
		TeamStats = pd.concat(Join_df, axis = 1)
		TeamStats.columns = [state.home.name, state.away.name]
		write_dataframe_csv(TeamStats, get_output_path('TeamStats.csv'))
#form calc (BOG Rebuild)
		for p, stats in FullStats.items():
			# SI bonus depends on whether it resulted in a goal or behind
			# Formula: SI*2 (+1 bonus for Goal), Intercepts*2, CW*2, TO*2
			si_score = stats['SI'] * 2
			if stats['G'] > 0: 
				si_score += stats['G'] 
				
			# Final BOG Score: Disposals + SI + Intercepts + Net Contests - Turnovers + Direct Scoring + Rebounds
			# Goals are weighted at 6 points each.
			# Intercepts are weighted at 4 points each to ensure defenders can challenge for BOG.
			# Net Contests (CW - CL) reward efficiency in 1v1s.
			# Rebounds (R50) reward defenders for retaining possession coming out of defense.
			net_contests = stats['CW'] - stats.get('CL', 0)
			rebound_buff = stats.get('R50', 0) * 2
			bog_score = (stats['K'] + stats['HB']) + si_score + (stats['INT'] * 4) + (net_contests * 2) - (stats['TO'] * 2) + (stats['G'] * 6) - stats['B'] + rebound_buff
			# Store the calculated BOG score into the form dictionary
			if p in state.home.player_form:
				state.home.player_form[p] = bog_score
			elif p in state.away.player_form:
				state.away.player_form[p] = bog_score

		FullForm = {**state.home.player_form, **state.away.player_form}
		df_form = pd.DataFrame(FullForm, index = ["BOG Score"])
		df_form = df_form.transpose()
		df_form['player'] = df_form.index
		df_form = df_form.sample(frac=1, random_state=0)
		df_form = df_form.sort_values(by='BOG Score',ascending=False)
		Three_Votes = df_form.iat[0,1]
		Two_Votes = df_form.iat[1,1]
		One_Vote = df_form.iat[2,1]
		write_dataframe_csv(df_form, get_output_path('Form.csv'))
#3-2-1 vote under stats
		with open(get_output_path('PlayerStats.csv'), 'a', newline= '\n') as AddBOGVotes:
			vote_writer = TextCSVWriter(AddBOGVotes)
			vote_writer.writerow(['\n'])
			vote_writer.writerow(['VOTES'])
			vote_writer.writerow([3, 2, 1])
			vote_writer.writerow([Three_Votes, Two_Votes, One_Vote])
			
			# Add sense check for CW and CL
			total_cw = df['CW'].sum()
			total_cl = df['CL'].sum()
			vote_writer.writerow(['\n'])
			vote_writer.writerow(['SENSE CHECK'])
			vote_writer.writerow(['Total CW', 'Total CL', 'Difference'])
			vote_writer.writerow([total_cw, total_cl, total_cw - total_cl])

		# CLEAN PRODUCTION REPORT (Side-by-Side)
		# ==========================================
		# Define production columns
		prod_cols = ['HO', 'K', 'M', 'HB', 'T', 'FF', 'FA', 'G', 'B', 'D', 'DT', 'CP', 'UP', 'CM', 'UM', 'T50', 'SPO', 'SMO', 'I50', 'R50', 'BNC']
		
		# Create clean versions of the team dataframes with Names as a column
		df_home_clean = df_home[prod_cols].reset_index().rename(columns={'index': 'HOME_PLAYER'})
		df_away_clean = df_away[prod_cols].reset_index().rename(columns={'index': 'AWAY_PLAYER'})
		
		# Ensure column order starts with Player Name
		home_final_cols = ['HOME_PLAYER'] + prod_cols
		away_final_cols = ['AWAY_PLAYER'] + prod_cols
		
		df_home_clean = df_home_clean[home_final_cols]
		df_away_clean = df_away_clean[away_final_cols]
		
		# Add a spacer column
		df_home_clean['|'] = "|"
		
		# Combine horizontally (using a simple concat as they are the same length)
		# We use .values on the second DF to avoid any index-matching issues
		production_report = pd.concat([df_home_clean, df_away_clean], axis=1)
		
		# Save without the row numbers (index=False)
		write_dataframe_csv(production_report, get_output_path('MatchReport.csv'), index=False)
#write scoring summary
		with open(get_output_path("Scoring Summary.txt"), 'w') as ss:
			ss.write("SCORING SUMMARY" + "\n")
			for line in state.scoreboard_log:
				ss.write(line + "\n")

		# Seal Commentary File if in competition mode
		if match_settings.competition_mode:
			filepath = get_output_path("Commentary.txt")
			if os.path.exists(filepath):
				# Read content to generate hash
				with open(filepath, "r", encoding="utf-8") as f:
					content = f.read()
				
				v_hash = hashlib.sha256(content.encode()).hexdigest().upper()
				
				# Append hash and seal
				with open(filepath, "a", encoding="utf-8") as f:
					f.write("\n\n" + "="*50 + "\n")
					f.write(f"COMPETITION MODE VERIFICATION KEY: {v_hash}\n")
					f.write("PRODUCED BY QOOTY ENGINE - FILE PROTECTED\n")
					f.write("="*50 + "\n")
				
				# Set to read-only
				mode = os.stat(filepath).st_mode
				os.chmod(filepath, mode & ~stat.S_IWRITE)

	def GamePlayTime():
		QTR_endTime = 20 + state.stoppage_time
		if state.qtr <= 4 and state.game_minutes <= QTR_endTime:
			global match_status
			match_status = "In Progress"
			state.game_seconds += state.speed
			# Track on-ground time for active on-field players
			for pos_key, p_name in state.home.pos_players.items():
				if "INT" not in pos_key and p_name in state.home.player_tog_seconds:
					state.home.player_tog_seconds[p_name] += state.speed
			for pos_key, p_name in state.away.pos_players.items():
				if "INT" not in pos_key and p_name in state.away.player_tog_seconds:
					state.away.player_tog_seconds[p_name] += state.speed
			pygame.time.delay(100)
		elif state.qtr == 5:
			match_status = "Finished"
			
			global playing_match
			global on_main_menu
			global post_match
			
			Player.recording_H2H()
			sim_game.GenerateStatReports()
			
			playing_match = False
			on_main_menu = False
			state.sim_running = False
			post_match = True

		if state.game_seconds >= 60:
			state.game_minutes += 1
			state.game_seconds -= 60
			state.stoppage_time = random.randint(5,15)
		if state.game_minutes >= QTR_endTime:
			if state.qtr == 1:
				state.q_lengths[0] = state.game_minutes
				print("Quarter 1 Length: " + str(state.q_lengths[0]) + " min")
			elif state.qtr == 2:
				state.q_lengths[1] = state.game_minutes
				print("Quarter 2 Length: " + str(state.q_lengths[1]) + " min")
			elif state.qtr == 3:
				state.q_lengths[2] = state.game_minutes
				print("Quarter 3 Length: " + str(state.q_lengths[2]) + " min")
			elif state.qtr == 4:
				state.q_lengths[3] = state.game_minutes
				print("Quarter 4 Length: " + str(state.q_lengths[3]) + " min")
			state.game_minutes = 0
			state.game_seconds = 0
			state.play_pos_line = 0
			state.play_pos_col = 0
			state.qtr += 1
			state.trans_type = "Contest"
			state.play_restart = True
			sim_game.EndOfQuarterComm()
			
	def PlayBook(play_type, movement, Max_lateralDist, sideways):
		# Save previous line position for I50/R50 tracking
		state.last_play_pos_line = state.play_pos_line
		Dir_lateral = random.randint(-1,1)
		# A kick must leave the kicker's coordinate; otherwise the receiving
		# lookup can select the kicker as the mark target.
		if sideways == "sideways" and "Kick" in play_type and Max_lateralDist:
			Dir_lateral = random.choice((-1, 1))
		if state.possession == "Home":
			state.play_pos_line += movement
			if sideways == "sideways":
				state.play_pos_col += Dir_lateral * Max_lateralDist
			else:
				state.play_pos_col += Dir_lateral * random.randint(0, Max_lateralDist)
		elif state.possession == "Away":
			state.play_pos_line -= movement
			if sideways == "sideways":
				state.play_pos_col += Dir_lateral * Max_lateralDist
			else:
				state.play_pos_col += Dir_lateral * random.randint(0, Max_lateralDist)
		global Access_playType
		Access_playType = play_type
	
	def NoSelfMark():
		if state.action_type == "Mark":
			if state.current_player == state.prev_player:
				state.action_type = "BallGet"
				state.trans_type = "Defending"
				state.comm_type = "No Mark"

	@staticmethod
	def get_contest_players() -> tuple[str, str]:
		"""Return (home_player, away_player) contesting in the current game context."""
		if state.action_type in ("Ball Up", "Rucking") or state.center_bounce or state.boundary_throw_in:
			h_p = state.home.pos_players.get("h_RUCK", "")
			a_p = state.away.pos_players.get("a_RUCK", "")
			if h_p and a_p:
				return h_p, a_p

		if state.current_player:
			if state.current_player in state.home.players:
				return state.current_player, state.current_oppo
			elif state.current_player in state.away.players:
				return state.current_oppo, state.current_player

		col, line = state.play_pos_col, state.play_pos_line
		h_pos = state.home.coord_to_pos().get((col, line), "C")
		a_pos = state.away.coord_to_pos().get((col, line), "C")
		h_p = state.home.pos_players.get(state.home.pos_key(h_pos), "")
		a_p = state.away.pos_players.get(state.away.pos_key(a_pos), "")
		return h_p, a_p

	@staticmethod
	def get_contest_winner():
		h_p, a_p = sim_game.get_contest_players()
		h_stats = state.get_effective_stats(h_p, a_p)
		a_stats = state.get_effective_stats(a_p, h_p)

		# Ruck contests driven by Strength x Agility; ground ball contests driven by Strength vs Strength
		is_ruck = state.action_type in ("Ball Up", "Rucking") or state.center_bounce or state.boundary_throw_in
		if is_ruck:
			threshold = h_stats.composite_contest_probability(("strength", "agility"), a_stats)
		else:
			threshold = h_stats.contest_probability("strength", a_stats.strength)

		margin = abs(state.home_score - state.away_score)
		is_clutch_home_buff = (
			match_settings.home_ground_advantage and 
			state.qtr == 4 and 
			margin <= 18
		)
		if is_clutch_home_buff:
			threshold = min(0.70, threshold + 0.05)
		
		return "Home" if random.random() < threshold else "Away"

	def Generate_Play_contest():
		#state.speed = 4
		if state.play_restart:
			state.possession = "None"
			state.action_type = "Ball Up"
			state.center_bounce = True
		if state.boundary_throw_in:
			state.possession = "None"
			state.action_type = "Ball Up"

		if state.possession == "None":
			if state.action_type == "Ball Up":
				state.possession = sim_game.get_contest_winner()
				
				Player.RuckContest()
				#print(state.current_player, state.current_oppo)

				state.trans_type = "Contest"
			else:
				state.possession = sim_game.get_contest_winner()
				state.action_type = "BallGet"
				state.trans_type = "Defending"
				state.comm_type = "Loose Ball Get"

		else:
			freekickRoll = random.randint(1,10)
			if freekickRoll > 9:
				state.action_type = "Free Kick"
				state.trans_type = "Carrying"
				state.comm_type = "Free Kick Paid"

			else:
				if state.action_type == "Rucking":
					possessionRoll = random.randint(1,3)
					if state.possession == "Home" and possessionRoll == 1:
						state.possession = "Away"
					elif state.possession == "Away" and possessionRoll == 1:
						state.possession = "Home"
					state.action_type = "BallGet"
					state.trans_type = "Defending"
					
					state.comm_type = "Hard Ball Get"
				elif state.action_type == "Kick":
					winner = sim_game.get_contest_winner()
					if winner == "Home":
						if state.possession == "Away":
							state.current_player = state.current_oppo
						state.possession = "Home"
					elif winner == "Away":
						if state.possession == "Home":
							state.current_player = state.current_oppo
						state.possession = "Away"

					# Contested Mark vs Spoil driven by Strength x Speed
					p_stats = state.get_effective_stats(state.current_player, state.current_oppo)
					o_stats = state.get_effective_stats(state.current_oppo, state.current_player)
					mark_prob = p_stats.composite_contest_probability(("strength", "speed"), o_stats)

					if random.random() < mark_prob:
						Player.UpdatePlayerInPossession()
						Player.UpdateOpponent()
						
						state.action_type = "Mark"
						state.trans_type = "Carrying"
						
						state.comm_type = "Contested Mark Taken"
					else:
						state.action_type = "BallGet"
						state.trans_type = "Defending"
						
						state.comm_type = "Spoil"
						# Credit the spoil to the defending opponent
						if state.current_oppo:
							if state.current_oppo in state.home.stats:
								state.home.stats[state.current_oppo]['SPO'] += 1
							elif state.current_oppo in state.away.stats:
								state.away.stats[state.current_oppo]['SPO'] += 1
				else:
					state.possession = sim_game.get_contest_winner()
					state.action_type = "BallGet"
					state.trans_type = "Defending"
					
					state.comm_type = "Loose Ball Get"
		
		Player.updatePlayerStats(state.possession, state.action_type, state.current_player)
		BestOnGround.TrackForm(state.current_player, state.current_oppo)
	
	def Generate_Play_defender():
		contest_carrier = state.current_player
		contest_defender = state.current_oppo
		if state.possession in ["Home", "Away"]:
			oppo_possession = "Away" if state.possession == "Home" else "Home"
			
			if state.action_type == "EffectiveKick":
				state.action_type = "Mark"
				state.trans_type = "Carrying"
				if state.current_player == state.prev_player:
					receiving_team = state.home if state.possession == "Home" else state.away
					opposing_team = state.away if state.possession == "Home" else state.home
					receiver = receiving_team.nearest_on_field_player(
						(state.play_pos_col, state.play_pos_line),
						{state.prev_player},
					)
					if receiver is None:
						state.action_type = "BallGet"
						state.trans_type = "Defending"
						state.comm_type = "No Mark"
					else:
						receiver_pos, state.current_player = receiver
						opponent_pos = receiving_team.opponent_pos(receiver_pos)
						state.current_oppo = opposing_team.player_at(opponent_pos)
						state.comm_type = "Uncontested Mark Taken"
				else:
					state.comm_type = "Uncontested Mark Taken"
			else:
				if state.congestion_limiter < 2:
					p_stats = state.get_effective_stats(state.current_player, state.current_oppo)
					o_stats = state.get_effective_stats(state.current_oppo, state.current_player)
					# Agility vs Pressure (evasion) & Speed vs Speed (breakaway acceleration)
					agility_breakaway = p_stats.contest_probability("agility", o_stats.pressure)
					speed_breakaway = p_stats.contest_probability("speed", o_stats.speed)
					breakaway_prob = agility_breakaway * 0.50 + speed_breakaway * 0.50

					turnover_roll = random.random()
					if turnover_roll < 0.15:
						state.possession = "None"
						state.action_type = "Spills Free"
						state.trans_type = "Contest"
						state.comm_type = "Ball Spills Free"
						state.congestion_limiter += 1
					elif turnover_roll < 0.15 + 0.85 * (1.0 - breakaway_prob):
						state.action_type = "Lose Ball"
						BestOnGround.TrackForm(state.current_player, state.current_oppo)

						Player.UpdatePlayerInPossession()
						Player.UpdateOpponent()
						state.possession = oppo_possession

						# Opponent's Pressure vs Carrier's Agility for Tackle vs Dispossession
						tackle_prob = o_stats.contest_probability("pressure", p_stats.agility)
						lose_roll = random.random()
						if lose_roll < 0.90 * tackle_prob:
							state.action_type = "Tackle"
							state.trans_type = "Defending"
							state.comm_type = "Tackle Laid"
							state.congestion_limiter += 1
						elif lose_roll < 0.90:
							state.action_type = "Dispossession"
							state.trans_type = "Defending"
							state.comm_type = "Player Dispossessed"
							state.congestion_limiter += 1
						else:
							state.action_type = "Free Against"
							state.trans_type = "Carrying"
							state.comm_type = "Free Paid Against"
							state.congestion_limiter = 0
					else:
						state.action_type = "Finds Space"
						state.trans_type = "Carrying"
						state.comm_type = "Breakaway"
						state.congestion_limiter = 0
				else:
					state.action_type = "Finds Space"
					state.trans_type = "Carrying"
					state.comm_type = "Breakaway"
					state.congestion_limiter = 0
		else:
			state.trans_type = "Contest"
			state.comm_type = "Ball Up For Grabs"
		
		# A defensive pressure outcome belongs to the opponent who applied the
		# pressure, not the original ball carrier. Preserve that matchup even
		# though the positional players are refreshed above for the next play.
		if state.action_type in ("Tackle", "Dispossession", "Free Against") and contest_defender:
			state.current_player = contest_carrier
			state.current_oppo = contest_defender
			Player.updatePlayerStats(
				state.possession,
				state.action_type,
				contest_defender,
				contest_carrier,
			)
		else:
			Player.updatePlayerStats(state.possession, state.action_type, state.current_player)

	def Generate_Play_ballCarrier():
		#state.speed = 7
		# A disposal updates the ball coordinates before its outcome is resolved.
		# Keep the starting position so a smother cannot carry the ball over the
		# scoring line and be awarded as a goal on the same play.
		pre_disposal_line = state.play_pos_line
		pre_disposal_col = state.play_pos_col
		
		if state.action_type == "Out on the Full" or state.action_type == "Behind":
			if state.play_pos_line == 2:
				state.possession = "Away"
				state.current_player = state.current_oppo
			elif state.play_pos_line == -2:
				state.possession = "Home"
				state.current_player = state.current_oppo

		isSideways = random.randint(0,1)
		movementRoll = random.randint(1,100)
		
		attacking_depth = state.play_pos_line if state.possession == "Home" else -state.play_pos_line
		
		# MIDFIELD LINK BUFF: Force ball flow through Centers and Wings
		if attacking_depth == -1:
			# From Half Back, 40% chance to force a short pass forward (hits Center)
			if random.randint(1, 10) <= 4:
				movementRoll = random.randint(76, 100)
				isSideways = 0
		elif attacking_depth == 0:
			# At Center, 25% chance to force the ball out wide (hits Wings)
			if random.randint(1, 10) <= 2:
				movementRoll = random.randint(26, 100) # Short Kick or Handball
				isSideways = 1
		
		if attacking_depth == 2:
			if movementRoll > 80:
				sim_game.PlayBook("Short Kick", 1, 0, "forwards")
				state.action_type = "Kick"
				state.comm_type = "Chip Forwards"
			elif 40 < movementRoll <= 80:
				sim_game.PlayBook("Short Kick", 0, 1, "sideways")
				state.action_type = "Kick"
				state.comm_type = "Chip Sideways"
				sim_game.DisposalEfficency()
			elif 12 < movementRoll <= 40:
				sim_game.PlayBook("Handball", 0, 1, "sideways")
				state.action_type = "Handball"
				state.comm_type = "Handball Sideways"
			else:
				sim_game.PlayBook("Long Kick", 2, 2, "forwards")
				state.action_type = "Kick"
				state.comm_type = "Long Bomb"
				
		else:
			if movementRoll > 75:
				if isSideways == 0:
					sim_game.PlayBook("Short Kick", 1, 0, "forwards")
					state.action_type = "Kick"
					state.comm_type = "Chip Forwards"
				elif isSideways == 1:
					sim_game.PlayBook("Short Kick", 0, 1, "sideways")
					state.action_type = "Kick"
					state.comm_type = "Chip Sideways"
				sim_game.DisposalEfficency()
			elif 25 < movementRoll <= 75:
				if isSideways == 0:
					sim_game.PlayBook("Handball", 1, 0, "forwards")
					state.action_type = "Handball"
					state.comm_type = "Handball Forwards"
				elif isSideways == 1:
					sim_game.PlayBook("Handball", 0, 1, "sideways")
					state.action_type = "Handball"
					state.comm_type = "Handball Sideways"

			elif 12 < movementRoll <= 25:
				sim_game.PlayBook("Run And Bounce", 1, 0, "forwards")
				state.action_type = "Run"
				state.comm_type = "Run and Bounce"
				state.trans_type = "Carrying"

				# Speed contest vs opponent to maintain possession during running bounce
				p_stats = state.get_effective_stats(state.current_player, state.current_oppo)
				o_stats = state.get_effective_stats(state.current_oppo, state.current_player)
				bounce_success = p_stats.contest_probability("speed", o_stats.speed)
				if random.random() > bounce_success:
					# Failed bounce / caught while bouncing -> Spills free
					state.possession = "None"
					state.action_type = "Spills Free"
					state.trans_type = "Contest"
					state.comm_type = "Ball Spills Free"
			else:
				if movementRoll <= 3 and state.play_pos_line == 0:
					sim_game.PlayBook("TORP", 3, 2, "forwards")
					state.action_type = "Kick"
					state.comm_type = "Torpedo Kick"
				else:
					sim_game.PlayBook("Long Kick", 2, 2, "forwards")
					state.action_type = "Kick"
					state.comm_type = "Long Bomb"
		
		# --- Smother chance on Kick or Handball (Opponent's Pressure vs Carrier's Agility) ---
		if state.action_type in ("Kick", "Handball"):
			o_stats = state.get_effective_stats(state.current_oppo, state.current_player)
			p_stats = state.get_effective_stats(state.current_player, state.current_oppo)
			smother_prob = o_stats.contest_probability("pressure", p_stats.agility) * 0.08
			if random.random() < smother_prob:
				# Credit smother to the opponent
				if state.current_oppo:
					if state.current_oppo in state.home.stats:
						state.home.stats[state.current_oppo]['SMO'] += 1
					elif state.current_oppo in state.away.stats:
						state.away.stats[state.current_oppo]['SMO'] += 1
				state.comm_type = "Smothered"
				state.action_type = "Lose Ball"
				state.trans_type = "Defending"
				state.play_pos_line = pre_disposal_line
				state.play_pos_col = pre_disposal_col

		Player.updatePlayerStats(state.possession, state.action_type, state.current_player)
		BestOnGround.TrackForm(state.current_player, state.current_oppo)
	
	def DisposalEfficency():
		p_stats = state.get_effective_stats(state.current_player, state.current_oppo)
		o_stats = state.get_effective_stats(state.current_oppo, state.current_player)
		# Skill (kicking accuracy, 70% weight) + Speed separation on the lead (30% weight)
		kicker_skill = p_stats.skill_probability()
		speed_separation = p_stats.contest_probability("speed", o_stats.speed)
		effective_prob = kicker_skill * 0.70 + speed_separation * 0.30

		if random.random() < effective_prob:
			state.trans_type = "Defending"
			if state.action_type == "Kick":
				state.action_type = "EffectiveKick"
		else:
			state.trans_type = "Contest"


	def GamePlayBallPos():	
		state.play_restart = None
		
		if state.play_pos_col < -1:
			state.left_throw_in = True
			state.boundary_throw_in = True

		elif state.play_pos_col > 1:
			state.right_throw_in = True
			state.boundary_throw_in = True

		else:
			state.left_throw_in = False
			state.right_throw_in = False
			state.boundary_throw_in = False
		
		if state.play_pos_line >= 3:
			if state.left_throw_in:
				state.play_pos_line = 2
				state.play_pos_col = -1
				state.action_type = "Out on the Full"
				state.trans_type = "Carrying"
				state.comm_type = "No Score"
				state.boundary_throw_in = False
				sim_game.commentate()

			elif state.right_throw_in:
				state.play_pos_line = 2
				state.play_pos_col = 1
				state.action_type = "Out on the Full"
				state.trans_type = "Carrying"
				state.comm_type = "No Score"
				state.boundary_throw_in = False
				sim_game.commentate()

			else:
				p_stats = state.get_effective_stats(state.current_player, state.current_oppo)
				difficulty = p_stats.skill_probability() * 100
				if state.play_pos_col != 0:
					difficulty -= 10
				if state.action_type == "Mark":
					difficulty += 10
				else:
					difficulty -= 10
				difficulty = max(10.0, min(90.0, difficulty))
					
				shotRollHome = random.random() * 100
				if shotRollHome > difficulty:
					state.home_behinds += 1
					state.play_pos_line = 2
					state.play_pos_col = 0
					state.action_type = "Behind"
					state.trans_type = "Carrying"
					state.comm_type = "Behind Kicked"
					Player.updatePlayerStats(state.possession, state.action_type, state.current_player)

				else:
					state.home_goals += 1
					state.action_type = "Goal"
					state.comm_type = "Goal Kicked"
					Player.updatePlayerStats(state.possession, state.action_type, state.current_player)
					
					state.play_restart = True
				state.home_score = state.home_goals * 6 + state.home_behinds
				state.away_score = state.away_goals * 6 + state.away_behinds
				Player.WriteScore()
				sim_game.commentate()
				sim_game.ScoreUpdateComm()
			BestOnGround.TrackForm(state.current_player, state.current_oppo)

		if state.play_pos_line <= -3:
			if state.left_throw_in:
				state.play_pos_line = -2
				state.play_pos_col = -1
				state.action_type = "Out on the Full"
				state.trans_type = "Carrying"
				state.comm_type = "No Score"
				state.boundary_throw_in = False
				sim_game.commentate()

			elif state.right_throw_in:
				state.play_pos_line = -2
				state.play_pos_col = 1
				state.action_type = "Out on the Full"
				state.trans_type = "Carrying"
				state.comm_type = "No Score"
				state.boundary_throw_in = False
				sim_game.commentate()

			else:
				p_stats = state.get_effective_stats(state.current_player, state.current_oppo)
				difficulty = p_stats.skill_probability() * 100
				if state.play_pos_col != 0:
					difficulty -= 10
				if state.action_type == "Mark":
					difficulty += 10
				else:
					difficulty -= 10
				difficulty = max(10.0, min(90.0, difficulty))
					
				shotRollAway = random.random() * 100
				if shotRollAway > difficulty:
					state.away_behinds += 1
					state.play_pos_line = -2
					state.play_pos_col = 0
					state.action_type = "Behind"
					state.trans_type = "Carrying"
					state.comm_type = "Behind Kicked"

					Player.updatePlayerStats(state.possession, state.action_type, state.current_player)

				else:
					state.away_goals += 1
					state.action_type = "Goal"
					state.comm_type = "Goal Kicked"

					Player.updatePlayerStats(state.possession, state.action_type, state.current_player)
					
					state.play_restart = True
				state.home_score = state.home_goals * 6 + state.home_behinds
				state.away_score = state.away_goals * 6 + state.away_behinds
				Player.WriteScore()
				sim_game.commentate()
				sim_game.ScoreUpdateComm()
			BestOnGround.TrackForm(state.current_player, state.current_oppo)
		
		if state.play_restart:
			state.play_pos_line = 0
			state.play_pos_col = 0
			state.trans_type = "Contest"
		
		if state.boundary_throw_in:
			if state.right_throw_in:
				state.play_pos_col = 1
			elif state.left_throw_in:
				state.play_pos_col = -1
			state.trans_type = "Contest"
			state.comm_type = "Boundary Throw In"
			sim_game.commentate()

	FIELD_POSITIONS_MAP = [
		# (pos_key, team, coord, x, y)
		# Line 2 (Away Backs vs Home Forwards)
		("a_rBP",  "Away", (-1,  2), 400,  52),
		("a_FB",   "Away", ( 0,  2), 470,  52),
		("a_lBP",  "Away", ( 1,  2), 540,  52),
		("h_lFP",  "Home", (-1,  2), 400,  68),
		("h_FF",   "Home", ( 0,  2), 470,  68),
		("h_rFP",  "Home", ( 1,  2), 540,  68),

		# Line 1 (Away Half Backs vs Home Half Forwards)
		("a_rHBF", "Away", (-1,  1), 400, 100),
		("a_CHB",  "Away", ( 0,  1), 470, 100),
		("a_lHBF", "Away", ( 1,  1), 540, 100),
		("h_lHFF", "Home", (-1,  1), 400, 116),
		("h_CHF",  "Home", ( 0,  1), 470, 116),
		("h_rHFF", "Home", ( 1,  1), 540, 116),

		# Line 0 (Centres)
		("a_rW",   "Away", (-1,  0), 400, 168),
		("a_C",    "Away", ( 0,  0), 470, 168),
		("a_lW",   "Away", ( 1,  0), 540, 168),
		("h_lW",   "Home", (-1,  0), 400, 184),
		("h_C",    "Home", ( 0,  0), 470, 184),
		("h_rW",   "Home", ( 1,  0), 540, 184),

		# Line -1 (Away Half Forwards vs Home Half Backs)
		("a_rHFF", "Away", (-1, -1), 400, 236),
		("a_CHF",  "Away", ( 0, -1), 470, 236),
		("a_lHFF", "Away", ( 1, -1), 540, 236),
		("h_lHBF", "Home", (-1, -1), 400, 252),
		("h_CHB",  "Home", ( 0, -1), 470, 252),
		("h_rHBF", "Home", ( 1, -1), 540, 252),

		# Line -2 (Away Forwards vs Home Backs)
		("a_rFP",  "Away", (-1, -2), 400, 284),
		("a_FF",   "Away", ( 0, -2), 470, 284),
		("a_lFP",  "Away", ( 1, -2), 540, 284),
		("h_lBP",  "Home", (-1, -2), 400, 300),
		("h_FB",   "Home", ( 0, -2), 470, 300),
		("h_rBP",  "Home", ( 1, -2), 540, 300),

		# Followers (Away: top-right, Home: bottom-right)
		("a_RUCK", "Away", None,     584,  16),
		("a_RR",   "Away", None,     584,  32),
		("a_R",    "Away", None,     584,  48),
		("h_RUCK", "Home", None,     584, 268),
		("h_RR",   "Home", None,     584, 284),
		("h_R",    "Home", None,     584, 300),

		# Interchange Benches (Away: top-left, Home: bottom-left)
		("a_INT1", "Away", None,     334,  16),
		("a_INT2", "Away", None,     334,  32),
		("h_INT1", "Home", None,     334, 284),
		("h_INT2", "Home", None,     334, 300),
	]

	def PlayerLabels(pos, team, x, y):
		"""Compatibility stub."""
		pass

	def map_play():
		"""Draw 8-bit positional boxes on the footy oval with real-time flashing for the ball carrier."""
		global Pos_Coordinates
		Pos_Coordinates = (state.play_pos_col, state.play_pos_line)

		ticks = pygame.time.get_ticks()
		flash_on = (ticks // 150) % 2 == 0

		for pos_key, team, coord, x, y in sim_game.FIELD_POSITIONS_MAP:
			# Player name from roster
			if team == "Home":
				p_name = state.home.pos_players.get(pos_key, "")
			else:
				p_name = state.away.pos_players.get(pos_key, "")

			# Determine if this position/player currently has possession
			is_carrier = False
			if p_name and state.current_player and p_name == state.current_player:
				is_carrier = True
			elif coord is not None and Pos_Coordinates == coord and state.possession == team:
				is_carrier = True
			elif coord is None and state.follow_with_ball and p_name == state.current_player:
				is_carrier = True

			# Box styling
			bw, bh = 44, 14
			if is_carrier and flash_on:
				fill_col   = (255, 230,  45) # Bright Golden Amber flash
				border_col = (255, 255, 255) # Pure white highlight
				text_col   = ( 12,  15,  10) # Dark text for high contrast
			elif is_carrier:
				fill_col   = ( 45, 115, 240) if team == "Home" else (235,  45,  45)
				border_col = (255, 230,  45) # Glowing amber border
				text_col   = (255, 255, 255)
			else:
				fill_col   = ( 20,  40,  95) if team == "Home" else (100,  20,  20)
				border_col = ( 40,  70, 150) if team == "Home" else (150,  40,  40)
				text_col   = (235, 240, 255) if team == "Home" else (255, 235, 235)

			# Draw 8-bit beveled box
			pygame.draw.rect(win, fill_col, (x, y, bw, bh))
			pygame.draw.rect(win, border_col, (x, y, bw, bh), 1)

			# 8-bit corner pixel notches
			win.set_at((x, y), (18, 22, 14))
			win.set_at((x + bw - 1, y), (18, 22, 14))
			win.set_at((x, y + bh - 1), (18, 22, 14))
			win.set_at((x + bw - 1, y + bh - 1), (18, 22, 14))

			# Active ball indicator dot
			if is_carrier:
				ball_col = (255, 255, 255) if flash_on else (255, 220, 40)
				pygame.draw.circle(win, ball_col, (x - 4, y + 7), 2)

			# Render player surname (up to 5 characters)
			short_name = p_name[:5] if p_name else pos_key[2:]
			p_surf = myfont_playLbl.render(short_name, 1, text_col)
			win.blit(p_surf, (x + 3, y + 1))
		

	
	def commentate():
		global commentary
		if state.qtr == 5:
			commentary = "MATCH OVER!"
			PrintCommentary = "{" + str(state.qtr) + "} " + commentary
		else:
			# Get the list of lines for this commentary type
			lines = COMMENTARY_DATA.get(state.comm_type, ["{player} performs {action}"])
			raw_line = random.choice(lines)
			
			# Replace placeholders
			# {player} -> Current player
			# {oppo} -> Current opponent
			# {team} -> Team of the current player
			current_team = state.home.name if state.possession == "Home" else state.away.name
			
			commentary = raw_line.format(
				player=state.current_player,
				oppo=state.current_oppo,
				prev=state.prev_player if state.prev_player else "A teammate",
				team=current_team,
				action=state.comm_type
			)
			
			PrintCommentary = "{" + str(state.qtr) + "}" + "[" + sim_game.areaOfGround + "] " + displayTime + ": " + commentary
			
		with open(get_output_path("Commentary.txt"), "a") as textcommentary:
			textcommentary.write(PrintCommentary + '\n')
	
	def Comm_MatchStart():
		First = "Match commencing shortly ... " + state.home.name + " v " + state.away.name + '\n'
		if match_settings.competition_mode:
			s = match_settings.season_number
			rd = match_settings.round_number
			rf = getattr(state, 'roster_fingerprint', 'N/A')
			m_id = match_settings.match_id
			First += f"COMPETITION MODE ACTIVE - MATCH ID: {m_id} ({s}, {rd})\n"
			First += f"ROSTER FINGERPRINT: {rf}\n"
		First += '\n'
		DisplayMatchUps = format_team_lineup(state)
		filepath = get_output_path("Commentary.txt")
		# Unprotect file if it was previously sealed
		if os.path.exists(filepath):
			mode = os.stat(filepath).st_mode
			os.chmod(filepath, mode | stat.S_IWRITE)
			
		with open(filepath, "w") as newGameComm:
			newGameComm.write(First + DisplayMatchUps + '\n' + '\n')

	
	def match_sim_running():
		global match_status, commentary, displayTime
		# region agent log
		_agent_log(
			"engine.match_sim_running",
			"enter",
			{"QTR": state.qtr, "sim_running_before": state.sim_running},
			"H5",
		)
		# endregion
		sim_game.reset_state_for_new_match()
		match_status = "In Progress"
		commentary = ""
		displayTime = "0:00"
		# region agent log
		_agent_log(
			"engine.match_sim_running",
			"after_reset_state",
			{"QTR": state.qtr, "match_status": match_status},
			"H5",
		)
		# endregion
		_loop_logged = False
		sim_game.GetRunSpeed()
		try:
			Player.Initiate()
		except (DuplicatePlayerNameError, SkillAllocationError) as exc:
			global playing_match, on_main_menu, post_match
			state.sim_running = False
			playing_match = False
			post_match = False
			on_main_menu = True
			if isinstance(exc, SkillAllocationError):
				show_skill_allocation_error(str(exc))
			else:
				show_roster_error(str(exc))
			return
		# region agent log
		_agent_log("engine.match_sim_running", "after_initiate", {"QTR": state.qtr}, "H3")
		# endregion
		Player.StartIntLog()
		BestOnGround.MakeLists()
		sim_game.Comm_MatchStart()
		sim_game.RandomWeather()
		# region agent log
		_agent_log("engine.match_sim_running", "before_while_loop", {"QTR": state.qtr}, "H3")
		# endregion
		state.sim_running = True
		sim_game._agent_logged_ms = False
		while state.sim_running:
			if not _loop_logged:
				# region agent log
				_agent_log(
					"engine.match_sim_running",
					"first_while_frame",
					{
						"match_status": repr(globals().get("match_status", "__ABSENT__")),
						"commentary": repr(globals().get("commentary", "__ABSENT__"))[:200],
						"QTR": state.qtr,
					},
					"H4",
				)
				# endregion
				_loop_logged = True

			win.blit(game_bg, (0,0))
			# ── 8-Bit Scoreboard Displays ─────────────────────────────────
			if state.game_seconds < 10:
				displayTime = str(state.game_minutes) + ":0" + str(state.game_seconds)
			else:
				displayTime = str(state.game_minutes) + ":" + str(state.game_seconds)

			# QTR & TIME
			QTR_display = myfont_score_num.render(str(state.qtr), 1, RETRO_GOLD)
			win.blit(QTR_display, (60, 29))
			GameTime_display = myfont_score_num.render(displayTime, 1, RETRO_GOLD)
			win.blit(GameTime_display, (196, 29))

			# Weather condition badge
			cond_str = str(match_settings.weather)[:4].upper()
			win.blit(myfont_badge.render(cond_str, 1, (160, 210, 140)), (268, 33))

			# Home Team row (G, B, Total)
			win.blit(myfont_score_team.render(state.home.name[:14], 1, (240, 245, 255)), (22, 78))
			win.blit(myfont_score_num.render(str(state.home_goals), 1, (240, 245, 255)), (152, 78))
			win.blit(myfont_score_num.render(str(state.home_behinds), 1, (240, 245, 255)), (202, 78))
			win.blit(myfont_score_num.render(str(state.home_score), 1, RETRO_GOLD), (258, 78))

			# Away Team row (G, B, Total)
			win.blit(myfont_score_team.render(state.away.name[:14], 1, (255, 235, 235)), (22, 134))
			win.blit(myfont_score_num.render(str(state.away_goals), 1, (255, 235, 235)), (152, 134))
			win.blit(myfont_score_num.render(str(state.away_behinds), 1, (255, 235, 235)), (202, 134))
			win.blit(myfont_score_num.render(str(state.away_score), 1, RETRO_GOLD), (258, 134))

			# ── Live Match Leaders Panel ──────────────────────────────────
			draw_match_leaders(win)

			sim_game.GamePlayTime()
			if not getattr(sim_game, "_agent_logged_ms", False):
				# region agent log
				_agent_log(
					"engine.match_sim_running",
					"after_first_GamePlayTime",
					{"match_status": repr(globals().get("match_status", "__ABSENT__")), "QTR": state.qtr},
					"H4",
				)
				# endregion
				sim_game._agent_logged_ms = True

			if match_status == "In Progress":

				if state.action_type != "Run" and state.action_type != "Mark" and state.action_type != "Free Kick":
					if state.action_type == "Ball Up":
						Player.RuckContest()
					else:
						follower_involve = random.randint(1,5)
						if follower_involve == 1:
							Player.Follower()
						else:
							Player.UpdatePlayerInPossession()
							if not state.follow_with_ball:
								Player.UpdateOpponent()
							else:
								state.follow_with_ball = False

				if state.trans_type == "Contest":
					sim_game.GetConditions(match_settings.weather, state.trans_type)
					sim_game.Generate_Play_contest()
					#sim_game.comm_contest()
				elif state.trans_type == "Defending":
					sim_game.GetConditions(match_settings.weather, state.trans_type)
					sim_game.Generate_Play_defender()
					#sim_game.comm_defence()
				elif state.trans_type == "Carrying":
					sim_game.GetConditions(match_settings.weather, state.trans_type)
					sim_game.Generate_Play_ballCarrier()
					#sim_game.comm_carry()

				sim_game.NoSelfMark()

				sim_game.commentate()


				sim_game.GamePlayBallPos()

				Player.Interchange()

			pygame.time.delay(sim_game.simRunSpeedDelay)

			sim_game.map_play()
			# ── 8-Bit Commentary Box Display ─────────────────────────────
			comm_str = commentary if 'commentary' in globals() and commentary else "Game ready to commence..."
			if len(comm_str) > 72:
				words = comm_str.split()
				l1, l2 = "", ""
				for w in words:
					if len(l1) + len(w) + 1 <= 68 and not l2:
						l1 += (w + " ")
					else:
						l2 += (w + " ")
				win.blit(myfont_comm_text.render(l1.strip(), 1, (245, 240, 210)), (18, 356))
				win.blit(myfont_comm_text.render(l2.strip(), 1, (215, 210, 180)), (18, 372))
			else:
				win.blit(myfont_comm_text.render(comm_str, 1, (245, 240, 210)), (18, 364))

			sim_game.BallPosition()

			pygame.display.update()
			for event in pygame.event.get():
				if event.type == pygame.QUIT:
					pygame.quit()


def show_roster_error(message: str) -> None:
	"""Show the invalid roster until acknowledged; allow retry from the menu."""
	global run
	font = pygame.font.SysFont("Verdana", 17)
	lines, line = [], ""
	for char in " ".join(message.split()):
		if font.size(line + char)[0] > ScreenWidth - 80:
			lines.append(line)
			line = ""
		line += char
	lines.append(line)
	offset = 0
	while True:
		win.fill((25, 30, 25))
		win.blit(myfont_main.render("Cannot start match", True, Soft_Red), (40, 30))
		for i, text in enumerate(lines[offset:offset + 9]):
			win.blit(font.render(text, True, White), (40, 80 + i * 24))
		win.blit(font.render("Edit the roster, then select Play Footy again.", True, White), (40, 320))
		win.blit(font.render("Enter / Esc: back     Up / Down: scroll", True, White), (40, 350))
		pygame.display.update()
		for event in pygame.event.get():
			if event.type == pygame.QUIT:
				run = False
				return
			if event.type == pygame.KEYDOWN:
				if event.key in (pygame.K_RETURN, pygame.K_ESCAPE):
					return
				if event.key == pygame.K_DOWN:
					offset = min(max(0, len(lines) - 9), offset + 1)
				if event.key == pygame.K_UP:
					offset = max(0, offset - 1)
		clock.tick(30)


def show_skill_allocation_error(message: str) -> None:
	"""Show a branded, actionable error when a player breaks skill-budget rules."""
	global run, on_main_menu, instructions, instructions_page
	title_font = pygame.font.SysFont("Verdana", 28, bold=True)
	heading_font = pygame.font.SysFont("Verdana", 14, bold=True)
	body_font = pygame.font.SysFont("Consolas", 13)
	small_font = pygame.font.SysFont("Consolas", 11)

	# Wrap the player-specific validation message to fit its highlighted card.
	words = " ".join(message.split()).split(" ")
	message_lines, line = [], ""
	for word in words:
		candidate = f"{line} {word}".strip()
		if body_font.size(candidate)[0] > 540 and line:
			message_lines.append(line)
			line = word
		else:
			line = candidate
	if line:
		message_lines.append(line)

	while run:
		win.blit(start_bg, (0, 0))
		overlay = pygame.Surface((ScreenWidth, ScreenHeight), pygame.SRCALPHA)
		overlay.fill((8, 10, 5, 230))
		win.blit(overlay, (0, 0))

		# Header and warning badge use the same match-day palette as the guides.
		pygame.draw.circle(win, (190, 62, 42), (39, 39), 21)
		pygame.draw.circle(win, (255, 145, 90), (39, 39), 21, 2)
		bang = title_font.render("!", 1, RETRO_WHITE)
		win.blit(bang, (39 - bang.get_width() // 2, 39 - bang.get_height() // 2))
		win.blit(title_font.render("CHECK PLAYER SKILLS", 1, MENU_AMBER), (73, 18))
		win.blit(myfont_menu_tag.render("The match cannot start until this roster entry is fixed.", 1, MENU_TAGLINE), (75, 51))
		pygame.draw.line(win, MENU_BORDER, (18, 74), (622, 74), 2)

		pygame.draw.rect(win, (53, 20, 16), (28, 89, 584, 82))
		pygame.draw.rect(win, (210, 82, 55), (28, 89, 584, 82), 2)
		win.blit(heading_font.render("WHAT NEEDS ATTENTION", 1, (255, 174, 120)), (43, 101))
		for i, text in enumerate(message_lines[:2]):
			win.blit(body_font.render(text, 1, RETRO_WHITE), (43, 127 + i * 19))

		pygame.draw.rect(win, (20, 23, 13), (28, 184, 584, 105))
		pygame.draw.rect(win, (86, 91, 48), (28, 184, 584, 105), 1)
		win.blit(heading_font.render("SKILL ALLOCATION RULES", 1, MENU_AMBER_BRIGHT), (43, 196))
		rules = [
			"• Use zero or positive whole numbers for every skill.",
			"• STR + SPD + AGI + SKL + END + PRS + AUR must total 100 or less.",
			"• Blank skill cells use the default allocation: 15 each, plus 10 Aura.",
		]
		for i, rule in enumerate(rules):
			win.blit(small_font.render(rule, 1, RETRO_WHITE), (43, 221 + i * 20))

		win.blit(small_font.render("Edit TeamSelection.csv, save it, then choose Play Footy again.", 1, MENU_TAGLINE), (43, 305))

		mx, my = pygame.mouse.get_pos()
		back_rect = (95, 337, 210, 42)
		guide_rect = (335, 337, 210, 42)
		back_hover = back_rect[0] + back_rect[2] > mx > back_rect[0] and back_rect[1] + back_rect[3] > my > back_rect[1]
		guide_hover = guide_rect[0] + guide_rect[2] > mx > guide_rect[0] and guide_rect[1] + guide_rect[3] > my > guide_rect[1]
		_draw_menu_button(win, back_rect, MENU_OLIVE_HOVER if back_hover else MENU_OLIVE, MENU_BORDER)
		_draw_menu_button(win, guide_rect, MENU_OLIVE_HOVER if guide_hover else MENU_OLIVE, MENU_BORDER)
		back_label = myfont_menu_btn.render("< Back to Menu", 1, MENU_AMBER_BRIGHT if back_hover else MENU_AMBER)
		guide_label = myfont_menu_btn.render("View Skill Guide >", 1, MENU_AMBER_BRIGHT if guide_hover else MENU_AMBER)
		win.blit(back_label, (back_rect[0] + (back_rect[2] - back_label.get_width()) // 2,
		                      back_rect[1] + (back_rect[3] - back_label.get_height()) // 2))
		win.blit(guide_label, (guide_rect[0] + (guide_rect[2] - guide_label.get_width()) // 2,
		                       guide_rect[1] + (guide_rect[3] - guide_label.get_height()) // 2))
		pygame.display.update()

		for event in pygame.event.get():
			if event.type == pygame.QUIT:
				run = False
				return
			if event.type == pygame.KEYDOWN and event.key in (pygame.K_RETURN, pygame.K_ESCAPE):
				on_main_menu = True
				return
			if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
				if back_hover:
					on_main_menu = True
					return
				if guide_hover:
					on_main_menu = False
					instructions = True
					instructions_page = 2
					return
		clock.tick(30)


def main() -> None:
	"""Main pygame loop: menu, match simulation, post-match stats, and settings."""
	# mouse/click must be module-level: UI helpers read them without receiving arguments.
	global run, on_main_menu, playing_match, settings, instructions, instructions_page, post_match, mouse, click
	run = True
	on_main_menu = True
	playing_match = False
	settings = False
	instructions = False
	instructions_page = 1
	post_match = False

	while run:
		pygame.event.get()

		clock.tick(20)

		mouse = pygame.mouse.get_pos()
		click = pygame.mouse.get_pressed()

		if on_main_menu:
			main_menu()

		elif playing_match:
			sim_game.match_sim_running()

		elif post_match:
			ShowPostMatchScreen()

		elif settings:
			open_settings()

		elif instructions:
			open_instructions()

		for event in pygame.event.get():
			if event.type == pygame.QUIT:
				run = False
	pygame.quit()
