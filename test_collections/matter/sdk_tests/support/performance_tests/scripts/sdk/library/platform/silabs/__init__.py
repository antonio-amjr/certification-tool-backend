from .silabs import SilabsDUT

def create_dut_object(test_config):
    return SilabsDUT(test_config)