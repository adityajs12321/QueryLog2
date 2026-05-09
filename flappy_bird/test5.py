import pygame
import random
import sys

# --- Game Constants ---
SCREEN_WIDTH = 640
SCREEN_HEIGHT = 480
FPS = 60

# Colors
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
SKY_BLUE = (135, 206, 235)
GREEN = (0, 128, 0)
RED = (255, 0, 0)

# Bird properties
BIRD_WIDTH = 30
BIRD_HEIGHT = 20
BIRD_START_X = SCREEN_WIDTH // 4
BIRD_FLAP_VELOCITY = -7
GRAVITY = 0.5
MAX_FALL_VELOCITY = 10

# Pipe properties
PIPE_WIDTH = 60
PIPE_GAP = 120  # Vertical gap between top and bottom pipe
PIPE_SPEED = 3
PIPE_SPAWN_INTERVAL = 1500  # Milliseconds between new pipes
PIPE_MIN_HEIGHT = 50
PIPE_MAX_HEIGHT = SCREEN_HEIGHT - PIPE_GAP - PIPE_MIN_HEIGHT

# Ground properties (to prevent bird from falling off screen completely)
GROUND_HEIGHT = 30

# Initialize Pygame
pygame.init()

# --- Setup Screen ---
screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
pygame.display.set_caption("Flappy Pygame")
clock = pygame.time.Clock()

# --- Fonts ---
font = pygame.font.Font(None, 36)
game_over_font = pygame.font.Font(None, 48)
instruction_font = pygame.font.Font(None, 24)

# --- Game Variables ---
bird_y = SCREEN_HEIGHT // 2
bird_velocity_y = 0
score = 0
game_active = False  # False = Menu/Game Over, True = Playing
pipes = []  # List to store pipe dictionaries: {'rect_top': Rect, 'rect_bottom': Rect, 'passed': False}
last_pipe_spawn_time = pygame.time.get_ticks()

# Image paths (empty as we are drawing shapes)
image_paths = []

# --- Helper Functions ---

def draw_bird(x, y):
    """Draws the bird as a yellow rectangle."""
    pygame.draw.rect(screen, (255, 255, 0), (x, y, BIRD_WIDTH, BIRD_HEIGHT))

def create_pipe():
    """Generates a new pipe pair."""
    top_pipe_height = random.randint(PIPE_MIN_HEIGHT, PIPE_MAX_HEIGHT)
    bottom_pipe_y = top_pipe_height + PIPE_GAP
    bottom_pipe_height = SCREEN_HEIGHT - bottom_pipe_y - GROUND_HEIGHT

    rect_top = pygame.Rect(SCREEN_WIDTH, 0, PIPE_WIDTH, top_pipe_height)
    rect_bottom = pygame.Rect(SCREEN_WIDTH, bottom_pipe_y, PIPE_WIDTH, bottom_pipe_height)
    return {'rect_top': rect_top, 'rect_bottom': rect_bottom, 'passed': False}

def draw_pipes(pipes_list):
    """Draws all pipes in the list."""
    for pipe in pipes_list:
        pygame.draw.rect(screen, GREEN, pipe['rect_top'])
        pygame.draw.rect(screen, GREEN, pipe['rect_bottom'])

def move_pipes(pipes_list):
    """Moves pipes to the left and removes off-screen pipes."""
    for pipe in pipes_list:
        pipe['rect_top'].x -= PIPE_SPEED
        pipe['rect_bottom'].x -= PIPE_SPEED
    return [pipe for pipe in pipes_list if pipe['rect_top'].right > 0]

def check_collision(bird_rect, pipes_list):
    """Checks for collisions between the bird and pipes or ground."""
    # Ground collision
    if bird_rect.bottom >= SCREEN_HEIGHT - GROUND_HEIGHT:
        return True
    # Ceiling collision (optional, Flappy Bird usually doesn't have a ceiling limit)
    if bird_rect.top <= 0:
        return True

    # Pipe collision
    for pipe in pipes_list:
        if bird_rect.colliderect(pipe['rect_top']) or bird_rect.colliderect(pipe['rect_bottom']):
            return True
    return False

def reset_game():
    """Resets all game variables to their initial state."""
    global bird_y, bird_velocity_y, score, pipes, game_active, last_pipe_spawn_time
    bird_y = SCREEN_HEIGHT // 2
    bird_velocity_y = 0
    score = 0
    pipes = []
    game_active = True
    last_pipe_spawn_time = pygame.time.get_ticks() + PIPE_SPAWN_INTERVAL # Initial delay for first pipe

# --- Main Game Loop ---
running = True
while running:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_SPACE:
                if game_active:
                    bird_velocity_y = BIRD_FLAP_VELOCITY
                else:
                    reset_game()

    # --- Game Logic ---
    if game_active:
        # Bird movement
        bird_velocity_y += GRAVITY
        bird_velocity_y = min(bird_velocity_y, MAX_FALL_VELOCITY) # Limit max fall speed
        bird_y += bird_velocity_y

        bird_rect = pygame.Rect(BIRD_START_X, int(bird_y), BIRD_WIDTH, BIRD_HEIGHT)

        # Pipe spawning
        current_time = pygame.time.get_ticks()
        if current_time - last_pipe_spawn_time > PIPE_SPAWN_INTERVAL:
            pipes.append(create_pipe())
            last_pipe_spawn_time = current_time

        # Move pipes
        pipes = move_pipes(pipes)

        # Score update
        for pipe in pipes:
            if not pipe['passed'] and pipe['rect_top'].right < BIRD_START_X:
                score += 1
                pipe['passed'] = True

        # Collision check
        if check_collision(bird_rect, pipes):
            game_active = False

    # --- Drawing ---
    screen.fill(SKY_BLUE) # Background

    # Draw pipes
    draw_pipes(pipes)

    # Draw ground
    pygame.draw.rect(screen, GREEN, (0, SCREEN_HEIGHT - GROUND_HEIGHT, SCREEN_WIDTH, GROUND_HEIGHT))

    # Draw bird
    if game_active or not game_active and bird_y < SCREEN_HEIGHT - GROUND_HEIGHT - BIRD_HEIGHT:
         # Only draw bird if game is active or if it's falling to ground after collision
        draw_bird(BIRD_START_X, int(bird_y))

    # Display score
    score_text = font.render(f"Score: {score}", True, BLACK)
    screen.blit(score_text, (10, 10))

    # Game Over / Start Screen
    if not game_active:
        if score == 0: # Start screen
            title_text = game_over_font.render("Flappy Pygame", True, BLACK)
            title_rect = title_text.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 - 50))
            screen.blit(title_text, title_rect)

            instruction_text = instruction_font.render("Press SPACE to Start", True, BLACK)
            instruction_rect = instruction_text.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 + 10))
            screen.blit(instruction_text, instruction_rect)
        else: # Game Over screen
            game_over_text = game_over_font.render("GAME OVER", True, RED)
            game_over_rect = game_over_text.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 - 50))
            screen.blit(game_over_text, game_over_rect)

            final_score_text = font.render(f"Final Score: {score}", True, BLACK)
            final_score_rect = final_score_text.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2))
            screen.blit(final_score_text, final_score_rect)

            restart_text = instruction_font.render("Press SPACE to Play Again", True, BLACK)
            restart_rect = restart_text.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 + 40))
            screen.blit(restart_text, restart_rect)


    pygame.display.flip()
    clock.tick(FPS)

# --- Quit Pygame ---
pygame.quit()
sys.exit()