import pygame

from sigilwave.game import Game


def main() -> None:
    pygame.init()
    pygame.display.set_caption("Sigil / Wave")
    screen = pygame.display.set_mode((1280, 800), pygame.RESIZABLE)

    game = Game(screen)
    game.run()

    pygame.quit()


if __name__ == "__main__":
    main()
