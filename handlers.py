from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from datetime import datetime

import database as db
from config import STAROSTA_PASSWORD
from keyboards import (
    get_groups_keyboard, 
    get_roles_keyboard, 
    get_main_menu, 
    get_assignments_inline_keyboard,
    get_delete_assignments_keyboard
)

router = Router()

# Состояния FSM
class RegistrationState(StatesGroup):
    choosing_group = State()
    choosing_role = State()
    entering_password = State()

class AddAssignmentState(StatesGroup):
    entering_subject = State()
    entering_description = State()
    entering_deadline = State()

# --- СТАРТ И РЕГИСТРАЦИЯ ---

@router.message(CommandStart())
@router.message(F.text == "🔄 Сменить группу/роль")
async def cmd_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(
        "👋 Привет! Я бот контроля учебных дедлайнов.\n\n"
        "Пожалуйста, выбери свою учебную группу:",
        reply_markup=get_groups_keyboard()
    )
    await state.set_state(RegistrationState.choosing_group)

@router.callback_query(RegistrationState.choosing_group, F.data.startswith("reg_group:"))
async def process_group_choice(callback: CallbackQuery, state: FSMContext) -> None:
    group = callback.data.split(":")[1]
    await state.update_data(chosen_group=group)
    
    await callback.message.edit_text(
        f"Выбрана группа: **{group}**\n\nТеперь укажи свой статус:",
        reply_markup=get_roles_keyboard(),
        parse_mode="HTML"
    )
    await state.set_state(RegistrationState.choosing_role)
    await callback.answer()

@router.callback_query(RegistrationState.choosing_role, F.data.startswith("reg_role:"))
async def process_role_choice(callback: CallbackQuery, state: FSMContext) -> None:
    role = callback.data.split(":")[1]
    data = await state.get_data()
    group = data.get("chosen_group")

    if role == "starosta":
        await callback.message.edit_text(
            "🔒 Для подтверждения статуса старосты, пожалуйста, введи пароль доступа:"
        )
        await state.set_state(RegistrationState.entering_password)
    else:
        await db.register_user(callback.from_user.id, group, "student")
        await state.clear()
        await callback.message.delete()
        await callback.message.answer(
            f"✅ Ты успешно зарегистрирован как **Студент** группы **{group}**!",
            reply_markup=get_main_menu("student"),
            parse_mode="HTML"
        )
    await callback.answer()

@router.message(RegistrationState.entering_password)
async def process_password(message: Message, state: FSMContext) -> None:
    if message.text.strip() == STAROSTA_PASSWORD:
        data = await state.get_data()
        group = data.get("chosen_group")
        await db.register_user(message.from_user.id, group, "starosta")
        await state.clear()
        await message.answer(
            f"🎉 Пароль верный! Ты зарегистрирован как **Староста** группы **{group}**.\n"
            "Тебе доступно добавление и удаление дедлайнов для всей группы.",
            reply_markup=get_main_menu("starosta"),
            parse_mode="HTML"
        )
    else:
        await message.answer(
            "❌ Неверный пароль! Попробуй ввести еще раз или напиши /start для повторной регистрации."
        )

# --- ПРОСМОТР И ОТМЕТКА ЗАДАНИЙ ---

@router.message(F.text == "📋 Мои задания / Задолженности")
async def show_assignments(message: Message) -> None:
    user = await db.get_user(message.from_user.id)
    if not user:
        await message.answer("Сначала пройди регистрацию с помощью команды /start")
        return

    tasks = await db.get_user_assignments(user["telegram_id"], user["group_name"])
    if not tasks:
        await message.answer(
            f"🎉 В группе **{user['group_name']}** нет активных дедлайнов!",
            parse_mode="HTML"
        )
        return

    text = (
        f"📚 **Дедлайны группы {user['group_name']}:**\n\n"
        "Нажимай на кнопки ниже, чтобы отметить задание выполненным (поставится ✅) "
        "или снять отметку.\n"
        "*Выполненные задания окончательно исчезнут из списка через 2 дня.*\n\n"
    )

    today = datetime.now().date()
    for t in tasks:
        deadline = datetime.strptime(t["deadline_date"], "%Y-%m-%d").date()
        status = "✅ Сдано" if t["is_completed"] else ("⚠️ Просрочено!" if deadline < today else "⏳ Активно")
        text += (
            f"**• {t['subject']}**\n"
            f"  📝 Задание: {t['description']}\n"
            f"  📅 Дедлайн: {t['deadline_date']} ({status})\n\n"
        )

    await message.answer(text, reply_markup=get_assignments_inline_keyboard(tasks), parse_mode="HTML")

