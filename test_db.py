#!/usr/bin/env python3
"""
تست دیتابیس - بررسی وجود پیام‌ها
"""

import sqlite3
import os

# پیدا کردن فایل دیتابیس
possible_paths = [
    "bot_db.sqlite",
    "bot/bot_db.sqlite",
    "../bot_db.sqlite",
]

for db_path in possible_paths:
    if os.path.exists(db_path):
        print(f"✅ دیتابیس یافت شد: {db_path}")
        print(f"📍 مسیر کامل: {os.path.abspath(db_path)}")
        
        try:
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # بررسی جدول messages
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='messages'")
            if cursor.fetchone():
                print("✅ جدول messages وجود دارد")
                
                # تعداد پیام‌ها
                cursor.execute("SELECT COUNT(*) as count FROM messages")
                count = cursor.fetchone()['count']
                print(f"📊 تعداد پیام‌ها: {count}")
                
                if count > 0:
                    # نمایش 5 پیام اول
                    cursor.execute("SELECT message_name FROM messages LIMIT 5")
                    print("\n📝 نمونه پیام‌ها:")
                    for row in cursor.fetchall():
                        print(f"  - {row['message_name']}")
                else:
                    print("⚠️  جدول messages خالی است!")
            else:
                print("❌ جدول messages وجود ندارد!")
            
            conn.close()
            print()
        except Exception as e:
            print(f"❌ خطا در خواندن دیتابیس: {e}\n")
    else:
        print(f"❌ دیتابیس یافت نشد: {db_path}")

print("\n" + "="*50)
print("🔍 بررسی config ربات:")
try:
    from bot.db import DB_NAME
    print(f"📁 DB_NAME در config: {DB_NAME}")
    print(f"📍 مسیر کامل: {os.path.abspath(DB_NAME)}")
    
    if os.path.exists(DB_NAME):
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as count FROM messages")
        count = cursor.fetchone()[0]
        print(f"📊 تعداد پیام‌ها در این فایل: {count}")
        conn.close()
    else:
        print("❌ فایل دیتابیس در config موجود نیست!")
except Exception as e:
    print(f"❌ خطا: {e}")
