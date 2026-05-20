import asyncio, json, hashlib, os

#IP адрес сервера: Для только своего пк(127.0.0.1), для всех(0.0.0.0)
ip_addr = '0.0.0.0'
msg_size = 150 * 1024 * 1024

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.path.join(BASE_DIR, "users.json")
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
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(users_db, f, indent=4)

def get_hash(password: str):
    return hashlib.sha256(password.encode()).hexdigest()

async def handle_client(reader, writer):
    addr = writer.get_extra_info('peername')
    nickname = None
    
    try:
        data = await reader.read(msg_size)
        content = data.decode().strip()
        
        if "<<END_MSG>>" in content:
            content = content.replace("<<END_MSG>>", "").strip()

        writer.write("Введите ваш никнейм: <<END_MSG>>".encode())
        await writer.drain()
        
        raw_nickname = (await reader.read(msg_size)).decode().strip()
        nickname = raw_nickname.replace("<<END_MSG>>", "").strip()

        writer.write("Введите пароль: <<END_MSG>>".encode())
        await writer.drain()
        
        raw_password = (await reader.read(msg_size)).decode().strip()
        password = raw_password.replace("<<END_MSG>>", "").strip()
        password_hash = get_hash(password)

        if nickname in users_db:
            if users_db[nickname]["password_hash"] != password_hash:
                writer.write("ОШИБКА: Неверный пароль<<END_MSG>>".encode())
                await writer.drain()
                writer.close()
                return
            writer.write(f"С возвращением, {nickname}!\n<<END_MSG>>".encode())
        else:
            users_db[nickname] = {"password_hash": password_hash}
            save_db()
            writer.write(f"Регистрация успешна! Добро пожаловать, {nickname}.\n<<END_MSG>>".encode())
        await writer.drain()

        if "KEY:" in content:
            key_b64 = content.split("KEY:")[1]
            users_db[nickname]["public_key"] = key_b64
            save_db()
            print(f"[СЕРВЕР] Ключ для {nickname} сохранен.")

        active_users[nickname] = writer
        print(f"[СЕРВЕР] {nickname} ({addr}) вошел в чат.")
        
        msg = f"[СИСТЕМА] {nickname} присоединился к чату.<<END_MSG>>"
        for user, w in active_users.items():
            if user != nickname:
                w.write(msg.encode())
                await w.drain()

        server_buffer = ""
        CHUNK_SIZE = 32 * 1024

        while True:
            data = await reader.read(64 * 1024)
            if not data:
                break
            server_buffer += data.decode('utf-8', errors='ignore')
            
            while "<<END_MSG>>" in server_buffer:
                message, server_buffer = server_buffer.split("<<END_MSG>>", 1)
                message = message.strip()
                
                if message.lower() == 'stop':
                    break

                if "FILE_MSG:" in message:
                    print(f"[{nickname}]: Отправил файл (Размер: {len(message)} символов)")
                else:
                    print(f"[{nickname}]: {message}")
                
                final_msg = f"[{nickname}]: {message}<<END_MSG>>"
                encoded_msg = final_msg.encode('utf-8')
                total_size = len(encoded_msg)

                for user, w in list(active_users.items()):
                    if user != nickname:
                        try:
                            offset = 0
                            while offset < total_size:
                                chunk = encoded_msg[offset:offset + CHUNK_SIZE]
                                w.write(chunk)
                                await w.drain()
                                offset += len(chunk)
                        except Exception as send_err:
                            print(f"[ОШИБКА СЕТИ] Не удалось отправить пользователю {user}: {send_err}")
                            try:
                                del active_users[user]
                            except:
                                pass

    except Exception as e:
        print(f"[ОШИБКА] Проблема с {addr}: {e}")
    finally:
        if nickname and nickname in active_users:
            del active_users[nickname]
            print(f"[СЕРВЕР] {nickname} покинул чат.")
            
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
