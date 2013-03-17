#!/usr/bin/python

import time
import logging
import logging.config
import functools

from thirdparty.vec2 import vec2

from mm.common.networking import Server, DEFAULT_NETWORK_PORT
from mm.common.config import Config
from mm.common.scheduling import Scheduler
from mm.common.world import World, ActorStore
from mm.common.events import *

LOG = logging.getLogger(__name__)


def event_debug_printer(event):
    LOG.info('event: ' + str(event))


class ServerEventHandler(object):
    def __init__(self, server, world):
        self.server = server
        self.world = world

    def on_client_connected(self, event):
        # send world state to client
        enter_game_event = EnterGameEvent(
            self.world.width, self.world.height, self.world.actors)
        self.server.send_event(event.client_id, enter_game_event)

    def on_client_disconnected(self, event):
        LOG.info('Client disconnected: %d' % (event.client_id,))


def main():
    logging.config.fileConfig('logging.conf', disable_existing_loggers=False)

    try:
        config = Config()
        config.load('mm.conf')

        LOG.info('Loading actors')
        actor_store = ActorStore('actors.json')

        LOG.info('Initializing game')

        LOG.info('...initializing event distributor')
        event_distributor = EventDistributor()
        event_distributor.add_handler(event_debug_printer, ALL_EVENT_TYPES)

        LOG.info('...initializing scheduler')
        scheduler = Scheduler()

        LOG.info('...initializing server')
        server = Server(event_distributor, DEFAULT_NETWORK_PORT)
        event_distributor.add_handler(
            server.broadcast_event, ALL_GAME_EVENT_TYPES)

        LOG.info('...initializing world')
        width = 800
        height = 600
        world = World(event_distributor, scheduler, actor_store, width, height)
        world.spawn_actor('hero', vec2(300, 200))
        world.spawn_actor('hero', vec2(310, 210))
        world.spawn_actor('hero', vec2(320, 220))
        world.spawn_actor('hero', vec2(330, 230))
        world.spawn_actor('hero', vec2(340, 240))
        world.spawn_actor('creep', vec2(400, 300))
        world.spawn_actor('creep', vec2(410, 310))
        world.spawn_actor('creep', vec2(420, 320))
        world.spawn_actor('supercreep', vec2(400, 300))

        LOG.info('...initializing server event handler')
        event_handler = ServerEventHandler(server, world)
        event_distributor.add_handler(
            event_handler.on_client_connected, ClientConnectedEvent)
        event_distributor.add_handler(
            event_handler.on_client_disconnected, ClientDisconnectedEvent)

        LOG.info('Starting server')
        server.start_server()

        LOG.info('Entering main loop')
        last_time = time.time()
        while True:
            current_time = time.time()
            frame_time = current_time - last_time
            last_time = current_time

            # accept new clients and read data from clients
            server.accept_pending_clients()
            server.read_from_clients()

            # update timers
            scheduler.update(frame_time)

            # update world
            world.update(frame_time)

            # distribute posted events
            event_distributor.update()

            # compute delta event
            # TODO: send only updated actors
            server.broadcast_event(DeltaStateEvent(world.actors))

            # send data to clients
            server.write_to_clients()

            time.sleep(0.1)

    except Exception:
        LOG.exception('Game crashed :-(')
    except KeyboardInterrupt:
        LOG.info('Keyboard interrupt')

    LOG.info('Shutting down game')

    LOG.info('...stopping server')
    server.stop_server()


if __name__ == '__main__':
    main()
