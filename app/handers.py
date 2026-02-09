import asyncio
import logging
import re
from datetime import datetime, timedelta
from os import getenv

from aiogram import Bot, F, Router
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (CallbackQuery, InlineKeyboardButton,
                           InlineKeyboardMarkup, KeyboardButton, Message,
                           ReplyKeyboardMarkup, ReplyKeyboardRemove)

from app import keyboards as kb
from app.bot_msg import (COMMENT_REQUEST, CONTACT_REQUEST, ERROR_8, FAQ, FINAL,
                         HELLO, NON_QUEL_MSG, QUESTIONS, REMINDER_2H,
                         REMINDER_10MIN, REMINDER_24H, SUCCESS_MESSAGE)
from database.crud import (add_user, get_user_by_id, mark_reminder_sent,
                           save_survey, update_user_comments,
                           update_user_phone, update_user_started_at,
                           user_completed_survey)

router = Router()
MANAGER_ID = int(getenv('MANAGER_ID', 7830643648))

bot_instance: Bot = None


def set_bot_instance(bot: Bot):
    global bot_instance
    bot_instance = bot


class Form(StatesGroup):
    question_1 = State()
    question_2 = State()
    question_3 = State()
    question_4 = State()
    question_5 = State()
    question_6 = State()
    question_7 = State()
    question_8 = State()
    question_9 = State()
    waiting_for_contact = State()
    waiting_for_comments = State()


user_start_times = {}
user_reminder_tasks = {}

STATES_MAP = {
    1: Form.question_1,
    2: Form.question_2,
    3: Form.question_3,
    4: Form.question_4,
    5: Form.question_5,
    6: Form.question_6,
    7: Form.question_7,
    8: Form.question_8,
    9: Form.question_9,
}


@router.message(CommandStart())
async def start(message: Message, state: FSMContext) -> None:
    user_id = message.from_user.id
    await add_user(user_id=user_id, username=message.from_user.username)

    if message.from_user.id == MANAGER_ID:
        await message.answer("✅ Бот работает! Все новые анкеты будут автоматически скидываться в этот чат.")
        return

    if await user_completed_survey(user_id):
        user = await get_user_by_id(user_id)
        if user.qual:
            if not user.phone:
                await state.set_state(Form.waiting_for_contact)
                contact_keyboard = ReplyKeyboardMarkup(
                    keyboard=[
                        [KeyboardButton(text="📱 Поделиться контактом", request_contact=True)]],
                    resize_keyboard=True,
                    one_time_keyboard=True
                )
                await message.answer(CONTACT_REQUEST, reply_markup=contact_keyboard)
            elif not user.comments:
                await state.set_state(Form.waiting_for_comments)
                submit_keyboard = InlineKeyboardMarkup(
                    inline_keyboard=[[InlineKeyboardButton(
                        text="📤 Отправить заявку", callback_data="submit_application")]]
                )
                await message.answer(COMMENT_REQUEST, reply_markup=submit_keyboard)
            else:
                await message.answer(SUCCESS_MESSAGE)
        else:
            await message.answer(NON_QUEL_MSG, parse_mode=ParseMode.HTML)
            await asyncio.sleep(3)
            await message.answer(FAQ, reply_markup=kb.get_FAQ_keyboard())
        return

    await state.clear()
    await message.answer(HELLO, reply_markup=kb.get_start_keyboard())


async def send_manager_new_lead(user_id: int):
    """Отправить новую анкету менеджеру"""
    global bot_instance
    if not bot_instance:
        logging.error("Bot instance is not set. Cannot send lead to manager.")
        return

    user = await get_user_by_id(user_id)

    # Проверяем, что пользователь квалифицированный и прошел весь сценарий
    if not user or not user.qual or not user.phone or not user.comments:
        return

    lead_text = format_lead_message(user)
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(
            text="✅ Взять в работу", callback_data=f"take_lead_{user.user_id}")]]
    )

    # Отправляем сообщение менеджеру
    try:
        await bot_instance.send_message(chat_id=MANAGER_ID, text=lead_text, reply_markup=keyboard)
        logging.info(
            f"Отправлена анкета пользователя {user_id} менеджеру {MANAGER_ID}")
    except Exception as e:
        logging.error(f"Ошибка при отправке анкеты менеджеру: {e}")


