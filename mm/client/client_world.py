import logging
import random
import functools

import pygame

from thirdparty.vec2 import *
from mm.common.events import *
from mm.common.world import World, Actor
from mm.common.scheduling import Timer

LOG = logging.getLogger(__name__)


class ClientWorld(object):
    def __init__(self, event_distributor, scheduler, renderer, actor_store):
        self.event_distributor = event_distributor
        self.scheduler = scheduler
        self.renderer = renderer
        self.actor_store = actor_store

        self.world = None

        self.client_actors = {}

        self.event_distributor.add_handler(self.on_enter_game, EnterGameEvent)
        self.event_distributor.add_handler(self.on_delta_state, DeltaStateEvent)
        self.event_distributor.add_handler(self.on_actor_spawned, ActorSpawnedEvent)
        self.event_distributor.add_handler(self.on_actor_died, ActorDiedEvent)
        self.event_distributor.add_handler(self.on_attack, AttackEvent)
        self.event_distributor.add_handler(self.on_heal, HealEvent)
        self.event_distributor.add_handler(self.on_loot, LootEvent)
        self.event_distributor.add_handler(self.on_set_target, SetTargetEvent)

    def find_actor_by_id(self, actor_id):
        return self.world.find_actor_by_id(actor_id)

    def new_client_actor(self, actor):
        return ClientActor(
            actor, self.actor_store.get_params(actor.actor_type), self.renderer)

    def on_enter_game(self, event):
        LOG.info(
            'Enter game %d x %d, %d actors', event.width, event.height,
            len(event.actor_states))
        actors = [
            Actor.from_state(actor_state, self.world)
            for actor_state in event.actor_states]
        self.world = World(
            self.event_distributor, self.scheduler, self.actor_store,
            event.width, event.height, actors=actors)
        self.client_actors = dict(
            (actor.actor_id, self.new_client_actor(actor)) for actor in actors)

    def on_delta_state(self, event):
        for actor_state in event.actor_states:
            local_actor = self.find_actor_by_id(actor_state.actor_id)
            if local_actor:
                local_actor.update_state(actor_state)
            else:
                LOG.warning('State for unknown actor %d', actor_state.actor_id)

    def on_actor_spawned(self, event):
        local_actor = self.find_actor_by_id(event.actor_state.actor_id)
        if local_actor:
            LOG.error(
                'Spawned actor already exists: id=%d',
                event.actor_state.actor_id)
        else:
            actor = Actor.from_state(event.actor_state, self.world)
            self.world.add_actor(actor)
            self.client_actors[actor.actor_id] = ClientActor(
                actor, self.actor_store.get_params(actor.actor_type),
                self.renderer)

    def on_actor_died(self, event):
        LOG.info('Actor %d died', event.actor_id)

        # keep body around for a little while
        local_actor = self.find_actor_by_id(event.actor_id)
        if local_actor:
            self.world.actors.remove(local_actor)
        else:
            LOG.warning('Failed to find dead actor %d', event.actor_id)
        self.scheduler.post(
            functools.partial(self.remove_client_actor, event.actor_id), 30)

    def remove_client_actor(self, actor_id):
        del self.client_actors[actor_id]

    def on_attack(self, event):
        LOG.info('Actor %d attacked %d', event.attacker_id, event.victim_id)

        attacker = self.find_actor_by_id(event.attacker_id)
        victim = self.find_actor_by_id(event.victim_id)

        if attacker.is_hero:
            damage_color = (255, 64, 0)
        else:
            damage_color = (255, 0, 0)

        self.renderer.visualize_attack(attacker.pos, victim.pos, damage_color)

        if event.damage == 0:
            self.renderer.small_combat_text(
                attacker.pos, 'MISS', (192, 192, 192))
        else:
            if victim.is_hero:
                damage = -event.damage
                text_color = (255, 32, 32)
            else:
                damage = event.damage
                text_color = (64, 128, 255)

            self.renderer.combat_text(victim.pos, str(damage), text_color)

    def on_heal(self, event):
        local_actor = self.find_actor_by_id(event.actor_id)
        if local_actor:
            if local_actor.is_hero:
                self.renderer.small_combat_text(
                    local_actor.pos, '+' + str(event.heal), (64, 192, 32))

    def on_loot(self, event):
        local_actor = self.find_actor_by_id(event.actor_id)
        if local_actor:
            self.renderer.combat_text(
                local_actor.pos, '+' + str(event.loot), (192, 0, 192), False)

    def on_set_target(self, event):
        #local_actor = self.find_actor_by_id(event.actor_id)
        #if event.target_id:
        #    self.renderer.combat_text(local_actor.pos, '!', (255, 192, 64))
        pass

    def update(self, screen, frame_time):
        for client_actor in self.client_actors.itervalues():
            client_actor.update(screen, frame_time)


class ClientActor(object):
    def __init__(self, actor, spawn_params, renderer):
        self.actor = actor
        self.renderer = renderer

        if 'image' in spawn_params:
            self.image = self.renderer.load_image(spawn_params['image'])
        else:
            self.image = None

        if 'image_dead' in spawn_params:
            self.image_dead = self.renderer.load_image(
                spawn_params['image_dead'])
        else:
            self.image_dead = None

        self.color = tuple(spawn_params.get('color', (0, 0, 0)))

    def update(self, screen, frame_time):
        self.draw(screen)

    def draw(self, screen, icon=False):
        pos_tuple = self.actor.pos.as_int_tuple()

        if self.image:
            if self.actor.is_dead() and self.image_dead:
                image = self.image_dead
            else:
                image = self.image
        else:
            image = None

        if image:
            # draw image
            screen.blit(image, self.image_dead.get_rect(center=pos_tuple))
        else:
            # draw circle
            if self.actor.is_alive():
                color = self.color
            else:
                color = (128, 128, 128)

            if self.actor.is_hero:
                border_thickness = 2
            else:
                border_thickness = 0

            pygame.draw.circle(
                screen, color, self.actor.pos.as_int_tuple(), self.actor.radius,
                border_thickness)

        if not icon:
            if self.actor.is_alive():
                # attack range
                pygame.draw.circle(
                    screen, (192, 192, 192), pos_tuple,
                    int(self.actor.attack_range), 1)

                # threat range
                pygame.draw.circle(
                    screen, (224, 224, 224), pos_tuple,
                    int(self.actor.threat_range), 1)

                # health bar
                self.renderer.draw_health_bar(
                    screen, self.actor.pos, self.actor.health,
                    self.actor.max_health)
