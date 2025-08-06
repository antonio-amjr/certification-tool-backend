from matter_qa.library.base_test_classes.otbr_base_class import OTBRBaseClass
from matter_qa.library.helper_libs.capture import TCPDumpCapture
from matter_qa.library.helper_libs.ssh import SSH, SSHConfig


class OTBR_ON_SHH(OTBRBaseClass):

    def __init__(self, test_config, *args, **kwargs):
        super().__init__()
        self.test_config = test_config
        if hasattr(test_config, "otbr_device_config") is False:
            raise ValueError("otbr_device_config argument is missing in the Nordic DUT config\
                                  otbr_device_config argument is must if the capture_tcpdump_on_otbr is set to True ")
        self.otbr_on_ssh_object = getattr(test_config.otbr_device_config, 'otbr_on_ssh')
        ssh_config = SSHConfig(self.otbr_on_ssh_object.otbr_device_hostname,
                               self.otbr_on_ssh_object.otbr_device_username,
                               self.otbr_on_ssh_object.otbr_device_password,
                               self.otbr_on_ssh_object.otbr_device_sudo_password)
        self.ssh_session = SSH(ssh_config)
        self.tcp_dump_object = TCPDumpCapture("OTBR_ON_SHH", self.ssh_session)

    def start_tcp_dump_capture(self, *args, **kwargs):
        self.tcp_dump_object.start()

    def stop_tcp_dump_capture(self, *args, **kwargs):
        self.tcp_dump_object.stop()

    def save_tcpdump_capture_file(self, *args, **kwargs):
        self.tcp_dump_object.get_capture_file(self.test_config.iter_log_path)
