import os
import asyncio
import gspread
from datetime import datetime
import pytz
from datetime import timedelta
import calendar
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
from aiogram import F
from aiogram.exceptions import TelegramBadRequest
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

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

# --- Настройки Google Календаря ---
CALENDAR_ID = 'godunova.tbilisi@gmail.com'
CALENDAR_SCOPES = ['https://www.googleapis.com/auth/calendar']
# Используем тот же credentials.json
cal_creds = Credentials.from_service_account_file('credentials.json', scopes=CALENDAR_SCOPES)
calendar_service = build('calendar', 'v3', credentials=cal_creds)

AVAILABLE_SLOTS = ["12:00", "13:00", "15:00", "16:00"]

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

# Клавиатура с ближайшими 4 рабочими днями и кнопкой полного календаря
def get_quick_dates_keyboard():
    keyboard = []
    days_added = 0
    current_date = datetime.now(moscow_tz)
    
    row = []
    # Ищем ближайшие 4 рабочих дня (исключая СБ и ВС)
    while days_added < 4:
        current_date += timedelta(days=1)
        if current_date.weekday() < 5:  # 0-4 это ПН-ПТ
            # Формируем красивый текст кнопки, например: "ВТ, 27 Окт"
            btn_text = f"{RU_WEEKDAYS[current_date.weekday()]}, {current_date.day} {RU_MONTHS[current_date.month]}"
            # В callback_data зашиваем саму дату (например, qdate_2023-10-27)
            btn_cb = f"qdate_{current_date.strftime('%Y-%m-%d')}"
            row.append(InlineKeyboardButton(text=btn_text, callback_data=btn_cb))
            days_added += 1
            
            # Ставим по 2 кнопки в один ряд
            if len(row) == 2:
                keyboard.append(row)
                row = []
                
    # Добавляем кнопки календаря и возврата в меню
    keyboard.append([InlineKeyboardButton(text="📅 Открыть весь календарь", callback_data="open_full_calendar")])
    keyboard.append([InlineKeyboardButton(text="🔙 Назад в меню", callback_data="back_to_main")])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


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
# Обработка нажатия "Разовая сессия"
# Обработка нажатия "Разовая сессия"
@dp.callback_query(F.data == "catalog_single")
async def handle_single_session(callback: types.CallbackQuery):
    text = (
        "🗓 *Разовая сессия*\n\n"
        "Стоимость: 3 500 ₽\n"
        "Формат: 1 встреча (60 минут)\n\n"
        "Выберите удобный день для записи:"
    )
    
    # Убираем кнопки у предыдущего сообщения (чтобы не засорять чат активными кнопками)
    await callback.message.edit_reply_markup(reply_markup=None)
    # Отправляем новое сообщение в ленту
    await callback.message.answer(text, reply_markup=get_quick_dates_keyboard(), parse_mode="Markdown")
    await callback.answer()


# Обработка кнопки "Назад в меню"
@dp.callback_query(F.data == "back_to_main")
async def handle_back_to_main(callback: types.CallbackQuery):
    # Прячем кнопки
    await callback.message.edit_reply_markup(reply_markup=None)
    # Присылаем стартовое сообщение заново
    await cmd_start(callback.message)
    await callback.answer()


# Создание нашего собственного календаря
def get_custom_calendar(year: int, month: int):
    keyboard = []
    
    # 1. Шапка: Месяц и Год + кнопки перелистывания
    month_name = RU_MONTHS[month]
    keyboard.append([
        InlineKeyboardButton(text="◀️", callback_data=f"nav_prev_{year}_{month}"),
        InlineKeyboardButton(text=f"{month_name} {year}", callback_data="ignore"),
        InlineKeyboardButton(text="▶️", callback_data=f"nav_next_{year}_{month}")
    ])
    
    # 2. Дни недели (Пн, Вт, Ср...)
    weekdays_row = [InlineKeyboardButton(text=day, callback_data="ignore") for day in ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]]
    keyboard.append(weekdays_row)
    
    # 3. Сетка дней
    month_calendar = calendar.monthcalendar(year, month)
    for week in month_calendar:
        row = []
        # enumerate(week) дает нам и порядковый номер дня недели (0-6), и само число
        for weekday_idx, day in enumerate(week):
            if day == 0:
                row.append(InlineKeyboardButton(text=" ", callback_data="ignore"))
            elif weekday_idx in (5, 6): # 5 - СБ, 6 - ВС
                # Выходным дням вешаем специальный ярлык "weekend"
                row.append(InlineKeyboardButton(text=str(day), callback_data="weekend"))
            else:
                # Рабочим дням (0-4) оставляем обычный выбор даты
                date_str = f"{year}-{month:02d}-{day:02d}"
                row.append(InlineKeyboardButton(text=str(day), callback_data=f"caldate_{date_str}"))
        keyboard.append(row)
        
    # 4. Кнопка Назад
    keyboard.append([InlineKeyboardButton(text="🔙 Отмена", callback_data="catalog_single")])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


