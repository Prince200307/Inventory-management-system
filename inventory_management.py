import os
import sqlite3
from contextlib import contextmanager

DB_FOLDER= "data"
DB_PATH = os.path.join(DB_FOLDER, "inventory.db")

@contextmanager
def get_db_connection():
    '''Context manager for database connection'''
    conn= None
    try:
        conn= sqlite3.connect(DB_PATH)
        conn.execute("PRAGMA foreign_keys = ON") #Enable foreignkey constraints
        conn.row_factory = sqlite3.Row #Return rows as dictionaries
        yield conn
        conn.commit() #Commit changes if no exceptions
    except Exception as e:
        if conn:
            conn.rollback() #Rollback changes on exception
        raise e
    finally:
        if conn:
            conn.close()


def setup_database():
    '''Set up the database schema and create necessary tables if they do not exist'''

    if not os.path.exists(DB_FOLDER):
        os.makedirs(DB_FOLDER)

    with get_db_connection() as conn:
        cursor= conn.cursor()

        #create tables with transaction logging
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_name TEXT UNIQUE NOT NULL,
            quantity INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            CHECK (quantity >= 0)
        );
        """)
        #create transaction log for audit trail
        cursor.execute("""
        CREATE TABLE inventory_transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER NOT NULL
                REFERENCES products(id)
                ON DELETE CASCADE,
            transaction_type TEXT NOT NULL,
            old_quantity INTEGER,
            new_quantity INTEGER,
            change_amount INTEGER,
            performed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)
        #create index for faster lookups
        cursor.execute('''CREATE INDEX IF NOT EXISTS idx_product_name ON products(product_name)''')
        cursor.execute('''CREATE INDEX IF NOT EXISTS idx_transaction_product ON inventory_transactions(product_id)''')


def log_transaction(cursor, product_id, transaction_type, old_quantity, new_quantity):
    '''Log all inventory transactions for audit trail'''
    change_amount = new_quantity - old_quantity if old_quantity is not None else new_quantity
    cursor.execute('''
        INSERT INTO inventory_transactions (product_id, transaction_type, old_quantity, new_quantity, change_amount)
        VALUES (?, ?, ?, ?, ?)
    ''', (product_id, transaction_type, old_quantity, new_quantity, change_amount))


def print_tablular(headers, rows):
    col_widths = [len(h) for h in headers]

    for row in rows:
        for i, col in enumerate(row):
            col_widths[i] = max(col_widths[i], len(str(col)))

    line = "+" + "+".join("-" * (w + 2) for w in col_widths) + "+"
    header_row = "|" + "|".join(f" {headers[i].ljust(col_widths[i])} " for i in range(len(headers))) + "|"

    print(line)
    print(header_row)
    print(line)

    for row in rows:
        print("|" + "|".join(f" {str(row[i]).ljust(col_widths[i])} " for i in range(len(row))) + "|")

    print(line)


def get_integer_input(prompt):
    '''Helper function to get integer input from user'''
    while True:
        try:
            value= int(input(prompt))
            if value < 0:
                print("Please enter a non-negative integer.")
                continue
            return value
        except ValueError:
            print("Invalid input. Please enter a valid integer.")


def add_product():
    """Add multiple new products to inventory with transaction"""
    print("\n--- Add Product ---")
    print("Enter 'quit' as product name to return to menu")
    print("-" * 40)

    while True:
        product_name = input("\nEnter product name (or 'quit' to stop): ").strip()

        if product_name.lower() == 'quit':
            print("Returning to main menu...")
            break

        if not product_name:
            print("Product name cannot be empty.")
            continue

        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()

                # Check if product already exists
                cursor.execute(
                    'SELECT id FROM products WHERE product_name = ?',
                    (product_name,)
                )
                existing_product = cursor.fetchone()
                if existing_product:
                    print(f"Product '{product_name}' already exists in inventory.")
                    continue
                quantity = get_integer_input("Enter initial quantity: ")

                # Insert new product
                cursor.execute(
                    'INSERT INTO products (product_name, quantity) VALUES (?, ?)',
                    (product_name, quantity)
                )

                # Get the product ID for logging
                product_id = cursor.lastrowid

                # Log the transaction
                log_transaction(cursor, product_id, 'ADD', 0, quantity)
                print(f"✓ Product '{product_name}' added with quantity {quantity}.")

        except sqlite3.IntegrityError:
            print(f"Product '{product_name}' already exists in inventory.")
        except Exception as e:
            print(f"Error adding product: {e}")


def update_product_quantity():
    '''Update the quantity of an existing product with transaction logging'''
    print("Update Product Quantity")
    product_name= input("Enter product name: ").strip()
    if not product_name:
        print("Product name cannot be empty.")
        return
    new_quantity= get_integer_input("Enter new quantity: ")

    try:
        with get_db_connection() as conn:
            cursor= conn.cursor()


            #Fetch existing product
            cursor.execute('''
                SELECT id, quantity FROM products WHERE product_name = ?
            ''', (product_name,))
            product= cursor.fetchone()
            if not product:
                print(f"Error: Product '{product_name}' does not exist.")
                return

            product_id= product['id']
            old_quantity= product['quantity']

            #Update quantity
            cursor.execute('''
                UPDATE products SET quantity = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?
            ''', (new_quantity, product_id))

            #log transaction
            log_transaction(cursor, product_id, 'UPDATE', old_quantity, new_quantity)
            print(f"Product '{product_name}' quantity updated from {old_quantity} to {new_quantity}.")
    except Exception as e:
        print(f"An error occurred: {e}")


