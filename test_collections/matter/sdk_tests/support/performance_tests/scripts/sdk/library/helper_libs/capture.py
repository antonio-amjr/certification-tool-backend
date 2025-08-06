import logging
import threading
from datetime import datetime, timezone
from pathlib import Path

from invoke.exceptions import UnexpectedExit
from matter_qa.library.helper_libs.ssh import SSH


log = logging.getLogger("capture")
log.propagate = True


class Capture:

    def __init__(self, platform: str, ssh: SSH):
        # The current time used for naming the file.
        self.now = datetime.now()
        self.platform_now = datetime.fromtimestamp(float(ssh.run("date +%s.%N").stdout), timezone.utc)
        # The platform of the script execution used for naming the file.
        self.platform = platform
        # Opened SSH connection to the device.
        self.ssh = ssh

    @property
    def capture_file(self) -> Path:
        """The full path of the file with the capture data."""
        raise NotImplementedError

    def start(self):
        """Starts the capture process. This method should be overridden in subclasses."""
        raise NotImplementedError

    def stop(self):
        """Stops the capture process. This method should be overridden in subclasses."""
        raise NotImplementedError

    def get_service_journal(self, service: str, path: Path):
        """Save the journal of the given service to a file.

        Args:
            service (str): The name of the service to get the journal for.
            path (Path): The path where the journal will be saved.
        """
        since = self.platform_now.strftime("%Y-%m-%d %H:%M:%S UTC")
        self.ssh.run(f"journalctl -u {service} -S '{since}' --output=short-unix --no-pager --no-hostname > {path}")

    def get_capture_file(self, destination: Path, compress: bool = True, delete: bool = True):
        """Downloads capture file from the DUT and then deletes it from the DUT.

        Args:
            destination (Path): The directory where the file will be downloaded.
            compress (bool): Compress the file before downloading it.
            delete (bool): Delete the file after downloading it from the DUT.
        """
        try:
            path = self.capture_file
            if compress:
                self.ssh.run(f"bzip2 {path}")
                path = path.with_suffix(path.suffix + ".bz2")
            destination_path = Path(destination) / path.name
            self.ssh.get(str(path), str(destination_path))
            if delete:
                self.ssh.remove(str(path))
            return destination_path
        except (FileNotFoundError, UnexpectedExit):
            log.error(f"{path} does not exist on the server", exc_info=True)


class TCPDumpCapture(Capture):

    @property
    def capture_file(self) -> Path:
        return Path("/tmp") / f"{self.platform}_tcpdump_{self.now.strftime('%Y-%m-%d_%H-%M-%S')}.pcap"

    def _capture(self):
        """
        Starts capturing network traffic on the DUT device using tcpdump. If tcpdump is already running,
        it stops the current process and restarts it to capture the network traffic again.
        """
        try:
            log.info(f"Starting TCP capture to {self.capture_file}")
            self.ssh.sudo(f"tcpdump -i any -w {self.capture_file} port not 22")
        except Exception:
            log.error("Failed to start TCP traffic capture", exc_info=True)

    def start(self):
        """Starts tcpdump on the DUT."""
        self.thread = threading.Thread(target=self._capture)
        self.thread.daemon = True
        self.thread.start()

    def stop(self):
        """Stops the tcpdump capture by killing the tcpdump process."""
        try:
            self.ssh.sudo("pkill tcpdump")
            self.ssh.sudo(f"chown {self.ssh.user} {self.capture_file}")
        except Exception:
            log.error("Failed to stop TCP traffic capture", exc_info=True)
        finally:
            self.thread.join()


class DBusCapture(Capture):

    @property
    def capture_file(self) -> Path:
        return Path("/tmp") / f"{self.platform}_dbus-monitor_{self.now.strftime('%Y-%m-%d_%H-%M-%S')}.pcap"

    def _capture(self):
        try:
            log.info(f"Starting D-Bus capture to {self.capture_file}")
            self.ssh.sudo(f"dbus-monitor --system --pcap > {self.capture_file}")
        except UnexpectedExit as e:
            # In case of SIGTERM, the process will exit with code 143.
            # This is expected behavior, so we can ignore it.
            if e.result.return_code != 143:
                raise
        except Exception:
            log.error("Failed to start D-Bus capture", exc_info=True)

    def start(self):
        self.thread = threading.Thread(target=self._capture)
        self.thread.daemon = True
        self.thread.start()

    def stop(self):
        try:
            self.ssh.sudo("pkill dbus-monitor")
            self.ssh.sudo(f"chown {self.ssh.user} {self.capture_file}")
        except Exception:
            log.error("Failed to stop D-Bus capture", exc_info=True)
        finally:
            self.thread.join()


class HCIDumpCapture(Capture):

    @property
    def capture_file(self) -> Path:
        return Path("/tmp") / f"{self.platform}_hcidump_{self.now.strftime('%Y-%m-%d_%H-%M-%S')}.hcidump"

    def _capture(self):
        try:
            log.info(f"Starting HCI capture to {self.capture_file}")
            self.ssh.sudo(f"hcidump --save-dump={self.capture_file}")
        except UnexpectedExit as e:
            # In case of SIGTERM, the process will exit with code 143 or -1
            # for some unknown reasons...
            # This is expected behavior, so we can ignore it.
            if e.result.return_code not in (-1, 143):
                raise
        except Exception:
            log.error("Failed to start HCI capture", exc_info=True)

    def start(self):
        self.thread = threading.Thread(target=self._capture)
        self.thread.daemon = True
        self.thread.start()

    def stop(self):
        try:
            self.ssh.sudo("pkill hcidump")
            self.ssh.sudo(f"chown {self.ssh.user} {self.capture_file}")
        except Exception:
            log.error("Failed to stop HCI capture", exc_info=True)
        finally:
            self.thread.join()


class BluezCapture(Capture):

    @property
    def capture_file(self) -> Path:
        return Path("/tmp") / f"{self.platform}_bluetoothd_{self.now.strftime('%Y-%m-%d_%H-%M-%S')}.log"

    def start(self):
        # The Bluetooth system service is managed by systemd, so we do not need
        # to start it anything here.
        pass

    def stop(self):
        try:
            self.get_service_journal("bluetooth", self.capture_file)
        except Exception:
            log.error("Failed to get Bluetooth system service logs", exc_info=True)


class WPASupplicantCapture(Capture):

    @property
    def capture_file(self) -> Path:
        return Path("/tmp") / f"{self.platform}_wpasupplicant_{self.now.strftime('%Y-%m-%d_%H-%M-%S')}.log"

    def start(self):
        try:
            self.ssh.sudo("wpa_cli log_level debug")
        except Exception:
            log.error("Failed to start WPA supplicant verbose logging", exc_info=True)

    def stop(self):
        try:
            self.ssh.sudo("wpa_cli log_level info")
        except Exception:
            log.error("Failed to stop WPA supplicant verbose logging", exc_info=True)
        try:
            self.get_service_journal("wpa_supplicant", self.capture_file)
        except Exception:
            log.error("Failed to get WPA supplicant system service logs", exc_info=True)