# Открытие нашего календаря
@dp.callback_query(F.data == "open_full_calendar")
async def process_custom_calendar(callback: types.CallbackQuery):
    now = datetime.now(moscow_tz)
    markup = get_custom_calendar(now.year, now.month)
    
    # Убираем быстрые кнопки дат у старого сообщения
    await callback.message.edit_reply_markup(reply_markup=None)
    # Присылаем календарь новым сообщением
    await callback.message.answer("📅 Выберите дату в календаре:", reply_markup=markup)
    await callback.answer()

# Функция проверки свободных слотов в Google Календаре
def get_free_slots(date_str):
    # Границы дня (00:00 - 23:59) по МСК
    start_of_day = moscow_tz.localize(datetime.strptime(f"{date_str} 00:00:00", "%Y-%m-%d %H:%M:%S"))
    end_of_day = moscow_tz.localize(datetime.strptime(f"{date_str} 23:59:59", "%Y-%m-%d %H:%M:%S"))

    events_result = calendar_service.events().list(
        calendarId=CALENDAR_ID,
        timeMin=start_of_day.isoformat(),
        timeMax=end_of_day.isoformat(),
        singleEvents=True,
        orderBy='startTime'
    ).execute()

    events = events_result.get('items', [])
    free_slots = AVAILABLE_SLOTS.copy()

    for event in events:
        start = event['start'].get('dateTime', event['start'].get('date'))
        end = event['end'].get('dateTime', event['end'].get('date'))
        
        # Если событие на весь день
        if 'T' not in start:
            if event.get('transparency') != 'transparent':
                return [] # День полностью занят, возвращаем пустоту
            continue
            
        # Учитываем букву Z (UTC) для совместимости
        event_start = datetime.fromisoformat(start.replace('Z', '+00:00')).astimezone(moscow_tz)
        event_end = datetime.fromisoformat(end.replace('Z', '+00:00')).astimezone(moscow_tz)

        # Проверяем пересечение с нашими слотами (1 час на сессию)
        for slot in free_slots[:]:
            slot_time = moscow_tz.localize(datetime.strptime(f"{date_str} {slot}:00", "%Y-%m-%d %H:%M:%S"))
            slot_end = slot_time + timedelta(minutes=60)
            
            if event_start < slot_end and event_end > slot_time:
                free_slots.remove(slot)

    return free_slots


# Клавиатура со свободными слотами
def get_time_slots_keyboard(date_str, free_slots):
    keyboard = []
    row = []
    for slot in free_slots:
        # Кнопка будет передавать, например: time_2026-10-27_15:00
        row.append(InlineKeyboardButton(text=f"🕒 {slot}", callback_data=f"time_{date_str}_{slot}"))
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
        
    keyboard.append([InlineKeyboardButton(text="🔙 Назад к выбору дня", callback_data="catalog_single")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

# Обработка пустых кнопок в календаре (названия дней недели, пустые клетки)
@dp.callback_query(F.data == "ignore")
async def process_ignore(callback: types.CallbackQuery):
    await callback.answer()

# Обработка нажатия на выходные дни в календаре
@dp.callback_query(F.data == "weekend")
async def process_weekend(callback: types.CallbackQuery):
    # show_alert=True покажет всплывающее окошко с текстом прямо по центру экрана
    await callback.answer("Анастасия не проводит консультации в выходные дни 🛋\nПожалуйста, выберите будний день.", show_alert=True)


# Перелистывание месяцев
# Перелистывание месяцев
@dp.callback_query(F.data.startswith("nav_"))
async def process_calendar_navigation(callback: types.CallbackQuery):
    # Правильно разбиваем: 'nav', 'next' (или 'prev'), '2026', '10'
    prefix, action, year_str, month_str = callback.data.split("_")
    year, month = int(year_str), int(month_str)
    
    if action == "next":
        month += 1
        if month > 12:
            month = 1
            year += 1
    elif action == "prev":
        month -= 1
        if month < 1:
            month = 12
            year -= 1
            
    markup = get_custom_calendar(year, month)
    
    try:
        await callback.message.edit_reply_markup(reply_markup=markup)
    except TelegramBadRequest:
        pass
        
    await callback.answer()

# Выбор даты в календаре (и для быстрых кнопок, и для сетки)
@dp.callback_query(F.data.startswith("caldate_") | F.data.startswith("qdate_"))
async def process_date_selection(callback: types.CallbackQuery):
    selected_date_str = callback.data.split("_")[1]
    
    # Прячем календарь
    await callback.message.edit_reply_markup(reply_markup=None)
    
    # Показываем сообщение о загрузке (пока Google думает)
    loading_msg = await callback.message.answer(f"⏳ Проверяю расписание на {selected_date_str}...")
    
    # Запускаем проверку в Google Календаре
    loop = asyncio.get_running_loop()
    free_slots = await loop.run_in_executor(None, get_free_slots, selected_date_str)
    
    # Удаляем сообщение с часиками
    await loading_msg.delete()
    
    # Если все слоты заняты
    if not free_slots:
        await callback.message.answer(
            f"К сожалению, на {selected_date_str} всё время занято 😔\nПожалуйста, выберите другой день.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="🔙 Выбрать другой день", callback_data="catalog_single")
            ]])
        )
    else:
        # Выдаем кнопки со свободным временем
        await callback.message.answer(
            f"✅ Выбрана дата: {selected_date_str}\n\nВыберите свободное время (МСК):",
            reply_markup=get_time_slots_keyboard(selected_date_str, free_slots)
        )
    await callback.answer()

