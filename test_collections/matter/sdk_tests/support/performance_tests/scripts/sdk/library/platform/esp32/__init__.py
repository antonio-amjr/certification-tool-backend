from .esp32 import Esp32Dut

def create_dut_object(test_config):
    return Esp32Dut(test_config)