@router.callback_query(F.data.startswith("toggle_task:"))
async def toggle_task_callback(callback: CallbackQuery) -> None:
    user = await db.get_user(callback.from_user.id)
    if not user:
        await callback.answer("Ошибка: пользователь не найден.", show_alert=True)
        return

    task_id = int(callback.data.split(":")[1])
    new_status = await db.toggle_assignment_status(callback.from_user.id, task_id)
    
    tasks = await db.get_user_assignments(user["telegram_id"], user["group_name"])
    status_msg = "✅ Задание отмечено как выполненное!" if new_status else "❌ Отметка о выполнении снята."
    await callback.answer(status_msg)
    
    try:
        await callback.message.edit_reply_markup(
            reply_markup=get_assignments_inline_keyboard(tasks)
        )
    except Exception:
        pass

# --- ДОБАВЛЕНИЕ ДЕДЛАЙНА (СТАРОСТА) ---

@router.message(F.text == "➕ Добавить дедлайн")
async def add_deadline_start(message: Message, state: FSMContext) -> None:
    user = await db.get_user(message.from_user.id)
    if not user or user["role"] != "starosta":
        await message.answer("Эта команда доступна только старостам.")
        return

    await message.answer("Введи название предмета (например: *Высшая математика*):", parse_mode="HTML")
    await state.set_state(AddAssignmentState.entering_subject)

@router.message(AddAssignmentState.entering_subject)
async def add_subject(message: Message, state: FSMContext) -> None:
    subject = message.text.strip()
    if len(subject) < 2:
        await message.answer("Слишком короткое название предмета. Попробуй еще раз:")
        return

    await state.update_data(subject=subject)
    await message.answer("Опиши суть задания (например: *Лабораторная работа №3, отчет и защита*):")
    await state.set_state(AddAssignmentState.entering_description)

@router.message(AddAssignmentState.entering_description)
async def add_description(message: Message, state: FSMContext) -> None:
    await state.update_data(description=message.text.strip())
    await message.answer(
        "Введи крайний срок сдачи (дедлайн) в формате **ДД.ММ.ГГГГ**\n"
        "Например: `25.10.2026`",
        parse_mode="HTML"
    )
    await state.set_state(AddAssignmentState.entering_deadline)

@router.message(AddAssignmentState.entering_deadline)
async def add_deadline_finish(message: Message, state: FSMContext) -> None:
    date_text = message.text.strip()
    try:
        parsed_date = datetime.strptime(date_text, "%d.%m.%Y").date()
    except ValueError:
        await message.answer(
            "❌ Неверный формат даты! Пожалуйста, используй формат **ДД.ММ.ГГГГ** (например, 25.10.2026):",
            parse_mode="HTML"
        )
        return

    data = await state.get_data()
    user = await db.get_user(message.from_user.id)

    db_date_str = parsed_date.strftime("%Y-%m-%d")
    await db.add_assignment(
        group_name=user["group_name"],
        subject=data["subject"],
        description=data["description"],
        deadline_date=db_date_str,
        created_by=message.from_user.id
    )

    await state.clear()
    await message.answer(
        f"✅ **Дедлайн успешно добавлен!**\n\n"
        f"📌 Предмет: **{data['subject']}**\n"
        f"📝 Задание: {data['description']}\n"
        f"📅 Срок сдачи: **{date_text}**\n"
        f"👥 Группа: **{user['group_name']}**",
        reply_markup=get_main_menu("starosta"),
        parse_mode="HTML"
    )

# --- УДАЛЕНИЕ ДЕДЛАЙНА (СТАРОСТА) ---

@router.message(F.text == "🗑 Удалить дедлайн")
async def delete_deadline_start(message: Message) -> None:
    user = await db.get_user(message.from_user.id)
    if not user or user["role"] != "starosta":
        await message.answer("Эта команда доступна только старостам.")
        return

    tasks = await db.get_assignments_by_group(user["group_name"])
    if not tasks:
        await message.answer("В вашей группе пока нет созданных заданий для удаления.")
        return

    await message.answer(
        "Выберите задание, которое нужно **безвозвратно удалить** из базы группы:",
        reply_markup=get_delete_assignments_keyboard(tasks),
        parse_mode="HTML"
    )

@router.callback_query(F.data.startswith("delete_task:"))
async def process_delete_task(callback: CallbackQuery) -> None:
    user = await db.get_user(callback.from_user.id)
    if not user or user["role"] != "starosta":
        await callback.answer("Действие разрешено только старосте.", show_alert=True)
        return

    task_id = int(callback.data.split(":")[1])
    deleted = await db.delete_assignment(task_id, user["group_name"])

    if deleted:
        await callback.answer("🗑 Задание удалено!", show_alert=True)
    else:
        await callback.answer("Задание уже было удалено.", show_alert=True)

    # Обновляем список оставшихся заданий
    tasks = await db.get_assignments_by_group(user["group_name"])
    if tasks:
        await callback.message.edit_text(
            "Задание удалено. Выберите следующее или нажмите «Отмена»:",
            reply_markup=get_delete_assignments_keyboard(tasks)
        )
    else:
        await callback.message.edit_text("Все задания группы были удалены.")

@router.callback_query(F.data == "delete_cancel")
async def cancel_delete(callback: CallbackQuery) -> None:
    await callback.message.delete()
    await callback.answer("Удаление отменено.")