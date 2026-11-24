import os
import json
from vkbottle import Bot, BaseStateGroup, Keyboard, KeyboardButtonColor, Text, Location, Callback
from vkbottle.bot import Message, MessageEvent
import database as db

TOKEN = os.getenv("BOT_TOKEN")
ADMIN_SCREEN_NAME = "v_klim"
ADMIN_ID = None

bot = Bot(token=TOKEN)

def format_people_dative(n: int) -> str:
    if 11 <= (n % 100) <= 19:
        return f"{n} людям"
    last = n % 10
    if last == 1:
        return f"{n} человеку"
    return f"{n} людям"

class Form(BaseStateGroup):
    NAME = "name"
    AGE = "age"
    GENDER = "gender"
    TARGET_GENDER = "target_gender"
    LOCATION = "location"
    BIO = "bio"
    MEDIA = "media"

class UpdateGeo(BaseStateGroup):
    WAITING_GEO = "waiting_geo"

class UpdateBio(BaseStateGroup):
    WAITING_BIO = "waiting_bio"

DISTRICTS = [
    "Центральный округ",
    "Дзёмги (Ленинский)",
    "Привокзальный район",
    "66-й квартал / Мылки",
    "Таёжный / Дружба",
    "Менделеева / Амурлитмаш",
    "Парус / Силинский",
    "Хапсоль / Индустриальный"
]

def get_main_menu_kb():
    kb = Keyboard(one_time=False, inline=False)
    kb.add(Text("🔥 Смотреть анкеты"), color=KeyboardButtonColor.PRIMARY)
    kb.add(Text("👤 Моя анкета"), color=KeyboardButtonColor.SECONDARY)
    return kb.get_json()

def get_gender_kb():
    kb = Keyboard(one_time=True)
    kb.add(Text("🙋‍♂️ Парень"), color=KeyboardButtonColor.PRIMARY)
    kb.add(Text("🙋‍♀️ Девушка"), color=KeyboardButtonColor.PRIMARY)
    return kb.get_json()

def get_target_kb():
    kb = Keyboard(one_time=True)
    kb.add(Text("💃 Девушек"), color=KeyboardButtonColor.PRIMARY)
    kb.add(Text("🕺 Парней"), color=KeyboardButtonColor.PRIMARY)
    return kb.get_json()

def get_geo_kb():
    kb = Keyboard(one_time=True)
    kb.add(Location())
    kb.row()
    kb.add(Text("🕶 Инкогнито (Комса)"), color=KeyboardButtonColor.SECONDARY)
    for idx, d in enumerate(DISTRICTS):
        if idx % 2 == 0:
            kb.row()
        kb.add(Text(d))
    return kb.get_json()

def get_quick_kb(old_val, allow_skip=False):
    if not old_val and not allow_skip:
        return Keyboard().get_json()
    kb = Keyboard(one_time=True)
    if old_val:
        kb.add(Text(str(old_val)[:40]), color=KeyboardButtonColor.PRIMARY)
    if allow_skip:
        if old_val:
            kb.row()
        kb.add(Text("⏭ Пропустить"), color=KeyboardButtonColor.SECONDARY)
    return kb.get_json()

def get_media_done_kb():
    kb = Keyboard(one_time=True)
    kb.add(Text("✅ Готово, опубликовать"), color=KeyboardButtonColor.POSITIVE)
    return kb.get_json()

def get_cancel_kb():
    kb = Keyboard(one_time=True)
    kb.add(Text("❌ Отмена"), color=KeyboardButtonColor.NEGATIVE)
    return kb.get_json()

def format_card(user: dict, is_own=False, prefix="") -> str:
    header = "✨ Твоя визитка в КомсаМэтч\n\n" if is_own else prefix
    place = user.get("location_text") or "г. Комсомольск-на-Амуре"
    dist = f"📍 {user['distance_str']}" if user.get("distance_str") else f"📍 {place}"
    bio = f"\n\n💬 {user['bio']}" if user.get("bio") and user["bio"].strip() else ""
    return f"{header}👤 {user['name']}, {user['age']}\n{dist}{bio}"

