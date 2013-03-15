#!/usr/bin/python

import logging
import logging.config
import pygame

from mm.client.session import Session
from mm.common.config import Config

LOG = logging.getLogger(__name__)

WINDOW_TITLE = 'MMO Manager 2013'


def main():
    logging.config.fileConfig('logging.conf', disable_existing_loggers=False)

    try:
        config = Config()
        config.load('mm.conf')

        LOG.info('initializing pygame')
        pygame.init()

        LOG.info('initializing pygame.font')
        pygame.font.init()

        try:
            screen_width = int(config.get('rendering', 'width'))
            screen_height = int(config.get('rendering', 'height'))
        except KeyError:
            screen_width = 800
            screen_height = 600

        LOG.info('setting display mode %d x %d', screen_width, screen_height)
        screen = pygame.display.set_mode((screen_width, screen_height))

        pygame.display.set_caption(WINDOW_TITLE)

        LOG.info('initializing game')
        session = Session(screen)
        session.menu()

        clock = pygame.time.Clock()

        try:
            max_fps = float(config.get('rendering', 'max_fps'))
            if max_fps <= 0.0:
                LOG.warn('invalid max_fps %f, should be >= 0', max_fps)
                max_fps = 60.
        except KeyError:
            max_fps = 60.

        LOG.info('maximum fps %.2f', max_fps)

        while session.is_running():
            frame_time = min(clock.tick() / 1000.0, 1.0 / max_fps)
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    LOG.info('got pygame.QUIT, exiting...')
                    session.quit()
                else:
                    session.on_event(event)
            session.update(screen, frame_time)
            pygame.display.flip()

        LOG.info('game shutdown')
    except Exception:
        LOG.exception('game crashed :-(')


if __name__ == '__main__':
    main()
