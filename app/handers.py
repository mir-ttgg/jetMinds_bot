import asyncio
import logging
import re
from os import getenv
from zoneinfo import ZoneInfo

from aiogram import Bot, F, Router
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (CallbackQuery, InlineKeyboardButton,
                           InlineKeyboardMarkup, KeyboardButton, Message,
                           ReplyKeyboardMarkup, ReplyKeyboardRemove)

from app import keyboards as kb
from app.bot_msg import (COMMENT_REQUEST, CONTACT_REQUEST, ERROR_8, FAQ, FINAL,
                         HELLO, NON_QUEL_MSG, QUESTIONS, REMINDER_10MIN,
                         REMINDER_24H, REMINDER_2H, SUCCESS_MESSAGE)
from database.crud import (add_user, get_user_by_id, mark_reminder_sent,
                           save_survey, update_user_comments,
                           update_user_phone, update_user_started_at,
                           user_completed_survey)

router = Router()


contact_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📱 Поделиться контактом", request_contact=True)]],
    resize_keyboard=True
)
submit_keyboard = InlineKeyboardMarkup(
    inline_keyboard=[[InlineKeyboardButton(
        text="📤 Отправить заявку", callback_data="submit_application")]]
)


def get_continue_keyboard(user_id: int) -> InlineKeyboardMarkup:
    """Клавиатура для продолжения опроса из напоминания."""
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(
            text="Продолжить опрос", callback_data=f"continue_{user_id}")]]
    )


def get_take_lead_keyboard(user_id: int) -> InlineKeyboardMarkup:

    return InlineKeyboardMarkup(
        inline_keyboard=[[
            InlineKeyboardButton(text="✅ Взять в работу",
                                 callback_data=f"take_lead_{user_id}")
        ]]
    )


MANAGER_ID = int(getenv('MANAGER_ID', 7830643648))
bot_instance: Bot = None
user_reminder_tasks = {}


async def cancel_reminders(user_id: int):
    if user_id in user_reminder_tasks:
        tasks = user_reminder_tasks.pop(user_id, [])
        for task in tasks:
            if not task.done():
                task.cancel()
        logging.info(f"Напоминания для {user_id} были отменены.")


def set_bot_instance(bot: Bot):
    global bot_instance
    bot_instance = bot


class Form(StatesGroup):
    question_1, question_2, question_3, question_4, question_5, question_6, question_7, question_8, question_9, waiting_for_contact, waiting_for_comments = [
        State() for _ in range(11)]


STATES_MAP = {
    1: Form.question_1, 2: Form.question_2, 3: Form.question_3, 4: Form.question_4, 5: Form.question_5,
    6: Form.question_6, 7: Form.question_7, 8: Form.question_8, 9: Form.question_9,
}


def clean_text(text: str) -> str:
    """Агрессивно очищает текст от всех переносов и лишних пробелов."""
    if not isinstance(text, str):
        text = str(text)
    # Заменяем переносы, затем сжимаем множественные пробелы в один
    return ' '.join(text.replace('\\n', ' ').strip().split())


async def _update_history_display(bot: Bot, chat_id: int, state: FSMContext):
    data = await state.get_data()
    history_message_id = data.get("history_message_id")
    question_items: list[tuple[int, str]] = []

    for key, value in data.items():

        if not key.startswith("question_"):
            continue
        _, idx = key.split("_", 1)
        if not idx.isdigit():
            continue
        if not value:
            continue
        question_items.append((int(idx), value))

    question_items.sort(key=lambda x: x[0])

    if not question_items:
        history_text = "📋 Ваши ответы:\n\nПока нет ответов."
    else:
        history_entries = []
        for q_num, answer_text in question_items:
            question_text_raw = QUESTIONS.get(
                q_num, {}).get("text", f"Вопрос {q_num}")
            question_clean = clean_text(question_text_raw)
            answer_clean = clean_text(answer_text)
            history_entries.append(
                f"{q_num}. {question_clean}\n   ✅ {answer_clean}"
            )
        history_body = "\n\n".join(history_entries)
        history_text = f"📋 Ваши ответы:\n\n{history_body}"

    if history_message_id:
        try:
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=history_message_id,
                text=history_text
            )
        except TelegramBadRequest as e:
            if "message is not modified" not in str(e):
                logging.error(f"Error regenerating history: {e}")


