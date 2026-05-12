import asyncio, sys, base64
from nacl.public import PrivateKey, Box

my_private_key = PrivateKey.generate()
my_public_key = my_private_key.public_key
peers_keys = {}
server_ip = 'k2huq8clkg.localto.net'
server_port = '2791'

async def listen_server(reader):
    try:
        while True:
            data = await reader.read(1024)
            if not data:
                print("\n[Система] Соединение разорвано сервером.")
                break
            print(f"\n{data.decode().strip()}")
            print(end="", flush=True) # Возвращаем приглашение ко вводу
    except Exception as e:
        print(f"\n[Ошибка чтения]: {e}")

async def send_messages(writer):
    print("--- Вы вошли в чат ---")

    pub_key_b64 = base64.b64encode(bytes(my_public_key)).decode('utf-8')
    
    # Отправляем серверу спец-сообщение (протокол)
    writer.write(f"KEY:{pub_key_b64}".encode())
    await writer.drain()

    loop = asyncio.get_event_loop()
    try:
        while True:
            # Читаем ввод пользователя
            message = await loop.run_in_executor(None, input)
            
            if not message:
                continue

            if message.lower() == 'stop':
                break
                
            writer.write(message.encode())
            await writer.drain()
    except Exception as e:
        print(f"[Ошибка отправки]: {e}")
    finally:
        writer.close()
        try:
            await writer.wait_closed()
        except:
            pass

async def main():
    try:
        # Подключаемся
        reader, writer = await asyncio.open_connection(server_ip, server_port)
        
        # Запускаем задачи
        listen_task = asyncio.create_task(listen_server(reader))
        send_task = asyncio.create_task(send_messages(writer))

        # Ждем именно задачу отправки. Пока ты не введешь Stop, клиент не умрет.
        await send_task
        
        # Отменяем прослушку после выхода из отправки
        listen_task.cancel()
        
    except Exception as e:
        print(f"Ошибка подключения: {e}")

if __name__ == "__main__":
    asyncio.run(main())