def format_lead_message(user):
    answers = [
        f"1. {user.ans_1}" if user.ans_1 else "1. Нет ответа",
        f"2. {user.ans_2}" if user.ans_2 else "2. Нет ответа",
        f"3. {user.ans_3}" if user.ans_3 else "3. Нет ответа",
        f"4. {user.ans_4}" if user.ans_4 else "4. Нет ответа",
        f"5. {user.ans_5}" if user.ans_5 else "5. Нет ответа",
        f"6. {user.ans_6}" if user.ans_6 else "6. Нет ответа",
        f"7. {user.ans_7}" if user.ans_7 else "7. Нет ответа",
        f"8. {user.ans_8}" if user.ans_8 else "8. Нет ответа",
        f"9. {user.ans_9}" if user.ans_9 else "9. Нет ответа"
    ]

    return (
        f"Дата и время: {user.survey_completed_at.strftime('%d.%m.%Y %H:%M') if user.survey_completed_at else 'Не указано'}\n"
        f"TG ID: {user.user_id}\n"
        f"Username: {user.username or 'прочерк'}\n"
        f"Список ответов пользователя:\n" +
        "\n".join(answers) + f"\n\nТелефон: {user.phone}\n"
        f"Комментарий/способ связи: {user.comments}"
    )


@router.callback_query(F.data.startswith('take_lead_'))
async def take_lead(callback: CallbackQuery):
    if callback.from_user.id != MANAGER_ID:
        await callback.answer("Доступ запрещен", show_alert=True)
        return

    user_id = int(callback.data.split('_')[2])

    try:
        await callback.message.delete()
    except:
        pass

    await callback.message.answer("Лид закреплён за вами")

    user = await get_user_by_id(user_id)
    if user:
        lead_text = format_lead_message(user)
        await callback.message.answer(lead_text)

    await callback.answer()


@router.callback_query(F.data == 'start_form')
async def start_form(callback: CallbackQuery, state: FSMContext) -> None:
    user_id = callback.from_user.id
    if await user_completed_survey(user_id):
        user = await get_user_by_id(user_id)
        if user and user.qual:
            if not user.phone:
                await callback.answer("Вы уже прошли опрос, но не оставили контакт", show_alert=True)
                await state.set_state(Form.waiting_for_contact)
                contact_keyboard = ReplyKeyboardMarkup(
                    keyboard=[
                        [KeyboardButton(text="📱 Поделиться контактом", request_contact=True)]],
                    resize_keyboard=True,
                    one_time_keyboard=True
                )
                await callback.message.answer(CONTACT_REQUEST, reply_markup=contact_keyboard, parse_mode=ParseMode.HTML)
            elif not user.comments:
                await callback.answer("Вы уже прошли опрос, но не оставили комментарии", show_alert=True)
                await state.set_state(Form.waiting_for_comments)
                submit_keyboard = InlineKeyboardMarkup(
                    inline_keyboard=[[InlineKeyboardButton(
                        text="📤 Отправить заявку", callback_data="submit_application")]]
                )
                await callback.message.answer(COMMENT_REQUEST, reply_markup=submit_keyboard)
            else:
                await callback.answer("Вы уже прошли опрос и оставили заявку", show_alert=True)
        else:
            await callback.answer("Вы уже прошли опрос", show_alert=True)
        return

    await state.clear()
    await state.set_state(STATES_MAP[1])
    user_start_times[user_id] = datetime.now()
    await update_user_started_at(user_id)
    await schedule_reminders(user_id, callback.message)
    await state.set_data({'answers_history': '📋 Ваши ответы:\n\n', 'current_question': 1})
    history_msg = await callback.message.answer('📋 Ваши ответы:\n\n')
    await state.update_data(history_message_id=history_msg.message_id)

    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except:
        pass

    await send_question(callback.message, state, 1)
    await callback.answer()


async def send_question(message: Message, state: FSMContext, question_num: int):
    if question_num == 8:
        back_keyboard = kb.get_back_keyboard(8)
        question_msg = await message.answer(QUESTIONS[question_num]['text'], reply_markup=back_keyboard)
    else:
        question_msg = await message.answer(
            QUESTIONS[question_num]['text'],
            reply_markup=kb.get_question_keyboard(
                question_num, QUESTIONS[question_num]['options'])
        )
    await state.update_data(question_message_id=question_msg.message_id)


async def update_history(state: FSMContext, question_num: int, answer_text: str):
    data = await state.get_data()
    history = data.get('answers_history', '📋 Ваши ответы:\n\n')
    history_message_id = data.get('history_message_id')
    history += f"{question_num}. {QUESTIONS[question_num]['text']}\n   ✅ {answer_text}\n\n"
    await state.update_data(answers_history=history)
    return history, history_message_id


async def schedule_reminders(user_id: int, message: Message):
    if user_id in user_reminder_tasks:
        for task in user_reminder_tasks[user_id]:
            task.cancel()
        user_reminder_tasks[user_id] = []
    else:
        user_reminder_tasks[user_id] = []

    task_10min = asyncio.create_task(
        send_reminder(user_id, message, 10, REMINDER_10MIN))
    task_2h = asyncio.create_task(
        send_reminder(user_id, message, 120, REMINDER_2H))
    task_24h = asyncio.create_task(send_reminder(
        user_id, message, 1440, REMINDER_24H))

    user_reminder_tasks[user_id].extend([task_10min, task_2h, task_24h])


