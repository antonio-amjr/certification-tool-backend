from .tizen import Tizen

def create_dut_object(test_config):
    return Tizen(test_config)
