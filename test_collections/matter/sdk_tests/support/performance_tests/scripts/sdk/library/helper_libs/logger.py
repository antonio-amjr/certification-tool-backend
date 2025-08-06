import logging
import inspect
import sys
import os
import traceback
from abc import ABC, abstractmethod

root_log = logging.getLogger()
logging.root.setLevel(logging.NOTSET)
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.NOTSET)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(funcName)s:%(lineno)s - %(message)s')
console_handler.setFormatter(formatter)
root_log.addHandler(console_handler)

class qa_logger(object):
    
    def __init__(self, name=None) -> None:
        self.log = root_log

    def create_log_file(self,log_file_name):
        self.log_file_handler= logging.FileHandler(log_file_name)
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(name)s - %(message)s')
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(funcName)s:%(lineno)s - %(message)s')
        self.log_file_handler.setFormatter(formatter)
        self.log_file_handler.setLevel(logging.NOTSET)
        # Add the file handler to the logger
        self.log.addHandler(self.log_file_handler)
        return self.log_file_handler
    
    def close_log_file(self, log_file_handler):
        self.log.removeHandler(log_file_handler)
        log_file_handler.close()

    def get_logger(self):
        return self.log