from aiogram.types import (
    ReplyKeyboardMarkup, 
    KeyboardButton, 
    InlineKeyboardMarkup, 
    InlineKeyboardButton
)
from config import ALLOWED_GROUPS

def get_groups_keyboard() -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text=grp, callback_data=f"reg_group:{grp}")]
        for grp in ALLOWED_GROUPS
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_roles_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="👨‍🎓 Студент", callback_data="reg_role:student"),
            InlineKeyboardButton(text="⭐ Староста", callback_data="reg_role:starosta")
        ]
    ])

def get_main_menu(role: str) -> ReplyKeyboardMarkup:
    keyboard = [
        [KeyboardButton(text="📋 Мои задания / Задолженности")]
    ]
    if role == "starosta":
        keyboard.append([
            KeyboardButton(text="➕ Добавить дедлайн"),
            KeyboardButton(text="🗑 Удалить дедлайн")
        ])
    keyboard.append([KeyboardButton(text="🔄 Сменить группу/роль")])
    
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

def get_assignments_inline_keyboard(assignments: list) -> InlineKeyboardMarkup:
    buttons = []
    for item in assignments:
        status_icon = "✅" if item["is_completed"] else "❌"
        btn_text = f"{status_icon} {item['subject']} (до {item['deadline_date']})"
        buttons.append([
            InlineKeyboardButton(
                text=btn_text, 
                callback_data=f"toggle_task:{item['id']}"
            )
        ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_delete_assignments_keyboard(assignments: list) -> InlineKeyboardMarkup:
    """Клавиатура со списком заданий, которые староста может удалить."""
    buttons = []
    for item in assignments:
        btn_text = f"🗑 {item['subject']} — {item['description'][:20]} (до {item['deadline_date']})"
        buttons.append([
            InlineKeyboardButton(
                text=btn_text, 
                callback_data=f"delete_task:{item['id']}"
            )
        ])
    buttons.append([InlineKeyboardButton(text="✖ Отмена", callback_data="delete_cancel")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)