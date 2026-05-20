import asyncio
import base64
import os
import threading
from nacl.public import PrivateKey

class ConsoleChatClient:
    def __init__(self):
        self.reader = None
        self.writer = None
        self.loop = None
        self.my_private_key = PrivateKey.generate()
        self.my_public_key = self.my_private_key.public_key
        self.server_ip = '192.168.50.163'
        self.server_port = 8888

    def _process_incoming_file(self, raw_message):
        try:
            start_idx = raw_message.find("FILE_MSG:")
            clean_message = raw_message[start_idx:].strip()
            parts = clean_message.split(":", 2)
            if len(parts) < 3:
                print("\n❌ Ошибка: Файл поврежден")
                return
            _, file_name, file_b64 = parts
            missing_padding = len(file_b64) % 4
            if missing_padding:
                file_b64 += '=' * (4 - missing_padding)
            file_bytes = base64.b64decode(file_b64.encode('utf-8'))
            script_dir = os.path.dirname(os.path.abspath(__file__))
            save_dir = os.path.join(script_dir, "downloads")
            os.makedirs(save_dir, exist_ok=True)
            full_path = os.path.join(save_dir, file_name)
            with open(full_path, "wb") as f:
                f.write(file_bytes)
            print(f"\n✅ Файл сохранен: {full_path}")
        except Exception as e:
            print(f"\n❌ Ошибка файла: {e}")

    def send_file_path(self, file_path):
        if not self.writer:
            print("\n[Система]: Нет подключения к серверу!")
            return
        if os.path.exists(file_path) and os.path.isfile(file_path):
            file_name = os.path.basename(file_path)
            try:
                with open(file_path, "rb") as f:
                    file_bytes = f.read()
                file_b64 = base64.b64encode(file_bytes).decode('utf-8')
                package = f"FILE_MSG:{file_name}:{file_b64}<<END_MSG>>"
                self.writer.write(package.encode('utf-8'))
                if self.loop and self.loop.is_running():
                    asyncio.run_coroutine_threadsafe(self.writer.drain(), self.loop)
                print(f"\n[Вы отправили файл]: {file_name}")
            except Exception as e:
                print(f"\n[Ошибка отправки]: {str(e)}")
        else:
            print("\n❌ Ошибка: Файл не найден!")

    def start(self):
        threading.Thread(target=self._connect_async, daemon=True).start()
        self._input_loop()

    def _connect_async(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.loop.run_until_complete(self.main())

    async def main(self):
        try:
            print(f"[Connecting] Попытка подключения к {self.server_ip}:{self.server_port}...")
            self.reader, self.writer = await asyncio.open_connection(self.server_ip, self.server_port)
            print("[System] Connected to server")
            pub_key_b64 = base64.b64encode(bytes(self.my_public_key)).decode('utf-8')
            self.writer.write(f"KEY:{pub_key_b64}".encode())
            await self.writer.drain()
            await self.listen_server()
        except Exception as e:
            print(f"[Error] Connection failed: {e}")

    async def listen_server(self):
        buffer = ""
        CHUNK_SIZE = 32 * 1024
        try:
            while True:
                data = await self.reader.read(CHUNK_SIZE)
                if not data:
                    print("\n[System] Disconnected from server")
                    break
                buffer += data.decode('utf-8', errors='ignore')
                while "<<END_MSG>>" in buffer:
                    message, buffer = buffer.split("<<END_MSG>>", 1)
                    message = message.strip()
                    if "FILE_MSG:" in message:
                        threading.Thread(target=self._process_incoming_file, args=(message,), daemon=True).start()
                    else:
                        print(f"\n{message}")
        except Exception as e:
            print(f"\n[Ошибка сети]: {e}")

    def _input_loop(self):
        while True:
            try:
                message = input().strip()
                if not message:
                    continue
                if message.lower() == 'exit' or message.lower() == 'stop':
                    self.disconnect()
                    break
                if message.startswith("/file "):
                    file_path = message.replace("/file ", "", 1).strip()
                    self.send_file_path(file_path)
                    continue
                if self.writer:
                    package = f"{message}<<END_MSG>>"
                    self.writer.write(package.encode())
                    if self.loop and self.loop.is_running():
                        asyncio.run_coroutine_threadsafe(self.writer.drain(), self.loop)
            except (KeyboardInterrupt, SystemExit):
                self.disconnect()
                break

    def disconnect(self):
        try:
            if self.writer and self.loop and self.loop.is_running():
                self.writer.write("stop".encode())
                asyncio.run_coroutine_threadsafe(self.writer.drain(), self.loop)
                self.writer.close()
            print("[System] Disconnected from server")
        except Exception as e:
            print(f"[Error] {e}")

if __name__ == "__main__":
    client = ConsoleChatClient()
    client.start()