async def send_reminder(user_id: int, message: Message, minutes: int, reminder_text: str):
    try:
        await asyncio.sleep(minutes * 60)

        if await user_completed_survey(user_id):
            return

        user = await get_user_by_id(user_id)
        if user:
            if minutes == 10 and user.reminder_10min_sent:
                return
            elif minutes == 120 and user.reminder_2h_sent:
                return
            elif minutes == 1440 and user.reminder_24h_sent:
                return

        continue_keyboard = InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(
                text="➡️ Продолжить", callback_data=f"continue_{user_id}")]]
        )

        await message.answer(reminder_text, reply_markup=continue_keyboard)
        await mark_reminder_sent(user_id, minutes)

    except Exception as e:
        logging.error(
            f"Ошибка при отправке напоминания пользователю {user_id}: {e}")


@router.callback_query(F.data.startswith('continue_'))
async def continue_survey(callback: CallbackQuery, state: FSMContext):
    try:
        target_user_id = int(callback.data.split('_')[1])
        if callback.from_user.id != target_user_id:
            await callback.answer("Это напоминание не для вас", show_alert=True)
            return

        if await user_completed_survey(target_user_id):
            await callback.answer("Вы уже завершили опрос", show_alert=True)
            try:
                await callback.message.delete()
            except:
                pass
            return

        try:
            await callback.message.delete()
        except:
            pass

        data = await state.get_data()
        current_question = data.get('current_question', 1)

        if current_question > 1:
            history = data.get('answers_history', '📋 Ваши ответы:\n\n')
            history_message_id = data.get('history_message_id')
            if history_message_id:
                try:
                    await callback.bot.edit_message_text(
                        chat_id=callback.message.chat.id,
                        message_id=history_message_id,
                        text=history
                    )
                except:
                    history_msg = await callback.message.answer(history)
                    await state.update_data(history_message_id=history_msg.message_id)
            await send_question(callback.message, state, current_question)
        else:
            await start_form(callback, state)

        await callback.answer()
    except Exception as e:
        logging.error(f"Ошибка в continue_survey: {e}")
        await callback.answer("Произошла ошибка", show_alert=True)


@router.callback_query(F.data.startswith('answer_'))
async def form_answer(callback: CallbackQuery, state: FSMContext) -> None:
    user_id = callback.from_user.id
    if await user_completed_survey(user_id):
        await callback.answer("Вы уже прошли опрос", show_alert=True)
        return

    parts = callback.data.split('_', 2)
    question_num = int(parts[1])
    answer_idx = int(parts[2])

    current_data = await state.get_data()
    current_question = current_data.get('current_question', 1)
    if question_num != current_question:
        await callback.answer()
        return

    answer_text = QUESTIONS[question_num]['options'][answer_idx]
    history, history_message_id = await update_history(state, question_num, answer_text)

    if history_message_id:
        try:
            await callback.bot.edit_message_text(
                chat_id=callback.message.chat.id,
                message_id=history_message_id,
                text=history
            )
        except TelegramBadRequest as e:
            if "message is not modified" not in str(e):
                logging.error(f"Error editing history: {e}")

    await state.update_data({f'question_{question_num}': answer_text})

    question_message_id = current_data.get('question_message_id')
    if question_message_id:
        try:
            await callback.bot.delete_message(chat_id=callback.message.chat.id, message_id=question_message_id)
        except:
            pass

    await callback.answer()
    next_question_num = question_num + 1
    await state.update_data(current_question=next_question_num)

    if next_question_num in STATES_MAP:
        await state.set_state(STATES_MAP[next_question_num])
        await send_question(callback.message, state, next_question_num)
    else:
        data = await state.get_data()
        all_questions_answered = all(
            f'question_{i}' in data for i in range(1, 10))
        if not all_questions_answered:
            await callback.answer("Ответьте на все вопросы", show_alert=True)
            return

        qual = not (
            data.get('question_1') == 'до 14' or
            data.get('question_2') == 'школа' or
            data.get('question_4') == 'Рассчитываю только на грант' or
            data.get('question_6') == '2028 и позже' or
            data.get('question_9') == 'самостоятельно'
        )

        await save_survey(
            user_id=callback.from_user.id,
            ans_1=data.get('question_1'),
            ans_2=data.get('question_2'),
            ans_3=data.get('question_3'),
            ans_4=data.get('question_4'),
            ans_5=data.get('question_5'),
            ans_6=data.get('question_6'),
            ans_7=data.get('question_7'),
            ans_8=data.get('question_8'),
            ans_9=data.get('question_9'),
            qual=qual
        )

        question_message_id = data.get('question_message_id')
        if question_message_id:
            try:
                await callback.bot.delete_message(chat_id=callback.message.chat.id, message_id=question_message_id)
            except:
                pass

        if user_id in user_reminder_tasks:
            for task in user_reminder_tasks[user_id]:
                task.cancel()
            del user_reminder_tasks[user_id]

        await state.clear()
        logging.info(
            f'Анкета от пользователя {callback.from_user.id}: Квал - {qual}')

        if qual:
            await state.set_state(Form.waiting_for_contact)
            contact_keyboard = ReplyKeyboardMarkup(
                keyboard=[
                    [KeyboardButton(text="📱 Поделиться контактом", request_contact=True)]],
                resize_keyboard=True,
                one_time_keyboard=True
            )
            await callback.message.answer(CONTACT_REQUEST, reply_markup=contact_keyboard)
        else:
            await callback.message.answer(NON_QUEL_MSG)
            await asyncio.sleep(3)
            await callback.message.answer(FAQ, reply_markup=kb.get_FAQ_keyboard())


