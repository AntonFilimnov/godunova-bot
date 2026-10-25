import os
import asyncio
import gspread
from datetime import datetime
import pytz
from datetime import timedelta
from aiogram_calendar import SimpleCalendar, SimpleCalendarCallback
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
RU_WEEKDAYS = {0: "ПН", 1: "ВТ", 2: "СР", 3: "ЧТ", 4: "ПТ", 5: "СБ", 6: "ВС"}
RU_MONTHS = {1: "Янв", 2: "Фев", 3: "Мар", 4: "Апр", 5: "Май", 6: "Июн", 7: "Июл", 8: "Авг", 9: "Сен", 10: "Окт", 11: "Ноя", 12: "Дек"}

# Главное меню (без "Мои записи" для MVP)
def get_main_keyboard():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🗓 Разовая сессия", callback_data="catalog_single")],
        [InlineKeyboardButton(text="📚 Пакет сессий", callback_data="catalog_package")],
        [InlineKeyboardButton(text="💬 Связаться со специалистом", callback_data="contact_specialist")]
    ])
    return keyboard

@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    intro_text = (
       "Рада приветствовать!\n\n"
        "Меня зовут Настя Годунова. Я клинический психолог, бизнес-психолог и коуч.\n\n"
        "Образование: MBA (HISTES), аккредитация европейского психолога, клиническая психология, КПТ и коучинг.\n\n"
        "Работаю с тревогой, депрессией, БАР, эмоциональными трудностями, самооценкой и отношениями. При необходимости сопровождаю клиентов совместно с врачом-психиатром.\n\n"
        "Также работаю с запросами на профессиональную реализацию, эмоциональную устойчивость, финансовый рост и преодоление выгорания.\n\n"
        "Стоимость консультаций (60 минут):\n"
        "• 1 сессия — 3 500 ₽\n"
        "• 3 сессии — 9 900 ₽\n"
        "• 5 сессий — 15 750 ₽\n"
        "• 10 сессий — 28 000 ₽\n\n"
        "💻 Формат: онлайн — Google Meet, Яндекс Телемост или VK Видео.\n\n"
        "При покупке пакета можно сразу выбрать даты всех встреч или записаться только на первую сессию, а остальные согласовывать по мере работы.\n\n"
        "Если у вас есть вопросы или вы хотите обсудить свой запрос, напишите мне лично."
    
    )
    
    # Замените ссылку на реальную фотографию
    photo_file = FSInputFile("photo.jpg")
    
    await message.answer_photo(
        photo=photo_file,
        caption=intro_text,
        reply_markup=get_main_keyboard()
    )

# Обработка нажатий на кнопки
# Обработка нажатий на "Разовая сессия" и "Пакет сессий"
@dp.callback_query(F.data.in_({"catalog_single", "catalog_package"}))
async def handle_catalog_navigation(callback: types.CallbackQuery):
    # Определяем, что именно нажал пользователь для записи в базу
    action = "Разовая сессия" if callback.data == "catalog_single" else "Пакет сессий"
    current_time = datetime.now(moscow_tz).strftime("%Y-%m-%d %H:%M:%S")
    
    # Записываем действие в Google Таблицу
    row_data = [
        callback.from_user.id,
        callback.from_user.username or "Нет юзернейма",
        callback.from_user.full_name,
        action,
        current_time
    ]
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, worksheet.append_row, row_data)

    # Пока выводим меню тарифов (по второму скриншоту)
    await callback.message.edit_reply_markup(reply_markup=get_catalog_keyboard())
    await callback.answer()


# Обработка кнопки "Связаться со специалистом"
@dp.callback_query(F.data == "contact_specialist")
async def handle_contact(callback: types.CallbackQuery):
    current_time = datetime.now(moscow_tz).strftime("%Y-%m-%d %H:%M:%S")
    
    # Записываем действие в Google Таблицу
    row_data = [
        callback.from_user.id,
        callback.from_user.username or "Нет юзернейма",
        callback.from_user.full_name,
        "Связь со специалистом",
        current_time
    ]
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, worksheet.append_row, row_data)

    # Заглушка, которую мы потом заменим на реальный контакт
    await callback.message.answer("Для связи со специалистом напишите: @username_psihologa")
    await callback.answer()

async def main():
    print("Бот запущен...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())