async def send_profile(peer_id: int, user: dict, inline_kb=None, is_own=False, prefix=""):
    text = format_card(user, is_own=is_own, prefix=prefix)
    atts = ",".join(user.get("attachments_list", []))
    await bot.api.messages.send(
        peer_id=peer_id,
        message=text,
        attachment=atts if atts else None,
        keyboard=inline_kb,
        random_id=0
    )
async def start_reg(message: Message, old_user: dict = None):
    ctx = {"old_user": old_user or {}, "attachments": []}
    await bot.state_dispenser.set(message.peer_id, Form.NAME, **ctx)
    await message.answer(
        "✏️ Шаг 1/7. Как тебя зовут?",
        keyboard=get_quick_kb((old_user or {}).get("name"))
    )

@bot.on.message(text=["Начать", "начать", "/start", "Старт", "старт"])
async def cmd_start(message: Message):
    await bot.state_dispenser.delete(message.peer_id)
    user = await db.get_user(message.from_id)
    if user:
        if user.get("is_banned"):
            await message.answer("🚫 Твоя анкета заблокирована за нарушение правил.")
            return
        if not user.get("is_active", 1):
            kb = Keyboard(inline=True)
            kb.add(Callback("🔥 Вернуть анкету в поиск", payload={"cmd": "wake_up"}), color=KeyboardButtonColor.POSITIVE)
            await message.answer(
                f"💫 Мы тебя помним, {user['name']}!\nТвоя анкета сейчас спит и скрыта от других. Хочешь снова пообщаться с кем-то новым в Комсе?",
                keyboard=kb.get_json()
            )
            return
        await message.answer(
            f"👋 С возвращением, {user['name']}! Твой профиль активен.\nВыбирай действие в меню ниже 👇",
            keyboard=get_main_menu_kb()
        )
    else:
        await message.answer("🌊 Добро пожаловать в КомсаМэтч!\nЗдесь знакомятся и находят компанию в Комсомольске-на-Амуре. Соберём анкету за 1 минуту!")
        await start_reg(message)

@bot.on.message(state=Form.NAME)
async def step_name(message: Message):
    if not message.text:
        await message.answer("Напиши своё имя текстом:")
        return
    state = await bot.state_dispenser.get(message.peer_id)
    payload = state.payload
    payload["name"] = message.text.strip()[:30]
    await bot.state_dispenser.set(message.peer_id, Form.AGE, **payload)
    await message.answer("🎂 Шаг 2/7. Сколько тебе лет?", keyboard=get_quick_kb(payload.get("old_user", {}).get("age")))

@bot.on.message(state=Form.AGE)
async def step_age(message: Message):
    if not message.text or not message.text.strip().isdigit():
        await message.answer("⚠️ Введи свой возраст цифрами:")
        return
    age = int(message.text.strip())
    if age < 14:
        await message.answer("🛡 К сожалению, нашим ботом можно пользоваться с 14 лет в связи с заботой о вас и вашей безопасности.")
        return
    if age > 67:
        await message.answer("⚠️ Просим указать ваш настоящий возраст (от 14 до 67 лет):")
        return
    state = await bot.state_dispenser.get(message.peer_id)
    payload = state.payload
    payload["age"] = age
    await bot.state_dispenser.set(message.peer_id, Form.GENDER, **payload)
    await message.answer("👤 Шаг 3/7. Выбери свой пол:", keyboard=get_gender_kb())

@bot.on.message(state=Form.GENDER)
async def step_gender(message: Message):
    txt = message.text or ""
    if "Парень" in txt:
        gender = "Парень"
    elif "Девушка" in txt:
        gender = "Девушка"
    else:
        await message.answer("Выбери вариант кнопкой ниже 👇", keyboard=get_gender_kb())
        return
    state = await bot.state_dispenser.get(message.peer_id)
    payload = state.payload
    payload["gender"] = gender
    await bot.state_dispenser.set(message.peer_id, Form.TARGET_GENDER, **payload)
    await message.answer("💘 Шаг 4/7. Кого ты хочешь найти?", keyboard=get_target_kb())

