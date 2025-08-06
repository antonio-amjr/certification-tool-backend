from .production_matter_device import ProductionMatterDevice

def create_dut_object(test_config):
    return ProductionMatterDevice(test_config)