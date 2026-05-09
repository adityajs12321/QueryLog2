import pygame

# --- Constants ---
BOARD_SIZE = 640 # Width and height of the chessboard area
STATUS_BAR_HEIGHT = 40
WIDTH, HEIGHT = BOARD_SIZE, BOARD_SIZE + STATUS_BAR_HEIGHT
ROWS, COLS = 8, 8
SQUARE_SIZE = BOARD_SIZE // COLS

# Colors
WHITE_COLOR = (255, 255, 255)
BLACK_COLOR = (0, 0, 0)
LIGHT_SQUARE = (200, 200, 200) # Light squares
DARK_SQUARE = (100, 100, 100)  # Dark squares
SELECTED_COLOR = (0, 255, 0)  # Green for selected piece
HIGHLIGHT_COLOR = (255, 255, 0) # Yellow for possible moves
CHECK_COLOR = (255, 0, 0) # Red for king in check
STATUS_BAR_BACKGROUND = (150, 150, 150) # Gray for status bar

# Piece image paths (assuming assets/ directory exists)
PIECE_IMAGES = {
    'white_pawn': 'assets/white_pawn.png',
    'white_rook': 'assets/white_rook.png',
    'white_knight': 'assets/white_knight.png',
    'white_bishop': 'assets/white_bishop.png',
    'white_queen': 'assets/white_queen.png',
    'white_king': 'assets/white_king.png',
    'black_pawn': 'assets/black_pawn.png',
    'black_rook': 'assets/black_rook.png',
    'black_knight': 'assets/black_knight.png',
    'black_bishop': 'assets/black_bishop.png',
    'black_queen': 'assets/black_queen.png',
    'black_king': 'assets/black_king.png',
}

# --- Pygame Initialization ---
pygame.init()
SCREEN = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Pygame Chess")

