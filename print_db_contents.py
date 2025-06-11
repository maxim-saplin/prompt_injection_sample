#!/usr/bin/env python3

import psycopg2
from psycopg2.extras import RealDictCursor
import sys
from tabulate import tabulate

def get_connection():
    """Connect to the PostgreSQL database"""
    try:
        conn = psycopg2.connect(
            host="localhost",
            port=5432,
            dbname="shopdb",
            user="postgres",
            password="password",
        )
        return conn
    except psycopg2.Error as e:
        print(f"Error connecting to database: {e}")
        sys.exit(1)

def get_all_tables(conn):
    """Get list of all user tables in the database"""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_type = 'BASE TABLE'
            ORDER BY table_name;
        """)
        tables = [row[0] for row in cur.fetchall()]
    return tables

def print_table_contents(conn, table_name):
    """Print all contents of a specific table"""
    print(f"\nTABLE: {table_name.upper()}", end="")
    
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        try:
            # Get column names
            cur.execute(f"""
                SELECT column_name, data_type 
                FROM information_schema.columns 
                WHERE table_name = %s 
                ORDER BY ordinal_position;
            """, (table_name,))
            columns = cur.fetchall()
            
            if not columns:
                print("No columns found for this table.")
                return
            
            # Get all data from table
            cur.execute(f"SELECT * FROM {table_name} ORDER BY 1;")
            rows = cur.fetchall()
            
            if not rows:
                print("\nNo data found in this table.")
                return
            
            print(f", {len(rows)} rows")
            
            # Convert rows to list of lists for tabulate
            headers = list(rows[0].keys())
            data = [[row[col] for col in headers] for row in rows]
            
            print(tabulate(data, headers=headers, tablefmt='grid'))
                
        except psycopg2.Error as e:
            print(f"Error querying table {table_name}: {e}")

def main():
    """Main function to print all database table contents"""
    print("Database Contents Report")
    print("=" * 60)
    
    conn = get_connection()
    
    try:
        # Get all tables
        tables = get_all_tables(conn)
        
        if not tables:
            print("No tables found in the database.")
            return
        
        print(f"\nFound {len(tables)} table(s): {', '.join(tables)}")
        
        # Print contents of each table
        for table in tables:
            print_table_contents(conn, table)
            
    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        conn.close()
        print(f"\n{'='*60}")
        print("Database connection closed.")

if __name__ == "__main__":
    main() 