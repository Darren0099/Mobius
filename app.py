"""Windows desktop entrypoint for the Mobius file studio."""
import sys
import traceback
from pathlib import Path


def crash_logger(error_type, error, tb):
    if issubclass(error_type, KeyboardInterrupt):
        return sys.__excepthook__(error_type, error, tb)
    target = Path.home() / 'Documents' / 'Mobius'
    target.mkdir(parents=True, exist_ok=True)
    message = ''.join(traceback.format_exception(error_type, error, tb))
    with (target / 'mobius-error.log').open('a', encoding='utf-8') as log:
        log.write(message + '\n')
    if sys.platform == 'win32':
        import ctypes
        ctypes.windll.user32.MessageBoxW(0,
            f'Gagal menjalankan Mobius. Detail: {target / "mobius-error.log"}\n\n{str(error)[:300]}',
            'Mobius Error', 0x10)
    else:
        print(message, file=sys.stderr)


sys.excepthook = crash_logger

if __name__ == '__main__':
    from mobius.ui import start
    start()
