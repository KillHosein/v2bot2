#!/usr/bin/env python3
"""
اسکریپت بروزرسانی متن‌های دیتابیس
این اسکریپت متن‌های جدید قابل تغییر را به جدول messages اضافه می‌کند.
"""

import sqlite3
import sys
import os

DB_NAME = "bot_db.sqlite"

def initialize_messages_table():
    """ایجاد جدول messages اگر وجود ندارد"""
    try:
        with sqlite3.connect(DB_NAME) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    message_name TEXT PRIMARY KEY,
                    text TEXT,
                    file_id TEXT,
                    file_type TEXT
                )
            """)
            conn.commit()
            print("✅ جدول messages ایجاد شد")
            return True
    except Exception as e:
        print(f"❌ خطا در ایجاد جدول: {e}")
        return False

def update_messages():
    """اضافه کردن متن‌های جدید به دیتابیس"""
    new_messages = {
        # متن‌های اصلی
        'start_main': '👋 سلام! به ربات فروش کانفیگ ما خوش آمدید.\nبرای شروع از دکمه‌های زیر استفاده کنید.',
        'admin_panel_main': '🖥️ پنل مدیریت ربات. لطفا یک گزینه را انتخاب کنید.',
        'buy_config_main': '📡 **خرید کانفیگ**\n\nلطفا یکی از پلن‌های زیر را انتخاب کنید:',
        'payment_info_text': '💳 **اطلاعات پرداخت** 💳\n\nمبلغ پلن انتخابی را به یکی از کارت‌های زیر واریز کرده و سپس اسکرین‌شات رسید را در همین صفحه ارسال نمایید.',
        'renewal_reminder_text': '⚠️ **یادآوری تمدید سرویس**\n\nکاربر گرامی، اعتبار سرویس شما رو به اتمام است.\n\n{details}\n\nبرای جلوگیری از قطع شدن سرویس، لطفاً از طریق دکمه "سرویس من" در منوی اصلی ربات اقدام به تمدید نمایید.',
        # متن‌های منوی ادمین
        'admin_messages_menu': 'مدیریت پیام‌ها و صفحات:',
        'admin_users_menu': '👥 مدیریت کاربران',
        'admin_stats_title': '📈 **آمار ربات**',
        'admin_panels_menu': '🖥️ مدیریت پنل‌ها',
        'admin_plans_menu': '📋 مدیریت پلن‌ها',
        'admin_cards_menu': '💳 مدیریت کارت‌های بانکی',
        'admin_settings_menu': '⚙️ **تنظیمات کلی ربات**',
        'trial_panel_select': 'پنل ساخت تست را انتخاب کنید:',
        'trial_inbound_select': (
            'انتخاب اینباند کانفیگ تست\n\n'
            'این گزینه فقط برای پنل‌های XUI/3xUI/Alireza/TX-UI کاربرد دارد.\n'
            'اینباندی را انتخاب کنید تا کانفیگ‌های تست روی همان اینباند ساخته شوند.'
        )
    }
    
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        # بررسی وجود جدول messages و ایجاد آن در صورت نیاز
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='messages'")
        if not cursor.fetchone():
            print("⚠️  جدول messages یافت نشد. در حال ایجاد...")
            cursor.close()
            conn.close()
            if not initialize_messages_table():
                return False
            # اتصال مجدد بعد از ایجاد جدول
            conn = sqlite3.connect(DB_NAME)
            cursor = conn.cursor()
        
        # اضافه کردن متن‌های جدید
        added = 0
        updated = 0
        for message_name, text in new_messages.items():
            cursor.execute(
                "SELECT message_name FROM messages WHERE message_name = ?",
                (message_name,)
            )
            exists = cursor.fetchone()
            
            if exists:
                # بروزرسانی متن موجود (اختیاری)
                cursor.execute(
                    "UPDATE messages SET text = ? WHERE message_name = ?",
                    (text, message_name)
                )
                updated += 1
                print(f"✅ متن '{message_name}' بروزرسانی شد")
            else:
                # اضافه کردن متن جدید
                cursor.execute(
                    "INSERT INTO messages (message_name, text, file_id, file_type) VALUES (?, ?, NULL, NULL)",
                    (message_name, text)
                )
                added += 1
                print(f"➕ متن '{message_name}' اضافه شد")
        
        conn.commit()
        cursor.close()
        conn.close()
        print(f"\n✅ بروزرسانی کامل شد!")
        print(f"   - {added} متن جدید اضافه شد")
        print(f"   - {updated} متن موجود بروزرسانی شد")
        return True
            
    except sqlite3.Error as e:
        print(f"❌ خطا در بروزرسانی دیتابیس: {e}")
        return False
    except Exception as e:
        print(f"❌ خطای غیرمنتظره: {e}")
        return False


if __name__ == "__main__":
    print("🔄 شروع بروزرسانی متن‌های دیتابیس...")
    print(f"📁 دیتابیس: {DB_NAME}")
    
    # بررسی وجود فایل دیتابیس
    if not os.path.exists(DB_NAME):
        print(f"⚠️  فایل دیتابیس یافت نشد. در حال ایجاد {DB_NAME}...")
        # ایجاد فایل جدید
        try:
            with sqlite3.connect(DB_NAME) as conn:
                print("✅ فایل دیتابیس ایجاد شد")
        except Exception as e:
            print(f"❌ خطا در ایجاد فایل دیتابیس: {e}")
            sys.exit(1)
    
    print()
    success = update_messages()
    
    if success:
        print("\n✅ همه چیز با موفقیت انجام شد!")
        print("\n📝 توجه: می‌توانید این متن‌ها را از طریق منوی 'مدیریت پیام‌ها' در پنل ادمین ویرایش کنید.")
        sys.exit(0)
    else:
        print("\n❌ بروزرسانی با خطا مواجه شد!")
        sys.exit(1)
