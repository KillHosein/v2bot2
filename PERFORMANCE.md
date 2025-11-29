# 🚀 راهنمای بهینه‌سازی Performance ربات

## 📊 تنظیمات سیستم عامل

### 1. افزایش Swap (اگر RAM کم است)
```bash
# چک کردن swap فعلی
sudo swapon --show
free -h

# ایجاد 2GB swap (اگر ندارید)
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile

# Permanent کردن
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab

# بهینه‌سازی swappiness (استفاده کمتر از swap)
sudo sysctl vm.swappiness=10
echo 'vm.swappiness=10' | sudo tee -a /etc/sysctl.conf
```

### 2. تنظیمات Systemd برای محدود کردن RAM
```bash
sudo systemctl edit wingsbot
```
اضافه کنید:
```ini
[Service]
MemoryMax=512M
MemoryHigh=400M
CPUQuota=50%
```

### 3. بهینه‌سازی SQLite Database
```bash
# Optimize database (هر هفته یکبار)
cd ~/v2bot
sqlite3 bot.db "VACUUM;"
sqlite3 bot.db "ANALYZE;"
```

---

## ⚙️ تنظیمات ربات

### 1. کاهش فرکانس Job ها
در پنل ادمین > تنظیمات:
- **Notification Job**: هر 24 ساعت (پیش‌فرض)
- **Auto Backup**: هر 6-12 ساعت (نه هر 3 ساعت)
- **Daily Expiration Check**: روزانه یکبار

### 2. غیرفعال کردن ویژگی‌های غیر ضروری
```sql
# اگر از هشدار ترافیک استفاده نمی‌کنید
sqlite3 ~/v2bot/bot.db "UPDATE settings SET value='0' WHERE key='traffic_alert_enabled';"

# اگر از یادآوری زمانی استفاده نمی‌کنید
sqlite3 ~/v2bot/bot.db "UPDATE settings SET value='0' WHERE key='time_alert_enabled';"
```

### 3. پاکسازی لاگ‌های قدیمی
```bash
# پاکسازی لاگ‌های بیش از 7 روز
sudo journalctl --vacuum-time=7d

# محدود کردن سایز لاگ به 100MB
sudo journalctl --vacuum-size=100M
```

---

## 🔍 مانیتورینگ Performance

### 1. چک کردن مصرف RAM
```bash
# RAM usage ربات
ps aux | grep python | grep wingsbot

# یا با systemctl
systemctl status wingsbot
```

### 2. چک کردن سایز Database
```bash
du -h ~/v2bot/bot.db
```

### 3. چک کردن تعداد Connection ها
```bash
# تعداد connection های فعال
ss -tunap | grep python | wc -l
```

---

## 🛠️ بهینه‌سازی‌های پیشرفته

### 1. استفاده از Connection Pooling
کد فعلی از WAL mode استفاده می‌کند که بهینه است.

### 2. Caching
ربات حالا از cache برای settings استفاده می‌کند (cache.py).

### 3. استفاده از Index ها
Database از index های زیر استفاده می‌کند:
- `idx_orders_status_date`
- `idx_orders_user`
- `idx_wallet_tx_user_status`
- `idx_panels_enabled`

---

## 📈 توصیه‌ها بر اساس تعداد کاربر

### کمتر از 100 کاربر
- RAM مورد نیاز: **256-512 MB**
- CPU: 1 Core کافی است
- Swap: 1GB

### 100-500 کاربر
- RAM مورد نیاز: **512MB-1GB**
- CPU: 1-2 Cores
- Swap: 2GB
- Notification interval: 24h

### بیش از 500 کاربر
- RAM مورد نیاز: **1-2GB**
- CPU: 2+ Cores
- Swap: 2-4GB
- یک VPS مجزا برای ربات
- استفاده از PostgreSQL به جای SQLite (در آینده)

---

## 🐛 اگر ربات کند است

### تشخیص bottleneck:
```bash
# 1. چک کردن CPU usage
top -p $(pgrep -f wingsbot)

# 2. چک کردن I/O wait
iostat -x 1 10

# 3. چک کردن network latency
ping -c 10 your-panel-domain.com

# 4. چک کردن لاگ برای errors
sudo journalctl -u wingsbot -n 200 --no-pager | grep -i error
```

### راه‌حل‌ها:
1. **اگر CPU بالاست**: کاهش job frequency
2. **اگر RAM تمام است**: افزایش swap یا RAM
3. **اگر I/O بالاست**: VACUUM database
4. **اگر Network کند است**: چک کردن اتصال به پنل

---

## 💾 Backup قبل از بهینه‌سازی
```bash
# Backup database
cp ~/v2bot/bot.db ~/v2bot/bot.db.backup.$(date +%Y%m%d)

# Backup کل ربات
tar -czf ~/v2bot-backup-$(date +%Y%m%d).tar.gz ~/v2bot/
```

---

## 📞 مشکل دارید؟
اگر بعد از این بهینه‌سازی‌ها همچنان مشکل دارید:
- لاگ کامل را چک کنید
- تعداد کاربران و سرویس‌های فعال را بررسی کنید
- مشخصات سرور را چک کنید (RAM, CPU, Disk)
