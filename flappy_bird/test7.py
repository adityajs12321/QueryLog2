# text = "lmfao lmfao 'assets/generated_image.png' rrrr 'assets/background.png'"
text = """import pygame
import random
import os

# Initialize Pygame
pygame.init()

# Screen dimensions
SCREEN_WIDTH = 640
SCREEN_HEIGHT = 480
SCREEN = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
pygame.display.set_caption("Flappy Bird Clone")

# Colors
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
GREEN = (0, 200, 0)
RED = (255, 0, 0)
YELLOW = (255, 255, 0)
LIGHT_BLUE = (135, 206, 235) # Sky color

# Game constants
FPS = 60
BIRD_GRAVITY = 0.5
BIRD_JUMP_VELOCITY = -9
PIPE_SPEED = 3
PIPE_WIDTH = 70
PIPE_GAP_HEIGHT = 150 # Vertical gap between top and bottom pipes
PIPE_SPAWN_INTERVAL = 1500 # milliseconds (how often new pipes appear)
GROUND_HEIGHT = 50 # Simulate ground at the bottom

# Bird properties
BIRD_START_X = 100
BIRD_START_Y = SCREEN_HEIGHT // 2 - 10
BIRD_WIDTH = 34
BIRD_HEIGHT = 24

# Font
font = pygame.font.Font(None, 50)
small_font = pygame.font.Font(None, 30)

# --- Asset Loading (with fallback) ---
# Helper function to load and scale assets
def load_asset(path, scale=None):
    try:
        img = pygame.image.load(path).convert_alpha()
        if scale:
            img = pygame.transform.scale(img, scale)
        return img
    except pygame.error:
        print(f"Warning: Could not load asset '{path}'. Using fallback.")
        return None

# Background image
BACKGROUND = load_asset('assets/background.png', (SCREEN_WIDTH, SCREEN_HEIGHT))
if BACKGROUND is None:
    BACKGROUND = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
    BACKGROUND.fill(LIGHT_BLUE)

# Bird image
BIRD_IMAGE = load_asset('assets/bird.png', (BIRD_WIDTH, BIRD_HEIGHT))
if BIRD_IMAGE is None:
    BIRD_IMAGE = pygame.Surface((BIRD_WIDTH, BIRD_HEIGHT))
    BIRD_IMAGE.fill(YELLOW) # Fallback color

# Pipe images (scaled dynamically in Pipe class)
PIPE_TOP_IMAGE = load_asset('assets/pipe_top.png')
PIPE_BOTTOM_IMAGE = load_asset('assets/pipe_bottom.png')

# Ground image
GROUND_IMAGE = load_asset('assets/ground.png', (SCREEN_WIDTH, GROUND_HEIGHT))
if GROUND_IMAGE is None:
    GROUND_IMAGE = pygame.Surface((SCREEN_WIDTH, GROUND_HEIGHT))
    GROUND_IMAGE.fill(GREEN) # Fallback color

# --- Game Classes ---
class Bird:
    def __init__(self):
        self.rect = BIRD_IMAGE.get_rect(x=BIRD_START_X, y=BIRD_START_Y)
        self.velocity = 0

    def flap(self):
        self.velocity = BIRD_JUMP_VELOCITY

    def update(self):
        self.velocity += BIRD_GRAVITY
        self.rect.y += self.velocity

        # Keep bird within top screen bounds
        if self.rect.top < 0:
            self.rect.top = 0
            self.velocity = 0

    def draw(self):
        SCREEN.blit(BIRD_IMAGE, self.rect)

class Pipe:
    def __init__(self, x):
        self.x = x
        
        # Determine the height of the top pipe randomly
        # Ensure there's enough space for both pipes and the gap, plus a buffer
        min_top_pipe_height = 50 
        max_top_pipe_height = SCREEN_HEIGHT - GROUND_HEIGHT - PIPE_GAP_HEIGHT - 50
        
        self.top_pipe_height = random.randint(min_top_pipe_height, max_top_pipe_height)

        self.bottom_pipe_y = self.top_pipe_height + PIPE_GAP_HEIGHT
        self.bottom_pipe_height = SCREEN_HEIGHT - GROUND_HEIGHT - self.bottom_pipe_y

        # Create rects for collision detection
        self.top_rect = pygame.Rect(self.x, 0, PIPE_WIDTH, self.top_pipe_height)
        self.bottom_rect = pygame.Rect(self.x, self.bottom_pipe_y, PIPE_WIDTH, self.bottom_pipe_height)

        self.passed = False # To track if the bird has passed this pipe for scoring

        # Scale pipe images if loaded, otherwise use rects directly for drawing
        if PIPE_TOP_IMAGE and PIPE_BOTTOM_IMAGE:
            self.scaled_top_image = pygame.transform.scale(PIPE_TOP_IMAGE, (PIPE_WIDTH, self.top_pipe_height))
            self.scaled_bottom_image = pygame.transform.scale(PIPE_BOTTOM_IMAGE, (PIPE_WIDTH, self.bottom_pipe_height))
        else:
            self.scaled_top_image = None
            self.scaled_bottom_image = None

    def update(self):
        self.x -= PIPE_SPEED
        self.top_rect.x = self.x
        self.bottom_rect.x = self.x

    def draw(self):
        if self.scaled_top_image and self.scaled_bottom_image:
            SCREEN.blit(self.scaled_top_image, self.top_rect)
            SCREEN.blit(self.scaled_bottom_image, self.bottom_rect)
        else:
            # Fallback to drawing rectangles if images not loaded
            pygame.draw.rect(SCREEN, GREEN, self.top_rect)
            pygame.draw.rect(SCREEN, GREEN, self.bottom_rect)

    def off_screen(self):
        return self.x + PIPE_WIDTH < 0

# --- Game Functions ---
def reset_game():
    global bird, pipes, score, game_state, last_pipe_spawn_time
    bird = Bird()
    pipes = []
    score = 0
    game_state = "start" # After game over, go back to start screen
    last_pipe_spawn_time = pygame.time.get_ticks()

def draw_text(text, font, color, x, y):
    text_surface = font.render(text, True, color)
    text_rect = text_surface.get_rect(center=(x, y))
    SCREEN.blit(text_surface, text_rect)

# --- Main Game Loop Setup ---
clock = pygame.time.Clock()
bird = Bird()
pipes = []
score = 0
game_state = "start" # Possible states: "start", "playing", "game_over"
last_pipe_spawn_time = pygame.time.get_ticks() # Tracks when the last pipe was spawned

running = True
while running:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_SPACE:
                if game_state == "start":
                    game_state = "playing"
                    bird.flap() # Initial flap to start the game
                elif game_state == "playing":
                    bird.flap()
                elif game_state == "game_over":
                    reset_game()
        if event.type == pygame.MOUSEBUTTONDOWN: # Allow mouse click to flap/start/restart
            if game_state == "start":
                game_state = "playing"
                bird.flap()
            elif game_state == "playing":
                bird.flap()
            elif game_state == "game_over":
                reset_game()

    # --- Game Logic ---
    if game_state == "playing":
        bird.update()

        # Check for collision with ground
        if bird.rect.bottom >= SCREEN_HEIGHT - GROUND_HEIGHT:
            game_state = "game_over"

        # Spawn new pipes
        now = pygame.time.get_ticks()
        if now - last_pipe_spawn_time > PIPE_SPAWN_INTERVAL:
            pipes.append(Pipe(SCREEN_WIDTH))
            last_pipe_spawn_time = now

        # Update and draw pipes, check collisions and scoring
        pipes_to_remove = []
        for pipe in pipes:
            pipe.update()
            
            # Collision detection with bird
            if bird.rect.colliderect(pipe.top_rect) or bird.rect.colliderect(pipe.bottom_rect):
                game_state = "game_over"
            
            # Scoring: check if bird has passed the pipe
            if pipe.top_rect.right < bird.rect.left and not pipe.passed:
                score += 1
                pipe.passed = True # Mark as passed to avoid multiple scores for one pipe
            
            # Remove pipes that are off-screen
            if pipe.off_screen():
                pipes_to_remove.append(pipe)

        # Clean up off-screen pipes
        for pipe in pipes_to_remove:
            pipes.remove(pipe)

    # --- Drawing ---
    SCREEN.blit(BACKGROUND, (0, 0)) # Draw background first

    for pipe in pipes:
        pipe.draw() # Draw all active pipes

    bird.draw() # Draw the bird

    SCREEN.blit(GROUND_IMAGE, (0, SCREEN_HEIGHT - GROUND_HEIGHT)) # Draw ground on top

    # Display score always during gameplay
    draw_text(f"Score: {score}", small_font, BLACK, SCREEN_WIDTH // 2, 30)

    # Display game state messages
    if game_state == "start":
        draw_text("Flappy Bird Clone", font, BLACK, SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 - 50)
        draw_text("Press SPACE or Click to Start", small_font, BLACK, SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 + 10)
    elif game_state == "game_over":
        draw_text("GAME OVER!", font, RED, SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 - 50)
        draw_text(f"Your Score: {score}", small_font, BLACK, SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 + 10)
        draw_text("Press SPACE or Click to Restart", small_font, BLACK, SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 + 50)

    pygame.display.flip() # Update the full display Surface to the screen
    clock.tick(FPS) # Control frame rate

pygame.quit() # Uninitialize Pygame modules
"""

# import re

# m = re.findall("'assets/(.+?)'", text)

# print(m)

lmfao = []
lol = [56,75,24]
print(lmfao or lol)