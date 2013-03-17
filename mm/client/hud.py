import pygame

from thirdparty.vec2 import vec2

from mm.client.client_world import ClientActor
from mm.common.world import Actor
from mm.common.events import PlayerActionSpawnMobEvent


class MobIcon(object):
    WIDTH = 32
    HEIGHT = 32
    PADDING = 4

    def __init__(self, client_actor, pos):
        self.client_actor = client_actor
        self.bounds = pygame.Rect(pos, (MobIcon.WIDTH, MobIcon.HEIGHT))

    def draw(self, screen, selected):
        self.client_actor.actor.pos = vec2(self.bounds.centerx, self.bounds.centery)
        self.client_actor.draw(screen, True)

        if selected:
            border_color = (128, 128, 128)
        else:
            border_color = (224, 224, 224)

        pygame.draw.rect(screen, border_color, self.bounds, 2)

        if self.client_actor.actor.is_hero:
            other_rect = self.bounds.inflate(-8, -8)
            pygame.draw.rect(screen, (160, 160, 255), other_rect, 2)

    def get_actor_type(self):
        return self.client_actor.actor.actor_type

    def intersects(self, mouse_pos):
        return self.bounds.collidepoint(mouse_pos)

    def get_label(self):
        return self.client_actor.actor.actor_type


class Hud(object):
    def __init__(self, event_distributor, user, actor_store, renderer):
        self.event_distributor = event_distributor
        self.user = user
        self.actor_store = actor_store
        self.renderer = renderer
        self.coin_icon = self.renderer.load_image('coins.png')
        self.mob_icons = []

    def generate_mob_icons(self, screen_width, screen_height):
        icon_width = MobIcon.WIDTH
        icon_height = MobIcon.HEIGHT

        available_actor_types = self.user.get_available_actor_types()

        x = (screen_width - icon_width * len(available_actor_types)) // 2
        y = (screen_height - icon_height - 10)

        self.mob_icons = []

        for actor_type in available_actor_types:
            self.mob_icons.append(self.create_icon_for_mob(actor_type, (x, y)))
            x += icon_width + MobIcon.PADDING

    def create_icon_for_mob(self, actor_type, icon_pos):
        params = self.actor_store.get_params(actor_type)
        actor = Actor.from_params(
            self.actor_store.get_params(actor_type), 0, None)
        client_actor = ClientActor(actor, params, self.renderer)
        return MobIcon(client_actor, icon_pos)

    def find_icon_at(self, mouse_pos):
        for icon in self.mob_icons:
            if icon.intersects(mouse_pos):
                return icon
        return None

    def on_event(self, event):
        if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            clicked_icon = self.find_icon_at(pygame.mouse.get_pos())
            if clicked_icon:
                self.user.set_selected_actor_type(clicked_icon.get_actor_type())
            else:
                self.spawn_actor(
                    self.user.get_selected_actor_type(),
                    vec2(pygame.mouse.get_pos()))
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 2:
            self.spawn_actor('hero', vec2(pygame.mouse.get_pos()))

    def spawn_actor(self, actor_type, pos):
        self.event_distributor.post(PlayerActionSpawnMobEvent(actor_type, pos))

    def update(self, screen, frame_time):
        # compute claimed and unclaimed loot
        claimed_loot_value = 0
        unclaimed_loot_value = 0
        #for actor in self.world.actors:
        #    if not actor.is_dead():
        #        if actor.is_hero:
        #            claimed_loot_value += actor.loot_value
        #        else:
        #            unclaimed_loot_value += actor.loot_value

        # draw loot stats
        screen.blit(self.coin_icon, (10, 10))
        self.renderer.print_text(
            (34, 6), '%d (%d)' % (claimed_loot_value, unclaimed_loot_value),
            (255, 192, 0))

        # draw mob icons
        for icon in self.mob_icons:
            icon.draw(
                screen,
                self.user.get_selected_actor_type() == icon.get_actor_type())
            if icon.intersects(pygame.mouse.get_pos()):
                self.renderer.print_text(
                    (icon.bounds.centerx, icon.bounds.top - 10),
                    icon.get_label(), (64, 64, 64), True)