@bot.on.message(state=Form.TARGET_GENDER)
async def step_target(message: Message):
    txt = message.text or ""
    if "Девушек" in txt:
        target = "Девушка"
    elif "Парней" in txt:
        target = "Парень"
    else:
        await message.answer("Выбери вариант кнопкой ниже 👇", keyboard=get_target_kb())
        return
    state = await bot.state_dispenser.get(message.peer_id)
    payload = state.payload
    payload["target_gender"] = target
    await bot.state_dispenser.set(message.peer_id, Form.LOCATION, **payload)
    await message.answer(
        "📍 Шаг 5/7. Отправь геопозицию (покажет метры/км и время в пути), выбери район Комсомольска-на-Амуре или останься инкогнито 👇",
        keyboard=get_geo_kb()
    )

@bot.on.message(state=Form.LOCATION)
async def step_location(message: Message):
    state = await bot.state_dispenser.get(message.peer_id)
    payload = state.payload
    if message.geo and message.geo.coordinates:
        payload["lat"] = message.geo.coordinates.latitude
        payload["lon"] = message.geo.coordinates.longitude
        payload["location_text"] = "г. Комсомольск-на-Амуре"
    else:
        txt = (message.text or "").strip()
        payload["lat"] = None
        payload["lon"] = None
        if "Инкогнито" in txt or not txt:
            payload["location_text"] = "г. Комсомольск-на-Амуре"
        elif txt in DISTRICTS:
            payload["location_text"] = f"р-н {txt}"
        else:
            payload["location_text"] = txt[:40]
    await bot.state_dispenser.set(message.peer_id, Form.BIO, **payload)
    old_bio = payload.get("old_user", {}).get("bio")
    await message.answer(
        "📝 Шаг 6/7. Напиши пару слов о себе (интересы, кого ищешь) или нажми «⏭ Пропустить» — анкету можно создать и без текста:",
        keyboard=get_quick_kb(old_bio, allow_skip=True)
    )

@bot.on.message(state=Form.BIO)
async def step_bio(message: Message):
    state = await bot.state_dispenser.get(message.peer_id)
    payload = state.payload
    txt = message.text or ""
    payload["bio"] = "" if "Пропустить" in txt else txt[:400]
    await bot.state_dispenser.set(message.peer_id, Form.MEDIA, **payload)
    await message.answer(
        "📸 Шаг 7/7. Прикрепи от 1 до 3 фото (и по желанию 1 видео) и нажми «✅ Готово, опубликовать»:",
        keyboard=get_media_done_kb()
    )

@bot.on.message(state=Form.MEDIA)
async def step_media(message: Message):
    state = await bot.state_dispenser.get(message.peer_id)
    payload = state.payload
    atts = payload.get("attachments", [])

    if message.attachments:
        for a in message.attachments:
            if a.photo and len([x for x in atts if x.startswith("photo")]) < 3:
                key = f"_{a.photo.access_key}" if a.photo.access_key else ""
                atts.append(f"photo{a.photo.owner_id}_{a.photo.id}{key}")
            elif a.video and len([x for x in atts if x.startswith("video")]) < 1:
                key = f"_{a.video.access_key}" if a.video.access_key else ""
                atts.append(f"video{a.video.owner_id}_{a.video.id}{key}")
        payload["attachments"] = atts
        await bot.state_dispenser.set(message.peer_id, Form.MEDIA, **payload)

    if message.text and "Готово" in message.text:
        if not atts:
            await message.answer("⚠️ Прикрепи хотя бы 1 фото к сообщению перед публикацией!", keyboard=get_media_done_kb())
            return
        await db.add_user(
            user_id=message.from_id,
            name=payload["name"],
            age=payload["age"],
            gender=payload["gender"],
            target_gender=payload["target_gender"],
            lat=payload.get("lat"),
            lon=payload.get("lon"),
            location_text=payload.get("location_text", "г. Комсомольск-на-Амуре"),
            bio=payload.get("bio", ""),
            attachments_list=atts
        )
        await bot.state_dispenser.delete(message.peer_id)
        await message.answer("🎉 Готово! Твоя анкета опубликована. Вот как её видят другие 👇", keyboard=get_main_menu_kb())
        await menu_my_profile(message)
    else:
        photos_cnt = len([x for x in atts if x.startswith("photo")])
        videos_cnt = len([x for x in atts if x.startswith("video")])
        await message.answer(
            f"✅ Принято! Сейчас в анкете: фото — {photos_cnt}/3, видео — {videos_cnt}/1.\nМожешь добавить ещё или жми «✅ Готово, опубликовать» 👇",
            keyboard=get_media_done_kb()
        )
