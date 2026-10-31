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
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile, BotCommand
from aiogram import F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.exceptions import TelegramBadRequest
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

class BookingState(StatesGroup):
    waiting_for_name = State()
    waiting_for_phone = State()
    waiting_for_email = State()

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
worksheet_users = sh.worksheet("Пользователи") # Лист для базы клиентов
worksheet_packages = sh.worksheet("Баланс_пакетов") # Лист для учета пакетов

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

# Функция поиска пользователя в таблице
def get_existing_user(user_id):
    try:
        # Получаем все строки из листа (в виде списков)
        records = worksheet_users.get_all_values()
        # Идем с конца, чтобы найти самую свежую запись (если их несколько)
        for row in reversed(records):
            if str(row[0]) == str(user_id):
                return {"name": row[2], "phone": row[3], "email": row[4]}
        return None
    except Exception as e:
        print(f"Ошибка при поиске пользователя: {e}")
        return None

# Главное меню (без "Мои записи" для MVP)
def get_main_keyboard():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🗓 Разовая сессия", callback_data="catalog_single")],
        [InlineKeyboardButton(text="📚 Пакет сессий", callback_data="catalog_package")],
        [InlineKeyboardButton(text="💬 Связаться со специалистом", callback_data="contact_specialist")],
        [InlineKeyboardButton(text="📖 Правила работы", callback_data="show_rules")]
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

# --- Вывод полных правил ---
FULL_RULES_TEXT = (
    "📖 **ПРАВИЛА ЗАПИСИ И ПЕРЕНОСА КОНСУЛЬТАЦИЙ**\n\n"
    "**1. Запись и бронирование**\n"
    "1.1. Бронирование даты и времени осуществляется по 100% предоплате.\n"
    "1.2. Запись считается подтверждённой после поступления полной оплаты.\n\n"
    "**2. Перенос консультации**\n"
    "2.1. Бесплатный перенос возможен не позднее чем за 24 часа до назначенного времени.\n"
    "2.2. При обращении менее чем за 24 часа перенос возможен только по индивидуальному согласованию.\n\n"
    "**3. Опоздание и неявка**\n"
    "3.1. При опоздании сессия не продлевается. Она заканчивается в установленное время.\n"
    "3.2. При неявке без предупреждения время не переносится.\n\n"
    "**4. Пакеты консультаций**\n"
    "4.1. Срок начала использования пакета — 3 месяца с даты оплаты.\n"
    "4.2. Правила переноса распространяются на все встречи из пакета.\n\n"
    "**5. Форс-мажоры**\n"
    "Исключительные обстоятельства рассматриваются индивидуально. Если перенос происходит по инициативе специалиста, он бесплатен."
)

@dp.message(F.text == "/rules")
async def cmd_rules(message: types.Message):
    await message.answer(FULL_RULES_TEXT, parse_mode="Markdown")

@dp.callback_query(F.data == "show_rules")
async def handle_show_rules(callback: types.CallbackQuery):
    await callback.message.answer(FULL_RULES_TEXT, parse_mode="Markdown")
    await callback.answer()

# Обработка нажатия "Разовая сессия"
@dp.callback_query(F.data == "catalog_single")
async def handle_single_session(callback: types.CallbackQuery, state: FSMContext):
    # Очищаем память, чтобы точно сбросить выбор пакета, если он был
    await state.clear()
    
    text = (
        "🗓 *Разовая сессия*\n\n"
        "Стоимость: 3 500 ₽\n"
        "Формат: 1 встреча (60 минут)\n\n"
        "Выберите удобный день для записи:"
    )
    
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer(text, reply_markup=get_quick_dates_keyboard(), parse_mode="Markdown")
    await callback.answer()

# --- Обработка нажатия "Пакет сессий" ---
@dp.callback_query(F.data == "catalog_package")
async def handle_package_session(callback: types.CallbackQuery):
    text = (
        "📚 *Пакет сессий*\n\n"
        "Покупка пакета — это возможность пройти полноценный курс работы со специалистом по выгодной цене.\n\n"
        "❗️ **Условия пакета:**\n"
        "• Пакет действителен 3 месяца с момента оплаты.\n"
        "• При покупке пакета запись на первую сессию обязательна.\n"
        "Остальные встречи согласовываются по мере работы.\n\n"
        "Выберите подходящий тариф:"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="3 сессии (9 900 ₽)", callback_data="buy_package_3")],
        [InlineKeyboardButton(text="5 сессий (15 750 ₽)", callback_data="buy_package_5")],
        [InlineKeyboardButton(text="10 сессий (28 000 ₽)", callback_data="buy_package_10")],
        [InlineKeyboardButton(text="🔙 Назад в меню", callback_data="back_to_main")]
    ])
    
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer(text, reply_markup=keyboard, parse_mode="Markdown")
    await callback.answer()

