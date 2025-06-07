import logging
import logging.handlers
from pythonjsonlogger import jsonlogger
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any
import sys
import os
from dataclasses import dataclass
import traceback

@dataclass
class LogConfig:
    """Configuración del sistema de logging"""
    level: str = "INFO"
    console_enabled: bool = True
    file_enabled: bool = True
    json_format: bool = True
    log_dir: str = "logs"
    max_file_size: int = 10 * 1024 * 1024  # 10MB
    backup_count: int = 5
    format_string: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

class CustomJsonFormatter(jsonlogger.JsonFormatter):
    """Formatter JSON personalizado con campos adicionales"""
    
    def add_fields(self, log_record: Dict[str, Any], record: logging.LogRecord, message_dict: Dict[str, Any]):
        super().add_fields(log_record, record, message_dict)
        
        # Agregar timestamp con formato específico
        log_record['timestamp'] = datetime.utcnow().isoformat() + 'Z'
        
        # Agregar información de contexto si está disponible
        if hasattr(record, 'scraper_context'):
            log_record['context'] = record.scraper_context
            
        # Agregar información de performance si está disponible
        if hasattr(record, 'duration'):
            log_record['duration_ms'] = record.duration
            
        # Agregar stack trace para errores
        if record.exc_info:
            log_record['exception'] = {
                'type': record.exc_info[0].__name__ if record.exc_info[0] else None,
                'message': str(record.exc_info[1]) if record.exc_info[1] else None,
                'traceback': traceback.format_exception(*record.exc_info)
            }

class ScrapingLogger:
    """Logger especializado para web scraping con contexto y métricas"""
    
    def __init__(self, name: str = "scraper", config: LogConfig = None):
        self.config = config or LogConfig()
        self.logger = logging.getLogger(name)
        self.context = {}
        
        # Evitar duplicar handlers si ya existen
        if not self.logger.handlers:
            self._setup_logger()
    
    def _setup_logger(self):
        """Configurar handlers y formatters"""
        self.logger.setLevel(getattr(logging, self.config.level.upper()))
        
        # Console handler
        if self.config.console_enabled:
            console_handler = self._create_console_handler()
            self.logger.addHandler(console_handler)
        
        # File handler
        if self.config.file_enabled:
            file_handler = self._create_file_handler()
            if file_handler:
                self.logger.addHandler(file_handler)
    
    def _create_console_handler(self) -> logging.Handler:
        """Crear handler para consola con colores y formato mejorado"""
        handler = logging.StreamHandler(sys.stdout)
        
        if self.config.json_format:
            formatter = CustomJsonFormatter(
                fmt='%(timestamp)s %(name)s %(levelname)s %(message)s'
            )
        else:
            # Formatter con colores para desarrollo
            class ColoredFormatter(logging.Formatter):
                COLORS = {
                    'DEBUG': '\033[36m',    # Cyan
                    'INFO': '\033[32m',     # Green
                    'WARNING': '\033[33m',  # Yellow
                    'ERROR': '\033[31m',    # Red
                    'CRITICAL': '\033[35m', # Magenta
                    'RESET': '\033[0m'      # Reset
                }
                
                def format(self, record):
                    color = self.COLORS.get(record.levelname, self.COLORS['RESET'])
                    record.levelname = f"{color}{record.levelname}{self.COLORS['RESET']}"
                    return super().format(record)
            
            formatter = ColoredFormatter(
                fmt='%(asctime)s | %(name)s | %(levelname)s | %(message)s',
                datefmt='%H:%M:%S'
            )
        
        handler.setFormatter(formatter)
        return handler
    
    def _create_file_handler(self) -> Optional[logging.Handler]:
        """Crear handler para archivos con rotación"""
        try:
            log_dir = Path(self.config.log_dir)
            log_dir.mkdir(parents=True, exist_ok=True)
            
            log_file = log_dir / f"scraper_{datetime.now().strftime('%Y%m%d')}.log"
            
            handler = logging.handlers.RotatingFileHandler(
                filename=log_file,
                maxBytes=self.config.max_file_size,
                backupCount=self.config.backup_count,
                encoding='utf-8'
            )
            
            formatter = CustomJsonFormatter(
                fmt='%(timestamp)s %(name)s %(levelname)s %(message)s'
            )
            handler.setFormatter(formatter)
            
            return handler
            
        except Exception as e:
            print(f"Error configurando file handler: {e}")
            return None
    
    def set_context(self, **kwargs):
        """Establecer contexto global para logs"""
        self.context.update(kwargs)
    
    def clear_context(self):
        """Limpiar contexto"""
        self.context.clear()
    
    def _add_context_to_record(self, record):
        """Agregar contexto al record de logging"""
        if self.context:
            record.scraper_context = self.context.copy()
    
    def debug(self, message: str, **kwargs):
        """Log debug con contexto"""
        record = self.logger.makeRecord(
            self.logger.name, logging.DEBUG, '', 0, message, (), None
        )
        self._add_context_to_record(record)
        for key, value in kwargs.items():
            setattr(record, key, value)
        self.logger.handle(record)
    
    def info(self, message: str, **kwargs):
        """Log info con contexto"""
        record = self.logger.makeRecord(
            self.logger.name, logging.INFO, '', 0, message, (), None
        )
        self._add_context_to_record(record)
        for key, value in kwargs.items():
            setattr(record, key, value)
        self.logger.handle(record)
    
    def warning(self, message: str, **kwargs):
        """Log warning con contexto"""
        record = self.logger.makeRecord(
            self.logger.name, logging.WARNING, '', 0, message, (), None
        )
        self._add_context_to_record(record)
        for key, value in kwargs.items():
            setattr(record, key, value)
        self.logger.handle(record)
    
    def error(self, message: str, exc_info=None, **kwargs):
        """Log error con información de excepción"""
        record = self.logger.makeRecord(
            self.logger.name, logging.ERROR, '', 0, message, (), exc_info
        )
        self._add_context_to_record(record)
        for key, value in kwargs.items():
            setattr(record, key, value)
        self.logger.handle(record)
    
    def critical(self, message: str, exc_info=None, **kwargs):
        """Log critical con información de excepción"""
        record = self.logger.makeRecord(
            self.logger.name, logging.CRITICAL, '', 0, message, (), exc_info
        )
        self._add_context_to_record(record)
        for key, value in kwargs.items():
            setattr(record, key, value)
        self.logger.handle(record)