@bot.on.message(text=["🔥 Смотреть анкеты", "Смотреть анкеты"])
async def menu_search(message: Message):
    await bot.state_dispenser.delete(message.peer_id)
    user = await db.get_user(message.from_id)
    if not user:
        await message.answer("Сначала создай анкету — напиши «Начать»!")
        return
    if user.get("is_banned"):
        await message.answer("🚫 Твоя анкета заблокирована.")
        return
    if not user.get("is_active", 1):
        kb = Keyboard(inline=True)
        kb.add(Callback("🔥 Вернуть анкету в поиск", payload={"cmd": "wake_up"}), color=KeyboardButtonColor.POSITIVE)
        await message.answer(
            f"💫 Мы тебя помним, {user['name']}!\nВключи анкету обратно, чтобы смотреть других 👇",
            keyboard=kb.get_json()
        )
        return
    await show_next_profile(message.peer_id, message.from_id)

@bot.on.message(text=["👤 Моя анкета", "Моя анкета"])
async def menu_my_profile(message: Message):
    await bot.state_dispenser.delete(message.peer_id)
    user = await db.get_user(message.from_id)
    if not user:
        await message.answer("У тебя ещё нет анкеты. Напиши «Начать»!")
        return
    kb = Keyboard(inline=True)
    kb.add(Callback("✏️ Заполнить заново (быстро)", payload={"cmd": "edit_profile"}), color=KeyboardButtonColor.PRIMARY)
    kb.row()
    kb.add(Callback("📝 Изменить текст о себе", payload={"cmd": "edit_bio"}), color=KeyboardButtonColor.SECONDARY)
    kb.row()
    kb.add(Callback("📍 Сменить геопозицию / район", payload={"cmd": "edit_geo"}), color=KeyboardButtonColor.SECONDARY)
    kb.row()
    kb.add(Callback("💤 Скрыть анкету из поиска", payload={"cmd": "sleep_profile"}), color=KeyboardButtonColor.NEGATIVE)
    await send_profile(message.peer_id, user, inline_kb=kb.get_json(), is_own=True)

@bot.on.message(state=UpdateGeo.WAITING_GEO)
async def save_new_geo(message: Message):
    if message.geo and message.geo.coordinates:
        await db.update_location(message.from_id, message.geo.coordinates.latitude, message.geo.coordinates.longitude, "г. Комсомольск-на-Амуре")
        loc_label = "по GPS"
    else:
        txt = (message.text or "").strip()
        if "Инкогнито" in txt or not txt:
            loc_label = "г. Комсомольск-на-Амуре"
        elif txt in DISTRICTS:
            loc_label = f"р-н {txt}"
        else:
            loc_label = txt[:40]
        await db.update_location(message.from_id, None, None, loc_label)
    await bot.state_dispenser.delete(message.peer_id)
    await message.answer(f"✅ Локация обновлена ({loc_label})!", keyboard=get_main_menu_kb())

@bot.on.message(state=UpdateBio.WAITING_BIO)
async def save_new_bio(message: Message):
    txt = (message.text or "").strip()
    if "Отмена" in txt:
        await bot.state_dispenser.delete(message.peer_id)
        await message.answer("Отменено.", keyboard=get_main_menu_kb())
        return
    new_bio = "" if txt == "-" else txt[:400]
    await db.update_bio(message.from_id, new_bio)
    await bot.state_dispenser.delete(message.peer_id)
    await message.answer("✅ Текст анкеты обновлён!", keyboard=get_main_menu_kb())

