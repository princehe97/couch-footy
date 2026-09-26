"""Pygame team selection and library actions, before a match starts."""
from dataclasses import replace

import pygame

from qooty import match_settings
from qooty.constants import WINDOW_SCALE
from qooty.paths import PROJECT_ROOT
from qooty.player_attributes import MAX_TOTAL_POINTS, STAT_NAMES
from qooty.team_library import TeamLibrary, match_roster, team_from_roster
from qooty.team_selection import load_roster

BACKGROUND = (14, 18, 11)
PANEL = (29, 36, 22)
GOLD = (255, 210, 50)
TEXT = (238, 234, 214)
MUTED = (184, 188, 163)


class SetupClosed(Exception):
    """The application window was closed during setup."""


class TeamSetup:
    def __init__(self, surface, library=None):
        self.surface = surface
        self.library = library or TeamLibrary()
        self.font = pygame.font.SysFont('Consolas', 12)
        self.small = pygame.font.SysFont('Consolas', 10)
        self.title = pygame.font.SysFont('Verdana', 21, bold=True)
        self.clock = pygame.time.Clock()
        self.buttons = []
        self.teams = []
        self.errors = []
        self.selected = [None, None]
        self.pages = [0, 0]
        self.metadata = [match_settings.season_number, match_settings.round_number, match_settings.match_id]
        self.csv_error = ''
        self.reload_csv(initial=True)
        self.refresh()

    def refresh(self):
        self.teams, self.errors = self.library.list_teams()

    def reload_csv(self, initial=False):
        try:
            roster = load_roster(PROJECT_ROOT)
            self.selected = [team_from_roster(roster, side) for side in ('home', 'away')]
            self.metadata = [roster.season, roster.round, roster.match_id]
            self.pages = [0, 0]
            self.csv_error = ''
        except (OSError, ValueError) as exc:
            self.csv_error = f'CSV could not be loaded: {exc}'
            if not initial:
                self.message(self.csv_error)

    def text(self, text, x, y, width=600, color=TEXT, font=None):
        font = font or self.font
        text = str(text)
        while text and font.size(text)[0] > width:
            text = text[:-4] + '...' if len(text) > 4 else text[:-1]
        self.surface.blit(font.render(text, True, color), (x, y))

    def begin(self, title):
        self.buttons = []
        self.surface.fill(BACKGROUND)
        self.text(title, 16, 10, font=self.title, color=GOLD)

    def button(self, label, rect, action, enabled=True):
        rect = pygame.Rect(rect)
        pygame.draw.rect(self.surface, PANEL if enabled else BACKGROUND, rect, border_radius=4)
        pygame.draw.rect(self.surface, GOLD if enabled else MUTED, rect, 1, border_radius=4)
        self.text(label, rect.x + 7, rect.y + 7, rect.width - 14, GOLD if enabled else MUTED)
        if enabled:
            self.buttons.append((rect, action))

    def events(self):
        pygame.display.update()
        self.clock.tick(30)
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                raise SetupClosed()
            yield event

    def action(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            point = (event.pos[0] / WINDOW_SCALE, event.pos[1] / WINDOW_SCALE)
            for rect, action in self.buttons:
                if rect.collidepoint(point):
                    return action
        return None

    def wrapped(self, message, width=585):
        lines = []
        # Split long words too, so filenames and validation errors remain readable.
        line = ''
        for char in str(message):
            if char == '\n' or self.font.size(line + char)[0] > width:
                lines.append(line)
                line = ''
            if char != '\n':
                line += char
        if line:
            lines.append(line)
        return lines

    def message(self, message, confirm=False):
        lines = self.wrapped(message)
        page = 0
        while True:
            self.begin('Confirm update' if confirm else 'Team library')
            for i, line in enumerate(lines[page * 15:(page + 1) * 15]):
                self.text(line, 22, 55 + i * 18)
            if len(lines) > 15:
                self.button('More', (22, 350, 80, 30), 'more')
            self.button('Cancel' if confirm else 'OK', (370, 350, 100, 30), 'cancel')
            if confirm:
                self.button('Update team', (485, 350, 135, 30), 'confirm')
            for event in self.events():
                action = self.action(event)
                if action == 'more':
                    page = (page + 1) % ((len(lines) + 14) // 15)
                if action in ('cancel', 'confirm'):
                    return action == 'confirm'
                if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    return False

    def pick(self, title):
        self.refresh()
        page = 0
        while True:
            self.begin(title)
            self.text('Select a team; review its players on the setup screen.', 18, 43, color=MUTED)
            if not self.teams:
                self.text('No saved teams yet. Load CSV teams, then choose Save as new.', 18, 100)
            for i, team in enumerate(self.teams[page * 7:(page + 1) * 7]):
                self.button(f'[{team.team_id}]  {team.name}', (18, 70 + i * 36, 604, 30), ('team', team))
            self.button('<', (18, 350, 40, 30), 'prev', page > 0)
            self.text(f'Page {page + 1}', 68, 359)
            self.button('>', (132, 350, 40, 30), 'next', (page + 1) * 7 < len(self.teams))
            self.button(f'File issues ({len(self.errors)})', (190, 350, 180, 30), 'issues', bool(self.errors))
            self.button('Cancel', (510, 350, 110, 30), 'cancel')
            for event in self.events():
                action = self.action(event)
                if isinstance(action, tuple):
                    return action[1]
                if action == 'prev': page -= 1
                if action == 'next': page += 1
                if action == 'issues': self.message('\n\n'.join(self.errors))
                if action == 'cancel' or (event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE):
                    return None

    def save(self, side, update=False):
        team = self.selected[side]
        target = None
        if update:
            target = self.pick('Choose the saved team to update')
            if target is None:
                return
            if not self.message(f'Replace {target.name} [{target.team_id}] with the currently selected '
                                f'{team.name}? All 20 players, positions and allocations will be replaced.', confirm=True):
                return
        try:
            self.selected[side] = self.library.save(team, update_id=target.team_id if target else None)
        except (OSError, ValueError) as exc:
            self.message(f'Team was not saved. You can still play with this team.\n\n{exc}')
            return
        self.refresh()
        self.message(f'Saved {team.name}. It will be available under Saved teams next time you open Couch Footy.')

    def edit(self, side):
        original = self.selected[side]
        draft = original
        selected, page, swap = 0, 0, None
        focus, select_all = None, False
        name = draft.players[selected].name
        error = ''

        def commit_name():
            nonlocal draft, error
            players = list(draft.players)
            players[selected] = replace(players[selected], name=name.strip())
            candidate = replace(draft, players=tuple(players))
            try:
                candidate.validate()
            except ValueError as exc:
                error = str(exc)
                return False
            draft, error = candidate, ''
            return True

        while True:
            self.begin('EDIT TEAM')
            self.text('Team name', 18, 47, color=MUTED)
            self.button(draft.name + ('|' if focus == 'team' else ''),
                        (105, 39, 515, 28), ('focus', 'team'))
            self.text('Choose a player' if swap is None else 'Choose a player to swap with', 18, 77, 295, GOLD)
            for row, player in enumerate(draft.players[page * 10:(page + 1) * 10]):
                index = page * 10 + row
                self.button(f'{">" if index == selected else " "} {player.position:5} {player.name}',
                            (18, 97 + row * 22, 290, 21), ('player', index))
            self.button('<', (18, 322, 35, 27), ('page', -1), page > 0)
            self.text(f'Players {page * 10 + 1}-{page * 10 + 10} / 20', 63, 330, 200)
            self.button('>', (273, 322, 35, 27), ('page', 1), page < 1)
            player = draft.players[selected]
            self.text(f'{player.position} - player name', 325, 77, 295, MUTED)
            self.button(name + ('|' if focus == 'player' else ''), (325, 97, 295, 28), ('focus', 'player'))
            for row, stat in enumerate(STAT_NAMES):
                y = 132 + row * 23
                value = getattr(player.attributes, stat)
                self.text(stat.capitalize(), 325, y + 5, 135)
                self.button('-', (465, y, 32, 22), ('stat', (stat, -1)), value > 0)
                self.text(value, 505, y + 5, 45)
                self.button('+', (558, y, 32, 22), ('stat', (stat, 1)),
                            player.attributes.total() < MAX_TOTAL_POINTS)
            self.text(f'Points: {player.attributes.total()} / {MAX_TOTAL_POINTS}', 325, 298, 290, GOLD)
            self.button('Cancel swap' if swap is not None else 'Swap position...',
                        (325, 322, 295, 27), ('swap', None))
            self.text(error or 'Click a name to type; Ctrl+A selects all. Reduce points before adding.',
                      18, 352, 604, GOLD if error else MUTED, self.small)
            self.button('Cancel', (18, 370, 100, 27), ('cancel', None))
            self.button('Save changes' if original.team_id else 'Apply changes',
                        (465, 370, 155, 27), ('save', None))
            for event in self.events():
                action = self.action(event)
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        return
                    if focus is not None:
                        current = draft.name if focus == 'team' else name
                        if event.key == pygame.K_a and getattr(event, 'mod', 0) & pygame.KMOD_CTRL:
                            select_all = True
                            continue
                        if event.key == pygame.K_BACKSPACE:
                            current = '' if select_all else current[:-1]
                        elif event.unicode and event.unicode.isprintable():
                            current = event.unicode if select_all else current + event.unicode
                        else:
                            continue
                        select_all = False
                        if focus == 'team':
                            draft = replace(draft, name=current)
                        else:
                            name = current
                if action is None:
                    continue
                operation, value = action
                if operation == 'cancel':
                    return
                if operation == 'focus':
                    focus, select_all = value, False
                    continue
                focus, select_all = None, False
                if operation == 'page':
                    page += value
                if operation == 'stat':
                    stat, delta = value
                    attributes = replace(player.attributes, **{stat: getattr(player.attributes, stat) + delta})
                    try:
                        attributes.validate()
                    except ValueError as exc:
                        error = str(exc)
                        continue
                    players = list(draft.players)
                    players[selected] = replace(players[selected], attributes=attributes)
                    draft = replace(draft, players=tuple(players))
                    player = draft.players[selected]
                if operation == 'swap':
                    if swap is not None:
                        swap = None
                    elif commit_name():
                        swap = selected
                if operation == 'player' and commit_name():
                    if swap is not None:
                        players = list(draft.players)
                        first, second = players[swap], players[value]
                        players[swap] = replace(second, position=first.position)
                        players[value] = replace(first, position=second.position)
                        draft = replace(draft, players=tuple(players))
                        swap = None
                    selected = value
                    player = draft.players[selected]
                    name = player.name
                if operation == 'save' and commit_name():
                    try:
                        if original.team_id:
                            draft = self.library.save(draft, update_id=original.team_id)
                    except (OSError, ValueError) as exc:
                        error = f'Not saved: {exc}'
                        continue
                    self.selected[side] = draft
                    self.refresh()
                    return

    def run(self):
        focus = None
        while True:
            self.begin('MATCH TEAMS')
            self.button('Reload CSV', (492, 8, 132, 30), 'reload')
            fields = []
            for i, label in enumerate(('Season', 'Round', 'Match ID')):
                x = 18 + i * 204
                self.text(label, x, 49, color=MUTED)
                rect = pygame.Rect(x + 59, 42, 137, 27)
                pygame.draw.rect(self.surface, GOLD if focus == i else MUTED, rect, 1)
                self.text(self.metadata[i] + ('|' if focus == i else ''), x + 64, 49, 127)
                fields.append(rect)
            for side, label in enumerate(('HOME', 'AWAY')):
                x = 18 + side * 312
                team = self.selected[side]
                self.text(label, x, 81, color=GOLD)
                self.button('Edit', (x + 65, 75, 80, 28), ('edit', side), bool(team))
                self.button('Saved teams', (x + 156, 75, 138, 28), ('pick', side))
                self.text(team.name if team else 'Choose a team or reload CSV', x, 111, 294)
                self.text(f'Saved: {team.team_id[:12]}' if team and team.team_id else 'From CSV / not saved', x, 128, 294, MUTED, self.small)
                if team:
                    for row, player in enumerate(team.players[self.pages[side] * 5:(self.pages[side] + 1) * 5]):
                        y = 150 + row * 26
                        self.text(f'{player.position:5} {player.name}', x, y, 294)
                        values = ' '.join(f'{label}:{getattr(player.attributes, stat)}' for label, stat in
                                          zip(('S', 'Sp', 'Ag', 'Sk', 'E', 'P', 'Au'), STAT_NAMES))
                        self.text(values, x, y + 13, 294, MUTED, self.small)
                self.button('<', (x, 284, 34, 26), ('prev', side), bool(team))
                self.text(f'Players {self.pages[side] * 5 + 1}-{self.pages[side] * 5 + 5} / 20', x + 43, 291, 200, MUTED)
                self.button('>', (x + 260, 284, 34, 26), ('next', side), bool(team))
                self.button('Save as new', (x, 318, 140, 28), ('save', side), bool(team))
                self.button('Update saved...', (x + 150, 318, 144, 28), ('update', side), bool(team and self.teams))
            self.button('Back', (18, 360, 76, 29), 'back')
            issues = ([self.csv_error] if self.csv_error else []) + self.errors
            self.button(f'File issues ({len(issues)})', (106, 360, 161, 29), 'issues', bool(issues))
            self.text('S/Sp/Ag/Sk/E/P/Au = skills', 277, 370, 210, MUTED, self.small)
            self.button('Start match', (492, 360, 132, 29), 'start', all(self.selected))
            for event in self.events():
                action = self.action(event)
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    point = (event.pos[0] / WINDOW_SCALE, event.pos[1] / WINDOW_SCALE)
                    focus = next((i for i, rect in enumerate(fields) if rect.collidepoint(point)), None)
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE: return None
                    if focus is not None:
                        if event.key == pygame.K_BACKSPACE:
                            self.metadata[focus] = self.metadata[focus][:-1]
                        elif event.unicode.isprintable() and len(self.metadata[focus]) < 48:
                            self.metadata[focus] += event.unicode
                if action == 'back': return None
                if action == 'reload': self.reload_csv()
                if action == 'issues': self.message('\n\n'.join(issues))
                if action == 'start':
                    try:
                        return match_roster(*self.selected, *(value.strip() or '0' for value in self.metadata))
                    except ValueError as exc:
                        self.message(str(exc))
                if isinstance(action, tuple):
                    operation, side = action
                    if operation == 'pick':
                        team = self.pick(f'Choose {("home", "away")[side]} team')
                        if team:
                            self.selected[side] = team
                            self.pages[side] = 0
                    if operation == 'prev': self.pages[side] = (self.pages[side] - 1) % 4
                    if operation == 'next': self.pages[side] = (self.pages[side] + 1) % 4
                    if operation in ('save', 'update'): self.save(side, operation == 'update')
                    if operation == 'edit': self.edit(side)
