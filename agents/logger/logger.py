"""
日志模块 - 提供统一的日志记录功能
"""

import os
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional


class Logger:
    """统一的日志记录器"""
    
    def __init__(self, log_path: str = "./logs"):
        """
        初始化日志记录器
        
        Args:
            log_path: 日志文件存储路径
        """
        self.log_path = Path(log_path)
        
        # 按当前年月日创建子文件夹
        today = datetime.now().strftime("%Y%m%d")
        self.daily_log_path = self.log_path / today
        self.daily_log_path.mkdir(parents=True, exist_ok=True)
        
        # 初始化四个不同级别的日志记录器
        self._init_loggers()
    
    def _init_loggers(self):
        """初始化四个不同级别的日志记录器"""
        # 日志格式
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        # 创建四个不同级别的日志记录器
        self.loggers = {}
        
        # INFO级别日志
        info_logger = logging.getLogger('info')
        info_logger.setLevel(logging.INFO)
        info_handler = logging.FileHandler(self.daily_log_path / 'info.log', encoding='utf-8')
        info_handler.setFormatter(formatter)
        info_logger.addHandler(info_handler)
        info_logger.propagate = False
        self.loggers['info'] = info_logger
        
        # WARNING级别日志
        warning_logger = logging.getLogger('warning')
        warning_logger.setLevel(logging.WARNING)
        warning_handler = logging.FileHandler(self.daily_log_path / 'warning.log', encoding='utf-8')
        warning_handler.setFormatter(formatter)
        warning_logger.addHandler(warning_handler)
        warning_logger.propagate = False
        self.loggers['warning'] = warning_logger
        
        # DEBUG级别日志
        debug_logger = logging.getLogger('debug')
        debug_logger.setLevel(logging.DEBUG)
        debug_handler = logging.FileHandler(self.daily_log_path / 'debug.log', encoding='utf-8')
        debug_handler.setFormatter(formatter)
        debug_logger.addHandler(debug_handler)
        debug_logger.propagate = False
        self.loggers['debug'] = debug_logger
        
        # ERROR级别日志
        error_logger = logging.getLogger('error')
        error_logger.setLevel(logging.ERROR)
        error_handler = logging.FileHandler(self.daily_log_path / 'error.log', encoding='utf-8')
        error_handler.setFormatter(formatter)
        error_logger.addHandler(error_handler)
        error_logger.propagate = False
        self.loggers['error'] = error_logger
    
    def info(self, message: str):
        """记录INFO级别日志"""
        self.loggers['info'].info(message)
        # 同时输出到控制台
        print(f"[INFO] {message}")
    
    def warning(self, message: str):
        """记录WARNING级别日志"""
        self.loggers['warning'].warning(message)
        # 同时输出到控制台
        print(f"[WARNING] {message}")
    
    def debug(self, message: str):
        """记录DEBUG级别日志"""
        self.loggers['debug'].debug(message)
        # 同时输出到控制台
        print(f"[DEBUG] {message}")
    
    def error(self, message: str):
        """记录ERROR级别日志"""
        self.loggers['error'].error(message)
        # 同时输出到控制台
        print(f"[ERROR] {message}")
    
    def get_log_path(self) -> str:
        """获取当前日志路径"""
        return str(self.daily_log_path)
