# Telegram Database Backups

## Env sozlamalari

```env
TELEGRAM_BOT_TOKEN=
TELEGRAM_BACKUP_CHAT_ID=
BACKUP_TIMEZONE=Asia/Tashkent
BACKUP_SEND_TIME=18:00
BACKUP_KEEP_DAYS=7
ADMIN_TELEGRAM_IDS=
```

`TELEGRAM_BACKUP_CHAT_ID` asosiy backup chat ID. Eski `BACKUP_GROUP_ID` va `TELEGRAM_GROUP_ID` fallback sifatida hali ham o'qiladi.

`ADMIN_TELEGRAM_IDS` vergul bilan ajratiladi. Bo'sh bo'lsa `/db` uchun `accounts.BotAdmin` yoki Telegram ID bog'langan Django superuser tekshiriladi.

## Commandlar

```bash
python manage.py backup_databases
python manage.py send_db_backups
python manage.py configure_backup_bot
```

`backup_databases` backup fayllarni `backups/` ichiga yaratadi va Telegramga yubormaydi.

`send_db_backups` real-time backup yaratadi, Telegramga avval status xabari, keyin har bir faylni `sendDocument` orqali yuboradi.

`configure_backup_bot` bot token/chatni tekshiradi, `/db` commandni Telegramga ro'yxatdan o'tkazadi va default polling mode uchun webhookni o'chiradi. Webhook kerak bo'lsa:

```bash
python manage.py configure_backup_bot --mode webhook --webhook-url https://example.com/telegram/webhook/
```

## Fayl nomlari

Global backup:

```text
global_backup_YYYY-MM-DD_HH-MM.sql
global_backup_YYYY-MM-DD_HH-MM.sqlite3
```

Markaz backup:

```text
center_<slug>_backup_YYYY-MM-DD_HH-MM.sql
center_<slug>_backup_YYYY-MM-DD_HH-MM.json
```

Markaz uchun `.sql` faqat markazning `Center.db_*` credentiallari default DBdan farq qiladigan alohida PostgreSQL DB bo'lsa yaratiladi. Hozirgi ChaqmoqApp tenant ma'lumotlari asosan bitta physical DB ichida `center` FK orqali ajratilgan, shuning uchun bunday markazlar `center_scoped_snapshot` JSON sifatida export qilinadi.

## Scheduler

Render cron:

```text
0 13 * * *  # 18:00 Asia/Tashkent
python3 manage.py send_db_backups
```

APScheduler yoqilsa job ID:

```text
tenant-db-backup-daily-send-telegram
```

Production Render uchun Render Cron tavsiya qilingan. Web worker ichida scheduler faqat `BACKUP_SCHEDULER_ENABLED=true` bo'lsa ishga tushadi.

## PostgreSQL va pg_dump

PostgreSQL uchun `pg_dump` PATH ichida bo'lishi kerak. Agar Render Native Runtime ichida `pg_dump` topilmasa command aniq error beradi. Render Native Runtime OS-level paketlar uchun cheklangan; productionda ishonchli yechim Docker image ichida `postgresql-client` o'rnatish yoki `pg_dump` binaryni build vaqtida app pathga qo'shib `PATH`ga kiritish.
