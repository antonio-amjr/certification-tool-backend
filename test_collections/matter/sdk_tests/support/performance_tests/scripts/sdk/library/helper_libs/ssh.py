import logging
from fabric import Connection, Config
from mobly import signals

log = logging.getLogger("ssh")

log.propagate = True


class SSHConfig:
    """
    Configuration class for SSH connection parameters.
    """

    def __init__(self, hostname: str, username: str, password: str, sudo_password: str):
        """
        Initializes the SSHConfig with the required connection details.

        - param: hostname: The hostname or IP address of the target device.
        - param: username: The username for the SSH connection.
        - param: password: The password for the SSH connection.
        """
        self.hostname = hostname
        self.username = username
        self.password = password
        self.sudo_password = sudo_password


class CallbackStream:
    def __init__(self, callback):
        self.callback = callback

    def write(self, data):
        self.callback(data)

    def flush(self):
        pass


class SSH(Connection):
    """Local wrapper for fabric.Connection to handle SSH connections."""

    def __init__(self, config: SSHConfig):
        try:
            super().__init__(
                host=config.hostname,
                user=config.username,
                config=Config(overrides={"sudo": {"password": config.sudo_password}}),
                connect_kwargs={"password": config.password})
        except Exception as e:
            raise signals.TestAbortAll(f"Could not establish SSH connection: {e}")

    def remove(self, remote: str):
        """Removes the file from the remote server."""
        sftp = self.sftp()
        sftp.remove(remote)
