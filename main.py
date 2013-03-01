import pygame
from game import Game


def main():
    pygame.init()
    pygame.font.init()
    clock = pygame.time.Clock()
    screen = pygame.display.set_mode((800, 600))
    pygame.display.set_caption('MMO Manager 2013')
    game = Game(screen.get_width(), screen.get_height())
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
