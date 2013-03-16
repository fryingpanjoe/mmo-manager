import logging
import random
import math
import json

import pygame

from thirdparty.vec2 import vec2

from mm.common.scheduling import Timer
from mm.common.events import *

LOG = logging.getLogger(__name__)


class ActorStore(object):
    def __init__(self, filename):
        with open(filename) as actor_file:
            self.actors = json.load(actor_file)

    def get_params(self, actor_type):
        return self.actors[actor_type]

    def get_all_names(self):
        return self.actors.keys()


class World(object):
    def __init__(self, event_distributor, scheduler, actor_store,
                 width, height):
        self.event_distributor = event_distributor
        self.scheduler = scheduler
        self.actor_store = actor_store

        self.width = width
        self.height = height

        self.bounds = pygame.Rect(0, 0, self.width, self.height)

        self.spawn_area = pygame.Rect(0, 0, self.width, self.height)
        self.spawn_area.inflate_ip(-self.width // 3, -self.height // 3)

        self.actor_id_generator = 100

        self.actors = []

    def spawn_actor(self, actor_type, pos):
        actor_class = self.actor_store.get_params(actor_type)

        is_hero = actor_type == 'hero'

        speed = actor_class.get('speed', 1)

        radius = actor_class.get('radius', 1)

        # attack range
        min_attack_range = actor_class.get('min_range', radius)
        max_attack_range = actor_class.get('max_range', min_attack_range)
        attack_range = int(random.uniform(min_attack_range, max_attack_range))

        # threat range
        threat_range = actor_class.get('threat_range', 1.5 * attack_range)
        threat_range = max(radius, threat_range)

        # damage
        min_damage = max(0, actor_class.get('min_damage', 0))
        max_damage = actor_class.get('max_damage', min_damage)
        damage_range = (min_damage, max_damage)

        # health
        min_health = max(1, actor_class.get('min_health', 1))
        max_health = actor_class.get('max_health', min_health)
        max_health = int(random.uniform(min_health, max_health))
        health = max_health

        # health regen
        health_regen = actor_class.get('health_regen', 0)
        regen_time = actor_class.get('regen_time', 2)

        # loot
        if is_hero:
            loot_value = 0
        else:
            loot_avg = actor_class.get('loot_avg', 10)
            loot_var = actor_class.get('loot_var', loot_avg / 5)
            loot_value = max(1, int(random.gauss(loot_avg, loot_var)))

        attack_time = actor_class.get('attack_time', 2)

        miss_rate = actor_class.get('miss_rate', 0.1)

        # wander properties
        wander_radius = 100
        wander_time = (1, 4)

        # generator new actor id
        actor_id = self.get_next_actor_id()

        # create actor
        actor = Actor(
            actor_id, actor_type, is_hero, speed, radius, attack_range,
            threat_range, damage_range, max_health, max_health, health_regen,
            wander_radius, miss_rate, loot_value, wander_time, attack_time,
            regen_time, pos, self)

        # add actor to world
        self.actors.append(actor)
        self.event_distributor.post(ActorSpawnedEvent(actor))

        # return our newly spawned actor
        return actor

    def get_next_actor_id(self):
        self.actor_id_generator += 1
        return self.actor_id_generator

    def spawn_hero(self):
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

        return self.spawn_actor('hero', World.get_random_position_inside(r))

    def update(self, frame_time):
        for actor in self.actors:
            if actor.is_alive():
                actor.think(frame_time)

    def find_nearby_actors(self, pos, search_radius):
        for actor in self.actors:
            if (actor.is_alive() and
                pos.get_distance(actor.pos) - actor.radius < search_radius):
                yield actor

    def is_valid_position(self, pos):
        return self.bounds.collidepoint(pos.as_int_tuple())

    def on_actor_died(self, actor):
        self.event_distributor.post(ActorDiedEvent(actor.actor_id))
        self.actors.remove(actor)
        #self.scheduler.post(
        #    functools.partial(self.actors.remove, actor), 30)

    def on_attack(self, attacker, victim, damage):
        self.event_distributor.post(
            AttackEvent(attacker.actor_id, victim.actor_id, damage))

    def on_heal(self, actor, heal):
        self.event_distributor.post(HealEvent(actor.actor_id, heal))

    def on_set_target(self, actor, target):
        if target:
            target_id = target.actor_id
        else:
            target_id = 0
        self.event_distributor.post(
            SetTargetEvent(actor.actor_id, target_id))

    def on_loot(self, actor, loot):
        self.event_distributor.post(LootEvent(actor.actor_id, loot))

    @staticmethod
    def get_random_position_inside(spawn_area):
        return vec2(
            random.uniform(spawn_area.left, spawn_area.right),
            random.uniform(spawn_area.top, spawn_area.bottom))


class Actor(object):
    def __init__(self, actor_id, actor_type, is_hero, speed, radius,
                 attack_range, threat_range, damage_range, max_health,
                 health, health_regen, wander_radius, miss_rate, loot_value,
                 wander_time, attack_time, regen_time, pos, world):
        self.actor_id = actor_id
        self.actor_type = actor_type
        self.is_hero = is_hero
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

        self.world = world

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
            if actor.is_hero != self.is_hero:
                yield actor

    def is_in_range(self, other, max_range):
        return (self.pos.get_distance(other.pos) - other.radius) < max_range

    def take_damage(self, damage, attacker=None):
        self.health -= damage

        if self.is_dead():
            self.world.on_actor_died(self)

        if (not self.target or
            not self.is_in_range(self.target, self.attack_range)):
            self.set_target(attacker)

    def set_target(self, other):
        self.target = other
        self.world.on_set_target(self, self.target)

    def reward(self, loot):
        self.loot_value += loot
        self.world.on_loot(self, loot)

    def shoot_at_target(self):
        if self.attack_timer.is_expired_then_reset():
            if random.random() < self.miss_rate:
                # miss
                damage = 0
            else:
                damage = int(random.uniform(*self.damage_range))

                self.target.take_damage(damage, attacker=self)

                # give loot to heroes!
                if self.target.is_dead() and self.is_hero:
                    self.reward(self.target.loot_value)

            self.world.on_attack(self, self.target, damage)

    def is_dead(self):
        return self.health <= 0

    def is_alive(self):
        return self.health > 0

    def wander(self):
        if (self.wander_timer.is_expired() or
            self.pos.get_distance(self.move_dest) < self.radius):
            self.wander_timer.reset()
            self.set_random_destination()
            while not self.world.is_valid_position(self.move_dest):
                self.set_random_destination()

    def think(self, frame_time):
        # update timers
        self.wander_timer.update(frame_time)
        self.attack_timer.update(frame_time)
        self.regen_timer.update(frame_time)

        # move to or attack target, if any
        if self.target:
            if self.target.is_dead(): # or not self.is_in_range(self.target, self.threat_range):
                self.set_target(None)
                self.set_random_destination()
            elif self.is_in_range(self.target, self.attack_range):
                self.move_dest = self.pos
                self.shoot_at_target()
            else:
                self.move_dest = self.target.pos
        else:
            self.attack_or_wander()

        # heal actor
        if self.regen_timer.is_expired_then_reset() and not self.target:
            if self.health < self.max_health:
                heal = min(self.health_regen, self.max_health - self.health)

                self.health += heal

                if heal:
                    self.world.on_heal(self, heal)

        # move actor
        delta = self.move_dest - self.pos
        distance = delta.normalize_return_length()
        time = min(self.speed * frame_time, distance)
        movement = time * delta
        self.pos += time * delta
