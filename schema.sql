CREATE TABLE IF NOT EXISTS blacklist (
    user_id BIGINT UNIQUE PRIMARY KEY NOT NULL,
    mod_id BIGINT NOT NULL
);

CREATE TABLE IF NOT EXISTS guilds (
    id BIGINT UNIQUE PRIMARY KEY NOT NULL,
    prefix VARCHAR(10)
);

CREATE TABLE IF NOT EXISTS snipes (
    channel_id UNIQUE PRIMARY KEY NOT NULL,
    guild_id BIGINT NOT NULL,
    user_id BIGINT NOT NULL,
    message_id BIGINT NOT NULL,
    message VARCHAR(2000) NOT NULL,
    msg_type INTEGER NOT NULL
);