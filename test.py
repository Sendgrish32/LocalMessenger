import asyncio
import base64
import customtkinter as ctk
from nacl.public import PrivateKey
import threading

# Configure customtkinter appearance
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

class ChatClient:
    def __init__(self, root):
        self.root = root
        self.root.title("LocalMessenger - Chat")
        self.root.geometry("600x700")
        self.root.minsize(500, 800)
        
        self.reader = None
        self.writer = None
        self.my_private_key = PrivateKey.generate()
        self.my_public_key = self.my_private_key.public_key
        self.server_ip = '127.0.0.1'
        self.server_port = 8888
        
        self.setup_ui()
        self.connect_to_server()
    
    def setup_ui(self):
        # Title
        title_label = ctk.CTkLabel(self.root, text="LocalMessenger Chat", font=("Arial", 20, "bold"))
        title_label.pack(pady=10)
        
        # Chat display frame
        chat_frame = ctk.CTkFrame(self.root)
        chat_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Scrollable text area for messages
        self.chat_display = ctk.CTkTextbox(
            chat_frame,
            state="disabled",
            text_color="white",
            font=("Arial", 12)
        )
        self.chat_display.pack(fill="both", expand=True)
        
        # Input frame
        input_frame = ctk.CTkFrame(self.root)
        input_frame.pack(fill="x", padx=10, pady=10)
        
        # Message input field
        self.message_input = ctk.CTkEntry(
            input_frame,
            placeholder_text="Type your message here...",
            height=40,
            font=("Arial", 12)
        )
        self.message_input.pack(side="left", fill="both", expand=True, padx=(0, 10))
        self.message_input.bind("<Return>", lambda e: self.send_message())
        
        # Send button
        send_button = ctk.CTkButton(
            input_frame,
            text="Send",
            command=self.send_message,
            width=80,
            height=40,
            font=("Arial", 12)
        )
        send_button.pack(side="right", padx=(0, 10))
        
        # Exit button
        exit_button = ctk.CTkButton(
            input_frame,
            text="Exit",
            command=self.disconnect,
            width=80,
            height=40,
            font=("Arial", 12),
            fg_color="#d32f2f"
        )
        exit_button.pack(side="right")
        
        # Status label
        self.status_label = ctk.CTkLabel(
            self.root,
            text="Connecting...",
            text_color="orange",
            font=("Arial", 10)
        )
        self.status_label.pack(pady=5)
    
    def add_message_to_display(self, message):
        """Add message to chat display"""
        self.chat_display.configure(state="normal")
        self.chat_display.insert("end", message + "\n")
        self.chat_display.see("end")
        self.chat_display.configure(state="disabled")
    
    def update_status(self, status, color="white"):
        """Update status label"""
        self.status_label.configure(text=status, text_color=color)
    
    def connect_to_server(self):
        """Connect to server in a separate thread"""
        threading.Thread(target=self._connect_async, daemon=True).start()
    
    def _connect_async(self):
        """Run async connection"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(self.main())
    
    async def main(self):
        try:
            self.reader, self.writer = await asyncio.open_connection(self.server_ip, self.server_port)
            self.update_status("Connected to server", "green")
            self.add_message_to_display("[System] Connected to server")
            
            # Send public key
            pub_key_b64 = base64.b64encode(bytes(self.my_public_key)).decode('utf-8')
            self.writer.write(f"KEY:{pub_key_b64}".encode())
            await self.writer.drain()
            
            # Listen for incoming messages
            await self.listen_server()
            
        except Exception as e:
            self.update_status(f"Connection failed: {e}", "red")
            self.add_message_to_display(f"[Error] Connection failed: {e}")
    
    async def listen_server(self):
        """Listen for messages from server"""
        try:
            while True:
                data = await self.reader.read(1024)
                if not data:
                    self.update_status("Disconnected from server", "red")
                    self.add_message_to_display("[System] Disconnected from server")
                    break
                
                message = data.decode().strip()
                self.add_message_to_display(message)
                
        except Exception as e:
            self.update_status(f"Error reading from server: {e}", "red")
            self.add_message_to_display(f"[Error] {e}")
    
    def send_message(self):
        """Send message to server"""
        message = self.message_input.get()
        
        if not message:
            return
        
        if not self.writer:
            self.add_message_to_display("[Error] Not connected to server")
            return
        
        try:
            # Display your own message
            self.add_message_to_display(f"[You]: {message}")
            
            # Send message
            self.writer.write(message.encode())
            asyncio.run_coroutine_threadsafe(self.writer.drain(), asyncio.get_event_loop())
            
            # Clear input
            self.message_input.delete(0, "end")
            
        except Exception as e:
            self.add_message_to_display(f"[Error] Failed to send message: {e}")
    
    def disconnect(self):
        """Disconnect from server and close program"""
        try:
            if self.writer:
                # Send stop command
                self.writer.write("stop".encode())
                asyncio.run_coroutine_threadsafe(self.writer.drain(), asyncio.get_event_loop())
                self.writer.close()
            
            self.update_status("Disconnected", "orange")
            self.add_message_to_display("[System] Disconnected from server")
        except Exception as e:
            self.add_message_to_display(f"[Error] {e}")
        finally:
            # Close the program after 500ms
            self.root.after(500, self.root.destroy)

if __name__ == "__main__":
    root = ctk.CTk()
    app = ChatClient(root)
    root.mainloop()