@router.message(CommandStart())
async def start(message: Message, state: FSMContext) -> None:
    user_id = message.from_user.id
    await add_user(user_id=user_id, username=message.from_user.username)

    if user_id == MANAGER_ID:
        return await message.answer("✅ Бот работает! Все новые анкеты будут автоматически скидываться в этот чат.")

    await update_user_started_at(user_id)
    await schedule_reminders(user_id, message.chat.id)

    if await user_completed_survey(user_id):
        user = await get_user_by_id(user_id)
        if user and user.qual:
            if not user.phone:
                await state.set_state(Form.waiting_for_contact)
                await message.answer(CONTACT_REQUEST, reply_markup=contact_keyboard, parse_mode=ParseMode.HTML)
            elif not user.comments:
                await state.set_state(Form.waiting_for_comments)
                await message.answer(COMMENT_REQUEST, reply_markup=submit_keyboard)
            else:
                await message.answer(SUCCESS_MESSAGE)
                await cancel_reminders(user_id)
        else:
            await message.answer(NON_QUEL_MSG, parse_mode=ParseMode.HTML)
            await asyncio.sleep(3)
            await message.answer(FAQ, reply_markup=kb.get_FAQ_keyboard())
            await cancel_reminders(user_id)
        return

    await state.clear()
    await message.answer(HELLO, reply_markup=kb.get_start_keyboard())


async def format_username(username: str | None):
    if not username:
        return '-'
    return username if username.startswith('@') else f'@{username}'


async def send_manager_new_lead(user_id: int):
    if not bot_instance:
        return logging.error("Bot instance is not set.")
    user = await get_user_by_id(user_id)
    if not user or not user.qual or not user.phone:
        return

    formatted_time = 'Не указано'
    if user.survey_completed_at:
        moscow_time = user.survey_completed_at.astimezone(ZoneInfo("Europe/Moscow"))
        formatted_time = moscow_time.strftime('%d.%m.%Y %H:%M')

    answers = [f"{i}. {getattr(user, f'ans_{i}') or 'Нет ответа'}" for i in range(1, 10)]
    lead_text = (
        f"Дата и время: {formatted_time}\n"
        f"TG ID: {user.user_id}\nUsername: {await format_username(user.username)}\n"
        f"Список ответов пользователя:\n" + "\n".join(answers) +
        f"\n\nТелефон: {user.phone}\nКомментарий/способ связи: {user.comments or '-'}"
    )
    try:
        await bot_instance.send_message(MANAGER_ID, lead_text, reply_markup=get_take_lead_keyboard(user_id))
        logging.info(f"Отправлена анкета пользователя {user_id} менеджеру {MANAGER_ID}")
    except Exception as e:
        logging.error(f"Ошибка при отправке анкеты менеджеру: {e}")


@router.callback_query(F.data.startswith('take_lead_'))
async def take_lead(callback: CallbackQuery):
    if callback.from_user.id != MANAGER_ID:
        return await callback.answer("Доступ запрещен", show_alert=True)
    user_id = int(callback.data.split('_')[2])
    try:
        await callback.message.delete()
    except TelegramBadRequest:
        pass
    await callback.message.answer("Лид закреплён за вами")
    if user := await get_user_by_id(user_id):
        formatted_time = 'Не указано'
        if user.survey_completed_at:
            moscow_time = user.survey_completed_at.astimezone(ZoneInfo("Europe/Moscow"))
            formatted_time = moscow_time.strftime('%d.%m.%Y %H:%M')

        answers = [f"{i}. {getattr(user, f'ans_{i}') or 'Нет ответа'}" for i in range(1, 10)]
        lead_text = (
            f"Дата и время: {formatted_time}\n"
            f"TG ID: {user.user_id}\nUsername: @{user.username if user.username else '-'}\n"
            f"Список ответов пользователя:\n" + "\n".join(answers) +
            f"\n\nТелефон: {user.phone}\nКомментарий/способ связи: {user.comments or '-'}"
        )
        await callback.message.answer(lead_text)
    await callback.answer()


@router.callback_query(F.data == 'start_form')
async def start_form(callback: CallbackQuery, state: FSMContext) -> None:
    user_id = callback.from_user.id
    if await user_completed_survey(user_id):
        return await callback.answer("Вы уже прошли опрос.", show_alert=True)

    await state.clear()
    await state.set_state(STATES_MAP[1])
    await update_user_started_at(user_id)
    history_msg = await callback.message.answer('📋 Ваши ответы:\n\nПока нет ответов.')
    await state.set_data({'current_question': 1, 'history_message_id': history_msg.message_id})

    try:
        await callback.message.edit_reply_markup()
    except TelegramBadRequest:
        pass

    await send_question(callback.message, state, 1)
    await callback.answer()


