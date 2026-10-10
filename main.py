import asyncio
import os
import shutil
import zipfile
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import FSInputFile
from aiohttp import web
from collections import defaultdict

TOKEN = os.environ.get("BOT_TOKEN")

bot = Bot(token=TOKEN)
dp = Dispatcher()

user_sessions = defaultdict(list)

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    text = (
        "👋 Привіт! Я ваш особистий помічник для звітів.\n\n"
        "**Як працювати:**\n"
        "1. Відправте мені **ФОТО (скріншот)**, а в поле **ПІДПИС** вставте посилання на коментар.\n"
        "2. Я запам'ятаю їх по черзі.\n"
        "3. Коли закінчите зміну, напишіть /report\n\n"
        "Я зберу всі фото в один архів, пронумерую їх і додам табличку Excel з посиланнями.\n"
        "Якщо помилилися, напишіть /clear щоб почати звіт заново."
    )
    await message.answer(text, parse_mode="Markdown")

@dp.message(F.photo)
async def handle_photo(message: types.Message):
    user_id = message.from_user.id
    
    photo_file_id = message.photo[-1].file_id
    url = message.caption if message.caption else "ПОСИЛАННЯ_НЕ_ВКАЗАНО"
    
    user_sessions[user_id].append({
        "file_id": photo_file_id,
        "url": url
    })
    
    count = len(user_sessions[user_id])
    await message.reply(f"✅ Збережено! Це скріншот №{count}.")

@dp.message(Command("clear"))
async def cmd_clear(message: types.Message):
    user_id = message.from_user.id
    if user_id in user_sessions:
        user_sessions[user_id] = []
    await message.answer("🗑 Ваш поточний список очищено. Можете завантажувати нові скріншоти.")

@dp.message(Command("report"))
async def cmd_report(message: types.Message):
    user_id = message.from_user.id
    data = user_sessions.get(user_id, [])
    
    if not data:
        await message.answer("🤷‍♂️ У вас ще немає збережених скріншотів. Спочатку відправте фото.")
        return
        
    await message.answer("🔄 Збираю архів, це займе кілька секунд...")
    
    user_dir = f"temp_report_{user_id}"
    os.makedirs(user_dir, exist_ok=True)
    
    csv_lines = ["Номер,Посилання"]
    
    try:
        for index, item in enumerate(data, start=1):
            file_path = os.path.join(user_dir, f"{index}.jpg")
            
            file_info = await bot.get_file(item["file_id"])
            await bot.download_file(file_info.file_path, destination=file_path)
            
            safe_url = f'"{item["url"]}"' if ',' in item["url"] else item["url"]
            csv_lines.append(f"{index},{safe_url}")
            
        csv_path = os.path.join(user_dir, "links.csv")
        with open(csv_path, "w", encoding="utf-8-sig") as f:
            f.write("\n".join(csv_lines))
            
        zip_path = f"report_{user_id}.zip"
        with zipfile.ZipFile(zip_path, 'w') as zipf:
            for root, dirs, files in os.walk(user_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    zipf.write(file_path, arcname=file) 
                    
        archive_file = FSInputFile(zip_path, filename="Zvit.zip")
        await message.answer_document(
            document=archive_file, 
            caption=f"🎉 Ваш звіт готовий!\nКількість скріншотів: {len(data)}\nТаблиця `links.csv` всередині."
        )
        
        user_sessions[user_id] = []
        
    except Exception as e:
        await message.answer(f"❌ Виникла помилка: {e}")
    finally:
        if os.path.exists(user_dir):
            shutil.rmtree(user_dir)
        if os.path.exists(f"report_{user_id}.zip"):
            os.remove(f"report_{user_id}.zip")

async def health_check(request):
    return web.Response(text="Bot is running!")

async def main():
    app = web.Application()
    app.router.add_get('/', health_check)
    runner = web.AppRunner(app)
    await runner.setup()
    
    port = int(os.environ.get("PORT", 10000))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    
    print(f"Сервер запущено на порту {port}")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
