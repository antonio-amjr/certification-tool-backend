from types import SimpleNamespace


class TestConfig(SimpleNamespace):
    def __init__(self, config_dict=None):
        if config_dict:
            for key, value in config_dict.items():
                if isinstance(value, dict):
                    setattr(self, key, TestConfig(value))
                else:
                    setattr(self, key, value)
        else:
            self.general_configs = {
                "platform_execution": "rpi",
                "number_of_iterations": 10,
                "continue_excution_on_fail": True,
                "logFilePath": ".",
                "analytics_parameters": ["pairing_duration_info", "heap_usage"],
            }
            self.dut_config = {
                "rpi": {
                    "rpi_hostname": "192.168.8.100",
                    "rpi_username": "ubuntu",
                    "rpi_password": "raspberrypi",
                    "app_config": {
                        "matter_app": "./chip-all-clusters-app --discriminator 3890 --passcode 45612378"
                    },
                }
            }
            self.test_case_config = {
                "TC_Pair": {"number_of_iterations": 3, "retry_count": 3}
            }
        self._validate_config()

    def _validate_config(self):
        # TODO run some validation here to chk config object
        pass
