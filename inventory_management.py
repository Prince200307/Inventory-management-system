import os

filename= "stock.txt"

def get_integer_input(prompt):
    while True:
        try:
            value= int(input(prompt))
            if value < 0:
                print("Please enter a non-negative integer.")
                continue
            return value
        except ValueError:
            print("Invalid input. Please enter an integer value.")

def load_inventory():
    inventory = {}
    if not os.path.exists(filename):
        return inventory
    try:
        with open(filename, 'r') as file:
            for line in file:
                product, quantity = line.strip().split('\t')
                inventory[product] = int(quantity)
    except Exception as e:
        print(f"Error loading inventory: {e}")
    return inventory
def save_inventory(inventory):
    try:
        with open(filename, 'w') as file:
            for product, quantity in inventory.items():
                file.write(f"{product}\t{quantity}\n")
    except Exception as e:
        print(f"Error saving inventory: {e}")
def add_product(inventory):
    print("Adding product to inventory...")
    product_name= input("Enter product name: ")
    quantity= get_integer_input("Enter quantity: ")
    if product_name in inventory:
        inventory[product_name] += quantity
    else:
        inventory[product_name] = quantity
    save_inventory(inventory)
    print(f"Product '{product_name}' added/updated successfully.")
def add_quantity(inventory):
    print("Adding quantity to existing product...")
    product_name= input("Enter product name: ")
    if product_name in inventory:
        quantity= get_integer_input("Enter quantity to add: ")
        inventory[product_name] += quantity
        save_inventory(inventory)
        print(f"Quantity updated successfully for '{product_name}'.")
    else:
        print(f"Product '{product_name}' not found in inventory.")
def update_quantity(inventory):
    print("Updating quantity of existing product...")
    product_name= input("Enter product name: ")
    if product_name in inventory:
        quantity= get_integer_input("Enter new quantity: ")
        inventory[product_name] = quantity
        save_inventory(inventory)
        print(f"Quantity updated successfully for '{product_name}'.")
    else:
        print(f"Product '{product_name}' not found in inventory.")
def delete_quantity(inventory):
    print("Deleting quantity from existing product...")
    product_name= input("Enter product name: ")
    if product_name in inventory:
        quantity= get_integer_input("Enter quantity to delete: ")
        if quantity >= inventory[product_name]:
            inventory[product_name]= 0
            print(f"Product quantity '{product_name}' removed from inventory and set to 0.")
        else:
            inventory[product_name] -= quantity
            print(f"Quantity updated successfully for '{product_name}'.")
        save_inventory(inventory)
    else:
        print(f"Product '{product_name}' not found in inventory.")
def order_product(inventory):
    print("Ordering product...")
    product_name= input("Enter product name: ")
    if product_name in inventory:
        quantity= get_integer_input("Enter quantity to order: ")
        if quantity <= 0:
            print("Order quantity must be greater than zero.")
            return
        if quantity <= inventory[product_name]:
            inventory[product_name] -= quantity
            save_inventory(inventory)
            print(f"Order placed successfully for '{product_name}'.")
        else:
            print(f"Insufficient stock for '{product_name}'. Available quantity: {inventory[product_name]}")
    else:
        print(f"Product '{product_name}' not found in inventory.")
def display_inventory(inventory):
    print("Current Inventory:")
    if not inventory:
        print("Inventory is empty.")
        return
    else:
        for product, quantity in sorted(inventory.items()):
            print(f"Product: {product}, Quantity: {quantity}")
def main():
    inventory = load_inventory()
    while True:
        print("\nInventory Management System")
        print("1. Add Product")
        print("2. Add Quantity to Existing Product")
        print("3. Update Quantity of Existing Product")
        print("4. Delete Quantity from Existing Product")
        print("5. Order Product")
        print("6. Display Inventory")
        print("7. Exit")
        choice = input("Enter your choice (1-7): ")
        if choice == '1':
            add_product(inventory)
        elif choice == '2':
            add_quantity(inventory)
        elif choice == '3':
            update_quantity(inventory)
        elif choice == '4':
            delete_quantity(inventory)
        elif choice == '5':
            order_product(inventory)
        elif choice == '6':
            display_inventory(inventory)
        elif choice == '7':
            print("Exiting Inventory Management System.")
            break
        else:
            print("Invalid choice. Please enter a number between 1 and 7.")
if __name__ == "__main__":
    main()