from jarvis.main import JarvisAssistant
from jarvis.interfaces.chat_interface import ChatInterface
from jarvis.interfaces.terminal_interface import TerminalInterface


def main():
    assistant = JarvisAssistant(enable_voice=False, enable_terminal=False)
    try:
        chat = ChatInterface(assistant.process_input)
    except RuntimeError:
        # GUI not available; fallback to simple terminal interface
        term = TerminalInterface(callback=assistant.process_input)
        term.listen_loop()
        return
    chat.start()


if __name__ == "__main__":
    main()
