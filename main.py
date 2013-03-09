#!/usr/bin/python

import sys
import pygame
import logging.config

from mm.config import Config
from mm.game import Game


def main():
    pygame.init()
    pygame.font.init()
    clock = pygame.time.Clock()

    #config.load('mm.conf')
    logging.config.fileConfig('logging.conf')

    screen = pygame.display.set_mode((800, 600))
    pygame.display.set_caption('MMO Manager 2013')
    game = Game(screen)
    game.menu()
    while game.running:
        frame_time = min(clock.tick() / 1000.0, 0.1)
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                game.quit()
            else:
                game.on_event(event)
        game.update(screen, frame_time)
        pygame.display.flip()


if __name__ == '__main__':
    main()
