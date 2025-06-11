import os
import json
import psycopg2
from openai import AzureOpenAI
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

# Row-level security will be controlled via UI toggle

# System prompt for the shopping assistant
SYSTEM_PROMPT = (
    "You are a shopping assistant. The current user is {user_email}. "
    "You can call the following functions: view_balance, view_orders, make_order. "
    "Always respond in JSON format and use function calls when appropriate."
)

# Initialize LLM client
client = AzureOpenAI(
    api_key=os.getenv("AZURE_OPENAI_KEY"),
    api_version=os.getenv("AZURE_OPENAI_VERSION"),
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
    azure_deployment=os.getenv("AZURE_OPENAI_DEPLOYMENT")
)

# Helper to format assistant responses and function results
def format_content(content: str) -> str:
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError:
        return content
    # Prioritize explicit response field
    if isinstance(parsed, dict):
        if "response" in parsed:
            return parsed["response"]
        if "orders" in parsed:
            # Build markdown table for orders
            header = "| ID | Item | Quantity | Price | Created At |\n|---|---|---|---|---|\n"
            rows = [f"| {o['id']} | {o['item']} | {o['quantity']} | ${o['price']:.2f} | {o['created_at']} |" for o in parsed["orders"]]
            return header + "\n".join(rows)
        if "balance" in parsed:
            return f"Your current balance is ${parsed['balance']:.2f}."
        if "order_id" in parsed:
            msg = f"Your order has been created! Order ID: {parsed['order_id']}"
            if "total_cost" in parsed and "new_balance" in parsed:
                msg += f"\nTotal cost: ${parsed['total_cost']:.2f}"
                msg += f"\nRemaining balance: ${parsed['new_balance']:.2f}"
            return msg
        if "message" in parsed:
            return parsed["message"]
    return content

# Database connection helper
def get_connection():
    conn = psycopg2.connect(
        host="localhost",
        port=5432,
        dbname="shopdb",
        user="postgres",
        password="password",
    )
    if st.session_state.get("rls_enabled", False) and "user_email" in st.session_state:
        with conn.cursor() as cur:
            cur.execute("SET app.user_email = %s", (st.session_state["user_email"],))
        conn.commit()
    return conn

# Define tool wrappers
def view_balance(email=None):
    user_email = email if not st.session_state.get("rls_enabled", False) else st.session_state["user_email"]
    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute("SELECT balance FROM users WHERE email = %s", (user_email,))
        row = cur.fetchone()
    conn.close()
    if row:
        return {"balance": float(row[0])}
    return {"error": "User not found"}


