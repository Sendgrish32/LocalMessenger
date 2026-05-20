import asyncio, base64, os, threading
import customtkinter as ctk
from nacl.public import PrivateKey
from tkinter import filedialog

ctk.set_appearance_mode("system")
ctk.set_default_color_theme("green")

class ChatClient:

    def _process_incoming_file(self, raw_message):
        try:
            start_idx = raw_message.find("FILE_MSG:")
            clean_message = raw_message[start_idx:].strip()
            
            parts = clean_message.split(":", 2)
            if len(parts) < 3:
                self.add_message_to_display("❌ Ошибка: Файл поврежден")
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
            self.add_message_to_display(f"✅ Файл сохранен: {full_path}")
        except Exception as e:
            self.add_message_to_display(f"❌ Ошибка файла: {e}")

    def select_and_send_file(self):
        if not self.writer:
            self.add_message_to_display("[Система]: Нет подключения к серверу!")
            return
        file_path = filedialog.askopenfilename()
        
        if file_path:
            file_name = os.path.basename(file_path)
            
            try:
                with open(file_path, "rb") as f:
                    file_bytes = f.read()
                file_b64 = base64.b64encode(file_bytes).decode('utf-8')
                package = f"FILE_MSG:{file_name}:{file_b64}<<END_MSG>>"
                
                self.writer.write(package.encode('utf-8'))
                asyncio.run_coroutine_threadsafe(self.writer.drain(), self.loop)
                
                self.add_message_to_display(f"[Вы отправили файл]: {file_name}")
                
            except Exception as e:
                self.add_message_to_display(f"[Ошибка отправки]: {str(e)}")

    def __init__(self, root):
        self.root = root
        self.root.title("Messenger")
        self.root.geometry("500x600")
        self.root.minsize(500, 600)
        
        self.reader = None
        self.writer = None
        self.loop = None
        
        self.my_private_key = PrivateKey.generate()
        self.my_public_key = self.my_private_key.public_key
        
        self.server_ip = "127.0.0.1"
        self.server_port = 8888
        self.msg_size = 150 * 1024 * 1024
        
        self.setup_ui()
        self.connect_to_server()
    
    def setup_ui(self):
        exit_button = ctk.CTkButton(
            self.root,
            text="Exit",
            command=self.disconnect,
            width=40,
            height=40,
            font=("Arial", 10),
            fg_color="#d32f2f",
            hover_color="#b71c1c"
        )
        exit_button.place(relx=1.0, rely=0.0, x=-10, y=10, anchor="ne")

        title_label = ctk.CTkLabel(self.root, text="Messenger", font=("Arial", 20, "bold"))
        title_label.pack(pady=10)

        self.chat_display = ctk.CTkScrollableFrame(self.root, label_text="Messages")
        self.chat_display.pack(fill="both", expand=True, padx=10, pady=10)
        
        input_frame = ctk.CTkFrame(self.root)
        input_frame.pack(fill="x", padx=10, pady=10)
        
        self.message_input = ctk.CTkEntry(
            input_frame,
            placeholder_text="Type your message here...",
            height=40,
            font=("Arial", 12)
        )
        self.message_input.pack(side="left", fill="both", expand=True, padx=(0, 10))
        self.message_input.bind("<Return>", lambda e: self.send_message())
        
        send_button = ctk.CTkButton(
            input_frame,
            text="Send",
            command=self.send_message,
            width=80,
            height=40,
            font=("Arial", 12)
        )
        send_button.pack(side="right", padx=(0, 10))

        file_button = ctk.CTkButton(
            input_frame, 
            text="📎", 
            command=self.select_and_send_file, 
            width=40,
            height=40,
            font=("Arial", 20)
        )
        file_button.pack(side="left", padx=(0, 5))

        self.status_label = ctk.CTkLabel(
            self.root,
            text="Connecting...",
            text_color="orange",
            font=("Arial", 10)
        )
        self.status_label.pack(pady=5)
    
    def add_message_to_display(self, message):
        self.root.after(0, self._insert_message_label, message)

    def _insert_message_label(self, message):
        msg_label = ctk.CTkLabel(
            master=self.chat_display, 
            text=message, 
            font=("Arial", 14), 
            justify="left"
        )
        msg_label.pack(anchor="w", padx=10, pady=1)
        self.root.update_idletasks()
        self.chat_display._parent_canvas.yview_moveto(1.0)
    
    def update_status(self, status, color="white"):
        self.root.after(0, lambda: self.status_label.configure(text=status, text_color=color))
    
    def connect_to_server(self):
        threading.Thread(target=self._connect_async, daemon=True).start()
    
    def _connect_async(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.loop.run_until_complete(self.main())
    
    async def main(self):
        try:
            self.reader, self.writer = await asyncio.open_connection(self.server_ip, self.server_port)
            self.update_status("Connected to server", "green")
            self.add_message_to_display("[System] Connected to server")
            
            pub_key_b64 = base64.b64encode(bytes(self.my_public_key)).decode('utf-8')
            self.writer.write(f"KEY:{pub_key_b64}".encode())
            await self.writer.drain()
            await self.listen_server()
        except Exception as e:
            self.update_status(f"Connection failed: {e}", "red")
            self.add_message_to_display(f"[Error] Connection failed: {e}")
    
    async def listen_server(self):
        buffer = ""
        CHUNK_SIZE = 32 * 1024
        try:
            while True:
                data = await self.reader.read(CHUNK_SIZE)
                if not data:
                    break
                
                buffer += data.decode('utf-8', errors='ignore')
                while "<<END_MSG>>" in buffer:
                    message, buffer = buffer.split("<<END_MSG>>", 1)
                    message = message.strip()
                    if "FILE_MSG:" in message:
                        threading.Thread(target=self._process_incoming_file, args=(message,), daemon=True).start()
                    else:
                        self.add_message_to_display(message)
                        
        except Exception as e:
            self.add_message_to_display(f"[Ошибка сети]: {e}")
    
    def send_message(self):
        message = self.message_input.get()
        if not message or not self.writer:
            return
        try:
            self.add_message_to_display(f"[You]: {message}")
            package = f"{message}<<END_MSG>>"
            self.writer.write(package.encode())

            if self.loop and self.loop.is_running():
                asyncio.run_coroutine_threadsafe(self.writer.drain(), self.loop)
            
            self.message_input.delete(0, "end")
            
        except Exception as e:
            self.add_message_to_display(f"[Error] Failed to send message: {e}")
    
    def disconnect(self):
        try:
            if self.writer and self.loop and self.loop.is_running():
                self.writer.write("stop".encode())
                asyncio.run_coroutine_threadsafe(self.writer.drain(), self.loop)
                self.writer.close()
            
            self.update_status("Disconnected", "orange")
            self.add_message_to_display("[System] Disconnected from server")
        except Exception as e:
            self.add_message_to_display(f"[Error] {e}")
        finally:
            self.root.after(500, self.root.destroy)

if __name__ == "__main__":
    root = ctk.CTk()
    app = ChatClient(root)
    root.mainloop()