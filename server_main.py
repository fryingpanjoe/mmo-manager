#!/usr/bin/python

import time
import logging
import logging.config

from mm.common.config import Config
from mm.common.scheduling import Scheduler
from mm.common.world import World, ActorStore
from mm.common.events import EventDistributor, ALL_EVENT_TYPES

LOG = logging.getLogger(__name__)


def event_printer(event):
    LOG.info('event: ' + event)


def main():
    logging.config.fileConfig('logging.conf', disable_existing_loggers=False)

    try:
        config = Config()
        config.load('mm.conf')

        width = 800
        height = 600

        LOG.info('loading actor store')
        actor_store = ActorStore('actors.json')

        LOG.info('initializing game')
        event_distributor = EventDistributor()
        event_distributor.add_handler(event_printer, ALL_EVENT_TYPES)

        scheduler = Scheduler()

        world = World(event_distributor, scheduler, actor_store, width, height)

        LOG.info('starting game')

        last_time = time.time()

        while True:
            current_time = time.time()
            frame_time = current_time - last_time
            last_time = current_time

            scheduler.update(frame_time)

            world.update(frame_time)

            event_distributor.update()

            time.sleep(0.1)

        LOG.info('game shutdown')
    except Exception:
        LOG.exception('game crashed :-(')
    except KeyboardInterrupt:
        LOG.info('keyboard interrupt')


if __name__ == '__main__':
    main()