async def send_question(message: Message, state: FSMContext, question_num: int):
    question_data = QUESTIONS[question_num]
    markup = kb.get_back_keyboard(
        question_num) if question_num == 8 else kb.get_question_keyboard(
        question_num, question_data['options'])
    question_msg = await message.answer(question_data['text'], reply_markup=markup)
    await state.update_data(question_message_id=question_msg.message_id)


async def schedule_reminders(user_id: int, chat_id: int):
    await cancel_reminders(user_id)
    if user_id == MANAGER_ID:
        return

    user_reminder_tasks[user_id] = [
        asyncio.create_task(send_reminder(
            user_id, chat_id, 10, REMINDER_10MIN)),
        asyncio.create_task(send_reminder(user_id, chat_id, 120, REMINDER_2H)),
        asyncio.create_task(send_reminder(
            user_id, chat_id, 1440, REMINDER_24H))
    ]
    logging.info(f"Scheduled reminders for user {user_id}.")


async def send_reminder(user_id: int, chat_id: int, minutes: int, text: str):
    try:
        await asyncio.sleep(minutes * 60)
        if await user_completed_survey(user_id):
            return

        user = await get_user_by_id(user_id)
        if not user:
            return

        sent_flag = f'reminder_{"10m" if minutes == 10 else "2h" if minutes == 120 else "24h"}_sent'
        if getattr(user, sent_flag, False):
            return

        if bot_instance:
            await bot_instance.send_message(chat_id, text, reply_markup=get_continue_keyboard(user_id))
            await mark_reminder_sent(user_id, minutes)
        else:
            logging.error(
                "Ошибка в отправке напоминания: экземпляр бота не установлен.")
    except asyncio.CancelledError:
        logging.info(
            f"Напоминание для {user_id} ({minutes} мин) было отменено.")
    except Exception as e:
        logging.error(f"Ошибка в отправлении напоминании {user_id}: {e}")


@router.callback_query(F.data.startswith('continue_'))
async def continue_survey(callback: CallbackQuery, state: FSMContext):
    target_user_id = int(callback.data.split('_')[1])
    if callback.from_user.id != target_user_id:
        return await callback.answer("Это напоминание не для вас.", show_alert=True)

    await cancel_reminders(target_user_id)

    if await user_completed_survey(target_user_id):
        try:
            await callback.message.delete()
        except:
            pass
        return await callback.answer("Вы уже завершили опрос.", show_alert=True)

    try:
        await callback.message.delete()
    except:
        pass

    current_state = await state.get_state()
    if not current_state:
        await start_form(callback, state)
    else:
        q_num = (await state.get_data()).get('current_question', 1)
        await _update_history_display(callback.bot, callback.message.chat.id, state)
        await send_question(callback.message, state, q_num)

    await callback.answer()


async def process_survey_completion(message: Message, state: FSMContext, user_id: int, data: dict):
    # data = await state.get_data()

    qual = not (data.get('question_1') == 'до 14' or data.get('question_2') == 'школа' or data.get('question_4') ==
                'Рассчитываю только на грант' or data.get('question_6') == '2028 и позже' or data.get('question_9') == 'самостоятельно')
    answers = {f'ans_{i}': data.get(f'question_{i}') for i in range(1, 10)}
    await save_survey(user_id=user_id, qual=qual, **answers)
    await state.clear()
    if qual:
        logging.info(f'Анкета от пользователя {user_id}: Квал - {qual}')
        await state.set_state(Form.waiting_for_contact)
        await message.answer(CONTACT_REQUEST, reply_markup=contact_keyboard, parse_mode=ParseMode.HTML)
    else:
        logging.info(f'Анкета от пользователя {user_id}: Неквал - {qual}')
        await cancel_reminders(user_id)
        await message.answer(NON_QUEL_MSG, parse_mode=ParseMode.HTML)
        await asyncio.sleep(3)
        await message.answer(FAQ, reply_markup=kb.get_FAQ_keyboard())


