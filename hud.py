import pygame
from vec2 import vec2
from world import Actor


class MobIcon(object):
    WIDTH = 32
    HEIGHT = 32
    PADDING = 4

    def __init__(self, actor, pos):
        self.actor = actor
        self.bounds = pygame.Rect(pos, (MobIcon.WIDTH, MobIcon.HEIGHT))

    def draw(self, screen, selected):
        self.actor.pos = vec2(self.bounds.centerx, self.bounds.centery)
        self.actor.draw(screen, True)

        pygame.draw.rect(screen, (128, 128, 128) if selected else (224, 224, 224), self.bounds, 2)

        if self.actor.is_player:
            other_rect = self.bounds.inflate(-8, -8)
            pygame.draw.rect(screen, (160, 160, 255), other_rect, 2)

    def get_mob_type(self):
        return self.actor.type

    def intersects(self, mouse_pos):
        return self.bounds.collidepoint(mouse_pos)

    def get_label(self):
        return self.actor.type


class Hud(object):
    def __init__(self, user, mob_store, world, rendering):
        self.user = user
        self.mob_store = mob_store
        self.world = world
        self.rendering = rendering
        self.mob_icons = []
        self.coin_icon = self.rendering.load_image('coins.png')

    def generate_mob_icons(self, screen_width, screen_height):
        self.mob_icons = []
        icon_width = MobIcon.WIDTH
        icon_height = MobIcon.HEIGHT
        available_mob_names = self.user.get_available_mob_names()
        x = (screen_width - icon_width * len(available_mob_names)) // 2
        y = (screen_height - icon_height - 10)
        for mob_name in available_mob_names:
            self.mob_icons.append(self.create_icon_for_mob(mob_name, (x, y)))
            x += icon_width + MobIcon.PADDING

    def create_icon_for_mob(self, mob_name, icon_pos):
        params = self.mob_store.get_params(mob_name)
        actor = Actor(mob_name, params, vec2(0, 0), self.world, self.rendering)
        return MobIcon(actor, icon_pos)

    def find_icon_at(self, mouse_pos):
        for icon in self.mob_icons:
            if icon.intersects(mouse_pos):
                return icon
        return None

    def on_event(self, event):
        if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            clicked_icon = self.find_icon_at(pygame.mouse.get_pos())
            if clicked_icon:
                self.user.set_selected_mob_type(clicked_icon.get_mob_type())
            else:
                spawn_pos = vec2(pygame.mouse.get_pos())
                if self.world.is_valid_position(spawn_pos):
                    self.world.spawn_actor_at(
                        self.user.get_selected_mob_type(), spawn_pos)
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 2:
            self.world.add_player()

    def update(self, screen, frame_time):
        # compute claimed and unclaimed loot
        claimed_loot_value = 0
        unclaimed_loot_value = 0
        for actor in self.world.actors:
            if not actor.is_dead():
                if actor.is_player:
                    claimed_loot_value += actor.loot_value
                else:
                    unclaimed_loot_value += actor.loot_value

        # draw loot stats
        screen.blit(self.coin_icon, (10, 10))
        self.rendering.print_text(
            (34, 6), '%d (%d)' % (claimed_loot_value, unclaimed_loot_value),
            (255, 192, 0))

        # draw mob icons
        for icon in self.mob_icons:
            icon.draw(
                screen,
                self.user.get_selected_mob_type() == icon.get_mob_type())
            if icon.intersects(pygame.mouse.get_pos()):
                self.rendering.print_text(
                    (icon.bounds.centerx, icon.bounds.top - 10),
                    icon.get_label(), (64, 64, 64), True)