def view_orders(email=None):
    user_email = email if not st.session_state.get("rls_enabled", False) else st.session_state["user_email"]
    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT o.id, o.item, o.quantity, o.price, o.created_at
            FROM orders o
            JOIN users u ON o.user_id = u.id
            WHERE u.email = %s
            """,
            (user_email,)
        )
        rows = cur.fetchall()
    conn.close()
    orders = [
        {"id": r[0], "item": r[1], "quantity": r[2], "price": float(r[3]), "created_at": r[4].isoformat()}
        for r in rows
    ]
    return {"orders": orders}


def make_order(item, quantity, price, email=None):
    user_email = email if not st.session_state.get("rls_enabled", False) else st.session_state["user_email"]
    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute("SELECT id, balance FROM users WHERE email = %s", (user_email,))
        user = cur.fetchone()
        if not user:
            conn.close()
            return {"error": "User not found"}
        user_id, balance = user[0], float(user[1])
        
        total_cost = float(price) * quantity
        if balance < total_cost:
            conn.close()
            return {"error": f"Insufficient balance. Required: ${total_cost:.2f}, Available: ${balance:.2f}"}
        
        # Create order and update balance
        cur.execute(
            "INSERT INTO orders (user_id, item, quantity, price) VALUES (%s, %s, %s, %s) RETURNING id",
            (user_id, item, quantity, price),
        )
        order_id = cur.fetchone()[0]
        
        new_balance = balance - total_cost
        cur.execute(
            "UPDATE users SET balance = %s WHERE id = %s",
            (new_balance, user_id)
        )
        conn.commit()
    conn.close()
    return {"order_id": order_id, "total_cost": total_cost, "new_balance": new_balance}

# Streamlit App Layout
st.set_page_config(page_title="Shop Chat", layout="wide")

# Authentication
if "user_email" not in st.session_state:
    st.sidebar.title("Login")
    email = st.sidebar.radio(
        "Select your user",
        ("alice@example.com", "bob@example.com"),
        index=0,
    )
    rls_enabled = st.sidebar.checkbox(
        "Enable Row-Level Security",
        value=False,
        help="When enabled, functions will use session context instead of email parameters"
    )
    if st.sidebar.button("Login"):
        st.session_state["user_email"] = email
        st.session_state["rls_enabled"] = rls_enabled
        st.rerun()
else:
    # Move email/logout to sidebar for a fixed top pane
    st.sidebar.markdown(f"**Logged in as:** {st.session_state['user_email']}")
    rls_status = "Enabled" if st.session_state.get("rls_enabled", False) else "Disabled"
    st.sidebar.markdown(f"**RLS:** {rls_status}")
    if st.sidebar.button("Logout"):
        del st.session_state["user_email"]
        if "rls_enabled" in st.session_state:
            del st.session_state["rls_enabled"]
        if "messages" in st.session_state:
            del st.session_state["messages"]
        st.rerun()

# Only show chat after login
if "user_email" in st.session_state:
    # Center chat in a wider column
    chat_cols = st.columns([1])
    with chat_cols[0]:
        st.title("Assistant Chat Bot")
        if "messages" not in st.session_state:
            st.session_state["messages"] = [
                {"role": "system", "content": SYSTEM_PROMPT.format(user_email=st.session_state['user_email'])}
            ]

        # Render chat history
        for msg in st.session_state["messages"]:
            role = msg.get("role")
            # Skip internal function messages
            if role == "function":
                continue
            content = msg.get("content")
            # Skip empty-assistant messages (e.g. function-call placeholders)
            if content is None:
                continue
            if role == "assistant":
                display = format_content(content)
            else:
                display = content
            with st.chat_message(role):
                st.markdown(display)

    # User input at bottom - outside column layout
    if prompt := st.chat_input("How can I help you today?"):
        st.session_state["messages"].append({"role": "user", "content": prompt})
        with chat_cols[0]:
            with st.chat_message("user"):
                st.markdown(prompt)

        # First LLM call
            response = client.chat.completions.create(
                model=os.getenv("AZURE_OPENAI_DEPLOYMENT"),
                messages=st.session_state["messages"],
                functions=[
                    {"name": "view_balance", "description": "Get current user's balance", "parameters": {"type": "object", "properties": {"email": {"type": "string"}}, "required": ["email"]}},
                    {"name": "view_orders", "description": "Get list of orders for current user", "parameters": {"type": "object", "properties": {"email": {"type": "string"}}, "required": ["email"]}},
                    {"name": "make_order", "description": "Create a new order", "parameters": {"type": "object", "properties": {"item": {"type": "string"}, "quantity": {"type": "integer"}, "price": {"type": "number"}, "email": {"type": "string"}}, "required": ["item", "quantity", "price", "email"]}}
                ],
                function_call="auto"
            )
            msg = response.choices[0].message
            # If LLM requested a function
            if msg.function_call:
                fname = msg.function_call.name
                fargs = json.loads(msg.function_call.arguments)
                if fname == "view_balance":
                    result = view_balance(email=fargs.get("email"))
                elif fname == "view_orders":
                    result = view_orders(email=fargs.get("email"))
                else:
                    result = make_order(item=fargs.get("item"), quantity=fargs.get("quantity"), price=fargs.get("price"), email=fargs.get("email"))
                # Append function messages
                st.session_state["messages"].append(msg.to_dict())
                st.session_state["messages"].append({"role": "function", "name": fname, "content": json.dumps(result)})
                # Second LLM call for final answer
                followup = client.chat.completions.create(
                    model=os.getenv("AZURE_OPENAI_DEPLOYMENT"),
                    messages=st.session_state["messages"]
                )
                final = followup.choices[0].message
                # Format and display assistant response
                display = format_content(final.content)
                st.session_state["messages"].append(final.to_dict())
                with chat_cols[0]:
                    with st.chat_message("assistant"):
                        st.markdown(display)
            else:
                # Normal response
                st.session_state["messages"].append(msg.to_dict())
                # Format and display assistant response
                display = format_content(msg.content)
                with chat_cols[0]:
                    with st.chat_message("assistant"):
                        st.markdown(display)