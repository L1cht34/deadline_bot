import pytz
from aiogram import Bot
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler

import database as db
from config import TIMEZONE

async def send_daily_deadline_alerts(bot: Bot) -> None:
    """
    Рассылка в 18:00 (каждый день):
    1. Напоминания по конкретным предметам, если до дедлайна 7, 3, 2 или 1 день.
    2. Ежедневные напоминания по всем просроченным заданиям.
    """
    students = await db.get_all_students()

    for student in students:
        telegram_id = student["telegram_id"]
        group_name = student["group_name"]

        data = await db.get_upcoming_and_overdue_for_user(telegram_id, group_name)
        upcoming = data["upcoming"]
        overdue = data["overdue"]

        # Напоминание о горящих дедлайнах
        if upcoming:
            text = "⏰ **Приближаются сроки сдачи заданий!**\n\n"
            for item in upcoming:
                text += (
                    f"📌 **{item['subject']}**\n"
                    f"📝 {item['description']}\n"
                    f"⏳ Осталось дней: **{item['days_left']}** (до {item['deadline_date']})\n\n"
                )
            text += "*Не забудь сдать работу и отметить ее в боте!*"
            try:
                await bot.send_message(telegram_id, text, parse_mode="HTML")
            except Exception:
                pass  # Студент мог заблокировать бота

        # Напоминание о просроченных заданиях
        if overdue:
            text = "🚨 **ВНИМАНИЕ! У тебя есть просроченные задания:**\n\n"
            for item in overdue:
                text += (
                    f"❌ **{item['subject']}**\n"
                    f"📝 {item['description']}\n"
                    f"⚠️ Дедлайн истек: **{item['deadline_date']}** (просрочено на {item['days_overdue']} дн.)\n\n"
                )
            text += "*Пожалуйста, свяжись с преподавателем и закрой долг!*"
            try:
                await bot.send_message(telegram_id, text, parse_mode="HTML")
            except Exception:
                pass

async def send_periodic_all_assignments(bot: Bot) -> None:
    """
    Общая сводка по всем активным заданиям каждые 3 дня в 19:00.
    """
    students = await db.get_all_students()
    today = datetime.now().date()

    for student in students:
        telegram_id = student["telegram_id"]
        group_name = student["group_name"]

        tasks = await db.get_user_assignments(telegram_id, group_name)
        # Оставляем только незакрытые задания
        pending_tasks = [t for t in tasks if not t["is_completed"]]

        if not pending_tasks:
            continue

        text = f"📅 **Плановая сводка дедлайнов (группа {group_name})**\n\n"
        for t in pending_tasks:
            deadline = datetime.strptime(t["deadline_date"], "%Y-%m-%d").date()
            status = "⚠️ Просрочено" if deadline < today else "⏳ В процессе"
            text += (
                f"• **{t['subject']}**\n"
                f"  Задание: {t['description']}\n"
                f"  Срок: {t['deadline_date']} ({status})\n\n"
            )
        text += "Проверить подробнее и отметить сдачу можно в меню «Мои задания»."

        try:
            await bot.send_message(telegram_id, text, parse_mode="HTML")
        except Exception:
            pass

def setup_scheduler(bot: Bot) -> AsyncIOScheduler:
    """Конфигурация и запуск APScheduler."""
    tz = pytz.timezone(TIMEZONE)
    scheduler = AsyncIOScheduler(timezone=tz)

    # 1. Ежедневно в 18:00 — проверка приближающихся (7, 3, 2, 1 день) и просроченных заданий
    scheduler.add_job(
        send_daily_deadline_alerts,
        trigger="cron",
        hour=18,
        minute=0,
        args=[bot]
    )

    # 2. Каждые 3 дня в 19:00 — общая сводка по всем текущим заданиям
    scheduler.add_job(
        send_periodic_all_assignments,
        trigger="interval",
        days=3,
        start_date=datetime.now(tz).replace(hour=19, minute=0, second=0),
        args=[bot]
    )

    return scheduler