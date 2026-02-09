from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def get_question_keyboard(question_num: int, options: list) -> InlineKeyboardMarkup:
    buttons = []
    for idx, option in enumerate(options):
        buttons.append([InlineKeyboardButton(
            text=option,
            callback_data=f'answer_{question_num}_{idx}'
        )])

    if question_num > 1:
        buttons.append([InlineKeyboardButton(
            text='Назад',
            callback_data=f'back_{question_num}'
        )])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_back_keyboard(question_num: int) -> InlineKeyboardMarkup:
    if question_num > 1:
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text='Назад',
                callback_data=f'back_{question_num}'
            )]
        ])
    return None


def get_start_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text='Оценить шансы на поступление', callback_data='start_form')],
        [InlineKeyboardButton(
            text='Получить бесплатную консультацию', callback_data='start_form')]
    ])


def get_FAQ_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text='Instagram*',
                              url='http://instagram.com/jetminds.company/')],
        [InlineKeyboardButton(text='Телеграм-канал',
                              url='http://t.me/jetmindscompany')]
    ])
