from abc import ABC, abstractmethod

class OTBRBaseClass(ABC):

    @abstractmethod
    def __init__(self):
        pass

    @abstractmethod
    def start_tcp_dump_capture(self, *args, **kwargs):
        pass

    @abstractmethod
    def stop_tcp_dump_capture(self, *args, **kwargs):
        pass

    @abstractmethod
    def save_tcpdump_capture_file(self, *args, **kwargs):
        pass

