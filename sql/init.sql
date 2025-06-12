-- Create application role for the web app client
CREATE ROLE app_user WITH LOGIN PASSWORD 'secure_app_password' NOSUPERUSER INHERIT NOCREATEDB NOCREATEROLE NOREPLICATION;

-- Grant necessary privileges
GRANT CONNECT ON DATABASE shopdb TO app_user;
GRANT USAGE ON SCHEMA public TO app_user;

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
(1, 'Alice''s Widget', 2, 25.50),
(2, 'Bob''s Gadget', 1, 15.00);

-- Grant table privileges to app_user (after tables exist)
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE users, orders TO app_user;

-- Create a helper function to safely get the user email
CREATE OR REPLACE FUNCTION get_current_user_email() RETURNS TEXT AS $$
BEGIN
  RETURN current_setting('app.user_email', true);
EXCEPTION
  WHEN OTHERS THEN
    RETURN NULL;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Enable and force Row-Level Security on users table
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE users FORCE ROW LEVEL SECURITY;

CREATE POLICY user_select_policy ON users
  FOR SELECT USING (email = get_current_user_email());

CREATE POLICY user_update_policy ON users
  FOR UPDATE USING (email = get_current_user_email())
  WITH CHECK (email = get_current_user_email());

-- Enable and force Row-Level Security on orders table
ALTER TABLE orders ENABLE ROW LEVEL SECURITY;
ALTER TABLE orders FORCE ROW LEVEL SECURITY;

CREATE POLICY order_select_policy ON orders
  FOR SELECT USING (user_id IN (SELECT id FROM users WHERE email = get_current_user_email()));

CREATE POLICY order_insert_policy ON orders
  FOR INSERT WITH CHECK (user_id IN (SELECT id FROM users WHERE email = get_current_user_email()));

CREATE POLICY order_update_policy ON orders
  FOR UPDATE USING (user_id IN (SELECT id FROM users WHERE email = get_current_user_email()))
  WITH CHECK (user_id IN (SELECT id FROM users WHERE email = get_current_user_email()));

CREATE POLICY order_delete_policy ON orders
  FOR DELETE USING (user_id IN (SELECT id FROM users WHERE email = get_current_user_email())); 