# --- Load and Scale Piece Images ---
LOADED_PIECES = {}
for name, path in PIECE_IMAGES.items():
    try:
        image = pygame.image.load(path).convert_alpha()
        LOADED_PIECES[name] = pygame.transform.scale(image, (SQUARE_SIZE, SQUARE_SIZE))
    except pygame.error as e:
        print(f"Could not load image {path}: {e}")
        # Create a placeholder if image fails to load
        LOADED_PIECES[name] = pygame.Surface((SQUARE_SIZE, SQUARE_SIZE), pygame.SRCALPHA)
        LOADED_PIECES[name].fill((255, 0, 255, 128)) # Pink transparent placeholder
        font = pygame.font.Font(None, 24)
        piece_letter = name.split('_')[1][0].upper() # First letter of piece type, capitalized
        color_letter = name.split('_')[0][0].upper() # First letter of color, capitalized
        text_surf = font.render(f"{color_letter}{piece_letter}", True, BLACK_COLOR)
        text_rect = text_surf.get_rect(center=(SQUARE_SIZE//2, SQUARE_SIZE//2))
        LOADED_PIECES[name].blit(text_surf, text_rect)


# --- Piece Class ---
class Piece:
    def __init__(self, color, piece_type, row, col):
        self.color = color # 'white' or 'black'
        self.type = piece_type # 'pawn', 'rook', 'knight', 'bishop', 'queen', 'king'
        self.image = LOADED_PIECES[f"{color}_{piece_type}"]
        self.row = row
        self.col = col
        self.has_moved = False # For castling, pawn double move (though castling not implemented)

    def __repr__(self):
        return f"{self.color} {self.type} at ({self.row}, {self.col})"

    def draw(self, screen):
        screen.blit(self.image, (self.col * SQUARE_SIZE, self.row * SQUARE_SIZE))

    def get_pseudo_legal_moves(self, board_state):
        # This method returns all moves possible by the piece's type,
        # ignoring whether it puts the King in check.
        # It handles blocking by other pieces.
        moves = []
        
        # Helper to add moves (avoids duplicate code for sliding pieces)
        def add_sliding_moves(dr, dc):
            for i in range(1, 8):
                new_row, new_col = self.row + dr * i, self.col + dc * i
                if 0 <= new_row < ROWS and 0 <= new_col < COLS:
                    target_piece = board_state[new_row][new_col]
                    if target_piece is None:
                        moves.append((new_row, new_col))
                    elif target_piece.color != self.color:
                        moves.append((new_row, new_col))
                        break # Blocked by opponent, but can capture
                    else: # Blocked by own piece
                        break
                else:
                    break # Out of bounds

        if self.type == 'pawn':
            direction = -1 if self.color == 'white' else 1
            # Single step forward
            new_row = self.row + direction
            if 0 <= new_row < ROWS and board_state[new_row][self.col] is None:
                moves.append((new_row, self.col))
                # Double step on first move
                if not self.has_moved:
                    double_step_row = self.row + 2 * direction
                    if 0 <= double_step_row < ROWS and board_state[double_step_row][self.col] is None:
                        moves.append((double_step_row, self.col))
            # Captures
            for dc in [-1, 1]:
                target_col = self.col + dc
                if 0 <= new_row < ROWS and 0 <= target_col < COLS:
                    target_piece = board_state[new_row][target_col]
                    if target_piece and target_piece.color != self.color:
                        moves.append((new_row, target_col))

        elif self.type == 'rook':
            directions = [(0, 1), (0, -1), (1, 0), (-1, 0)] # right, left, down, up
            for dr, dc in directions:
                add_sliding_moves(dr, dc)

        elif self.type == 'knight':
            L_moves = [(-2, -1), (-2, 1), (-1, -2), (-1, 2), (1, -2), (1, 2), (2, -1), (2, 1)]
            for dr, dc in L_moves:
                new_row, new_col = self.row + dr, self.col + dc
                if 0 <= new_row < ROWS and 0 <= new_col < COLS:
                    target_piece = board_state[new_row][new_col]
                    if target_piece is None or target_piece.color != self.color:
                        moves.append((new_row, new_col))

        elif self.type == 'bishop':
            directions = [(1, 1), (1, -1), (-1, 1), (-1, -1)] # diag down-right, down-left, up-right, up-left
            for dr, dc in directions:
                add_sliding_moves(dr, dc)

        elif self.type == 'queen':
            # Queen combines Rook and Bishop moves
            directions = [(0, 1), (0, -1), (1, 0), (-1, 0), (1, 1), (1, -1), (-1, 1), (-1, -1)]
            for dr, dc in directions:
                add_sliding_moves(dr, dc)

        elif self.type == 'king':
            # King moves one step in any direction
            directions = [(0, 1), (0, -1), (1, 0), (-1, 0), (1, 1), (1, -1), (-1, 1), (-1, -1)]
            for dr, dc in directions:
                new_row, new_col = self.row + dr, self.col + dc
                if 0 <= new_row < ROWS and 0 <= new_col < COLS:
                    target_piece = board_state[new_row][new_col]
                    if target_piece is None or target_piece.color != self.color:
                        moves.append((new_row, new_col))
            # No castling in this pseudo-legal move generation, handled by Game class
            
        return moves

# --- Game Logic ---
class Game:
    def __init__(self):
        self.board = self.setup_board()
        self.turn = 'white'
        self.selected_piece_pos = None # (row, col) of selected piece
        self.legal_moves = [] # List of (row, col) for legal moves of selected_piece
        self.king_in_check = {'white': False, 'black': False}
        self.game_over = False
        self.winner = None
        self.font = pygame.font.Font(None, 36)


    def setup_board(self):
        board = [[None for _ in range(COLS)] for _ in range(ROWS)]

        # Pawns
        for c in range(COLS):
            board[1][c] = Piece('black', 'pawn', 1, c)
            board[6][c] = Piece('white', 'pawn', 6, c)

        # Rooks
        board[0][0] = Piece('black', 'rook', 0, 0)
        board[0][7] = Piece('black', 'rook', 0, 7)
        board[7][0] = Piece('white', 'rook', 7, 0)
        board[7][7] = Piece('white', 'rook', 7, 7)

        # Knights
        board[0][1] = Piece('black', 'knight', 0, 1)
        board[0][6] = Piece('black', 'knight', 0, 6)
        board[7][1] = Piece('white', 'knight', 7, 1)
        board[7][6] = Piece('white', 'knight', 7, 6)

        # Bishops
        board[0][2] = Piece('black', 'bishop', 0, 2)
        board[0][5] = Piece('black', 'bishop', 0, 5)
        board[7][2] = Piece('white', 'bishop', 7, 2)
        board[7][5] = Piece('white', 'bishop', 7, 5)

        # Queens
        board[0][3] = Piece('black', 'queen', 0, 3)
        board[7][3] = Piece('white', 'queen', 7, 3)

        # Kings
        board[0][4] = Piece('black', 'king', 0, 4)
        board[7][4] = Piece('white', 'king', 7, 4)

        return board

    def find_king_position_on_board(self, board_state, color):
        for r in range(ROWS):
            for c in range(COLS):
                piece = board_state[r][c]
                if piece and piece.color == color and piece.type == 'king':
                    return (r, c)
        return None

    def is_in_check(self, board_state, player_color):
        king_pos = self.find_king_position_on_board(board_state, player_color)
        if not king_pos: 
            return False # King has been captured, which means game over

        kr, kc = king_pos
        opponent_color = 'white' if player_color == 'black' else 'black'

        for r in range(ROWS):
            for c in range(COLS):
                piece = board_state[r][c]
                if piece and piece.color == opponent_color:
                    # Check if this opponent piece can attack the king's square
                    pseudo_moves = piece.get_pseudo_legal_moves(board_state)
                    if (kr, kc) in pseudo_moves:
                        return True
        return False

    def get_legal_moves_for_piece(self, piece, start_row, start_col):
        if not piece or piece.color != self.turn:
            return []

        pseudo_moves = piece.get_pseudo_legal_moves(self.board)
        legal_moves = []

        for move_r, move_c in pseudo_moves:
            # Simulate the move on a temporary board state
            # Create a deep copy of the board to simulate the move without affecting the actual game board
            simulated_board = [row[:] for row in self.board] 
            
            # Temporarily move the piece on the simulated board
            temp_piece = simulated_board[start_row][start_col] # The piece we are moving
            simulated_board[start_row][start_col] = None # Remove from start
            simulated_board[move_r][move_c] = temp_piece # Place at destination

            # Update the piece's coordinates temporarily for the check, then revert
            original_piece_row, original_piece_col = temp_piece.row, temp_piece.col
            temp_piece.row, temp_piece.col = move_r, move_c

            if not self.is_in_check(simulated_board, self.turn):
                legal_moves.append((move_r, move_c))
            
            # Revert piece's coordinates in case it's used elsewhere for other checks (good practice)
            temp_piece.row, temp_piece.col = original_piece_row, original_piece_col

        return legal_moves

    def handle_click(self, row, col):
        if self.game_over:
            return

        clicked_piece = self.board[row][col]

        if self.selected_piece_pos:
            sr, sc = self.selected_piece_pos
            
            # Check if clicked on a legal move square
            if (row, col) in self.legal_moves:
                self.move_piece(sr, sc, row, col)
                self.selected_piece_pos = None
                self.legal_moves = []
                self.switch_turn()
            elif clicked_piece and clicked_piece.color == self.turn:
                # Clicked on own piece, select new piece
                self.selected_piece_pos = (row, col)
                piece_obj = self.board[row][col]
                self.legal_moves = self.get_legal_moves_for_piece(piece_obj, row, col)
            else:
                # Invalid move or clicked on opponent's piece not on a valid path, deselect
                self.selected_piece_pos = None
                self.legal_moves = []
        else:
            # No piece selected, try to select one
            if clicked_piece and clicked_piece.color == self.turn:
                self.selected_piece_pos = (row, col)
                self.legal_moves = self.get_legal_moves_for_piece(clicked_piece, row, col)

        # Update check status after any potential board change
        self.king_in_check['white'] = self.is_in_check(self.board, 'white')
        self.king_in_check['black'] = self.is_in_check(self.board, 'black')
        
        # Check for game over (basic checkmate/stalemate logic)
        self.check_game_over()


    def move_piece(self, start_row, start_col, end_row, end_col):
        piece_to_move = self.board[start_row][start_col]
        if not piece_to_move:
            return

        # Handle pawn promotion
        if piece_to_move.type == 'pawn' and \
           ((piece_to_move.color == 'white' and end_row == 0) or \
            (piece_to_move.color == 'black' and end_row == ROWS - 1)):
            self.board[end_row][end_col] = Piece(piece_to_move.color, 'queen', end_row, end_col) # Always promote to Queen
        else:
            self.board[end_row][end_col] = piece_to_move
        
        self.board[start_row][start_col] = None # Clear the starting square
        
        # Update piece's internal position
        piece_to_move.row = end_row
        piece_to_move.col = end_col
        piece_to_move.has_moved = True # Mark piece as moved (important for pawn double move logic)


    def switch_turn(self):
        self.turn = 'black' if self.turn == 'white' else 'white'

    def check_game_over(self):
        # Determine if the current player has any legal moves
        has_any_legal_move = False
        for r in range(ROWS):
            for c in range(COLS):
                piece = self.board[r][c]
                if piece and piece.color == self.turn:
                    if self.get_legal_moves_for_piece(piece, r, c):
                        has_any_legal_move = True
                        break
            if has_any_legal_move:
                break
        
        if not has_any_legal_move:
            if self.is_in_check(self.board, self.turn):
                self.game_over = True
                self.winner = 'white' if self.turn == 'black' else 'black'
                print(f"Checkmate! {self.winner} wins!")
            else:
                self.game_over = True
                self.winner = 'Stalemate'
                print("Stalemate! It's a draw.")


    def draw_board(self, screen):
        # Draw board squares
        for r in range(ROWS):
            for c in range(COLS):
                color = LIGHT_SQUARE if (r + c) % 2 == 0 else DARK_SQUARE
                pygame.draw.rect(screen, color, (c * SQUARE_SIZE, r * SQUARE_SIZE, SQUARE_SIZE, SQUARE_SIZE))

        # Highlight selected piece
        if self.selected_piece_pos:
            sr, sc = self.selected_piece_pos
            pygame.draw.rect(screen, SELECTED_COLOR, (sc * SQUARE_SIZE, sr * SQUARE_SIZE, SQUARE_SIZE, SQUARE_SIZE), 3)

        # Highlight legal moves
        for r, c in self.legal_moves:
            # Draw a circle in the center of the target square
            center_x = c * SQUARE_SIZE + SQUARE_SIZE // 2
            center_y = r * SQUARE_SIZE + SQUARE_SIZE // 2
            pygame.draw.circle(screen, HIGHLIGHT_COLOR, (center_x, center_y), SQUARE_SIZE // 4)
        
        # Highlight king in check
        king_pos = self.find_king_position_on_board(self.board, self.turn)
        if king_pos and self.is_in_check(self.board, self.turn):
             kr, kc = king_pos
             pygame.draw.rect(screen, CHECK_COLOR, (kc * SQUARE_SIZE, kr * SQUARE_SIZE, SQUARE_SIZE, SQUARE_SIZE), 5)


        # Draw pieces
        for r in range(ROWS):
            for c in range(COLS):
                piece = self.board[r][c]
                if piece:
                    piece.draw(screen)

    def draw_status_bar(self, screen):
        # Draw background for status bar
        pygame.draw.rect(screen, STATUS_BAR_BACKGROUND, (0, BOARD_SIZE, WIDTH, STATUS_BAR_HEIGHT))

        status_text = f"{self.turn.capitalize()}'s Turn"
        if self.game_over:
            status_text = f"GAME OVER! {self.winner} {'wins' if self.winner != 'Stalemate' else 'draws'}. Press 'R' to Restart."
        
        text_surface = self.font.render(status_text, True, BLACK_COLOR)
        # Center the text in the status bar
        text_rect = text_surface.get_rect(center=(WIDTH // 2, BOARD_SIZE + STATUS_BAR_HEIGHT // 2))
        screen.blit(text_surface, text_rect)


# --- Main Game Loop ---
def main():
    game = Game()
    running = True
    clock = pygame.time.Clock()

    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            if event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1: # Left click
                    mouse_x, mouse_y = event.pos
                    if mouse_y < BOARD_SIZE: # Only handle clicks on the board area
                        clicked_col = mouse_x // SQUARE_SIZE
                        clicked_row = mouse_y // SQUARE_SIZE
                        game.handle_click(clicked_row, clicked_col)
            
            # If game over, offer restart
            if game.game_over and event.type == pygame.KEYDOWN:
                if event.key == pygame.K_r: # 'R' key to restart
                    game = Game() # Reset game
                    print("Game restarted!")


        # Drawing
        game.draw_board(SCREEN)
        game.draw_status_bar(SCREEN)

        pygame.display.flip()
        clock.tick(60)

    pygame.quit()

if __name__ == "__main__":
    main()