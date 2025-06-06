from jarvis.main import JarvisAssistant
from jarvis.interfaces.chat_interface import ChatInterface


def main():
    assistant = JarvisAssistant(enable_voice=False, enable_terminal=False)
    chat = ChatInterface(assistant.process_input)
    chat.start()


if __name__ == "__main__":
    main()
