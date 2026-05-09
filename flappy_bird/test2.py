import pygame
import random
import sys

# Initialize Pygame
pygame.init()

# --- Constants ---
SCREEN_WIDTH = 288
SCREEN_HEIGHT = 512
FPS = 60
GRAVITY = 0.25
BIRD_FLAP = -6
PIPE_GAP = 100
PIPE_SPAWN_TIME = 1500  # milliseconds
SCORE_FONT = pygame.font.Font(None, 40)

# --- Set up the display ---
screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
pygame.display.set_caption('Flappy Bird')
clock = pygame.time.Clock()

# --- Load Images ---
try:
    bg_surface = pygame.image.load('assets/background-day.png').convert()
    bird_downflap = pygame.image.load('assets/bluebird-downflap.png').convert_alpha()
    bird_midflap = pygame.image.load('assets/bluebird-midflap.png').convert_alpha()
    bird_upflap = pygame.image.load('assets/bluebird-upflap.png').convert_alpha()
    bird_frames = [bird_downflap, bird_midflap, bird_upflap]
    bird_index = 0
    bird_surface = bird_frames[bird_index]
    bird_rect = bird_surface.get_rect(center=(50, SCREEN_HEIGHT // 2))

    # Bird flapping animation timer
    BIRDFLAP = pygame.USEREVENT + 1
    pygame.time.set_timer(BIRDFLAP, 200)

    pipe_surface = pygame.image.load('assets/pipe-green.png').convert_alpha()
    base_surface = pygame.image.load('assets/base.png').convert()
except pygame.error as e:
    print(f"Error loading image: {e}. Make sure 'assets' folder with images is in the same directory.")
    pygame.quit()
    sys.exit()

# --- Game Variables ---
bird_movement = 0
game_active = True
score = 0
high_score = 0
pipe_list = []
SPAWNPIPE = pygame.USEREVENT
pygame.time.set_timer(SPAWNPIPE, PIPE_SPAWN_TIME)
base_x_pos = 0

# --- Functions ---
def draw_floor():
    screen.blit(base_surface, (base_x_pos, 450))
    screen.blit(base_surface, (base_x_pos + SCREEN_WIDTH, 450))

def create_pipe():
    random_pipe_pos = random.choice([200, 250, 300, 350, 400])
    bottom_pipe = pipe_surface.get_rect(midtop=(350, random_pipe_pos))
    top_pipe = pipe_surface.get_rect(midbottom=(350, random_pipe_pos - PIPE_GAP))
    return bottom_pipe, top_pipe

def move_pipes(pipes):
    for pipe in pipes:
        pipe.centerx -= 2
    return [pipe for pipe in pipes if pipe.right > -50]

def draw_pipes(pipes):
    for pipe in pipes:
        if pipe.bottom >= 512:  # Bottom pipe
            screen.blit(pipe_surface, pipe)
        else:  # Top pipe
            flip_pipe = pygame.transform.flip(pipe_surface, False, True)
            screen.blit(flip_pipe, pipe)

def check_collision(pipes):
    for pipe in pipes:
        if bird_rect.colliderect(pipe):
            return False
    if bird_rect.top <= -100 or bird_rect.bottom >= 450:
        return False
    return True

def rotate_bird(bird):
    new_bird = pygame.transform.rotozoom(bird, -bird_movement * 3, 1)
    return new_bird

def bird_animation():
    new_bird = bird_frames[bird_index]
    new_bird_rect = new_bird.get_rect(center=(50, bird_rect.centery))
    return new_bird, new_bird_rect

def update_score(current_score, high_score_val):
    if current_score > high_score_val:
        high_score_val = current_score
    return high_score_val

def display_score(game_state):
    if game_state == 'main_game':
        score_surface = SCORE_FONT.render(str(int(score)), True, (255, 255, 255))
        score_rect = score_surface.get_rect(center=(SCREEN_WIDTH // 2, 50))
        screen.blit(score_surface, score_rect)
    if game_state == 'game_over':
        score_surface = SCORE_FONT.render(f'Score: {int(score)}', True, (255, 255, 255))
        score_rect = score_surface.get_rect(center=(SCREEN_WIDTH // 2, 50))
        screen.blit(score_surface, score_rect)

        high_score_surface = SCORE_FONT.render(f'High Score: {int(high_score)}', True, (255, 255, 255))
        high_score_rect = high_score_surface.get_rect(center=(SCREEN_WIDTH // 2, 420))
        screen.blit(high_score_surface, high_score_rect)

# --- Game Loop ---
while True:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            pygame.quit()
            sys.exit()
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_SPACE and game_active:
                bird_movement = 0
                bird_movement = BIRD_FLAP
            if event.key == pygame.K_SPACE and not game_active:
                game_active = True
                pipe_list.clear()
                bird_rect.center = (50, SCREEN_HEIGHT // 2)
                bird_movement = 0
                score = 0

        if event.type == SPAWNPIPE:
            if game_active:
                pipe_list.extend(create_pipe())

        if event.type == BIRDFLAP:
            if bird_index < 2:
                bird_index += 1
            else:
                bird_index = 0
            bird_surface, bird_rect = bird_animation()

    screen.blit(bg_surface, (0, 0))

    if game_active:
        # Bird
        bird_movement += GRAVITY
        rotated_bird = rotate_bird(bird_surface)
        bird_rect.centery += bird_movement
        screen.blit(rotated_bird, bird_rect)
        game_active = check_collision(pipe_list)

        # Pipes
        pipe_list = move_pipes(pipe_list)
        draw_pipes(pipe_list)

        # Score (simple implementation, actual scoring needs more logic)
        score += 0.01
        display_score('main_game')
    else:
        # Game Over Screen (simplified, can add a restart image)
        high_score = update_score(score, high_score)
        display_score('game_over')

    # Floor
    base_x_pos -= 1
    draw_floor()
    if base_x_pos <= -SCREEN_WIDTH:
        base_x_pos = 0

    pygame.display.update()
    clock.tick(FPS)