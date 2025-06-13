CREATE TABLE banned_users (
    id SERIAL PRIMARY KEY,
    group_id UUID NOT NULL,
    user_id BIGINT NOT NULL,
    banned_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (group_id) REFERENCES groups(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(telegram_id) ON DELETE CASCADE,
    UNIQUE (group_id, user_id)
);