import pygame
import json
from scheduling import Scheduler
from rendering import Renderer
from hud import Hud
from world import World
from menu import MenuState


class EntityStore(object):
    def __init__(self, filename):
        self.entity_types = json.load(open(filename, 'r'))

    def get_params(self, mob):
        return self.entity_types[mob]

    def get_all_names(self):
        return self.entity_types.keys()


class User(object):
    def __init__(self, entity_store):
        self.score = 0
        self.max_simultaneous_players = 0
        self.current_player_count = 0
        self.entity_store = entity_store
        self.available_mob_names = [
            name for name in self.entity_store.get_all_names()
            if name != 'player']
        self.selected_mob_name = self.available_mob_names[0]

    def add_available_mob_name(self, mob_name):
        self.available_mob_names.append(mob_name)

    def set_selected_mob_name(self, mob_name):
        if mob_name in self.available_mob_names:
            self.selected_mob_name = mob_name

    def get_available_mob_names(self):
        return self.available_mob_names

    def get_selected_mob_name(self):
        return self.selected_mob_name

    def on_loot(self, loot_value):
        self.score += loot_value // 10

    def on_player_death(self, p):
        self.score -= 10

    def on_player_enter(self, p):
        self.current_player_count += 1
        if self.current_player_count > self.max_simultaneous_players:
            self.current_player_count = self.max_simultaneous_players

    def on_player_leave(self, p):
        self.current_player_count -= 1


class PlayState(object):
    def __init__(self, game, screen_width, screen_height):
        entity_store = EntityStore('entities.json')
        self.game = game
        self.scheduler = Scheduler()
        self.renderer = Renderer()
        self.user = User(entity_store)
        self.world = World(
            screen_width, screen_height, self.user, entity_store,
            self.renderer, self.scheduler)
        self.hud = Hud(self.user, entity_store, self.world, self.renderer)
        self.hud.generate_mob_icons(screen_width, screen_height)

    def on_event(self, event):
        self.hud.on_event(event)

    def update(self, screen, frame_time):
        self.scheduler.update(frame_time)
        screen.fill((255, 255, 255))
        self.world.update(screen, frame_time)
        self.hud.update(screen, frame_time)
        self.renderer.update(screen, frame_time)


class Game(object):
    def __init__(self, screen):
        self.screen = screen
        self.running = True
        self.current_state = None
        self.previous_state = None
        self.in_game = False

    def menu(self):
        self.previous_state = self.current_state
        self.current_state = MenuState(
            self, self.screen.get_width(), self.screen.get_height(),
            in_game=self.in_game)

    def new_game(self):
        self.in_game = True
        self.previous_state = MenuState(
            self, self.screen.get_width(), self.screen.get_height(),
            in_game=self.in_game)
        self.current_state = PlayState(
            self, self.screen.get_width(), self.screen.get_height())

    def go_back(self):
        old = self.current_state
        self.current_state = self.previous_state
        self.previous_state = old

    def quit(self):
        self.running = False

    def on_event(self, event):
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self.go_back()
        else:
            self.current_state.on_event(event)

    def update(self, screen, frame_time):
        self.screen = screen
        self.current_state.update(screen, frame_time)
