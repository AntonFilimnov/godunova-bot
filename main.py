import os
import asyncio
import gspread
from datetime import datetime
import pytz
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
from aiogram import F

# Загрузка токена из файла .env
load_dotenv()
BOT_TOKEN = os.getenv('BOT_TOKEN')

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Настройка подключения к Google Sheets
# Укажите точное название вашей таблицы
SPREADSHEET_NAME = "База_Годунова_Бот" 
gc = gspread.service_account(filename='credentials.json')
sh = gc.open(SPREADSHEET_NAME)
worksheet = sh.sheet1

# Московское время
moscow_tz = pytz.timezone('Europe/Moscow')

def get_main_keyboard():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Запись на консультацию", callback_data="book_session")],
        [InlineKeyboardButton(text="Покупка абонемента", callback_data="buy_subscription")],
        [InlineKeyboardButton(text="Правила", callback_data="rules")]
    ])
    return keyboard

@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    intro_text = (
        "Здравствуйте! Я Анастасия Годунова, психолог. \n\n"
        "Здесь вы можете записаться ко мне на сессию, приобрести абонемент "
        "или ознакомиться с правилами моей работы. Выберите нужный пункт меню ниже:"
    )
    
    # Замените ссылку на реальную фотографию
    photo_file = FSInputFile("photo.jpg")
    
    await message.answer_photo(
        photo=photo_file,
        caption=intro_text,
        reply_markup=get_main_keyboard()
    )

# Обработка нажатий на кнопки
@dp.callback_query(F.data.in_({"book_session", "buy_subscription", "rules"}))
async def handle_button_click(callback: types.CallbackQuery):
    action_map = {
        "book_session": "Запись на консультацию",
        "buy_subscription": "Покупка абонемента",
        "rules": "Правила"
    }
    
    action = action_map[callback.data]
    current_time = datetime.now(moscow_tz).strftime("%Y-%m-%d %H:%M:%S")
    
    # Подготовка данных для записи
    row_data = [
        callback.from_user.id,
        callback.from_user.username or "Нет юзернейма",
        callback.from_user.full_name,
        action,
        current_time
    ]
    
    # Запись в Google Таблицу (в фоне, чтобы не тормозить бота)
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, worksheet.append_row, row_data)
    
    # Здесь позже добавим код для отправки конверсии в рекламный кабинет

    # Ответ пользователю
    await callback.message.answer(f"Вы выбрали: {action}. (Здесь будет следующий шаг)")
    await callback.answer() # Убираем часики на кнопке

async def main():
    print("Бот запущен...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())