from abc import ABC, abstractmethod

class BaseDutNodeClass(ABC):

    @abstractmethod
    def __init__(self):
        pass
    
    @abstractmethod
    def start_test(self, *args, **kwargs):
        pass

    @abstractmethod
    def reboot_dut(self, *args, **kwargs):
        pass

    @abstractmethod
    def factory_reset_dut(self, *args, **kwargs):
        pass

    @abstractmethod
    def start_matter_app(self, *args, **kwargs):
        pass

    @abstractmethod
    def start_logging(self, file_name, *args, **kwargs):
        pass

    @abstractmethod
    def stop_logging(self, *args, **kwargs):
        pass

    @abstractmethod
    def pre_iteration_loop(self, *args, **kwargs):
        pass

    @abstractmethod
    def post_iteration_loop(self, *args, **kwargs):
        pass

    @abstractmethod
    def end_test(self, *args, **kwargs):
        pass