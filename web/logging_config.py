import logging
import logging.handlers
from pathlib import Path
from concurrent_log_handler import ConcurrentRotatingFileHandler # Импортируем новый обработчик

class SocketIOHandler(logging.Handler):
    """Кастомный обработчик для отправки логов через Socket.IO."""
    def emit(self, record):
        try:
            from web.app import socketio
            # Форматируем сообщение
            msg = self.format(record)
            # Отправляем событие 'new_log' клиентам
            socketio.emit('new_log', {
                'message': msg,
                'level': record.levelname
            })
        except (ImportError, Exception):
            # Если socketio еще не инициализирован или произошла другая ошибка,
            # просто игнорируем, чтобы не вызвать рекурсивную ошибку логирования.
            pass

def setup_logging():
    """Настраивает систему логирования."""
    log_dir = Path(__file__).parent.parent / 'logs'
    log_dir.mkdir(exist_ok=True)
    log_file = log_dir / 'workflow.log'

    # Форматтер для всех обработчиков
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # Получаем корневой логгер и устанавливаем уровень
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    # Убираем все существующие обработчики, чтобы избежать дублирования
    if root_logger.hasHandlers():
        root_logger.handlers.clear()

    # 1. Обработчик для записи в файл (ConcurrentRotatingFileHandler)
    file_handler = ConcurrentRotatingFileHandler(
        log_file, maxBytes=1*1024*1024, backupCount=5, encoding='utf-8'
    )
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)

    # 2. Обработчик для вывода в консоль
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # 3. Обработчик для отправки через Socket.IO
    socketio_handler = SocketIOHandler()
    socketio_handler.setFormatter(formatter) # Используем тот же форматтер
    root_logger.addHandler(socketio_handler)

    root_logger.info("Система логирования настроена (файл, консоль, WebSocket).")
