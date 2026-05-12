import asyncio, json, hashlib, os

#IP адрес сервера: Для только своего пк(127.0.0.1), для всех(0.0.0.0)
ip_addr = '0.0.0.0'

#НАСТРОЙКИ И БАЗА ДАННЫХ
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.path.join(BASE_DIR, "users.json")

# Загружаем базу при старте
if os.path.exists(DB_FILE):
    with open(DB_FILE, "r", encoding="utf-8") as f:
        try:
            users_db = json.load(f)
        except json.JSONDecodeError:
            users_db = {}
else:
    users_db = {}

active_users = {}

def save_db():
    #ФУНКЦИЯ СОХРАНЕНИЯ ДАННЫХ ПОЛЬЗОВАТЕЛЕЙ
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(users_db, f, indent=4)

def get_hash(password: str):
    #ХЕШИРОВАНИЕ
    return hashlib.sha256(password.encode()).hexdigest()



async def handle_client(reader, writer):
    addr = writer.get_extra_info('peername')
    nickname = None
    
    try:
        data = await reader.read(1024)
        content = data.decode().strip()

        # 1. ЗАПРОС НИКНЕЙМА
        writer.write("Введите ваш никнейм: ".encode())
        await writer.drain()
        nickname = (await reader.read(1024)).decode().strip()

        # 2. ЗАПРОС ПАРОЛЯ
        writer.write("Введите пароль: ".encode())
        await writer.drain()
        password = (await reader.read(1024)).decode().strip()
        password_hash = get_hash(password)

        # 3. ПРОВЕРКА АВТОРИЗАЦИИ / РЕГИСТРАЦИЯ
        if nickname in users_db:
            # Если юзер есть
            if users_db[nickname]["password_hash"] != password_hash:
                writer.write("ОШИБКА: Неверный пароль".encode())
                await writer.drain()
                writer.close()
                return
            writer.write(f"С возвращением, {nickname}!\n".encode())
        else:
            # Если юзера нет
            users_db[nickname] = {"password_hash": password_hash}
            save_db() #СОХРАНЯЕМ ДАННЫЕ ПОЛЬЗОВАТЕЛЯ
            writer.write(f"Регистрация успешна! Добро пожаловать, {nickname}.\n".encode())
        await writer.drain()

        if content.startswith("KEY:"):
            key_b64 = content.split("KEY:")[1]
            users_db[nickname]["public_key"] = key_b64
            save_db()
            print(f"[СЕРВЕР] Ключ для {nickname} сохранен.")


        # 4. ВХОД В ЧАТ
        active_users[nickname] = writer
        print(f"[СЕРВЕР] {nickname} ({addr}) вошел в чат.")
        
        msg = f"[СИСТЕМА] {nickname} присоединился к чату."
        for user, w in active_users.items():
            if user != nickname:
                w.write(msg.encode())
                await w.drain()

        # 5. ЦИКЛ ОБМЕНА СООБЩЕНИЯМИ
        while True:
            data = await reader.read(1024)
            if not data:
                break
            
            message = data.decode().strip()
            if message.lower() == 'stop':
                break

            print(f"[{nickname}]: {message}")

            # Рассылка всем активным
            final_msg = f"[{nickname}]: {message}"
            for user, w in list(active_users.items()):
                if user != nickname:
                    try:
                        w.write(f"{final_msg}".encode())
                        await w.drain()
                    except:
                        # Если не удалось отправить
                        del active_users[user]

    except Exception as e:
        print(f"[ОШИБКА] Проблема с {addr}: {e}")
    finally:
        # Убираем пользователя из списка активных при выходе
        if nickname and nickname in active_users:
            del active_users[nickname]
            print(f"[СЕРВЕР] {nickname} покинул чат.")
            
            # Оповещаем остальных об уходе
            exit_msg = f"\n[СИСТЕМА] {nickname} покинул чат.\n "
            for user, w in active_users.items():
                try:
                    w.write(exit_msg.encode())
                    await w.drain()
                except:
                    pass
        
        writer.close()
        await writer.wait_closed()

async def main():
    server = await asyncio.start_server(handle_client, ip_addr, 8888)
    print(f"[СЕРВЕР] Запущен на {ip_addr}:8888. Ожидание подключений...")
    async with server:
        await server.serve_forever()

if __name__ == "__main__":
    asyncio.run(main())