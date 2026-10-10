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
        "👋 Привіт! Я ваш помічник для звітів.\n\n"
        "**Як працювати:**\n"
        "1. Відправте мені **ФОТО (скріншот)**, а в поле **ПІДПИС** вставте посилання.\n"
        "2. Я запам'ятаю їх по черзі.\n"
        "3. Коли закінчите зміну, напишіть /report\n\n"
        "Я згенерую гарну HTML-сторінку, де фото та посилання будуть поруч!\n"
        "Для скидання прогресу напишіть /clear"
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
    await message.answer("🗑 Ваш поточний список очищено.")

@dp.message(Command("report"))
async def cmd_report(message: types.Message):
    user_id = message.from_user.id
    data = user_sessions.get(user_id, [])
    
    if not data:
        await message.answer("🤷‍♂️ У вас ще немає збережених скріншотів. Спочатку відправте фото.")
        return
        
    await message.answer("🔄 Збираю HTML-звіт, це займе кілька секунд...")
    
    user_dir = f"temp_report_{user_id}"
    os.makedirs(user_dir, exist_ok=True)
    
    # Починаємо формувати HTML сторінку з красивим дизайном
    html_lines = [
        "<!DOCTYPE html>",
        "<html><head><meta charset='utf-8'><title>Звіт Коментарів</title>",
        "<style>",
        "body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: #f0f2f5; padding: 20px; }",
        ".container { max-width: 600px; margin: 0 auto; }",
        ".card { background: white; padding: 20px; margin-bottom: 25px; border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.05); }",
        ".card h3 { margin-top: 0; color: #1c1e21; border-bottom: 2px solid #e4e6eb; padding-bottom: 10px; }",
        ".card img { width: 100%; border-radius: 8px; border: 1px solid #e4e6eb; margin-bottom: 15px; }",
        ".link { word-break: break-all; font-size: 16px; background: #e7f3ff; padding: 12px; border-radius: 8px; }",
        ".link a { color: #1877f2; text-decoration: none; font-weight: bold; }",
        ".link a:hover { text-decoration: underline; }",
        "h1 { text-align: center; color: #1c1e21; margin-bottom: 30px; }",
        "</style></head><body><div class='container'>",
        f"<h1>Ваш звіт ({len(data)} фото)</h1>"
    ]
    
    try:
        for index, item in enumerate(data, start=1):
            file_path = os.path.join(user_dir, f"{index}.jpg")
            
            # Завантажуємо фотографію
            file_info = await bot.get_file(item["file_id"])
            await bot.download_file(file_info.file_path, destination=file_path)
            
            safe_url = item["url"]
            # Додаємо блок зі скріншотом і лінком у HTML
            html_lines.append(
                f"<div class='card'>"
                f"<h3>№{index}</h3>"
                f"<img src='{index}.jpg' alt='Скріншот {index}'>"
                f"<div class='link'><a href='{safe_url}' target='_blank'>🔗 {safe_url}</a></div>"
                f"</div>"
            )
            
        html_lines.append("</div></body></html>")
        
        # Зберігаємо HTML файл
        html_path = os.path.join(user_dir, "zvit.html")
        with open(html_path, "w", encoding="utf-8") as f:
            f.write("\n".join(html_lines))
            
        # Пакуємо в ZIP
        zip_path = f"report_{user_id}.zip"
        with zipfile.ZipFile(zip_path, 'w') as zipf:
            for root, dirs, files in os.walk(user_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    zipf.write(file_path, arcname=file) 
                    
        archive_file = FSInputFile(zip_path, filename="V візуальний_звіт.zip")
        await message.answer_document(
            document=archive_file, 
            caption=f"🎉 Звіт готовий!\nРозпакуйте архів і відкрийте файл `zvit.html` у браузері."
        )
        
        user_sessions[user_id] = []
        
    except Exception as e:
        await message.answer(f"❌ Помилка: {e}")
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
    
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