async def handle_answer(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    parts = callback.data.split('_', 2)
    q_num, ans_idx = int(parts[1]), int(parts[2])

    current_data = await state.get_data()
    if q_num != current_data.get('current_question'):
        return await callback.answer()

    answer_text = QUESTIONS[q_num]['options'][ans_idx]
    await state.update_data({f'question_{q_num}': answer_text})
    await _update_history_display(callback.bot, callback.message.chat.id, state)

    if q_msg_id := current_data.get('question_message_id'):
        try:
            await callback.bot.delete_message(callback.message.chat.id, q_msg_id)
        except:
            pass

    next_q = q_num + 1
    if next_q in STATES_MAP:
        await state.update_data(current_question=next_q)
        await state.set_state(STATES_MAP[next_q])
        await send_question(callback.message, state, next_q)
    else:
        final_data = await state.get_data()
        await process_survey_completion(callback.message, state, user_id, final_data)


@router.callback_query(F.data.startswith('answer_'))
async def form_answer(callback: CallbackQuery, state: FSMContext):
    if await user_completed_survey(callback.from_user.id):
        return await callback.answer("Вы уже прошли опрос.", show_alert=True)
    await handle_answer(callback, state)
    await callback.answer()


@router.callback_query(F.data.startswith('back_'))
async def process_back(callback: CallbackQuery, state: FSMContext):
    if await user_completed_survey(callback.from_user.id):
        return await callback.answer("Вы уже прошли опрос.", show_alert=True)

    data = await state.get_data()
    current_q = data.get('current_question', 1)
    if int(callback.data.split('_')[1]) != current_q:
        return await callback.answer()

    prev_q = current_q - 1
    if prev_q < 1:
        return await callback.answer()

    for i in range(current_q, 10):
        data.pop(f'question_{i}', None)
    data['current_question'] = prev_q
    await state.set_data(data)
    await state.set_state(STATES_MAP[prev_q])

    if q_msg_id := data.get('question_message_id'):
        try:
            await callback.bot.delete_message(callback.message.chat.id, q_msg_id)
        except:
            pass

    await _update_history_display(callback.bot, callback.message.chat.id, state)
    await send_question(callback.message, state, prev_q)
    await callback.answer()


@router.message(Form.question_8)
async def process_text_answer(message: Message, state: FSMContext):
    user_id = message.from_user.id
    if await user_completed_survey(user_id):
        return await message.answer("Вы уже прошли опрос")

    if not message.text or len(message.text) > 1500:
        return await message.answer(ERROR_8)

    await state.update_data({'question_8': message.text})
    current_data = await state.get_data()

    if q_msg_id := current_data.get('question_message_id'):
        try:
            await message.bot.delete_message(message.chat.id, q_msg_id)
        except:
            pass
    try:
        await message.delete()
    except:
        pass

    await _update_history_display(message.bot, message.chat.id, state)
    await state.set_state(STATES_MAP[9])
    await state.update_data(current_question=9)
    await send_question(message, state, 9)


@router.message(Form.waiting_for_contact)
async def process_contact(message: Message, state: FSMContext) -> None:
    phone = None
    if message.contact:
        phone = message.contact.phone_number
        if phone.startswith('8'):
            phone = '+7' + phone[1:]
        elif phone.startswith('7'):
            phone = '+' + phone
    elif message.text:
        pattern = r'^\+7\d{10}$'
        if re.match(pattern, message.text):
            phone = message.text
        else:
            await message.answer("Проверьте введенный вами номер на соответствие формату +7XXXXXXXXXX.")
            return
    else:
        await message.answer("Пожалуйста, поделитесь контактом или введите номер в формате +7XXXXXXXXXX.")
        return

    await update_user_phone(message.from_user.id, phone)
    await message.answer("✅ Контакт получен!", reply_markup=ReplyKeyboardRemove())
    await state.set_state(Form.waiting_for_comments)
    await message.answer(COMMENT_REQUEST, reply_markup=submit_keyboard)


@router.message(Form.waiting_for_comments)
async def process_comments(message: Message, state: FSMContext) -> None:
    if message.content_type != 'text' or len(message.text) > 1500:
        await message.answer(FINAL)
        return

    await update_user_comments(message.from_user.id, message.text)
    await message.answer(SUCCESS_MESSAGE)
    await cancel_reminders(message.from_user.id)
    await state.clear()

    await send_manager_new_lead(message.from_user.id)


@router.callback_query(F.data == "submit_application", Form.waiting_for_comments)
async def submit_application(callback: CallbackQuery, state: FSMContext):
    await update_user_comments(callback.from_user.id, "-")
    try:
        await callback.message.edit_reply_markup()
    except:
        pass
    await callback.message.answer(SUCCESS_MESSAGE)
    await cancel_reminders(callback.from_user.id)
    await state.clear()
    await send_manager_new_lead(callback.from_user.id)
    await callback.answer()
