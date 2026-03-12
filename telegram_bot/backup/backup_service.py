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

    if not db_url:
        logger.error("❌ Database backup failed: DATABASE_URL environment variable is not set.")
        return
    
    if not bot_token or not group_id:
        logger.error("❌ Database backup failed: BOT_TOKEN or BACKUP_GROUP_ID is missing.")
        return

    now = datetime.now().strftime("%Y_%m_%d")
    sql_filename = f"backup_{now}.sql"
    zip_filename = f"backup_{now}.zip"

    try:
        logger.info(f"🔄 Starting database backup process: {sql_filename}")
        
        # 1. Run pg_dump
        # We use pg_dump with the connection string.
        # Render's environment usually has pg_dump installed.
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

        # 2. Compress the SQL file into a ZIP archive
        logger.info(f"📦 Compressing backup to {zip_filename}...")
        with zipfile.ZipFile(zip_filename, 'w', zipfile.ZIP_DEFLATED) as zipf:
            zipf.write(sql_filename)
        
        # 3. Send the ZIP file to the Telegram Group
        logger.info(f"📤 Sending backup to Telegram group: {group_id}")
        
        # Create a temporary bot instance for the task
        # We use a context-safe approach to avoid interfering with the main bot session
        bot_instance = Bot(token=bot_token)
        try:
            document = FSInputFile(zip_filename)
            await bot_instance.send_document(
                chat_id=group_id,
                document=document,
                caption=f"✅ <b>Yutuq (Database Backup)</b>\n📅 Sana: <code>{now}</code>\n📂 Fayl: <code>{zip_filename}</code>",
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
    """Vaqtinchalik test rejimi: har 5 daqiqada va bot ishga tushishi bilan bir marta."""
    scheduler = AsyncIOScheduler(timezone='Asia/Tashkent')
    
    # 1. Asosiy reja: Har kuni 20:00 da
    scheduler.add_job(create_db_backup, CronTrigger(hour=20, minute=0), name="daily_db_backup")
    
    # 2. TEST: Har 5 daqiqada bir marta (ishlayotganini ko'rish uchun)
    scheduler.add_job(create_db_backup, 'interval', minutes=5, name="test_backup_5m")
    
    # 3. TEST: Bot ishga tushishi bilan DARHOL bir marta
    scheduler.add_job(create_db_backup, name="immediate_test_backup")
    
    scheduler.start()
    logger.info("🚀 TEST REJIMI: Backup scheduleri ishga tushdi (Darhol va har 5 daqiqada).")
