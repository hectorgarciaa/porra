CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    password TEXT NOT NULL,
    img TEXT DEFAULT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS user_sessions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    token TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS groups (
    id SERIAL PRIMARY KEY,
    letter TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS teams (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    fifa_slug TEXT NOT NULL UNIQUE,
    group_id INTEGER NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (group_id) REFERENCES groups(id) ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS players (
    id SERIAL PRIMARY KEY,
    team_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    surname TEXT NOT NULL,
    number INTEGER NOT NULL,
    num_goals INTEGER NOT NULL DEFAULT 0,
    num_assists INTEGER NOT NULL DEFAULT 0,
    num_yellow_cards INTEGER NOT NULL DEFAULT 0,
    num_red_cards INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (team_id) REFERENCES teams(id) ON DELETE CASCADE,
    UNIQUE (team_id, number)
);

CREATE TABLE IF NOT EXISTS matches (
    id SERIAL PRIMARY KEY,
    stage TEXT NOT NULL CHECK (stage IN ('groups', '32', '16', 'qf', 'sf', '3', 'f')),
    group_id INTEGER,
    local_team_id INTEGER NOT NULL,
    away_team_id INTEGER NOT NULL,
    kickoff_at TEXT NOT NULL,
    venue TEXT,
    local_goals INTEGER,
    away_goals INTEGER,
    winner_id INTEGER,
    scorer_ids TEXT NOT NULL DEFAULT '[]',
    own_goal_ids TEXT NOT NULL DEFAULT '[]',
    assists_ids TEXT NOT NULL DEFAULT '[]',
    yellow_card_ids TEXT NOT NULL DEFAULT '[]',
    red_card_ids TEXT NOT NULL DEFAULT '[]',
    has_extra_time INTEGER NOT NULL DEFAULT 0 CHECK (has_extra_time IN (0, 1)),
    has_penalties INTEGER NOT NULL DEFAULT 0 CHECK (has_penalties IN (0, 1)),
    local_penalties INTEGER,
    away_penalties INTEGER,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (group_id) REFERENCES groups(id) ON DELETE RESTRICT,
    FOREIGN KEY (local_team_id) REFERENCES teams(id) ON DELETE RESTRICT,
    FOREIGN KEY (away_team_id) REFERENCES teams(id) ON DELETE RESTRICT,
    FOREIGN KEY (winner_id) REFERENCES teams(id) ON DELETE RESTRICT,
    CHECK (local_team_id <> away_team_id),
    CHECK (
        (stage = 'groups' AND group_id IS NOT NULL) OR
        (stage <> 'groups' AND group_id IS NULL)
    ),
    CHECK (
        has_penalties = 0 OR
        (local_penalties IS NOT NULL AND away_penalties IS NOT NULL)
    ),
    CHECK (
        has_penalties = 0 OR has_extra_time = 1
    )
);

CREATE TABLE IF NOT EXISTS predictions (
    id SERIAL PRIMARY KEY,
    player_id INTEGER NOT NULL UNIQUE,
    points INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (player_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS match_predictions (
    id SERIAL PRIMARY KEY,
    prediction_id INTEGER NOT NULL,
    match_id INTEGER NOT NULL,
    local_goals INTEGER NOT NULL,
    away_goals INTEGER NOT NULL,
    winner_team_id INTEGER,
    has_extra_time INTEGER NOT NULL DEFAULT 0 CHECK (has_extra_time IN (0, 1)),
    has_penalties INTEGER NOT NULL DEFAULT 0 CHECK (has_penalties IN (0, 1)),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (prediction_id) REFERENCES predictions(id) ON DELETE CASCADE,
    FOREIGN KEY (match_id) REFERENCES matches(id) ON DELETE CASCADE,
    FOREIGN KEY (winner_team_id) REFERENCES teams(id) ON DELETE SET NULL,
    CHECK (has_penalties = 0 OR has_extra_time = 1),
    UNIQUE (prediction_id, match_id)
);

CREATE TABLE IF NOT EXISTS global_predictions (
    id SERIAL PRIMARY KEY,
    prediction_id INTEGER NOT NULL UNIQUE,
    winner_team_id INTEGER,
    runner_up_team_id INTEGER,
    third_place_team_id INTEGER,
    fourth_place_team_id INTEGER,
    best_player_player_id INTEGER,
    best_gk_player_id INTEGER,
    best_young_player_id INTEGER,
    max_scorer_player_id INTEGER,
    max_assister_player_id INTEGER,
    max_yellow_cards_player_id INTEGER,
    max_red_cards_player_id INTEGER,
    revelation_team_id INTEGER,
    disappointment_team_id INTEGER,
    revelation_player_id INTEGER,
    disappointment_player_id INTEGER,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (prediction_id) REFERENCES predictions(id) ON DELETE CASCADE,
    FOREIGN KEY (winner_team_id) REFERENCES teams(id) ON DELETE SET NULL,
    FOREIGN KEY (runner_up_team_id) REFERENCES teams(id) ON DELETE SET NULL,
    FOREIGN KEY (third_place_team_id) REFERENCES teams(id) ON DELETE SET NULL,
    FOREIGN KEY (fourth_place_team_id) REFERENCES teams(id) ON DELETE SET NULL,
    FOREIGN KEY (best_player_player_id) REFERENCES players(id) ON DELETE SET NULL,
    FOREIGN KEY (best_gk_player_id) REFERENCES players(id) ON DELETE SET NULL,
    FOREIGN KEY (best_young_player_id) REFERENCES players(id) ON DELETE SET NULL,
    FOREIGN KEY (max_scorer_player_id) REFERENCES players(id) ON DELETE SET NULL,
    FOREIGN KEY (max_assister_player_id) REFERENCES players(id) ON DELETE SET NULL,
    FOREIGN KEY (max_yellow_cards_player_id) REFERENCES players(id) ON DELETE SET NULL,
    FOREIGN KEY (max_red_cards_player_id) REFERENCES players(id) ON DELETE SET NULL,
    FOREIGN KEY (revelation_team_id) REFERENCES teams(id) ON DELETE SET NULL,
    FOREIGN KEY (disappointment_team_id) REFERENCES teams(id) ON DELETE SET NULL,
    FOREIGN KEY (revelation_player_id) REFERENCES players(id) ON DELETE SET NULL,
    FOREIGN KEY (disappointment_player_id) REFERENCES players(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS chat_messages (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    text TEXT,
    image_url TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);
