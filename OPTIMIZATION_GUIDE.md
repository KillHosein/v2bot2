# راهنمای بهینه‌سازی حافظه و عملکرد

## بهینه‌سازی‌های اعمال شده

### 1. بهینه‌سازی تنظیمات Application
- اضافه شدن **Connection Pool** با حداکثر 8 اتصال همزمان
- تنظیم **Timeout** مناسب برای جلوگیری از اتصالات معلق
- کاهش زمان انتظار در polling

### 2. پردازش تکه‌ای (Batch Processing)
- پردازش سفارشات به صورت دسته‌های 100 تایی
- آزادسازی حافظه بعد از هر batch
- جلوگیری از بارگذاری همه رکوردها در حافظه

### 3. کاهش سطح لاگ
- تغییر سطح پیش‌فرض لاگ از INFO به WARNING
- غیرفعال کردن لاگ‌های جزئی کتابخانه‌ها
- کاهش چشمگیر مصرف حافظه توسط سیستم لاگینگ

### 4. Garbage Collection
- اجرای خودکار garbage collection بعد از هر پنل
- پاکسازی اجباری حافظه در پایان job‌ها
- مانیتورینگ مصرف حافظه

### 5. بهینه‌سازی API Panel
- پشتیبانی از pagination در `get_all_users`
- پاکسازی فوری اشیاء بزرگ response
- کاهش حافظه مصرفی در هنگام دریافت لیست کاربران

## نصب بهینه‌سازی‌ها

### 1. نصب وابستگی جدید
```bash
pip install -r requirements.txt
```

این دستور پکیج `psutil` را برای مانیتورینگ حافظه نصب می‌کند.

### 2. تنظیمات محیطی اختیاری
می‌توانید در فایل `.env` این تنظیمات را اضافه کنید:

```bash
# سطح لاگ (DEBUG, INFO, WARNING, ERROR)
LOG_LEVEL=WARNING

# برای دیباگ می‌توانید به INFO تغییر دهید
# LOG_LEVEL=INFO
```

### 3. راه‌اندازی مجدد ربات
```bash
sudo systemctl restart wingsbot
```

یا اگر با Docker اجرا می‌کنید:
```bash
docker compose restart
```

## مانیتورینگ مصرف حافظه

### مشاهده لاگ‌های حافظه
```bash
sudo journalctl -u wingsbot -f | grep "Memory"
```

این دستور لاگ‌های مربوط به مصرف حافظه را نمایش می‌دهد.

### بررسی مصرف RAM سیستم
```bash
free -h
htop
```

## بهینه‌سازی‌های اضافی (اختیاری)

### 1. محدود کردن حافظه با systemd
می‌توانید در فایل systemd محدودیت حافظه تنظیم کنید:

```bash
sudo nano /etc/systemd/system/wingsbot.service
```

و این خطوط را در بخش `[Service]` اضافه کنید:
```ini
[Service]
MemoryMax=512M
MemoryHigh=400M
```

سپس:
```bash
sudo systemctl daemon-reload
sudo systemctl restart wingsbot
```

### 2. تنظیمات swap برای سرورهای کم RAM
اگر سرور شما RAM کمی دارد (کمتر از 1GB):

```bash
# ایجاد فایل swap 2GB
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile

# برای دائمی شدن
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

### 3. کاهش تعداد job های همزمان
اگر همچنان مشکل RAM دارید، می‌توانید فاصله job های تکراری را افزایش دهید:

در فایل `bot/app.py` خط مربوط به notification job را پیدا کنید و interval را افزایش دهید:
```python
# قبل: هر 6 ساعت
application.job_queue.run_repeating(check_low_traffic_and_expiry, interval=6*3600, ...)

# بعد: هر 12 ساعت
application.job_queue.run_repeating(check_low_traffic_and_expiry, interval=12*3600, ...)
```

## نتایج مورد انتظار

بعد از اعمال این بهینه‌سازی‌ها:
- ✅ کاهش 40-60% مصرف RAM
- ✅ کاهش CPU usage در پیک‌ها
- ✅ پاسخگویی سریع‌تر ربات
- ✅ ثبات بیشتر در سرورهای با RAM کم

## عیب‌یابی

### اگر ربات بالا نمی‌آید
```bash
# بررسی لاگ‌ها
sudo journalctl -u wingsbot -n 100 --no-pager

# اطمینان از نصب وابستگی‌ها
source .venv/bin/activate
pip install -r requirements.txt
```

### اگر همچنان مصرف RAM بالاست
1. تعداد کاربران و سرویس‌های فعال را بررسی کنید
2. تعداد پنل‌ها را کاهش دهید یا در چند سرور توزیع کنید
3. از Docker با محدودیت حافظه استفاده کنید

### برای بازگشت به حالت قبل
اگر مشکلی پیش آمد:
```bash
cd ~/v2bot
git checkout .
pip install -r requirements.txt
sudo systemctl restart wingsbot
```

## رفع خطای "خطا در به‌روزرسانی پیام"

### مشکل
پیام خطا: "خطا در به‌روزرسانی پیام. لطفا دوباره امتحان کنید"

### علت
این خطا زمانی رخ می‌دهد که Callback Query بیش از 30 ثانیه timeout شود یا پیام قدیمی باشد.

### راه‌حل (اعمال شده)
✅ **خودکار**: تمام callback query ها اکنون به صورت ایمن مدیریت می‌شوند:
- پاسخ فوری به callback query (جلوگیری از timeout)
- fallback خودکار به ارسال پیام جدید در صورت خطا
- مدیریت خطای "Message is too old"

### اگر همچنان خطا می‌گیرید
1. ربات را restart کنید
2. کش تلگرام را پاک کنید
3. نسخه جدید را از گیت‌هاب pull کنید

## تماس برای پشتیبانی
در صورت بروز مشکل، لاگ‌های ربات را بررسی کنید و در Github Issue گزارش دهید.
