# debug_smtp.py
from aiosmtpd.controller import Controller
from aiosmtpd.handlers import Debugging
import time

def run():
    handler = Debugging()   # a handler that prints incoming messages to stdout
    controller = Controller(handler, hostname='smtp.gmail.com', port=587)
    controller.start()
    print("== Debug SMTP server STARTED on smtp.gmail.com ==")
    print("Press Ctrl+C in this terminal to stop the server.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping debug SMTP server...")
    finally:
        controller.stop()
        print("Stopped.")
        
if __name__ == "__main__":
    run()
