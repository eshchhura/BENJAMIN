import tkinter as tk
from tkinter.scrolledtext import ScrolledText
from tkinter import TclError


class ChatInterface:
    """Simple Tkinter-based chat window."""

    def __init__(self, handle_func):
        """
        Parameters
        ----------
        handle_func: callable
            Function that takes a string input and returns a response string.
        """
        self.handle_func = handle_func
        try:
            self.window = tk.Tk()
        except TclError as e:  # pragma: no cover - GUI may be unavailable
            raise RuntimeError("Tkinter GUI unavailable") from e
        self.window.title("Benjamin Chat")

        self.chat_log = ScrolledText(self.window, state="disabled", width=80, height=20)
        self.chat_log.pack(padx=10, pady=10, fill="both", expand=True)

        self.entry_var = tk.StringVar()
        self.entry = tk.Entry(self.window, textvariable=self.entry_var)
        self.entry.pack(fill="x", padx=10, pady=(0, 10))
        self.entry.bind("<Return>", self._on_enter)

    def start(self):
        self.entry.focus()
        self.window.mainloop()

    def display(self, text: str):
        self._append(text)

    def _on_enter(self, event=None):
        user_text = self.entry_var.get().strip()
        if user_text:
            self._append(f"You: {user_text}")
            response = self.handle_func(user_text)
            if response:
                self._append(f"Benjamin: {response}")
        self.entry_var.set("")

    def _append(self, text: str):
        self.chat_log.configure(state="normal")
        self.chat_log.insert(tk.END, text + "\n")
        self.chat_log.configure(state="disabled")
        self.chat_log.see(tk.END)
