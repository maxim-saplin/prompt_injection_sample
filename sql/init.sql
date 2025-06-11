CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    balance NUMERIC NOT NULL
);

INSERT INTO users (name, email, balance) VALUES
('Alice', 'alice@example.com', 100.0),
('Bob', 'bob@example.com', 150.5);

CREATE TABLE orders (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    item TEXT NOT NULL,
    quantity INTEGER NOT NULL,
    price NUMERIC NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Sample orders for demonstration
INSERT INTO orders (user_id, item, quantity, price) VALUES
(1, 'Widget', 2, 25.50),
(2, 'Gadget', 1, 15.00); 