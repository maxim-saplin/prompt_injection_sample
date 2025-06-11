-- Enable and force RLS on users table
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE users FORCE ROW LEVEL SECURITY;
CREATE POLICY user_select_policy ON users
  FOR SELECT USING (email = current_setting('app.user_email', true));

-- Enable and force RLS on orders table
ALTER TABLE orders ENABLE ROW LEVEL SECURITY;
ALTER TABLE orders FORCE ROW LEVEL SECURITY;
CREATE POLICY order_select_policy ON orders
  FOR SELECT USING (user_id = (SELECT id FROM users WHERE email = current_setting('app.user_email', true)));
CREATE POLICY order_insert_policy ON orders
  FOR INSERT WITH CHECK (user_id = (SELECT id FROM users WHERE email = current_setting('app.user_email', true))); 