class PerformanceLogger:
    """Logger especializado para métricas de performance"""
    
    def __init__(self, logger: ScrapingLogger):
        self.logger = logger
        self.start_time = None
    
    def start(self, operation: str):
        """Iniciar medición de tiempo"""
        self.start_time = datetime.now()
        self.operation = operation
        self.logger.info(f"Iniciando: {operation}")
    
    def end(self, success: bool = True, **kwargs):
        """Finalizar medición y registrar métricas"""
        if self.start_time:
            duration = (datetime.now() - self.start_time).total_seconds() * 1000
            status = "completado" if success else "falló"
            
            self.logger.info(
                f"{self.operation} {status}",
                duration=duration,
                **kwargs
            )
        else:
            self.logger.warning("PerformanceLogger.end() llamado sin start()")

# Instancia global del logger
_logger_instance = None

def get_logger(name: str = "scraper", config: LogConfig = None) -> ScrapingLogger:
    """Factory function para obtener logger configurado"""
    global _logger_instance
    
    if _logger_instance is None:
        _logger_instance = ScrapingLogger(name, config)
    
    return _logger_instance

def get_performance_logger(name: str = "scraper") -> PerformanceLogger:
    """Factory function para obtener performance logger"""
    base_logger = get_logger(name)
    return PerformanceLogger(base_logger)

# Context manager para logging con contexto temporal
class LogContext:
    """Context manager para establecer contexto temporal en logs"""
    
    def __init__(self, logger: ScrapingLogger, **context):
        self.logger = logger
        self.context = context
        self.original_context = None
    
    def __enter__(self):
        self.original_context = self.logger.context.copy()
        self.logger.set_context(**self.context)
        return self.logger
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.logger.context = self.original_context