# --- Обработка выбора конкретного пакета ---
@dp.callback_query(F.data.startswith("buy_package_"))
async def process_package_selection(callback: types.CallbackQuery, state: FSMContext):
    package_size = int(callback.data.split("_")[2])
    
    # Сохраняем размер выбранного пакета в FSM
    await state.update_data(package=package_size)
    
    await callback.message.edit_reply_markup(reply_markup=None)
    text = (
        f"✅ Вы выбрали пакет из {package_size} сессий.\n\n"
        f"Давайте выберем день для вашей **первой** встречи:"
    )
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

# Общая функция финализации брони (чтобы не дублировать код)
# Общая функция финализации брони 
async def finalize_booking(message: types.Message, state: FSMContext, tg_user, save_to_sheet=True):
    user_data = await state.get_data()
    date_str = user_data['date']
    time_str = user_data['time']
    full_name = user_data['name']
    phone = user_data['phone']
    email = user_data['email']
    # Достаем размер пакета, если его нет (разовая) - возвращаем None
    package_size = user_data.get('package', None) 
    
    await state.clear()
    loading_msg = await message.answer("⏳ Создаю бронь в календаре...")

    loop = asyncio.get_running_loop()
    current_time = datetime.now(moscow_tz).strftime("%Y-%m-%d %H:%M:%S")

    # 1. Запись контактов в БД
    if save_to_sheet:
        user_row = [tg_user.id, f"@{tg_user.username}" if tg_user.username else "Нет", full_name, phone, email, current_time]
        try:
            await loop.run_in_executor(None, worksheet_users.append_row, user_row)
        except Exception as e:
            print(f"Ошибка записи пользователя: {e}")
            
    # 2. Если это пакет, записываем баланс в новую таблицу
    if package_size:
        package_row = [tg_user.id, f"@{tg_user.username}" if tg_user.username else "Нет", package_size, package_size]
        try:
            await loop.run_in_executor(None, worksheet_packages.append_row, package_row)
        except Exception as e:
            print(f"Ошибка записи баланса: {e}")

    # 3. Создание брони в Google Календаре
    start_time = moscow_tz.localize(datetime.strptime(f"{date_str} {time_str}:00", "%Y-%m-%d %H:%M:%S"))
    end_time = start_time + timedelta(minutes=15)
    
    # Меняем заголовок брони, если это пакет
    booking_title = f'ОЖИДАЕТ ОПЛАТЫ (Пакет {package_size}) - {full_name}' if package_size else f'ОЖИДАЕТ ОПЛАТЫ - {full_name}'
    
    event = {
        'summary': booking_title,
        'description': f'Telegram: @{tg_user.username or "Нет"}\nТелефон: {phone}\nEmail: {email}',
        'start': {'dateTime': start_time.isoformat(), 'timeZone': 'Europe/Moscow'},
        'end': {'dateTime': end_time.isoformat(), 'timeZone': 'Europe/Moscow'},
        'colorId': '4' 
    }

    try:
        created_event = await loop.run_in_executor(None, lambda: calendar_service.events().insert(calendarId=CALENDAR_ID, body=event).execute())
        event_id = created_event['id']
    except Exception as e:
        await loading_msg.delete()
        await message.answer("Произошла ошибка при бронировании. Попробуйте позже.")
        return
        
    await loading_msg.delete()
    
    # 4. Выбор суммы для кнопки оплаты
    prices = {None: "3 500 ₽", 3: "9 900 ₽", 5: "15 750 ₽", 10: "28 000 ₽"}
    payment_amount = prices.get(package_size)
    
    rules_text=(
        f"✅ **Ваша запись предварительно забронирована!**\n\n"
        f"**Дата:** {date_str}\n**Время:** {time_str} (МСК)\n\n"
        f"❗️ **Краткие условия:**\n"
        f"• Подтверждение брони после 100% предоплаты.\n"
        f"• Бесплатный перенос возможен строго за 24 часа.\n"
        f"• При опоздании время сессии не продлевается.\n\n"
        f"Полные условия доступны по команде /rules или в главном меню.\n"
        f"Нажимая «Оплатить», вы принимаете правила работы."
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"💳 Оплатить {payment_amount}", url="https://robokassa.com/")], 
        [InlineKeyboardButton(text="❌ Отменить бронь", callback_data=f"cancel_{event_id}")]
    ])
    
    await message.answer(rules_text, reply_markup=keyboard, parse_mode="Markdown")

