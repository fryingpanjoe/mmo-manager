import pygame
import os.path
from thirdparty.vec2 import *
from mm.scheduling import Timer


class Renderer(object):
    def __init__(self):
        self.font = pygame.font.Font('res/font.ttf', 24)
        self.small_font = pygame.font.Font('res/font.ttf', 18)
        self.image_cache = {}
        self.renderables = []

    def update(self, screen, frame_time):
        for (timer, renderable) in self.renderables:
            renderable.update(screen, frame_time)
        self.renderables[:] = [ (t,r) for (t,r) in self.renderables if t is not None and t.update(frame_time) ]

    def draw_health_bar(self, screen, pos, current_health, max_health):
        health_scale = float(current_health) / max_health
        bar_color = (255 * (1 - health_scale), 255 * health_scale, 0)
        bar_x = pos.x - 10
        bar_y = pos.y - 15
        bar_width = 20
        bar_height = 5
        pygame.draw.rect(screen, (255, 255, 255), (bar_x, bar_y, bar_width, bar_height))
        pygame.draw.rect(screen, bar_color, (bar_x, bar_y, int(bar_width * health_scale), bar_height))
        pygame.draw.rect(screen, (0, 0, 0), (bar_x, bar_y, bar_width, bar_height), 1)

    def combat_text(self, pos, text, color, floating = True):
        self.renderables.append((Timer(1), Text(self.font, text, pos, color, True, 50 if floating else 0, 70 if floating else 0)))

    def small_combat_text(self, pos, text, color, floating = True):
        self.renderables.append((Timer(1), Text(self.small_font, text, pos, color, True, 50 if floating else 0, 70 if floating else 0)))

    def print_text(self, pos, text, color, centered = False):
        self.renderables.append((None, Text(self.font, text, pos, color, centered)))

    def visualize_attack(self, from_, to, color):
        self.renderables.append((Timer(0.5), Line(from_, to, color, 1)))

    def load_image(self, filename, colorkey = None):
        if filename in self.image_cache:
            return self.image_cache[filename]
        try:
            image = pygame.image.load(
                os.path.join('res', filename)).convert_alpha()
            #if colorkey is not None:
            #    if colorkey is -1:
            #        colorkey = image.get_at((0,0))
            #    image.set_colorkey(colorkey, pygame.RLEACCEL)
            return image
        except pygame.error as message:
            print('Cannot load image:', filename)
            raise(SystemExit())


class Text(object):
    def __init__(self, font, text, pos, color, centered, speed = 0, accel = 0):
        self.text = font.render(str(text), True, color)
        self.pos = vec2(pos)
        self.speed = speed
        self.accel = accel
        self.centered = centered

    def update(self, screen, frame_time):
        self.pos -= vec2(0, self.speed * frame_time)
        self.speed += self.accel * frame_time
        screen.blit(self.text, self.text.get_rect(centerx=self.pos[0], centery=self.pos[1]) if self.centered else self.pos)


class Line(object):
    def __init__(self, src, dst, color, width):
        self.src = src
        self.dst = dst
        self.color = color
        self.width = width

    def update(self, screen, frame_time):
        pygame.draw.line(screen, self.color, self.src.as_int_tuple(), self.dst.as_int_tuple(), self.width)