# Обработка выбора времени (создание брони и выдача правил)
@dp.callback_query(F.data.startswith("time_"))
async def process_time_selection(callback: types.CallbackQuery):
    # Разбираем дату и время из callback, например time_2026-10-27_15:00
    _, date_str, time_str = callback.data.split("_")
    
    # Прячем кнопки времени у старого сообщения
    await callback.message.edit_reply_markup(reply_markup=None)
    
    # Показываем сообщение о загрузке
    loading_msg = await callback.message.answer("⏳ Создаю предварительную бронь...")

    # --- Создание временного события в Google Календаре ---
    # Высчитываем начало и конец (15 минут на оплату)
    start_time = moscow_tz.localize(datetime.strptime(f"{date_str} {time_str}:00", "%Y-%m-%d %H:%M:%S"))
    end_time = start_time + timedelta(minutes=15)
    
    event = {
        'summary': f'ОЖИДАЕТ ОПЛАТЫ - {callback.from_user.full_name}',
        'description': f'Telegram: @{callback.from_user.username or "Нет юзернейма"}',
        'start': {
            'dateTime': start_time.isoformat(),
            'timeZone': 'Europe/Moscow',
        },
        'end': {
            'dateTime': end_time.isoformat(),
            'timeZone': 'Europe/Moscow',
        },
        'colorId': '4' # Красный цвет события для наглядности
    }

    loop = asyncio.get_running_loop()
    try:
        # Отправляем запрос на создание события
        created_event = await loop.run_in_executor(
            None, 
            lambda: calendar_service.events().insert(calendarId=CALENDAR_ID, body=event).execute()
        )
        # Получаем уникальный ID этого события
        event_id = created_event['id']
    except Exception as e:
        await loading_msg.delete()
        await callback.message.answer("Произошла ошибка при бронировании в календаре. Попробуйте снова позже.")
        await callback.answer()
        return
        
    await loading_msg.delete()
    
    # --- Текст с правилами и кнопка оплаты ---
    # Я вставил стандартный текст правил. Если у заказчика есть точный текст, просто замените его здесь.
    rules_text = (
        f"✅ **Ваша запись предварительно забронирована!**\n\n"
        f"**Дата:** {date_str}\n"
        f"**Время:** {time_str} (МСК)\n\n"
        f"❗️ **Правила переноса и отмены:**\n"
        f"1. Перенос или отмена консультации возможны не позднее, чем за 24 часа до назначенного времени.\n"
        f"2. При отмене менее чем за 24 часа оплата не возвращается.\n"
        f"3. Опоздание на сессию вычитается из времени консультации.\n\n"
        f"Нажимая кнопку «Оплатить», вы соглашаетесь с этими правилами. У вас есть 15 минут на завершение оплаты."
    )
    
    # Кнопки Оплаты и Отмены. В кнопку отмены вшиваем event_id, чтобы потом удалить его из календаря
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        # Ссылку на Prodamus пока ставим как заглушку
        [InlineKeyboardButton(text="💳 Оплатить 3 500 ₽", url="https://prodamus.ru/")], 
        [InlineKeyboardButton(text="❌ Отменить бронь", callback_data=f"cancel_{event_id}")]
    ])
    
    await callback.message.answer(rules_text, reply_markup=keyboard, parse_mode="Markdown")
    await callback.answer()


# Обработка отмены брони клиентом
@dp.callback_query(F.data.startswith("cancel_"))
async def cancel_booking(callback: types.CallbackQuery):
    # Достаем ID события в календаре
    event_id = callback.data.split("_")[1]
    
    await callback.message.edit_reply_markup(reply_markup=None)
    
    # Удаляем событие из календаря Анастасии
    loop = asyncio.get_running_loop()
    try:
         await loop.run_in_executor(
             None, 
             lambda: calendar_service.events().delete(calendarId=CALENDAR_ID, eventId=event_id).execute()
         )
    except:
         pass # Игнорируем ошибку, если событие уже как-то удалилось
         
    await callback.message.answer("❌ Ваша бронь успешно отменена. Слот снова свободен.")
    # Возвращаем главное меню
    await cmd_start(callback.message)
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