async def show_next_profile(peer_id: int, user_id: int):
    need_bio = await db.increment_views_and_check_prompt(user_id)
    if need_bio:
        bio_kb = Keyboard(inline=True)
        bio_kb.add(Callback("✍️ Добавить текст в анкету", payload={"cmd": "edit_bio"}), color=KeyboardButtonColor.PRIMARY)
        await bot.api.messages.send(
            peer_id=peer_id,
            message="💡 Маленький совет! Ты посмотрел уже больше 10 анкет, а в твоём профиле пока пусто.\nМожет быть, всё-таки добавим пару слов о себе? Анкеты с описанием получают больше лайков 👇",
            keyboard=bio_kb.get_json(),
            random_id=0
        )

    admirer = await db.get_incoming_like(user_id)
    if admirer:
        tid = admirer["user_id"]
        kb = Keyboard(inline=True)
        kb.add(Callback("❤️ Взаимно!", payload={"cmd": "like", "uid": tid}), color=KeyboardButtonColor.POSITIVE)
        kb.add(Callback("👎 Неинтересно", payload={"cmd": "pass", "uid": tid}), color=KeyboardButtonColor.NEGATIVE)
        kb.row()
        kb.add(Callback("⚠️ Жалоба", payload={"cmd": "report", "uid": tid}), color=KeyboardButtonColor.SECONDARY)
        await send_profile(peer_id, admirer, inline_kb=kb.get_json(), prefix="💘 Ты понравился этому человеку!\n\n")
        return

    profile = await db.get_next_profile(user_id)
    if not profile:
        await bot.api.messages.send(
            peer_id=peer_id,
            message="😴 Анкеты пока закончились! Загляни чуть позже или позови друзей из Комсы!",
            keyboard=get_main_menu_kb(),
            random_id=0
        )
        return

    tid = profile["user_id"]
    kb = Keyboard(inline=True)
    kb.add(Callback("❤️ Лайк", payload={"cmd": "like", "uid": tid}), color=KeyboardButtonColor.POSITIVE)
    kb.add(Callback("👎 Дальше", payload={"cmd": "pass", "uid": tid}), color=KeyboardButtonColor.NEGATIVE)
    kb.row()
    kb.add(Callback("⚠️ Жалоба", payload={"cmd": "report", "uid": tid}), color=KeyboardButtonColor.SECONDARY)
    await send_profile(peer_id, profile, inline_kb=kb.get_json(), is_own=False)
