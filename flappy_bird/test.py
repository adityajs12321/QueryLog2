import pygame
import random
import sys

# Initialize Pygame
pygame.init()

# Game constants
SCREEN_WIDTH = 400
SCREEN_HEIGHT = 600
BIRD_WIDTH = 34
BIRD_HEIGHT = 24
PIPE_WIDTH = 52
PIPE_GAP = 150
GROUND_HEIGHT = 112
FPS = 60

# Colors
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
GREEN = (0, 255, 0)
YELLOW = (255, 255, 0)
BROWN = (139, 69, 19)
BLUE = (135, 206, 235)

class Bird:
    def __init__(self):
        self.x = 50
        self.y = SCREEN_HEIGHT // 2
        self.velocity = 0
        self.gravity = 0.8
        self.jump_strength = -9
        self.rect = pygame.Rect(self.x, self.y, BIRD_WIDTH, BIRD_HEIGHT)
    
    def jump(self):
        self.velocity = self.jump_strength
    
    def update(self):
        self.velocity += self.gravity
        self.y += self.velocity
        self.rect.y = self.y
        
        # Keep bird on screen
        if self.y < 0:
            self.y = 0
            self.velocity = 0
    
    def draw(self, screen):
        pygame.draw.ellipse(screen, YELLOW, self.rect)
        # Draw simple eye
        eye_x = self.rect.x + 20
        eye_y = self.rect.y + 8
        pygame.draw.circle(screen, BLACK, (eye_x, eye_y), 3)

class Pipe:
    def __init__(self, x):
        self.x = x
        self.height = random.randint(50, SCREEN_HEIGHT - GROUND_HEIGHT - PIPE_GAP - 50)
        self.top_rect = pygame.Rect(x, 0, PIPE_WIDTH, self.height)
        self.bottom_rect = pygame.Rect(x, self.height + PIPE_GAP, PIPE_WIDTH, 
                                     SCREEN_HEIGHT - GROUND_HEIGHT - self.height - PIPE_GAP)
        self.passed = False
    
    def update(self):
        self.x -= 3
        self.top_rect.x = self.x
        self.bottom_rect.x = self.x
    
    def draw(self, screen):
        pygame.draw.rect(screen, GREEN, self.top_rect)
        pygame.draw.rect(screen, GREEN, self.bottom_rect)
        # Add pipe caps
        pygame.draw.rect(screen, GREEN, (self.x - 2, self.height - 20, PIPE_WIDTH + 4, 20))
        pygame.draw.rect(screen, GREEN, (self.x - 2, self.height + PIPE_GAP, PIPE_WIDTH + 4, 20))
    
    def collides_with(self, bird):
        return bird.rect.colliderect(self.top_rect) or bird.rect.colliderect(self.bottom_rect)
    
    def is_off_screen(self):
        return self.x + PIPE_WIDTH < 0

class Game:
    def __init__(self):
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        pygame.display.set_caption("Flappy Bird")
        self.clock = pygame.time.Clock()
        self.font = pygame.font.Font(None, 36)
        self.reset_game()
    
    def reset_game(self):
        self.bird = Bird()
        self.pipes = []
        self.score = 0
        self.game_over = False
        self.game_started = False
    
    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_SPACE:
                    if not self.game_started:
                        self.game_started = True
                    elif self.game_over:
                        self.reset_game()
                        self.game_started = True
                    else:
                        self.bird.jump()
        return True
    
    def update(self):
        if not self.game_started or self.game_over:
            return
        
        self.bird.update()
        
        # Add new pipes
        if len(self.pipes) == 0 or self.pipes[-1].x < SCREEN_WIDTH - 200:
            self.pipes.append(Pipe(SCREEN_WIDTH))
        
        # Update pipes
        for pipe in self.pipes[:]:
            pipe.update()
            
            # Check for scoring
            if not pipe.passed and pipe.x + PIPE_WIDTH < self.bird.x:
                pipe.passed = True
                self.score += 1
            
            # Check collision
            if pipe.collides_with(self.bird):
                self.game_over = True
            
            # Remove off-screen pipes
            if pipe.is_off_screen():
                self.pipes.remove(pipe)
        
        # Check ground collision
        if self.bird.y + BIRD_HEIGHT >= SCREEN_HEIGHT - GROUND_HEIGHT:
            self.game_over = True
    
    def draw(self):
        # Sky background
        self.screen.fill(BLUE)
        
        # Draw pipes
        for pipe in self.pipes:
            pipe.draw(self.screen)
        
        # Draw ground
        pygame.draw.rect(self.screen, BROWN, 
                        (0, SCREEN_HEIGHT - GROUND_HEIGHT, SCREEN_WIDTH, GROUND_HEIGHT))
        
        # Draw bird
        self.bird.draw(self.screen)
        
        # Draw score
        score_text = self.font.render(f"Score: {self.score}", True, WHITE)
        self.screen.blit(score_text, (10, 10))
        
        # Draw game messages
        if not self.game_started:
            start_text = self.font.render("Press SPACE to start", True, WHITE)
            text_rect = start_text.get_rect(center=(SCREEN_WIDTH//2, SCREEN_HEIGHT//2))
            self.screen.blit(start_text, text_rect)
        elif self.game_over:
            game_over_text = self.font.render("Game Over!", True, WHITE)
            restart_text = self.font.render("Press SPACE to restart", True, WHITE)
            
            game_over_rect = game_over_text.get_rect(center=(SCREEN_WIDTH//2, SCREEN_HEIGHT//2 - 20))
            restart_rect = restart_text.get_rect(center=(SCREEN_WIDTH//2, SCREEN_HEIGHT//2 + 20))
            
            self.screen.blit(game_over_text, game_over_rect)
            self.screen.blit(restart_text, restart_rect)
        
        pygame.display.flip()
    
    def run(self):
        running = True
        while running:
            running = self.handle_events()
            self.update()
            self.draw()
            self.clock.tick(FPS)
        
        pygame.quit()
        sys.exit()

# Run the game
if __name__ == "__main__":
    game = Game()
    game.run()