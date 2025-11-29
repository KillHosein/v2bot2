#!/usr/bin/env python3
"""
Migration script to add notification fields to orders table
Run this before deploying the new version
"""

import sqlite3
import os

# Database path
DB_PATH = os.path.join(os.path.dirname(__file__), 'bot.db')

def run_migration():
    """Apply database migration"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        print("🔄 Starting migration...")
        
        # Check if columns already exist
        cursor.execute("PRAGMA table_info(orders)")
        columns = [col[1] for col in cursor.fetchall()]
        
        migrations_applied = []
        
        # Add notified_traffic_80
        if 'notified_traffic_80' not in columns:
            cursor.execute("ALTER TABLE orders ADD COLUMN notified_traffic_80 INTEGER DEFAULT 0")
            migrations_applied.append("notified_traffic_80")
            print("✅ Added column: notified_traffic_80")
        else:
            print("⏭️  Column notified_traffic_80 already exists")
        
        # Add notified_traffic_95
        if 'notified_traffic_95' not in columns:
            cursor.execute("ALTER TABLE orders ADD COLUMN notified_traffic_95 INTEGER DEFAULT 0")
            migrations_applied.append("notified_traffic_95")
            print("✅ Added column: notified_traffic_95")
        else:
            print("⏭️  Column notified_traffic_95 already exists")
        
        # Add notified_expiry_3d
        if 'notified_expiry_3d' not in columns:
            cursor.execute("ALTER TABLE orders ADD COLUMN notified_expiry_3d INTEGER DEFAULT 0")
            migrations_applied.append("notified_expiry_3d")
            print("✅ Added column: notified_expiry_3d")
        else:
            print("⏭️  Column notified_expiry_3d already exists")
        
        # Add notified_expiry_1d
        if 'notified_expiry_1d' not in columns:
            cursor.execute("ALTER TABLE orders ADD COLUMN notified_expiry_1d INTEGER DEFAULT 0")
            migrations_applied.append("notified_expiry_1d")
            print("✅ Added column: notified_expiry_1d")
        else:
            print("⏭️  Column notified_expiry_1d already exists")
        
        # Create index
        try:
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_orders_notifications 
                ON orders(status, notified_traffic_80, notified_traffic_95, notified_expiry_3d, notified_expiry_1d)
            """)
            print("✅ Created index: idx_orders_notifications")
        except Exception as e:
            print(f"⚠️  Index creation: {e}")
        
        # Commit changes
        conn.commit()
        print(f"\n✅ Migration completed successfully!")
        print(f"📊 Applied {len(migrations_applied)} new columns")
        
        if migrations_applied:
            print("\n📝 New columns added:")
            for col in migrations_applied:
                print(f"   - {col}")
        
        conn.close()
        
    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
        raise

if __name__ == '__main__':
    print("=" * 60)
    print("📦 V2Bot Database Migration")
    print("=" * 60)
    print()
    
    if not os.path.exists(DB_PATH):
        print(f"❌ Database not found at: {DB_PATH}")
        print("Please make sure the bot.db file exists.")
        exit(1)
    
    print(f"📁 Database: {DB_PATH}")
    print()
    
    try:
        run_migration()
        print()
        print("=" * 60)
        print("✅ Migration successful! You can now restart the bot.")
        print("=" * 60)
    except Exception as e:
        print()
        print("=" * 60)
        print(f"❌ Migration failed: {e}")
        print("=" * 60)
        exit(1)