def add_quantity_to_product():
    '''Add quantity to an existing product with transaction logging'''
    print("Add Quantity to Product")
    product_name= input("Enter product name: ").strip()
    if not product_name:
        print("Product name cannot be empty.")
        return
    add_quantity= get_integer_input("Enter quantity to add: ")

    try:
        with get_db_connection() as conn:
            cursor= conn.cursor()

            #Fetch existing product
            cursor.execute('''
                SELECT id, quantity FROM products WHERE product_name = ?
            ''', (product_name,))
            product= cursor.fetchone()
            if not product:
                print(f"Error: Product '{product_name}' does not exist.")
                return

            product_id= product['id']
            old_quantity= product['quantity']
            new_quantity= old_quantity + add_quantity

            #Update quantity
            cursor.execute('''
                UPDATE products SET quantity = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?
            ''', (new_quantity, product_id))

            #log transaction
            log_transaction(cursor, product_id, 'ADD_QUANTITY', old_quantity, new_quantity)
            print(f"Added {add_quantity} to '{product_name}'. New quantity is {new_quantity}.")
    except Exception as e:
        print(f"An error occurred: {e}")


def order_product():
    '''Order (reduce) quantity of an existing product with transaction logging'''
    print("Order Product")
    product_name= input("Enter product name: ").strip()
    if not product_name:
        print("Product name cannot be empty.")
        return

    try:
        with get_db_connection() as conn:
            cursor= conn.cursor()

            #Fetch existing product
            cursor.execute('''
                SELECT id, quantity FROM products WHERE product_name = ?
            ''', (product_name,))
            product= cursor.fetchone()
            if not product:
                print(f"Error: Product '{product_name}' does not exist.")
                return

            product_id= product['id']
            old_quantity= product['quantity']
            order_quantity= get_integer_input("Enter quantity to order: ")
            if order_quantity <= 0:
                print("Order quantity must be greater than zero.")
                return

            if order_quantity > old_quantity:
                print(f"Error: Insufficient quantity for '{product_name}'. Available: {old_quantity}, Requested: {order_quantity}.")
                return

            new_quantity= old_quantity - order_quantity

            #Update quantity
            cursor.execute('''
                UPDATE products SET quantity = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?
            ''', (new_quantity, product_id))

            #log transaction
            log_transaction(cursor, product_id, 'ORDER', old_quantity, new_quantity)
            print(f"Ordered {order_quantity} of '{product_name}'. New quantity is {new_quantity}.")
    except Exception as e:
        print(f"An error occurred: {e}")


def view_inventory():
    '''View current inventory'''
    print("\n📦 Current Inventory\n")

    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT product_name,
                       quantity,
                       created_at,
                       updated_at,
                       CASE
                           WHEN quantity = 0 THEN 'Out of Stock'
                           WHEN quantity < 5 THEN 'Low Stock'
                           ELSE 'In Stock'
                       END AS stock_status
                FROM products
                ORDER BY product_name
            """)

            rows = cursor.fetchall()
            if not rows:
                print("Inventory is empty.")
                return

            table = [
                [r["product_name"], r["quantity"], r["stock_status"],
                 r["created_at"], r["updated_at"]]
                for r in rows
            ]

            headers = ["Product", "Quantity", "Status", "Created At", "Updated At"]

            print_tabular(table, headers)

    except Exception as e:
        print(f"Error: {e}")



def view_transaction_log():
    '''View transaction log'''
    print("\n🧾 Transaction Log (Last 50)\n")

    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT t.id,
                       p.product_name,
                       t.transaction_type,
                       t.old_quantity,
                       t.new_quantity,
                       t.change_amount,
                       t.performed_at
                FROM inventory_transactions t
                JOIN products p ON t.product_id = p.id
                ORDER BY t.performed_at DESC
                LIMIT 50
            """)

            rows = cursor.fetchall()
            if not rows:
                print("No transactions found.")
                return

            table = [
                [r["id"], r["product_name"], r["transaction_type"],
                 r["old_quantity"], r["new_quantity"],
                 r["change_amount"], r["performed_at"]]
                for r in rows
            ]

            headers = ["ID", "Product", "Type", "Old Qty", "New Qty", "Change", "Time"]

            print_tablular(table, headers)

    except Exception as e:
        print(f"Error: {e}")


def backup_database():
    '''Backup the database to the specified path'''
    import shutil
    import datetime

    backup_folder = os.path.join(DB_FOLDER, "backups")
    if not os.path.exists(backup_folder):
        os.makedirs(backup_folder)

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = os.path.join(backup_folder, f"inventory_backup_{timestamp}.db")

    try:
        # Close any existing connections before backup
        shutil.copy2(DB_PATH, backup_path)
        print(f"Database backup created: {backup_path}")
    except Exception as e:
        print(f"Error creating backup: {e}")


def main():
    '''Main function to run the inventory management system'''
    #setup database
    try:
        setup_database()
        print("Database setup completed.")
    except Exception as e:
        print(f"Error setting up database: {e}")
        return

    #create initial backup
    backup_database()
    while True:
        print("\n=== Inventory Management System ===")
        print("1. Add Product")
        print("2. Update Product Quantity")
        print("3. Add Quantity to Product")
        print("4. Order Product")
        print("5. View Inventory")
        print("6. View Transaction Log")
        print("7. Backup Database")
        print("8. Exit")

        choice= input("Select an option (1-8): ").strip()
        if choice == '1':
            add_product()
        elif choice == '2':
            update_product_quantity()
        elif choice == '3':
            add_quantity_to_product()
        elif choice == '4':
            order_product()
        elif choice == '5':
            view_inventory()
        elif choice == '6':
            view_transaction_log()
        elif choice == '7':
            backup_database()
        elif choice == '8':
            print("Exiting Inventory Management System.")
            break
        else:
            print("Invalid option. Please try again.")

if __name__ == "__main__":
    main()