# --- 1. Обработчик выбора времени (Поиск клиента) ---
@dp.callback_query(F.data.startswith("time_"))
async def process_time_selection(callback: types.CallbackQuery, state: FSMContext):
    _, date_str, time_str = callback.data.split("_")
    await callback.message.edit_reply_markup(reply_markup=None)
    
    # Сохраняем выбранную дату и время
    await state.update_data(date=date_str, time=time_str)
    
    loading_msg = await callback.message.answer("⏳ Проверяю ваши данные...")
    
    # Ищем пользователя в базе
    loop = asyncio.get_running_loop()
    existing_user = await loop.run_in_executor(None, get_existing_user, callback.from_user.id)
    await loading_msg.delete()
    
    if existing_user:
        # Если нашли, сохраняем эти данные в стейт на случай подтверждения
        await state.update_data(name=existing_user['name'], phone=existing_user['phone'], email=existing_user['email'])
        
        text = (
            f"✅ Вы выбрали: {date_str} в {time_str} (МСК).\n\n"
            f"У меня сохранены ваши контактные данные:\n"
            f"👤 Имя: {existing_user['name']}\n"
            f"📞 Телефон: {existing_user['phone']}\n"
            f"✉️ Email: {existing_user['email']}\n\n"
            f"Используем их для оформления брони?"
        )
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Да, всё верно", callback_data="confirm_data")],
            [InlineKeyboardButton(text="✏️ Изменить данные", callback_data="edit_data")]
        ])
        await callback.message.answer(text, reply_markup=keyboard)
    else:
        # Если новый клиент — стандартный опрос
        await state.set_state(BookingState.waiting_for_name)
        await callback.message.answer(
            f"✅ Вы выбрали: {date_str} в {time_str} (МСК).\n\n"
            f"Для завершения бронирования, пожалуйста, напишите ваше **Имя и Фамилию**:",
            parse_mode="Markdown"
        )
    await callback.answer()

# --- 1.1 Обработка кнопок "Да, всё верно" и "Изменить данные" ---
@dp.callback_query(F.data == "confirm_data")
async def process_confirm_data(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_reply_markup(reply_markup=None)
    # Вызываем общую функцию (save_to_sheet=False, так как данные уже есть в базе)
    await finalize_booking(callback.message, state, callback.from_user, save_to_sheet=False)
    await callback.answer()

@dp.callback_query(F.data == "edit_data")
async def process_edit_data(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_reply_markup(reply_markup=None)
    await state.set_state(BookingState.waiting_for_name)
    await callback.message.answer("Давайте обновим информацию. Напишите ваше **Имя и Фамилию**:")
    await callback.answer()

# --- 2. Обработчик ввода имени ---
@dp.message(BookingState.waiting_for_name)
async def process_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    await state.set_state(BookingState.waiting_for_phone)
    await message.answer("Отлично! Теперь введите ваш **номер телефона**:")

# --- 3. Обработчик ввода телефона ---
@dp.message(BookingState.waiting_for_phone)
async def process_phone(message: types.Message, state: FSMContext):
    await state.update_data(phone=message.text)
    await state.set_state(BookingState.waiting_for_email)
    await message.answer("И последний шаг: напишите вашу **электронную почту** (на нее придет чек и ссылка):")

# --- 4. Обработчик ввода Email и финал ---
@dp.message(BookingState.waiting_for_email)
async def process_email(message: types.Message, state: FSMContext):
    await state.update_data(email=message.text)
    # Вызываем общую функцию (save_to_sheet=True, чтобы записать новые данные)
    await finalize_booking(message, state, message.from_user, save_to_sheet=True)

# Обработка отмены брони клиентом
@dp.callback_query(F.data.startswith("cancel_"))
async def cancel_booking(callback: types.CallbackQuery):
    event_id = callback.data.split("_")[1]
    
    await callback.message.edit_reply_markup(reply_markup=None)
    
    loop = asyncio.get_running_loop()
    try:
         await loop.run_in_executor(
             None, 
             lambda: calendar_service.events().delete(calendarId=CALENDAR_ID, eventId=event_id).execute()
         )
    except:
         pass 
         
    await callback.message.answer("❌ Ваша бронь успешно отменена. Слот снова свободен.")
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

async def set_default_commands(bot: Bot):
    commands = [
        BotCommand(command="start", description="Открыть главное меню")
    ]
    await bot.set_my_commands(commands)

async def main():
    print("Бот запущен...")
    await set_default_commands(bot)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())