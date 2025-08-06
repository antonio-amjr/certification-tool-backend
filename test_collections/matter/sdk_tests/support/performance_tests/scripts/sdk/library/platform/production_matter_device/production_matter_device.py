import logging

from matter_qa.library.base_test_classes.dut_base_class import BaseDutNodeClass

global log
log = logging.getLogger("DUT_platform") 


class ProductionMatterDevice(BaseDutNodeClass):
    def __init__(self, test_config, *args, **kwargs) -> None:
        super().__init__()
        self.test_config = test_config
        self.dut_config = test_config.dut_config.production_matter_device

    def start_test(self, *args, **kwargs):
        log.info("Starting test on production Matter device.")

    def factory_reset_dut(self, *args, **kwargs):
        log.warning("Performing factory reset on production Matter device is currently not supported.")

    def reboot_dut(self, *args, **kwargs):
        log.warning("Rebooting production Matter device is currently not supported.")

    def start_matter_app(self, *args, **kwargs):
        log.warning("Starting Matter application on production device is currently not supported.")

    def start_logging(self, file_name, *args, **kwargs):
        log.warning(f"Starting logging to {file_name} on production Matter device is currently not supported.")

    def stop_logging(self, *args, **kwargs):
        log.warning("Stopping logging on production Matter device is currently not supported.")

    def pre_iteration_loop(self, *args, **kwargs):
        log.warning("Executing pre-iteration setup on production device is currently not supported.")

    def post_iteration_loop(self, *args, **kwargs):
        log.warning("Executing post-iteration cleanup on production device is currently not supported.")

    def end_test(self, *args, **kwargs):
        log.info("Ending test on production Matter device.")