@router.callback_query(F.data.startswith('back_'))
async def process_back(callback: CallbackQuery, state: FSMContext) -> None:
    user_id = callback.from_user.id
    if await user_completed_survey(user_id):
        await callback.answer("Вы уже прошли опрос", show_alert=True)
        return

    current_data = await state.get_data()
    current_question = current_data.get('current_question', 1)
    back_from = int(callback.data.split('_')[1])

    if back_from != current_question:
        await callback.answer()
        return

    prev_question = current_question - 1
    if prev_question >= 1:
        await state.set_state(STATES_MAP[prev_question])

        if f'question_{current_question}' in current_data:
            del current_data[f'question_{current_question}']
            await state.set_data(current_data)

        history = current_data.get('answers_history', '📋 Ваши ответы:\n\n')
        lines = history.strip().split('\n')
        if len(lines) >= 3:
            lines = lines[:-2]
            history = '\n'.join(lines) + '\n\n'
            await state.update_data(answers_history=history)

        await state.update_data(current_question=prev_question)
        history_message_id = current_data.get('history_message_id')
        question_message_id = current_data.get('question_message_id')

        try:
            if history_message_id:
                await callback.bot.edit_message_text(
                    chat_id=callback.message.chat.id,
                    message_id=history_message_id,
                    text=history
                )

            if question_message_id:
                try:
                    await callback.bot.delete_message(chat_id=callback.message.chat.id, message_id=question_message_id)
                except:
                    pass

            await send_question(callback.message, state, prev_question)
        except TelegramBadRequest as e:
            if "message is not modified" not in str(e):
                logging.error(f"Error in process_back: {e}")

    await callback.answer()


@router.message(Form.question_8)
async def process_text_answer(message: Message, state: FSMContext) -> None:
    user_id = message.from_user.id
    if await user_completed_survey(user_id):
        await message.answer("Вы уже прошли опрос")
        return

    if message.content_type != 'text' or len(message.text) > 1500:
        await message.answer(ERROR_8)
        return

    current_data = await state.get_data()
    await state.update_data({'question_8': message.text})
    history, history_message_id = await update_history(state, 8, message.text)
    question_message_id = current_data.get('question_message_id')

    try:
        if history_message_id:
            await message.bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=history_message_id,
                text=history
            )

        if question_message_id:
            try:
                await message.bot.delete_message(chat_id=message.chat.id, message_id=question_message_id)
            except:
                pass

        try:
            await message.delete()
        except:
            pass
    except Exception as e:
        logging.error(f"Error editing message: {e}")

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

    submit_keyboard = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(
            text="📤 Отправить заявку", callback_data="submit_application")]]
    )
    await message.answer(COMMENT_REQUEST, reply_markup=submit_keyboard)


@router.message(Form.waiting_for_comments)
async def process_comments(message: Message, state: FSMContext) -> None:
    if message.content_type != 'text' or len(message.text) > 1500:
        await message.answer(FINAL)
        return

    await update_user_comments(message.from_user.id, message.text)
    await message.answer(SUCCESS_MESSAGE)
    await state.clear()

    # Отправляем анкету менеджеру
    await send_manager_new_lead(message.from_user.id)


@router.callback_query(F.data == "submit_application", Form.waiting_for_comments)
async def submit_application(callback: CallbackQuery, state: FSMContext) -> None:
    await update_user_comments(callback.from_user.id, "-")

    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except:
        pass

    await callback.message.answer(SUCCESS_MESSAGE)
    await state.clear()

    # Отправляем анкету менеджеру
    await send_manager_new_lead(callback.from_user.id)

    await callback.answer()
