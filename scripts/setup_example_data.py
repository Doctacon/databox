"""Setup script to create example data for testing."""

import sys
from pathlib import Path
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import random

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))
from config import settings


def create_sales_data():
    """Create example sales data."""
    print("Creating example sales data...")
    
    # Generate dates
    start_date = datetime.now() - timedelta(days=365)
    dates = pd.date_range(start=start_date, end=datetime.now(), freq='D')
    
    # Product categories
    categories = ['Electronics', 'Clothing', 'Food', 'Books', 'Home & Garden']
    products = {
        'Electronics': ['Laptop', 'Phone', 'Tablet', 'Headphones', 'Camera'],
        'Clothing': ['Shirt', 'Pants', 'Shoes', 'Jacket', 'Hat'],
        'Food': ['Pizza', 'Burger', 'Salad', 'Pasta', 'Sushi'],
        'Books': ['Fiction', 'Non-fiction', 'Science', 'History', 'Art'],
        'Home & Garden': ['Chair', 'Table', 'Lamp', 'Plant', 'Tool']
    }
    
    # Generate sales records
    records = []
    
    for date in dates:
        # Random number of sales per day
        num_sales = random.randint(50, 200)
        
        for _ in range(num_sales):
            category = random.choice(categories)
            product = random.choice(products[category])
            
            record = {
                'sale_date': date,
                'category': category,
                'product': product,
                'quantity': random.randint(1, 5),
                'unit_price': round(random.uniform(10, 500), 2),
                'customer_id': f"CUST{random.randint(1000, 9999)}",
                'store_id': f"STORE{random.randint(1, 10)}",
                'payment_method': random.choice(['Credit Card', 'Cash', 'Debit Card', 'PayPal'])
            }
            
            record['total_amount'] = round(record['quantity'] * record['unit_price'], 2)
            record['discount'] = round(record['total_amount'] * random.uniform(0, 0.2), 2)
            record['final_amount'] = round(record['total_amount'] - record['discount'], 2)
            
            records.append(record)
    
    # Create DataFrame
    df = pd.DataFrame(records)
    
    # Save to CSV
    output_path = settings.data_dir / "raw" / "sales_data.csv"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False)
    
    print(f"✓ Created sales_data.csv with {len(df)} records")
    return df


def create_customer_data():
    """Create example customer data."""
    print("Creating example customer data...")
    
    # Generate customer IDs from sales data
    sales_path = settings.data_dir / "raw" / "sales_data.csv"
    if sales_path.exists():
        sales_df = pd.read_csv(sales_path)
        customer_ids = sales_df['customer_id'].unique()
    else:
        customer_ids = [f"CUST{i}" for i in range(1000, 10000)]
    
    # Generate customer records
    records = []
    
    cities = ['New York', 'Los Angeles', 'Chicago', 'Houston', 'Phoenix', 
              'Philadelphia', 'San Antonio', 'San Diego', 'Dallas', 'San Jose']
    states = ['NY', 'CA', 'IL', 'TX', 'AZ', 'PA', 'TX', 'CA', 'TX', 'CA']
    
    for customer_id in customer_ids:
        city_idx = random.randint(0, len(cities) - 1)
        
        record = {
            'customer_id': customer_id,
            'first_name': f"First{customer_id[4:]}",
            'last_name': f"Last{customer_id[4:]}",
            'email': f"{customer_id.lower()}@example.com",
            'phone': f"555-{random.randint(100, 999)}-{random.randint(1000, 9999)}",
            'date_of_birth': (datetime.now() - timedelta(days=random.randint(7300, 25550))).date(),
            'registration_date': (datetime.now() - timedelta(days=random.randint(0, 730))).date(),
            'city': cities[city_idx],
            'state': states[city_idx],
            'zip_code': f"{random.randint(10000, 99999)}",
            'loyalty_tier': random.choice(['Bronze', 'Silver', 'Gold', 'Platinum']),
            'total_spent': round(random.uniform(100, 10000), 2),
            'last_purchase_date': (datetime.now() - timedelta(days=random.randint(0, 90))).date()
        }
        
        records.append(record)
    
    # Create DataFrame
    df = pd.DataFrame(records)
    
    # Save to CSV
    output_path = settings.data_dir / "raw" / "customers.csv"
    df.to_csv(output_path, index=False)
    
    print(f"✓ Created customers.csv with {len(df)} records")
    return df


def create_inventory_data():
    """Create example inventory data."""
    print("Creating example inventory data...")
    
    # Get unique products from sales data
    sales_path = settings.data_dir / "raw" / "sales_data.csv"
    if sales_path.exists():
        sales_df = pd.read_csv(sales_path)
        products = sales_df[['category', 'product']].drop_duplicates()
    else:
        # Create default products
        categories = ['Electronics', 'Clothing', 'Food', 'Books', 'Home & Garden']
        products_dict = {
            'Electronics': ['Laptop', 'Phone', 'Tablet', 'Headphones', 'Camera'],
            'Clothing': ['Shirt', 'Pants', 'Shoes', 'Jacket', 'Hat'],
            'Food': ['Pizza', 'Burger', 'Salad', 'Pasta', 'Sushi'],
            'Books': ['Fiction', 'Non-fiction', 'Science', 'History', 'Art'],
            'Home & Garden': ['Chair', 'Table', 'Lamp', 'Plant', 'Tool']
        }
        
        products = []
        for category, items in products_dict.items():
            for product in items:
                products.append({'category': category, 'product': product})
        products = pd.DataFrame(products)
    
    # Generate inventory records
    records = []
    
    for _, row in products.iterrows():
        for store_id in range(1, 11):
            record = {
                'sku': f"SKU{random.randint(10000, 99999)}",
                'product': row['product'],
                'category': row['category'],
                'store_id': f"STORE{store_id}",
                'quantity_on_hand': random.randint(0, 500),
                'reorder_point': random.randint(10, 50),
                'reorder_quantity': random.randint(50, 200),
                'unit_cost': round(random.uniform(5, 300), 2),
                'last_restocked': (datetime.now() - timedelta(days=random.randint(0, 30))).date(),
                'supplier': f"Supplier{random.randint(1, 20)}"
            }
            
            records.append(record)
    
    # Create DataFrame
    df = pd.DataFrame(records)
    
    # Save to CSV
    output_path = settings.data_dir / "raw" / "inventory.csv"
    df.to_csv(output_path, index=False)
    
    print(f"✓ Created inventory.csv with {len(df)} records")
    return df


def main():
    """Create all example data files."""
    print("Setting up example data...")
    
    # Create data directory
    (settings.data_dir / "raw").mkdir(parents=True, exist_ok=True)
    
    # Create datasets
    create_sales_data()
    create_customer_data()
    create_inventory_data()
    
    print("\n✓ All example data created successfully!")
    print(f"Data files are located in: {settings.data_dir / 'raw'}")


if __name__ == "__main__":
    main()