@bot.on.raw_event("message_event", dataclass=MessageEvent)
async def handle_callbacks(event: MessageEvent):
    payload = event.object.payload or {}
    cmd = payload.get("cmd")
    uid = event.object.user_id
    peer_id = event.object.peer_id

    await bot.api.messages.send_message_event_answer(
        event_id=event.object.event_id,
        user_id=uid,
        peer_id=peer_id
    )

    if cmd == "sleep_profile":
        await db.set_active(uid, False)
        await bot.api.messages.send(
            peer_id=peer_id,
            message="💤 Анкета скрыта из поиска! Мы сохранили твои данные. Чтобы вернуться — напиши «Начать».",
            keyboard=Keyboard().get_json(),
            random_id=0
        )
    elif cmd == "wake_up":
        await db.set_active(uid, True)
        await bot.api.messages.send(peer_id=peer_id, message="🔥 С возвращением в игру!", keyboard=get_main_menu_kb(), random_id=0)
        await show_next_profile(peer_id, uid)
    elif cmd == "edit_profile":
        old_u = await db.get_user(uid)
        await bot.state_dispenser.set(peer_id, Form.NAME, old_user=old_u or {}, attachments=[])
        await bot.api.messages.send(
            peer_id=peer_id,
            message="⚡ Режим быстрого заполнения!\n✏️ Шаг 1/7. Как тебя зовут?",
            keyboard=get_quick_kb((old_u or {}).get("name")),
            random_id=0
        )
    elif cmd == "edit_geo":
        await bot.state_dispenser.set(peer_id, UpdateGeo.WAITING_GEO)
        await bot.api.messages.send(peer_id=peer_id, message="📍 Отправь GPS, выбери район или останься инкогнито 👇", keyboard=get_geo_kb(), random_id=0)
    elif cmd == "edit_bio":
        await bot.state_dispenser.set(peer_id, UpdateBio.WAITING_BIO)
        await bot.api.messages.send(peer_id=peer_id, message="📝 Напиши новый текст о себе (или отправь «-», чтобы очистить):", keyboard=get_cancel_kb(), random_id=0)
    elif cmd == "view_likes":
        await show_next_profile(peer_id, uid)
    elif cmd in ("like", "pass"):
        tid = int(payload.get("uid"))
        is_like = (cmd == "like")
        is_match = await db.add_like(uid, tid, is_like)
        if is_match:
            u1 = await db.get_user(uid)
            u2 = await db.get_user(tid)
            if u1 and u2:
                next_kb = Keyboard(inline=True)
                next_kb.add(Callback("🔥 Смотреть дальше", payload={"cmd": "view_likes"}), color=KeyboardButtonColor.PRIMARY)
                await bot.api.messages.send(
                    peer_id=peer_id,
                    message=f"🎉 Бинго! Взаимная симпатия с [id{tid}|{u2['name']}]!\nНажимай на имя, чтобы открыть страницу и написать в личку 💌",
                    keyboard=next_kb.get_json(),
                    random_id=0
                )
                await bot.api.messages.send(
                    peer_id=tid,
                    message=f"🎉 Бинго! Взаимная симпатия с [id{uid}|{u1['name']}]!\nНажимай на имя, чтобы открыть страницу и написать в личку 💌",
                    keyboard=next_kb.get_json(),
                    random_id=0
                )
        else:
            if is_like:
                try:
                    likes_cnt = await db.count_incoming_likes(tid)
                    people_str = format_people_dative(max(1, likes_cnt))
                    already = "уже " if likes_cnt > 1 else ""
                    vkb = Keyboard(inline=True)
                    vkb.add(Callback("👀 Посмотреть, кто там", payload={"cmd": "view_likes"}), color=KeyboardButtonColor.POSITIVE)
                    await bot.api.messages.send(
                        peer_id=tid,
                        message=f"💘 Твоя анкета понравилась {already}{people_str}! Заканчивай с просмотром и давай посмотрим, кто там 👇",
                        keyboard=vkb.get_json(),
                        random_id=0
                    )
                except Exception:
                    pass
            await show_next_profile(peer_id, uid)
    elif cmd == "report":
        tid = int(payload.get("uid"))
        await db.add_like(uid, tid, False)
        await bot.api.messages.send(peer_id=peer_id, message="⚠️ Жалоба отправлена модератору.", random_id=0)
        t_info = await db.get_user(tid)
        if t_info and ADMIN_ID:
            bkb = Keyboard(inline=True)
            bkb.add(Callback("🚫 Забанить анкету", payload={"cmd": "ban", "uid": tid}), color=KeyboardButtonColor.NEGATIVE)
            await bot.api.messages.send(
                peer_id=ADMIN_ID,
                message=f"🚨 Жалоба на анкету!\nНарушитель: [id{tid}|{t_info['name']}], {t_info['age']}\nОписание: {t_info['bio']}",
                attachment=",".join(t_info.get("attachments_list", [])) or None,
                keyboard=bkb.get_json(),
                random_id=0
            )
        await show_next_profile(peer_id, uid)
    elif cmd == "ban" and uid == ADMIN_ID:
        tid = int(payload.get("uid"))
        await db.ban_user(tid)
        await bot.api.messages.send(peer_id=peer_id, message=f"✅ Пользователь [id{tid}|id{tid}] заблокирован.", random_id=0)

async def on_startup():
    global ADMIN_ID
    await db.init_db()
    try:
        users = await bot.api.users.get(user_ids=[ADMIN_SCREEN_NAME])
        if users:
            ADMIN_ID = next(iter(users)).id
            print(f"Админ определён: {ADMIN_SCREEN_NAME} -> {ADMIN_ID}")
    except Exception as e:
        print(f"Не удалось определить ID админа: {e}")
    print("ВК-бот КомсаМэтч запущен!")

bot.loop_wrapper.on_startup.append(on_startup())
bot.run_forever()
