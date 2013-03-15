import pygame
import json
from mm.common.scheduling import Scheduler
from mm.common.world import World
from mm.client.rendering import Renderer
from mm.client.hud import Hud


class MenuButton(object):
    def __init__(self, button_id, label, font, x, y, w, h):
        self.button_id = button_id
        self.label = label
        self.text = font.render(label, True, (32, 32, 32))
        self.bounds = pygame.rect.Rect(x, y, w, h)

    def set_position(self, (x, y)):
        self.bounds.topleft = (y, x)

    def draw(self, screen, highlight=False):
        color = (32, 32, 32) if highlight else (192, 192, 192)
        pygame.draw.rect(screen, color, self.bounds, 4)
        # FIXME: -4 is a font fix, remove if necessary.
        rect = self.text.get_rect(
            centerx=self.bounds.centerx, centery=self.bounds.centery - 4)
        screen.blit(self.text, rect)

    def is_intersecting(self, mouse_pos):
        return self.bounds.collidepoint(mouse_pos)


class MenuButtonTypes(object):
    CONTINUE = 0
    NEW_GAME = 1
    QUIT = 2


class MenuState(object):
    def __init__(self, game, screen_width, screen_height, ingame=False):
        self.game = game
        self.font = pygame.font.Font('res/font.ttf', 36)

        button_descs = [
            (MenuButtonTypes.NEW_GAME, 'NEW GAME'),
            (MenuButtonTypes.QUIT, 'QUIT')]

        if ingame:
            button_descs.append((MenuButtonTypes.CONTINUE, 'CONTINUE'))

        button_width = screen_width // 4
        button_height = 64

        padding = 8

        total_menu_width = button_width
        total_menu_height = (button_height + padding) * len(button_descs)

        x_pos = (screen_width - total_menu_width) // 2
        y_pos = (screen_height - total_menu_height) // 2

        self.buttons = []

        for (button_type, label) in button_descs:
            button = MenuButton(
                button_type, label, self.font, x_pos, y_pos, button_width,
                button_height)
            self.buttons.append(button)
            y_pos += button_height + padding

    def on_event(self, event):
        if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            for button in self.buttons:
                if button.is_intersecting(pygame.mouse.get_pos()):
                    if button.button_id == MenuButtonTypes.NEW_GAME:
                        self.game.new_game()
                    elif button.button_id == MenuButtonTypes.CONTINUE:
                        self.game.go_back()
                    elif button.button_id == MenuButtonTypes.QUIT:
                        self.game.quit()

    def update(self, screen, frame_time):
        screen.fill((255, 255, 255))
        mouse_pos = pygame.mouse.get_pos()
        for button in self.buttons:
            button.draw(screen, highlight=button.is_intersecting(mouse_pos))


class User(object):
    def __init__(self, actor_store):
        self.score = 0
        self.max_simultaneous_heroes = 0
        self.current_hero_count = 0
        self.actor_store = actor_store
        self.available_actor_types = [
            name for name in self.actor_store.get_all_names()
            if name != 'hero']
        self.selected_actor_type = self.available_actor_types[0]

    def set_selected_actor_type(self, actor_type):
        if actor_type in self.available_actor_types:
            self.selected_actor_type = actor_type

    def get_available_actor_types(self):
        return self.available_actor_types

    def get_selected_actor_type(self):
        return self.selected_actor_type

    def on_loot(self, loot_value):
        self.score += loot_value // 10

    def on_hero_death(self, p):
        self.score -= 10

    def on_hero_spawned(self, p):
        self.current_hero_count += 1
        if self.current_hero_count > self.max_simultaneous_heroes:
            self.current_hero_count = self.max_simultaneous_heroes

    def on_hero_leave(self, p):
        self.current_hero_count -= 1


class PlayState(object):
    def __init__(self, game, screen_width, screen_height):
        actor_store = ActorStore('actors.json')
        self.game = game
        self.scheduler = Scheduler()
        self.renderer = Renderer()
        self.user = User(actor_store)
        self.world = World(
            screen_width, screen_height, self.user, actor_store,
            self.renderer, self.scheduler)
        self.hud = Hud(self.user, actor_store, self.world, self.renderer)
        self.hud.generate_mob_icons(screen_width, screen_height)

    def on_event(self, event):
        self.hud.on_event(event)

    def update(self, screen, frame_time):
        self.scheduler.update(frame_time)
        screen.fill((255, 255, 255))
        self.world.update(screen, frame_time)
        self.hud.update(screen, frame_time)
        self.renderer.update(screen, frame_time)


class Session(object):
    def __init__(self, screen):
        self.screen = screen
        self.is_running = True
        self.current_state = None
        self.previous_state = None
        self.ingame = False

    def is_running(self):
        return self.is_running

    def menu(self):
        self.previous_state = self.current_state
        self.current_state = MenuState(
            self, self.screen.get_width(), self.screen.get_height(),
            ingame=self.ingame)

    def new_game(self):
        self.ingame = True
        self.previous_state = MenuState(
            self, self.screen.get_width(), self.screen.get_height(),
            ingame=self.ingame)
        self.current_state = PlayState(
            self, self.screen.get_width(), self.screen.get_height())

    def go_back(self):
        old = self.current_state
        self.current_state = self.previous_state
        self.previous_state = old

    def quit(self):
        self.is_running = False

    def on_event(self, event):
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self.go_back()
        else:
            self.current_state.on_event(event)

    def update(self, screen, frame_time):
        self.screen = screen
        self.current_state.update(screen, frame_time)
