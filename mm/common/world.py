import logging
import random
import math
import json
import traceback

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


class ObjectState(dict):
    def __init__(self, object_type, *args, **kwargs):
        super(ObjectState, self).__init__(*args, **kwargs)
        self.object_type = object_type

    def __getattr__(self, key):
        try:
            return self[key]
        except KeyError as error:
            raise AttributeError(error)


class World(object):
    def __init__(self, event_distributor, scheduler, actor_store,
                 width, height, actors=None):
        self.event_distributor = event_distributor
        self.scheduler = scheduler
        self.actor_store = actor_store

        self.width = width
        self.height = height

        self.bounds = pygame.Rect(0, 0, self.width, self.height)

        self.spawn_area = pygame.Rect(0, 0, self.width, self.height)
        self.spawn_area.inflate_ip(-self.width // 3, -self.height // 3)

        self.actor_id_generator = 100

        if actors:
            self.actors = actors
        else:
            self.actors = []

    def add_actor(self, actor):
        self.actors.append(actor)

    def spawn_actor(self, actor_type, pos):
        actor_id = self.get_next_actor_id()

        actor = Actor.from_params(
            self.actor_store.get_params(actor_type), actor_id, self, pos=pos)

        self.actors.append(actor)
        self.event_distributor.post(ActorSpawnedEvent(actor.get_state()))

        return actor

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

    def get_next_actor_id(self):
        self.actor_id_generator += 1
        return self.actor_id_generator

    def update(self, frame_time):
        for actor in self.actors:
            if actor.is_alive():
                actor.think(frame_time)

    def find_actor_by_id(self, actor_id):
        for actor in self.actors:
            if actor.actor_id == actor_id:
                return actor
        return None

    def find_nearby_actors(self, pos, search_radius):
        for actor in self.actors:
            if (actor.is_alive() and
                pos.get_distance(actor.pos) - actor.radius < search_radius):
                yield actor

    def is_valid_position(self, pos):
        return self.bounds.collidepoint(pos.as_int_tuple())

    def on_actor_died(self, actor):
        LOG.info('Actor %d died', actor.actor_id)
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
    @classmethod
    def from_state(cls, state, world):
        actor = cls(
            state.actor_id, state.actor_type, state.is_hero, state.speed,
            state.radius, state.attack_range, state.threat_range,
            state.damage_range, state.max_health, state.health,
            state.health_regen, state.wander_radius, state.miss_rate,
            state.loot_value, state.wander_timer, state.attack_timer,
            state.regen_timer, state.pos, world)
        actor.update_state(state)
        return actor

    @classmethod
    def from_params(cls, params, actor_id, world, pos=None):
        actor_type = params['type']

        is_hero = actor_type == 'hero'

        speed = params.get('speed', 1)

        radius = params.get('radius', 1)

        # attack range
        min_attack_range = params.get('min_range', radius)
        max_attack_range = params.get('max_range', min_attack_range)
        attack_range = int(random.uniform(min_attack_range, max_attack_range))

        # threat range
        threat_range = params.get('threat_range', 1.5 * attack_range)
        threat_range = max(radius, threat_range)

        # damage
        min_damage = max(0, params.get('min_damage', 0))
        max_damage = params.get('max_damage', min_damage)
        damage_range = (min_damage, max_damage)

        # health
        min_health = max(1, params.get('min_health', 1))
        max_health = params.get('max_health', min_health)
        max_health = int(random.uniform(min_health, max_health))
        health = max_health

        # health regen
        health_regen = params.get('health_regen', 0)

        regen_time = params.get('regen_time', 2)
        regen_timer = Timer(regen_time, False)

        # loot
        if is_hero:
            loot_value = 0
        else:
            loot_avg = params.get('loot_avg', 10)
            loot_var = params.get('loot_var', loot_avg / 5)
            loot_value = max(1, int(random.gauss(loot_avg, loot_var)))

        attack_time = params.get('attack_time', 2)
        attack_timer = Timer(attack_time, False)

        miss_rate = params.get('miss_rate', 0.1)

        # wander properties
        wander_radius = 100
        wander_time = (1, 4)
        wander_timer = Timer(wander_time, False)

        # create actor
        return cls(
            actor_id, actor_type, is_hero, speed, radius, attack_range,
            threat_range, damage_range, max_health, max_health, health_regen,
            wander_radius, miss_rate, loot_value, wander_timer, attack_timer,
            regen_timer, pos, world)

    def __init__(self, actor_id, actor_type, is_hero, speed, radius,
                 attack_range, threat_range, damage_range, max_health,
                 health, health_regen, wander_radius, miss_rate, loot_value,
                 wander_timer, attack_timer, regen_timer, pos, world):
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
        self.wander_timer = wander_timer
        self.attack_timer = attack_timer
        self.regen_timer = regen_timer

        if pos:
            self.pos = pos
        else:
            self.pos = vec2(0, 0)

        self.world = world

        self.target_id = None

        self.move_dest = vec2(0, 0)

        self.set_random_destination()

    def get_state(self):
        return ObjectState('actor', {
            'actor_id': self.actor_id,
            'actor_type': self.actor_type,
            'is_hero': self.is_hero,
            'speed': self.speed,
            'radius': self.radius,
            'attack_range': self.attack_range,
            'threat_range': self.threat_range,
            'damage_range': self.damage_range,
            'max_health': self.max_health,
            'health': self.health,
            'health_regen': self.health_regen,
            'wander_radius': self.wander_radius,
            'miss_rate': self.miss_rate,
            'loot_value': self.loot_value,
            'wander_timer': self.wander_timer,
            'attack_timer': self.attack_timer,
            'regen_timer': self.regen_timer,
            'pos': self.pos,
            'target_id': self.target_id,
            'move_dest': self.move_dest
        })

    def update_state(self, state):
        assert state.object_type == 'actor'
        for key, value in state.iteritems():
            setattr(self, key, value)

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

        target = self.world.find_actor_by_id(self.target_id)

        if (not target or
            not self.is_in_range(target, self.attack_range)):
            self.set_target(attacker)

    def set_target(self, target):
        if target:
            self.target_id = target.actor_id
        else:
            self.target_id = None

        self.world.on_set_target(self, target)

    def reward(self, loot):
        self.loot_value += loot
        self.world.on_loot(self, loot)

    def shoot_at_target(self):
        if self.attack_timer.is_expired_then_reset():
            target = self.world.find_actor_by_id(self.target_id)

            if random.random() < self.miss_rate:
                # miss
                damage = 0
            else:
                damage = int(random.uniform(*self.damage_range))
                target.take_damage(damage, attacker=self)

                # give loot to heroes!
                if target.is_dead() and self.is_hero:
                    self.reward(target.loot_value)

            self.world.on_attack(self, target, damage)

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
        if self.target_id:
            target = self.world.find_actor_by_id(self.target_id)
            if not target:
                LOG.info('Failed to find target %d, wandering', self.target_id)
                self.set_target(None)
                self.set_random_destination()
            else:
                if target.is_dead(): # or not self.is_in_range(target, self.threat_range):
                    self.set_target(None)
                    self.set_random_destination()
                elif self.is_in_range(target, self.attack_range):
                    self.move_dest = self.pos
                    self.shoot_at_target()
                else:
                    self.move_dest = target.pos
        else:
            self.attack_or_wander()

        # heal actor
        if self.regen_timer.is_expired_then_reset() and not self.target_id:
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
