import pygame
import random
import math
import json
import functools
from thirdparty.vec2 import vec2
from mm.scheduling import Timer


class ActorStore(object):
    def __init__(self):
        self.actors = {}

    def load_from_file(self, filename):
        with open(filename) as actor_file:
            self.actors = json.load(actor_file)

    def get_params(self, actor_type):
        return self.actors[actor_type]

    def get_all_names(self):
        return self.actors.keys()


def get_random_position_inside(spawn_area):
    return vec2(random.uniform(spawn_area.left, spawn_area.right), random.uniform(spawn_area.top, spawn_area.bottom))


class World(object):
    def __init__(self, scheduler, actor_store, width, height):
        self.scheduler = scheduler
        self.actor_store = actor_store

        self.width = width
        self.height = height

        self.bounds = pygame.Rect(0, 0, self.width, self.height)

        self.spawn_area = pygame.Rect(0, 0, self.width, self.height)
        self.spawn_area.inflate_ip(-self.width // 3, -self.height // 3)

        self.actors = []

    def spawn_actor(self, actor_type, pos):
        actor_class = self.actor_store.get_params(actor_type)

        is_player = actor_type == 'player'
        speed = actor_class.get('speed', 1)
        radius = actor_class.get('radius', 1)

        min_attack_range = actor_class.get('min_range', radius)
        max_attack_range = actor_class.get('max_range', min_attack_range)
        attack_range = int(random.uniform(min_attack_range, max_attack_range))

        default_threat_range = 1.5 * attack_range
        threat_range = actor_class.get(
            'threat_range', default_threat_range)
        threat_range = max(radius, threat_range)

        min_damage = max(0, actor_class.get('min_damage', 0))
        max_damage = actor_class.get('max_damage', min_damage)
        damage_range = (min_damage, max_damage)

        min_health = max(1, actor_class.get('min_health', 1))
        max_health = actor_class.get('max_health', min_health)
        max_health = int(random.uniform(min_health, max_health))
        health = max_health

        health_regen = actor_class.get('health_regen', 0)

        wander_radius = 100

        wander_time = (1, 4)
        attack_time = actor_class.get('attack_time', 2)
        regen_time = actor_class.get('regen_time', 2)

        miss_rate = actor_class.get('miss_rate', 0.1)

        if is_player:
            loot_value = 0
        else:
            loot_avg = actor_class.get('loot_avg', 10)
            loot_var = actor_class.get('loot_var', loot_avg / 5)
            loot_value = max(1, int(random.gauss(loot_avg, loot_var)))

        actor = Actor(
            actor_type, is_player, speed, radius, attack_range,
            threat_range, damage_range, max_health, max_health,
            health_regen, wander_radius, miss_rate, loot_value,
            wander_time, attack_time, regen_time, pos, self)

        self.actors.append(actor)

        return actor

    def spawn_player(self):
        pad = 64.

        r0 = pygame.Rect(-pad, -pad, self.width + pad, pad)
        r1 = pygame.Rect(self.width, -pad, pad, self.height + pad)
        r2 = pygame.Rect(0, self.height, self.width + pad, pad)
        r3 = pygame.Rect(-pad, 0, pad, self.height + pad)

        area_0 = float(self.width + pad) * pad
        area_1 = float(self.height + pad) * pad

        total_area = 2. * (area_0 + area_1)

        r0_prob = (area_0 / total_area)
        r1_prob = r0_prob + (area_1 / total_area)
        r2_prob = r1_prob + (area_0 / total_area)
        #r3_prob = r2_prob + (area_1 / total_area)

        dice_roll = random.random()
        if dice_roll < r0_prob: r = r0
        elif dice_roll < r1_prob: r = r1
        elif dice_roll < r2_prob: r = r2
        else: r = r3

        return self.spawn_actor('player', get_random_position_inside(r))

    def update(self, frame_time):
        for actor in self.actors:
            if actor.is_alive():
                actor.think(frame_time)

    def find_nearby_actors(self, pos, search_radius):
        for actor in self.actors:
            if (not actor.is_dead() and
                pos.get_distance(actor.pos) - actor.radius < search_radius):
                yield actor

    def is_valid_position(self, pos):
        return self.bounds.collidepoint(pos.as_int_tuple())

    def on_death(self, actor):
        # notify
        self.scheduler.post(
            functools.partial(self.actors.remove, actor), 30)


class Actor(object):
    def __init__(self, actor_type, is_player, speed, radius, attack_range,
                 threat_range, damage_range, max_health, health,
                 health_regen, wander_radius, miss_rate, loot_value,
                 wander_time, attack_time, regen_time, pos, world):
        self.actor_type = actor_type
        self.world = world
        self.is_player = is_player
        self.speed = speed
        self.radius = radius
        self.attack_range = attack_range
        self.threat_range = threat_range
        self.damage_range = damage_range
        self.max_health = max_health
        self.health = health
        self.health_regen = health_regen
        self.wander_radius = wander_radius
        self.miss_rate = miss_rate
        self.loot_value = loot_value

        self.wander_timer = Timer(wander_time, False)
        self.attack_timer = Timer(attack_time, False)
        self.regen_timer = Timer(regen_time, False)

        self.pos = pos

        self.target = None

        self.move_dest = vec2(0, 0)

        self.set_random_destination()

    def set_destination(self, pos, timeout=30):
        self.wander_timer.reset(timeout)
        self.move_dest = pos

    def set_random_destination(self):
        angle = random.random() * 2. * math.pi
        dx = math.cos(angle) * self.wander_radius
        dy = math.sin(angle) * self.wander_radius
        self.move_dest = self.pos + vec2(dx, dy)

    def attack_or_wander(self):
        if self.health > self.max_health / 2:
            nearby_enemies = list(self.find_nearby_enemies())
            if len(nearby_enemies) > 0:
                self.set_target(random.choice(nearby_enemies))
            else:
                self.wander()
        else:
            self.wander()

    def find_nearby_enemies(self):
        for actor in self.world.find_nearby_actors(self.pos, self.threat_range):
            if actor.is_player != self.is_player:
                yield actor

    def is_in_range(self, other, max_range):
        return (self.pos.get_distance(other.pos) - other.radius) < max_range

    def take_damage(self, damage, instigator):
        self.health -= damage

        if (not self.target or
            not self.is_in_range(self.target, self.attack_range)):
            self.set_target(instigator)

        #if self.is_player:
        #    damage = -damage
        #    text_color = (255, 32, 32)
        #else:
        #    text_color = (64, 128, 255)
        #self.renderer.combat_text(self.pos, str(damage), text_color)

    def set_target(self, other):
        self.target = other
        #if self.target:
        #    self.renderer.combat_text(self.pos, '!', (255, 192, 64))

    def reward(self, loot):
        self.loot_value += loot
        #loot_text = '+%d' % (self.target.loot_value)
        #self.renderer.combat_text(self.pos, loot_text, (192, 0, 192), False)

    def shoot_at_target(self):
        if self.attack_timer.is_expired_then_reset():
            if random.random() > self.miss_rate:
                self.target.take_damage(
                    int(random.uniform(*self.damage_range)), self)

                if self.target.is_dead():
                    if self.is_player:
                        self.reward(self.target.loot_value)
                    self.world.on_death(self.target)

                #if self.is_player:
                #    damage_color = (255, 64, 0)
                #else:
                #    damage_color = (255, 0, 0)
                #self.renderer.visualize_attack(
                #    self.pos, self.target.pos, damage_color)
            #else:
            #    self.renderer.small_combat_text(
            #        self.pos, 'MISS', (192, 192, 192))

    def is_dead(self):
        return self.health <= 0

    def wander(self):
        if (self.wander_timer.expired() or
            self.pos.get_distance(self.move_dest) < self.radius):
            self.wander_timer.reset()
            self.set_random_destination()
            while not self.world.is_valid_position(self.move_dest):
                self.set_random_destination()

    def think(self, frame_time):
        self.wander_timer.update(frame_time)
        self.attack_timer.update(frame_time)
        self.regen_timer.update(frame_time)

        if self.target:
            if self.target.is_dead():
                # or not self.is_in_range(self.target, self.threat_range):
                self.set_target(None)
                self.set_random_destination()
            elif self.is_in_range(self.target, self.attack_range):
                self.move_dest = self.pos
                self.shoot_at_target()
            else:
                self.move_dest = self.target.pos
        else:
            self.attack_or_wander()

        if self.regen_timer.is_expired_then_reset() and self.health < self.max_health and not self.target:
            health_increase = self.health_regen
            self.health = min(self.health + health_increase, self.max_health)
            #if self.is_player:
            #    self.renderer.small_combat_text(self.pos, '+' + str(health_increase), (64, 192, 32))

        self.move(frame_time)

    def move(self, frame_time):
        delta = self.move_dest - self.pos
        distance = delta.normalize_return_length()
        time = min(self.speed * frame_time, distance)
        self.pos += time * delta

    def update(self, frame_time):
        if not self.is_dead():
            self.think(frame_time)


class Actor(object):
    def __init__(self, name, spawn_params, pos, world, renderer):
        self.name = name
        self.spawn_params = spawn_params
        self.pos = pos
        self.world = world
        self.renderer = renderer

        self.is_player = self.name == 'player'

        if 'image' in self.spawn_params:
            self.image = self.renderer.load_image(self.spawn_params['image'])
        else:
            self.image = None
        if 'image_dead' in self.spawn_params:
            self.image_dead = self.renderer.load_image(
                self.spawn_params['image_dead'])
        else:
            self.image_dead = None

        self.color = tuple(self.spawn_params.get('color', (0, 0, 0)))
        self.speed = self.spawn_params.get('speed', 1)
        self.radius = self.spawn_params.get('radius', 1)

        min_range = self.spawn_params.get('min_range', self.radius)
        max_range = self.spawn_params.get('max_range', min_range)
        self.attack_range = int(random.uniform(min_range, max_range))

        default_threat_range = 1.5 * self.attack_range
        threat_range = self.spawn_params.get(
            'threat_range', default_threat_range)
        self.threat_range = max(self.radius, threat_range)

        min_damage = max(0, self.spawn_params.get('min_damage', 0))
        max_damage = self.spawn_params.get('max_damage', min_damage)
        self.damage_range = (min_damage, max_damage)

        min_health = max(1, self.spawn_params.get('min_health', 1))
        max_health = self.spawn_params.get('max_health', min_health)
        self.max_health = int(random.uniform(min_health, max_health))
        self.health = self.max_health

        self.health_regen = self.spawn_params.get('health_regen', 0)

        self.wander_timer = Timer((1, 4), False)
        self.attack_timer = Timer(
            self.spawn_params.get('attack_time', 2), False)
        self.regen_timer = Timer(self.spawn_params.get('regen_time', 2), False)

        self.wander_radius = 100

        self.miss_rate = self.spawn_params.get('miss_rate', 0.1)

        loot_avg = self.spawn_params.get('loot_avg', 10)
        loot_var = self.spawn_params.get('loot_var', loot_avg / 5)
        if self.is_player:
            self.loot_value = 0
        else:
            self.loot_value = max(1, int(random.gauss(loot_avg, loot_var)))

        self.target = None
        self.move_dest = vec2(0, 0)

        self.set_random_destination()

    def set_destination(self, pos, timeout=30):
        self.wander_timer.reset(timeout)
        self.move_dest = pos

    def set_random_destination(self):
        angle = random.random() * 2. * math.pi
        dx = math.cos(angle) * self.wander_radius
        dy = math.sin(angle) * self.wander_radius
        self.move_dest = self.pos + vec2(dx, dy)

    def attack_or_wander(self):
        if self.health > self.max_health / 2:
            nearby_enemies = list(self.find_nearby_enemies())
            if len(nearby_enemies) > 0:
                self.set_target(random.choice(nearby_enemies))
            else:
                self.wander()
        else:
            self.wander()

    def find_nearby_enemies(self):
        for actor in self.world.find_nearby_actors(self.pos, self.threat_range):
            if actor.is_player != self.is_player:
                yield actor

    def is_in_range(self, other, max_range):
        return (self.pos.get_distance(other.pos) - other.radius) < max_range

    def take_damage(self, damage, instigator):
        self.health -= damage

        if (not self.target or
            not self.is_in_range(self.target, self.attack_range)):
            self.set_target(instigator)

        if self.is_player:
            damage = -damage
            text_color = (255, 32, 32)
        else:
            text_color = (64, 128, 255)
        self.renderer.combat_text(self.pos, str(damage), text_color)

    def set_target(self, other):
        self.target = other
        #if self.target:
        #    self.renderer.combat_text(self.pos, '!', (255, 192, 64))

    def reward(self, loot):
        self.loot_value += loot
        loot_text = '+%d' % (self.target.loot_value)
        self.renderer.combat_text(self.pos, loot_text, (192, 0, 192), False)

    def shoot_at_target(self):
        if self.attack_timer.is_expired_then_reset():
            if random.random() > self.miss_rate:
                self.target.take_damage(
                    int(random.uniform(*self.damage_range)), self)

                if self.is_player:
                    damage_color = (255, 64, 0)
                else:
                    damage_color = (255, 0, 0)

                self.renderer.visualize_attack(
                    self.pos, self.target.pos, damage_color)

                if self.target.is_dead():
                    if self.is_player:
                        self.reward(self.target.loot_value)
                    self.world.on_death(self.target)
            else:
                self.renderer.small_combat_text(
                    self.pos, 'MISS', (192, 192, 192))

    def is_dead(self):
        return self.health <= 0

    def wander(self):
        if (self.wander_timer.expired() or
            self.pos.get_distance(self.move_dest) < self.radius):
            self.wander_timer.reset()
            self.set_random_destination()
            while not self.world.is_valid_position(self.move_dest):
                self.set_random_destination()

    def think(self, frame_time):
        self.wander_timer.update(frame_time)
        self.attack_timer.update(frame_time)
        self.regen_timer.update(frame_time)

        if self.target:
            if self.target.is_dead():
                # or not self.is_in_range(self.target, self.threat_range):
                self.set_target(None)
                self.set_random_destination()
            elif self.is_in_range(self.target, self.attack_range):
                self.move_dest = self.pos
                self.shoot_at_target()
            else:
                self.move_dest = self.target.pos
        else:
            self.attack_or_wander()

        self.move(frame_time)

        if self.regen_timer.is_expired_then_reset() and self.health < self.max_health and not self.target:
            health_increase = self.health_regen
            self.health = min(self.health + health_increase, self.max_health)
            if self.is_player:
                self.renderer.small_combat_text(self.pos, '+' + str(health_increase), (64, 192, 32))

    def move(self, frame_time):
        delta = self.move_dest - self.pos
        distance = delta.normalize_return_length()
        time = min(self.speed * frame_time, distance)
        self.pos += time * delta

    def update(self, screen, frame_time):
        if not self.is_dead():
            self.think(frame_time)
        self.draw(screen)

    def draw(self, screen, icon=False):
        if self.image is not None:
            if self.is_dead() and self.image_dead is not None:
                screen.blit(self.image_dead, self.image_dead.get_rect(center=self.pos.as_int_tuple()))
            else:
                screen.blit(self.image, self.image.get_rect(center=self.pos.as_int_tuple()))
        else:
            pygame.draw.circle(screen, self.color if not self.is_dead() else (128, 128, 128), self.pos.as_int_tuple(), self.radius, 2 if self.is_player else 0)
        if not icon:
            if not self.is_dead():
                pygame.draw.circle(screen, (192, 192, 192), self.pos.as_int_tuple(), int(self.attack_range), 1)
                pygame.draw.circle(screen, (224, 224, 224), self.pos.as_int_tuple(), int(self.threat_range), 1)
                self.renderer.draw_health_bar(screen, self.pos, self.health, self.max_health)


class ClientWorld(World):
    def __init__(self, renderer, scheduler, actor_store, width, height):
        self.actor_store = actor_store
        self.renderer = renderer
        self.scheduler = scheduler
        self.width = screen_width
        self.height = screen_height
        self.bounds = pygame.Rect(0, 0, self.width, self.height)
        self.spawn_area = pygame.Rect(0, 0, self.width, self.height)
        self.spawn_area.inflate_ip(-self.width // 3, -self.height // 3)
        self.actors = []

    def spawn_actor(self, actor_type, custom_spawn_area=None):
        spawn_pos = get_random_position_inside(custom_spawn_area if custom_spawn_area else self.spawn_area)
        if self.is_valid_position(spawn_pos):
            self.spawn_actor(actor_type, spawn_pos)

    def spawn_actor(self, actor_type, pos):
        actor = Actor(actor_type, self.actor_store.get_params(actor_type), pos, self)
        self.actors.append(actor)
        return actor

    def spawn_player(self):
        pad = 64
        r0 = pygame.Rect(-pad, -pad, self.width + pad, pad)
        r1 = pygame.Rect(self.width, -pad, pad, self.height + pad)
        r2 = pygame.Rect(0, self.height, self.width + pad, pad)
        r3 = pygame.Rect(-pad, 0, pad, self.height + pad)
        area_0 = (self.width + pad) * pad
        area_1 = (self.height + pad) * pad
        total_area = 2 * (area_0 + area_1)
        r0_prob = (area_0 / total_area)
        r1_prob = r0_prob + (area_1 / total_area)
        r2_prob = r1_prob + (area_0 / total_area)
        #r3_prob = r2_prob + (area_1 / total_area)
        dice_roll = random.random()
        if dice_roll < r0_prob: r = r0
        elif dice_roll < r1_prob: r = r1
        elif dice_roll < r2_prob: r = r2
        else: r = r3
        player = self.spawn_actor('player', get_random_position_inside(r))
        #player.set_destination(get_random_position_inside(self.spawn_area))

    def update(self, screen, frame_time):
        for a in self.actors:
            a.update(screen, frame_time)

    def find_nearby_actors(self, pos, search_radius):
        return [ a for a in self.actors if pos.get_distance(a.pos) - a.radius < search_radius if not a.is_dead() ]

    def is_valid_position(self, pos):
        return self.bounds.collidepoint(pos.as_int_tuple())

    def on_death(self, actor):
        if actor.is_player:
            self.user.on_player_death(actor)
        self.scheduler.post(functools.partial(self.actors.remove, actor), 30)
