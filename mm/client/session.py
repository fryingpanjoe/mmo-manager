import logging
import pygame

from mm.common.scheduling import Scheduler
from mm.common.world import World, ActorStore
from mm.common.networking import Client, DEFAULT_NETWORK_PORT
from mm.common.events import *
from mm.client.rendering import Renderer
from mm.client.hud import Hud
from mm.client.client_world import ClientWorld

LOG = logging.getLogger(__name__)


class MenuButton(object):
    def __init__(self, button_id, label, font, x, y, w, h):
        self.button_id = button_id
        self.label = label
        self.text = font.render(label, True, (32, 32, 32))
        self.bounds = pygame.rect.Rect(x, y, w, h)

    def set_position(self, p):
        x, y = p
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
    DISCONNECT = 1
    SINGLEPLAYER = 2
    MULTIPLAYER = 3
    QUIT = 4


class MenuState(object):
    def __init__(self, session, screen_width, screen_height, playing=False,
                 multiplayer=False):
        self.session = session
        self.font = pygame.font.Font('res/font.ttf', 36)

        button_descs = [
            (MenuButtonTypes.SINGLEPLAYER, 'SINGLEPLAYER'),
            (MenuButtonTypes.MULTIPLAYER, 'MULTIPLAYER'),
            (MenuButtonTypes.QUIT, 'QUIT')]

        if multiplayer:
            button_descs.append((MenuButtonTypes.DISCONNECT, 'DISCONNECT'))

        if playing:
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
                    if button.button_id == MenuButtonTypes.SINGLEPLAYER:
                        self.session.singleplayer_game()
                    if button.button_id == MenuButtonTypes.MULTIPLAYER:
                        self.session.multiplayer_game(
                            'localhost', DEFAULT_NETWORK_PORT)
                    elif button.button_id == MenuButtonTypes.CONTINUE:
                        self.session.return_to_game()
                    elif button.button_id == MenuButtonTypes.QUIT:
                        self.session.quit()

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


def event_debug_printer(event):
    LOG.info('event: ' + str(event))


class MultiplayerState(object):
    def __init__(self, session, client, event_distributor, scheduler, renderer,
                 actor_store, screen_width, screen_height):
        self.session = session
        self.client = client
        self.event_distributor = event_distributor
        self.scheduler = scheduler
        self.renderer = renderer
        self.actor_store = actor_store

        self.user = User(self.actor_store)

        self.hud = Hud(
            self.event_distributor, self.user, self.actor_store, self.renderer)
        self.hud.generate_mob_icons(screen_width, screen_height)

        self.client_world = ClientWorld(
            self.event_distributor, self.scheduler, self.renderer,
            self.actor_store)

        self.event_distributor.add_handler(
            self.on_client_disconnected, ClientDisconnectedEvent)
        self.event_distributor.add_handler(
            self.on_player_spawn_mob, PlayerActionSpawnMobEvent)

        self.event_distributor.add_handler(
            event_debug_printer, ALL_EVENT_TYPES)

    def on_event(self, event):
        self.hud.on_event(event)

    def update(self, screen, frame_time):
        self.client.read_from_server()
        self.scheduler.update(frame_time)
        screen.fill((255, 255, 255))
        self.client_world.update(screen, frame_time)
        self.hud.update(screen, frame_time)
        self.event_distributor.update()
        self.renderer.update(screen, frame_time)
        if self.client.is_connected():
            self.client.write_to_server()

    def on_client_disconnected(self, event):
        if event.client_id == 0:
            LOG.info('Disconnected from server')
            self.session.disconnect()
        else:
            LOG.info('Client %d disconnected', event.client_id)

    def on_disconnected_from_server(self):
        if self.client.is_connected():
            self.client.disconnect()

    def on_player_spawn_mob(self, event):
        LOG.info('Player spawn mob %s at %r', event.actor_type, event.pos)
        self.client.send_event(event)

"""
class SingleplayerState(object):
    def __init__(self, game, screen_width, screen_height):
        actor_store = ActorStore('actors.json')
        self.session = game
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
"""

class Session(object):
    def __init__(self, screen):
        self.screen = screen
        self.is_running = True
        self.menu_state = None
        self.play_state = None
        self.current_state = None

    def menu(self):
        if self.play_state:
            playing = True
            multiplayer = isinstance(self.play_state, MultiplayerState)
        else:
            playing = False
            multiplayer = False

        self.menu_state = MenuState(
            self, self.screen.get_width(), self.screen.get_height(),
            playing=playing, multiplayer=multiplayer)

        self.current_state = self.menu_state

    def singleplayer_game(self):
        pass

    def multiplayer_game(self, address, port):
        event_distributor = EventDistributor()
        client = Client(event_distributor)

        if client.connect(address, port):
            scheduler = Scheduler()
            renderer = Renderer()
            actor_store = ActorStore('actors.json')

            self.play_state = MultiplayerState(
                self, client, event_distributor, scheduler, renderer,
                actor_store, self.screen.get_width(), self.screen.get_height())

            self.current_state = self.play_state

    def return_to_game(self):
        if self.play_state:
            self.current_state = self.play_state

    def go_back(self):
        if self.current_state == self.play_state:
            self.current_state = self.menu_state
        else:
            self.current_state = self.play_state

    def disconnect(self):
        if self.play_state:
            self.play_state.on_disconnected_from_server()
            self.play_state = None

        self.menu()

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
