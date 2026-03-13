import os
import asyncio
import logging
import zipfile
from datetime import datetime
from aiogram import Bot
from aiogram.types import FSInputFile
from aiogram.exceptions import TelegramMigrateToChat
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

# Set up logging
logger = logging.getLogger(__name__)

# This is for manual command handling
from aiogram import Router, types
from aiogram.filters import Command
router = Router()

async def create_db_backup():
    """
    Creates a PostgreSQL backup using pg_dump, zips it, sends to Telegram, and cleans up.
    """
    db_url = os.getenv("DATABASE_URL")
    
    # 🚨 Render Production Logic: Construct URL if DATABASE_URL is missing but separate bits exist
    if not db_url:
        db_name = os.getenv("DB_NAME")
        db_user = os.getenv("DB_USER")
        db_pass = os.getenv("DB_PASSWORD")
        db_host = os.getenv("DB_HOST")
        db_port = os.getenv("DB_PORT", "5432")
        if all([db_name, db_user, db_pass, db_host]):
            db_url = f"postgresql://{db_user}:{db_pass}@{db_host}:{db_port}/{db_name}"
            print("[BACKUP] 🔗 Constructed DB URL from individual env vars.")

    bot_token = os.getenv("BOT_TOKEN")
    group_id = os.getenv("BACKUP_GROUP_ID")

    # Force integer ID for Telegram API
    if group_id:
        try:
            # Handle string IDs with '-' correctly
            group_id = int(str(group_id).strip())
        except ValueError:
            print(f"[BACKUP] ⚠️ Invalid BACKUP_GROUP_ID format: {group_id}")
            pass

    # Local mode check: Robust project root finding
    # Current file: telegram_bot/backup/backup_service.py
    # Project root: 3 levels up
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.abspath(os.path.join(current_dir, "..", ".."))
    sqlite_path = os.path.join(project_root, "db.sqlite3")
    
    print(f"[BACKUP] 🔎 System searching for database at: {sqlite_path}")
    logger.info(f"🔎 System searching for database at: {sqlite_path}")
    
    is_postgres = bool(db_url)
    is_sqlite = not is_postgres and os.path.exists(sqlite_path)

    if not is_postgres and not is_sqlite:
        print(f"[BACKUP] ❌ FAILED: Database not found. (Postgres URL: {bool(db_url)}, SQLite exists: {os.path.exists(sqlite_path)})")
        logger.error(f"❌ Database backup failed: No DATABASE_URL found and db.sqlite3 is missing at {sqlite_path}.")
        return
    
    if not bot_token or not group_id:
        logger.error("❌ Database backup failed: BOT_TOKEN or BACKUP_GROUP_ID is missing.")
        return

    now = datetime.now().strftime("%Y_%m_%d")
    sql_filename = f"backup_{now}.sql"
    db_file_to_zip = sql_filename
    zip_filename = f"backup_{now}.zip"

    try:
        print(f"[BACKUP] 🚀 STARTING BACKUP. Mode: {'PostgreSQL' if is_postgres else 'SQLite'}")
        if is_postgres:
            print(f"[BACKUP] 🔄 Attempting PostgreSQL backup using pg_dump...")
            try:
                # Check if pg_dump is available first
                check_process = await asyncio.create_subprocess_exec(
                    "pg_dump", "--version",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                await check_process.communicate()
            except FileNotFoundError:
                err = "❌ 'pg_dump' command not found on this server! Postgres backup is impossible without it."
                print(f"[BACKUP] {err}")
                if bot_token and group_id:
                    temp_bot = Bot(token=bot_token)
                    await temp_bot.send_message(group_id, f"⚠️ <b>Zahira nusxa xatosi:</b>\nServerda <code>pg_dump</code> topilmadi. PostgreSQL zahirasi uchun u zarur.\n\n💡 <b>Yechim:</b> Render'da 'Docker' muhitiga o'ting yoki qo'llab-quvvatlash bilan bog'laning.", parse_mode="HTML")
                    await temp_bot.session.close()
                return

            process = await asyncio.create_subprocess_exec(
                "pg_dump", db_url, "-f", sql_filename,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()
            
            if process.returncode != 0:
                error_msg = stderr.decode().strip()
                print(f"[BACKUP] ❌ pg_dump failed: {error_msg}")
                return
        else:
            logger.info("🔄 SQLite detected. Using db.sqlite3 for backup.")
            db_file_to_zip = sqlite_path
            # We don't need to create a new file, we'll zip the existing one

        # 2. Compress the DB file into a ZIP archive
        logger.info(f"📦 Compressing backup to {zip_filename}...")
        with zipfile.ZipFile(zip_filename, 'w', zipfile.ZIP_DEFLATED) as zipf:
            # For SQLite, we might want to name the file inside zip as 'db.sqlite3'
            arcname = "db.sqlite3" if is_sqlite else sql_filename
            zipf.write(db_file_to_zip, arcname=arcname)
        
        # 3. Send the ZIP file to the Telegram Group
        logger.info(f"📤 Sending backup to Telegram group: {group_id}")
        
        # Create a temporary bot instance for the task
        # We use a context-safe approach to avoid interfering with the main bot session
        bot_instance = Bot(token=bot_token)
        try:
            document = FSInputFile(zip_filename)
            type_name = "PostgreSQL" if is_postgres else "SQLite"
            await bot_instance.send_document(
                chat_id=group_id,
                document=document,
                caption=f"✅ <b>Yutuq (Database Backup)</b>\n📅 Sana: <code>{now}</code>\n🗄 Turi: <code>{type_name}</code>\n📂 Fayl: <code>{zip_filename}</code>",
                parse_mode="HTML"
            )
            logger.info("✅ Backup successfully sent to Telegram!")
        except TelegramMigrateToChat as e:
            new_id = e.migrate_to_chat_id
            print(f"[BACKUP] ⚠️ Group migrated to supergroup! New ID: {new_id}")
            logger.error(f"❌ Migration error: Group upgraded. Please update BACKUP_GROUP_ID to {new_id}")
            # Try once with the new ID
            try:
                await bot_instance.send_document(
                    chat_id=new_id,
                    document=FSInputFile(zip_filename),
                    caption=f"✅ <b>Yutuq (Database Backup)</b>\n📅 Sana: <code>{now}</code>\n🗄 Turi: {type_name}\n⚠️ <i>Guruh superguruhga o'zgardi. Yangi ID: {new_id}</i>",
                    parse_mode="HTML"
                )
            except Exception as e2:
                logger.error(f"Failed again with new ID: {e2}")
        finally:
            # Important: Close the session to prevent memory leaks or warnings
            await bot_instance.session.close()

    except Exception as e:
        logger.error(f"⚠️ Critical error during backup: {e}", exc_info=True)
    
    finally:
        # 4. Cleanup: Remove temporary files from server
        logger.info("🧹 Cleaning up temporary files...")
        if os.path.exists(sql_filename):
            try:
                os.remove(sql_filename)
            except Exception as e:
                logger.warning(f"Failed to delete {sql_filename}: {e}")
        
        if os.path.exists(zip_filename):
            try:
                os.remove(zip_filename)
            except Exception as e:
                logger.warning(f"Failed to delete {zip_filename}: {e}")
        
        logger.info("✨ Backup process finished.")

async def setup_backup_scheduler():
    """Har kuni soat 20:00 da backup qilish uchun shadulerni sozlash."""
    # Asia/Tashkent vaqti bilan (mavjud bot sozlamalariga mos)
    scheduler = AsyncIOScheduler(timezone='Asia/Tashkent')
    
    # Har kuni soat 20:00 da ishga tushirish
    trigger = CronTrigger(hour=22, minute=20)
    
    scheduler.add_job(create_db_backup, trigger, name="daily_db_backup")
    scheduler.start()
    
    print("🚀 Database backup scheduler initialized (Daily at 20:00).")
    logger.info("🚀 Database backup scheduler started (Daily at 20:00).")

@router.message(Command("backup_now"))
async def manual_backup_command(message: types.Message):
    """Admin uchun manunal backup buyrug'i (faqat test uchun)"""
    # Check if user is director or admin in your system logic if needed
    await message.answer("🔄 Zahira nusxasini yaratish boshlandi...")
    await create_db_backup()
    await message.answer("✅ Jarayon yakunlandi. Agar hammasi to'g'ri bo'lsa, guruhga fayl yuborildi.")
