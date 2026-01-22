-- Test schema for pgsql-test
-- This file is used to test the SQL file seeding functionality

CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT UNIQUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS posts (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    content TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Insert some test data
INSERT INTO users (name, email) VALUES 
    ('Alice', 'alice@example.com'),
    ('Bob', 'bob@example.com');

INSERT INTO posts (user_id, title, content) VALUES
    (1, 'Hello World', 'This is my first post!'),
    (1, 'Second Post', 'Another post by Alice'),
    (2, 'Bob''s Post', 'Hello from Bob');
