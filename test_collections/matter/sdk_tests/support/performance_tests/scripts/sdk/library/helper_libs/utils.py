
import os
import sys
import io
import traceback
import yaml
import logging
log = logging.getLogger("utils")
DEFAULT_CONFIG_DIR = './Matter_QA/Configs/'

class TestConfig(object):
    def __init__(self, config_dict=None):
        if config_dict:
            for key, value in config_dict.items():
                if isinstance(value, dict):
                    setattr(self, key, TestConfig(value))
                else:
                    setattr(self, key, value)
        

def default_config_reader():
    try:
        config_yaml_file = os.path.join(DEFAULT_CONFIG_DIR, "configFile.yaml")
        if not os.path.exists(config_yaml_file):
            
            log.error("The config file does not exist! exiting now! ")
            sys.exit(0)
        with io.open(config_yaml_file, 'r') as f:
            test_config_dict = yaml.safe_load(f)
            test_config = TestConfig(test_config_dict)
        return test_config
    except Exception as e:
        log.error(e)
        traceback.print_exc()

def extract_extended_panid(thread_data_set: bytes):
    # Remove any spaces and convert to upper case
    hex_string = thread_data_set.hex().upper()

    # Check if the string length is a multiple of 2
    if len(hex_string) % 2 != 0:
        raise ValueError("Invalid hex string.")

    tlv_index_tracker = 0
    tlv_list = []

    for i in range(len(hex_string)+1):
        # Each component (Type, Length) takes 2 hex digits (1 byte)
        if tlv_index_tracker >= len(hex_string):
            break
        if tlv_index_tracker + 2 > len(hex_string):
            raise ValueError("Incomplete Type field at position {}".format(i))
        tlv_identifier = hex_string[tlv_index_tracker:tlv_index_tracker + 2]

        if tlv_index_tracker + 4 > len(hex_string):
            raise ValueError("Incomplete Length field at position {}".format(i + 2))
        tlv_data_length_hex = hex_string[tlv_index_tracker + 2:tlv_index_tracker + 4]

        # Convert length from hex to int (base 16)
        tlv_data_length_int = int(tlv_data_length_hex, 16)

        # Calculate the start and end of the Value
        tlv_data_length_start_index = tlv_index_tracker + 4
        tlv_data_length_end_index = tlv_data_length_start_index + tlv_data_length_int * 2

        if tlv_data_length_end_index > len(hex_string):
            raise ValueError("Value field out of range at position {}".format(tlv_data_length_start_index))

        tlv_data = hex_string[tlv_data_length_start_index:tlv_data_length_end_index]

        # Append the parsed TLV to the list
        tlv_list.append({'Type': tlv_identifier, 'Length': tlv_data_length_hex, 'Value': tlv_data})

        # Move to the next TLV block
        tlv_index_tracker = tlv_data_length_end_index

    for tlv_data in tlv_list:
        if tlv_data['Type'] == '02':
            return tlv_data['Value']