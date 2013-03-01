import pygame


class MenuButton(object):
    def __init__(self, button_id, label, font, x, y, w, h):
        self.button_id = button_id
        self.label = label
        self.text = font.render(label, True, (32, 32, 32))
        self.bounds = pygame.rect.Rect(x, y, w, h)

    def set_position(self, (x, y)):
        self.bounds.topleft = (y, x)

    def draw(self, screen, highlight=False):
        color = (32, 32, 32) if highlight else (192, 192, 192)
        pygame.draw.rect(screen, color, self.bounds, 4)
        # FIXME: -4 is a font fix, remove if necessary.
        rect = self.text.get_rect(
            centerx=self.bounds.centerx, centery=self.bounds.centery - 4)
        screen.blit(self.text, rect)

    def is_intersecting(self, mouse_pos):
        return self.bounds.collidepoint(mouse_pos)


class MenuButtonTypes(object):
    CONTINUE = 0
    NEW_GAME = 1
    QUIT = 2


class MenuState(object):
    def __init__(self, game, screen_width, screen_height, in_game=False):
        self.game = game
        self.font = pygame.font.Font('font.ttf', 36)

        button_descs = [
            (MenuButtonTypes.NEW_GAME, 'NEW GAME'),
            (MenuButtonTypes.QUIT, 'QUIT')]

        if in_game:
            button_descs.append((MenuButtonTypes.CONTINUE, 'CONTINUE'))

        button_width = screen_width // 4
        button_height = 64

        padding = 8

        total_menu_width = button_width
        total_menu_height = (button_height + padding) * len(button_descs)

        x_pos = (screen_width - total_menu_width) // 2
        y_pos = (screen_height - total_menu_height) // 2

        self.buttons = []

        for (button_type, label) in button_descs:
            button = MenuButton(
                button_type, label, self.font, x_pos, y_pos, button_width,
                button_height)
            self.buttons.append(button)
            y_pos += button_height + padding

    def on_event(self, event):
        if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            for button in self.buttons:
                if button.is_intersecting(pygame.mouse.get_pos()):
                    if button.button_id == MenuButtonTypes.NEW_GAME:
                        self.game.new_game()
                    elif button.button_id == MenuButtonTypes.CONTINUE:
                        self.game.go_back()
                    elif button.button_id == MenuButtonTypes.QUIT:
                        self.game.quit()

    def update(self, screen, frame_time):
        screen.fill((255, 255, 255))
        mouse_pos = pygame.mouse.get_pos()
        for button in self.buttons:
            button.draw(screen, highlight=button.is_intersecting(mouse_pos))
