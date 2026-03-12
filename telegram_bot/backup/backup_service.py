import os
import asyncio
import logging
import zipfile
from datetime import datetime
from aiogram import Bot
from aiogram.types import FSInputFile
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

# Set up logging
logger = logging.getLogger(__name__)

async def create_db_backup():
    """
    Creates a PostgreSQL backup using pg_dump, zips it, sends to Telegram, and cleans up.
    """
    db_url = os.getenv("DATABASE_URL")
    bot_token = os.getenv("BOT_TOKEN")
    group_id = os.getenv("BACKUP_GROUP_ID")

    # Local mode check: If no DATABASE_URL, look for db.sqlite3 in project root
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sqlite_path = os.path.join(base_dir, "db.sqlite3")
    
    is_postgres = bool(db_url)
    is_sqlite = not is_postgres and os.path.exists(sqlite_path)

    if not is_postgres and not is_sqlite:
        logger.error("❌ Database backup failed: No DATABASE_URL found and db.sqlite3 is missing.")
        return
    
    if not bot_token or not group_id:
        logger.error("❌ Database backup failed: BOT_TOKEN or BACKUP_GROUP_ID is missing.")
        return

    now = datetime.now().strftime("%Y_%m_%d")
    sql_filename = f"backup_{now}.sql"
    db_file_to_zip = sql_filename
    zip_filename = f"backup_{now}.zip"

    try:
        if is_postgres:
            logger.info(f"🔄 Starting PostgreSQL backup via pg_dump: {sql_filename}")
            process = await asyncio.create_subprocess_exec(
                "pg_dump", db_url, "-f", sql_filename,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()

            if process.returncode != 0:
                error_msg = stderr.decode().strip()
                logger.error(f"❌ pg_dump failed with return code {process.returncode}: {error_msg}")
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
    trigger = CronTrigger(hour=21, minute=45)
    
    scheduler.add_job(create_db_backup, trigger, name="daily_db_backup")
    scheduler.start()
    
    logger.info("🚀 Database backup scheduler started (Daily at 20:00).")
