from .nordic import NordicDut

def create_dut_object(test_config):
    return NordicDut(test_config)