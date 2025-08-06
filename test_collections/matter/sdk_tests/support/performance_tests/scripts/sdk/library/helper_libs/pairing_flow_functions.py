import secrets
import sys

import chip.clusters as Clusters
from mobly import signals

from ..base_test_classes.matter_qa_base_test_class import MatterQABaseTestCaseClass, log
from ..helper_libs.exceptions import IterationError, TestCaseExit
from ..helper_libs.utils import extract_extended_panid


class PairingFlowFunctions(MatterQABaseTestCaseClass):
    """
    Pairing Flow Functions class contains the functions for Matter QA testing( Pairing flow),
    inheriting from MatterQABaseTestCaseClass.
    """

    class PaseSession:
        """
        context manager class used to open Pase Session,
        this context manager will control the opening and closing the pase session making it easier
        for the user to close the connection and capture the exceptions during executions
        """

        def __init__(self, pairing_class_object_reference):
            self.pairing_class_object_reference = pairing_class_object_reference

        async def __aenter__(self):
            """
            async entry point for the context manager where Pase session is extablished
            """
            try:
                await self.pairing_class_object_reference.establish_pasesession()
                log.info("Entering PASE session...")
            except Exception as e:
                log.error(f"Failed to establish pase session: {e}")
                raise IterationError(f"Failed to establish pase session: {e}")

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            """
            async exit point for the context manager where Pase session is closed
            """
            self.pairing_class_object_reference.close_session()
            if exc_type is not None:
                raise IterationError(exc_val)
            log.info("Exiting PASE session cleanly.")
            return False  # we need to always set this to False so that higher functions can catch the exceptions

    class CaseSession:
        """
        context manager class used to open Case Session, user can use this context manager to perform read/write operations
        allowed by DUT after Pase session

        """

        def __init__(
            self,
            pairing_class_object_reference,
            failure_handler=None,
            final_callback=None,
        ):
            self.pairing_class_object_reference = pairing_class_object_reference
            self.failure_handler = failure_handler
            self.final_callback = final_callback

        async def __aenter__(self):
            """
            async entry point for the context manager where Case session is extablished
            """
            log.info("Entering CASE session...")

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            """
            async exit point for the context manager where Case session is closed
            """
            if exc_type is not None:
                log.error(f"Execption occured in case session: {exc_type}")
                if self.failure_handler is not None:
                    try:
                        await self.failure_handler()
                    except Exception as e:
                        log.error(f"Failed to execute the {self.failure_handler}: {e}")
                raise IterationError(exc_val)

            if self.final_callback is not None:
                await self.final_callback()

            log.info("Exiting CASE session cleanly.")
            return False

    def __init__(self, *args, **kwargs):
        super().__init__(*args)
        self.th1 = self.default_controller
        self.ble_wifi_commission_bit = 1
        self.ble_thread_commission_bit = 2
        self.on_network_commission_bit = 4
        self.manual_code = None
        self.track_test_step = False
        self.list_of_commissioned_controller = []

    def print_test_steps(self, message=None, *args, **kwargs):
        """
        Print the test steps for the debugging and tracking purpose.
        """
        if self.track_test_step is True and message is not None:
            self.test_step_number += 1
            self.print_step(
                f"{self.test_config.current_iteration}-{self.test_step_number}", message
            )

    def get_manual_pairing_code(self, *args, **kwargs):
        """
        Extract the manual code from the config.
        """
        try:
            test_case_config = getattr(self.test_config, "test_case_config")
            test_case_specific_config = getattr(test_case_config, type(self).__name__)
            manual_code = test_case_specific_config.manual_code
        except Exception as e:
            log.error("Please add the Manual_code in config file")
            self.end_of_test(test_aborted=True)
            raise signals.TestAbortAll("Manual_code is missing in the config file")
        return manual_code

    async def generate_and_update_default_node_id(self, config_node_id_index: int):
        """
        Generate the Random Node_id
        """
        default_config = self.matter_test_config
        new_random_node_id = secrets.randbelow(2**32)
        default_config.dut_node_ids[config_node_id_index] = new_random_node_id

    async def establish_pasesession(self, *args, **kwargs):
        """
        To estabish a new pase sesssion using the Manual code
        """
        if self.manual_code is not None:
            self.th1_pasesession = await self.th1.EstablishPASESession(
                str(self.manual_code), self.dut_node_id
            )
            return True
        raise TestCaseExit(
            "Manual pairing code is not found, cannot establish the pase session \
                           hence exiting the test case."
        )

    async def send_armfailsafe_command(self, *args, **kwargs):
        """
        Send ArmFailSafe CMD from General Commissioning(0x0030)
        """
        self.print_test_steps("Send ArmFailSafe ")
        expirylengthseconds = kwargs["expirylengthseconds"]
        breadcrumb = kwargs["breadcrumb"]
        armfailsafe_cmd = await self.send_single_cmd(
            cmd=Clusters.GeneralCommissioning.Commands.ArmFailSafe(
                expiryLengthSeconds=expirylengthseconds, breadcrumb=breadcrumb
            ),
            dev_ctrl=self.th1,
            node_id=self.dut_node_id,
            endpoint=0,
        )
        if armfailsafe_cmd.errorCode != 0:
            raise IterationError(
                f"ArmFailSafe command failed with {armfailsafe_cmd.errorCode}"
            )

    async def send_setregulatoryconfig_command(self, *args, **kwargs):
        """
        Send SetRegulatoryConfig CMD from General Commissioning(0x0030)
        """
        self.print_test_steps("Send SetRegulatoryConfig CMD( 0,'XX', breadcrumb as 5)")
        newregulatoryconfig = kwargs["newregulatoryconfig"]
        countrycode = kwargs["countrycode"]
        breadcrumb = kwargs["breadcrumb"]
        setregulatory_cmd = await self.send_single_cmd(
            Clusters.GeneralCommissioning.Commands.SetRegulatoryConfig(
                newRegulatoryConfig=newregulatoryconfig,
                countryCode=countrycode,
                breadcrumb=breadcrumb,
            ),
            self.th1,
            self.dut_node_id,
            0,
        )
        if (
            setregulatory_cmd.errorCode
            is not Clusters.GeneralCommissioning.Enums.CommissioningErrorEnum.kOk
        ):
            raise IterationError(
                f"SetRegulatoryConfig command failed with {setregulatory_cmd.errorCode}"
            )

    async def send_setutctime_command(self, *args, **kwargs):
        """
        Send SetUTCTime CMD from General Commissioning(0x0030)
        """
        try:
            self.print_test_steps("Send SetUTCTime (UTCTime, 2 as SecondsGranularity)")
            utctime = kwargs["utctime"]
            granularity = kwargs["granularity"]
            await self.send_single_cmd(
                Clusters.TimeSynchronization.Commands.SetUTCTime(
                    UTCTime=utctime, granularity=granularity
                ),
                self.th1,
                self.dut_node_id,
                0,
            )

        except Exception as e:
            log.error(e)

    async def send_settimezone_command(self, *args, **kwargs):
        """
        Send SetTimeZone (list of timezonestruct) from  TimeSync(0x0038)
        """
        try:
            self.print_test_steps("Send SetTimeZone (UTCTime, 2 as SecondsGranularity)")
            timezone = kwargs["timezone"]
            await self.send_single_cmd(
                Clusters.TimeSynchronization.Commands.SetTimeZone(timeZone=timezone),
                self.th1,
                self.dut_node_id,
                0,
            )
        except Exception as e:
            log.error(e)

    async def send_setdstoffset_command(self, *args, **kwargs):
        """
        Send SetDSTOffset CMD from TimeSync(0x0038)
        """
        try:
            self.print_test_steps("Send SetDSTOffset command")
            dstoffset = kwargs["dstoffset"]
            await self.send_single_cmd(
                Clusters.TimeSynchronization.Commands.SetDSTOffset(DSTOffset=dstoffset),
                self.th1,
                self.dut_node_id,
                0,
            )
        except Exception as e:
            log.error(e)

    async def send_certificatechainrequest_command(self, *args, **kwargs):
        """
        Send CertificateChainRequest CMD from OperationalCredentials
        """
        self.print_test_steps("Send CertificateChainRequest (0x02) ")
        certificatetype = kwargs["certificatetype"]
        await self.send_single_cmd(
            Clusters.OperationalCredentials.Commands.CertificateChainRequest(
                certificateType=certificatetype
            ),
            self.th1,
            self.dut_node_id,
            0,
        )

    async def send_attestationrequest_command(self, *args, **kwargs):
        """
        Send AttestationRequest (0x00) from OperationalCredendials (0x3e)
        """
        self.print_test_steps(
            "Send CAttestationRequest (0x00) from OperationalCredendials (0x3e) "
        )
        nonce = kwargs["nonce"]
        await self.send_single_cmd(
            Clusters.OperationalCredentials.Commands.AttestationRequest(
                attestationNonce=nonce
            ),
            self.th1,
            self.dut_node_id,
            0,
        )

    async def send_csrequest_command(self, *args, **kwargs):
        """
        Send a CSR request (CMD 04) from OperationalCredendials (0x3e)
        """
        self.print_test_steps("Send a CSR request (CMD 04) from OperationalCredendials")
        nonce = kwargs["nonce"]
        updatenoc = kwargs["updatenoc"]
        admin = kwargs.get("admin", self.th1)
        dut_node_id = kwargs.get("dut_node_id", self.dut_node_id)
        endpoint = kwargs["endpoint"]

        csr_request = await self.send_single_cmd(
            cmd=Clusters.OperationalCredentials.Commands.CSRRequest(
                CSRNonce=nonce, isForUpdateNOC=updatenoc
            ),
            dev_ctrl=admin,
            node_id=dut_node_id,
            endpoint=endpoint,
        )
        chainForAddNOC = await admin.IssueNOCChain(csr_request, dut_node_id)

        if (
            chainForAddNOC.rcacBytes is None
            or chainForAddNOC.icacBytes is None
            or chainForAddNOC.nocBytes is None
            or chainForAddNOC.ipkBytes is None
        ):
            raise IterationError("Failed to add the chainForAddNOC command")

        return chainForAddNOC

    async def send_addtrustedrootcertificate_command(self, *args, **kwargs):
        """
        Send a AddTrustedRootCertificate (0xb)  from OperationalCredendials (0x3e)
        """
        self.print_test_steps(
            "Send a  AddTrustedRootCertificate (0xb) from OperationalCredendials"
        )
        chainForAddNOC = kwargs["chainForAddNOC"]
        await self.send_single_cmd(
            cmd=Clusters.OperationalCredentials.Commands.AddTrustedRootCertificate(
                rootCACertificate=chainForAddNOC.rcacBytes
            ),
            dev_ctrl=self.th1,
            node_id=self.dut_node_id,
            endpoint=0,
        )

    async def send_addnoc_command(self, *args, **kwargs):
        """
        Send AddNoC(0x06) from OperationalCredendials (0x3e)
        """
        self.print_test_steps("Send AddNoC(0x06) from OperationalCredendials (0x3e) ")
        chainForAddNOC = kwargs["chainForAddNOC"]
        caseadmin = kwargs["admin_nodeid"]
        addnoc = await self.send_single_cmd(
            cmd=Clusters.OperationalCredentials.Commands.AddNOC(
                NOCValue=chainForAddNOC.nocBytes,
                ICACValue=chainForAddNOC.icacBytes,
                IPKValue=chainForAddNOC.ipkBytes,
                caseAdminSubject=caseadmin,
                adminVendorId=0xFFF1,
            ),
            dev_ctrl=self.th1,
            node_id=self.dut_node_id,
            endpoint=0,
        )
        if (
            addnoc.statusCode
            is not Clusters.OperationalCredentials.Enums.NodeOperationalCertStatusEnum.kOk
        ):
            raise IterationError(f"AddNoC command failed with {addnoc.statusCode}")

    async def send_commissioningcomplete_command(self, *args, **kwargs):
        """
        Send CommissioningComplete (CMD 4) from General Commissioning(0x0030)
        """
        self.print_test_steps(
            "Send CommissioningComplete (CMD 4) from General Commissioning(0x0030) "
        )
        admin = kwargs.get("admin", self.th1)
        dut_node_id = kwargs.get("dut_node_id", self.dut_node_id)
        endpoint = kwargs["endpoint"]
        commissioningcomplete = await self.send_single_cmd(
            cmd=Clusters.GeneralCommissioning.Commands.CommissioningComplete(),
            dev_ctrl=admin,
            node_id=dut_node_id,
            endpoint=endpoint,
        )

        if (
            commissioningcomplete.errorCode
            is not Clusters.GeneralCommissioning.Enums.CommissioningErrorEnum.kOk
        ):
            raise IterationError(
                f"CommissioningComplete comand failed with {commissioningcomplete.errorCode}"
            )

    async def write_defaultotaproviders_attribute(self, *args, **kwargs):
        """
        Write DefaultOTAProviders Attribute from OtaSoftwareUpdateRequestor
        """
        provider_node_id = kwargs.get("provider_node_id", self.th1.nodeId)
        self.print_test_steps(
            "Write DefaultOTAProviders (0x0000) from OTA Software Update Requestor Cluster "
        )
        ota_update_write_data = [
            Clusters.OtaSoftwareUpdateRequestor.Structs.ProviderLocation(
                providerNodeID=provider_node_id, endpoint=0, fabricIndex=0x02
            )
        ]
        await self.write_single_attribute(
            attribute_value=Clusters.OtaSoftwareUpdateRequestor.Attributes.DefaultOTAProviders(
                ota_update_write_data
            ),
            endpoint_id=0,
            expect_success=False,
        )

    async def send_subscriberequest(self, *args, **kwargs):
        """
        SubscribeRequestMSg , with empty list of attribs and Urgent Events
        """
        self.print_test_steps(
            "SubscribeRequestMSg , with empty list of attribs and Urgent Events "
        )
        admin = kwargs.get("admin", self.th1)
        dut_node_id = kwargs.get("dut_node_id", self.dut_node_id)
        minintervalfloorseconds = kwargs["minintervalfloorseconds"]
        maxintervalceilingseconds = kwargs["maxintervalceilingseconds"]
        subscription = await admin.ReadAttribute(
            nodeid=dut_node_id,
            reportInterval=(minintervalfloorseconds, maxintervalceilingseconds),
            keepSubscriptions=False,
            attributes=[()],
        )
        return subscription

    async def read_fabric_attribute(self, *args, **kwargs):
        """
        Read Fabrics Attribute from OperationalCredentials
        """
        admin = kwargs.get("admin", self.th1)
        dut_node_id = kwargs.get("dut_node_id", self.dut_node_id)
        self.print_test_steps(
            f"Read Fabrics(0x01) from using node-id {dut_node_id} Node Operational Credential clusters(0x003E)"
        )

        await self.read_single_attribute(
            dev_ctrl=admin,
            node_id=dut_node_id,
            endpoint=0,
            attribute=Clusters.OperationalCredentials.Attributes.Fabrics,
        )

    async def read_serverlist_attribute(self, *args, **kwargs):
        """
        Read ServerList Attribute from Descriptor
        """
        self.print_test_steps("Read ServerList(0x0001) from Descriptor cluster(0x001D)")
        await self.read_single_attribute(
            self.th1, self.dut_node_id, 0, Clusters.Descriptor.Attributes.ServerList
        )

    async def read_network_commissiong_featuremap_attribute(self, *args, **kwargs):
        """
        Read FeatureMap Attribute from Netwrorking
        """
        self.print_test_steps(
            "Read FeatureMap (0x0000_FFFC) from Netwrorking cluster (0x0031)"
        )
        self.dut_commission_type = await self.read_single_attribute(
            self.th1,
            self.dut_node_id,
            0,
            Clusters.NetworkCommissioning.Attributes.FeatureMap,
        )

    async def connect_network(self, dut_commission_type, *args, **kwargs):
        """
        Establish a network connection for the DUT (Device Under Test) based on the specified commissioning type.

        This method handles the commissioning process for Wi-Fi, Thread, or On-Network types. Depending on the
        commissioning type, it sends the appropriate commands to add or update the network configuration, followed
        by a command to connect the device to the network.

        Args:
            dut_commission_type (int): Specifies the type of commissioning to perform. Possible values:
                - `self.ble_wifi_commission_bit`: Perform Wi-Fi commissioning.
                - `self.ble_thread_commission_bit`: Perform Thread commissioning.
                - `self.on_network_commission_bit`: Perform on-network commissioning.
            *args: Additional positional arguments (if any).
            **kwargs: Additional keyword arguments (if any).

        Raises:
            IterationError: If the connection to the network fails or the `ConnectNetwork` command returns a
                            non-success status.

        Notes:
            - Ensure `self.matter_test_config` is properly configured with valid Wi-Fi SSID, passphrase, and
            Thread operational dataset before invoking this method.
            - The `self.th1` device controller and `self.dut_node_id` must be correctly initialized.
        """

        if dut_commission_type == self.ble_wifi_commission_bit:
            self.print_test_steps("Send AddOrUpdateWiFiNetwork command")
            await self.send_single_cmd(
                Clusters.NetworkCommissioning.Commands.AddOrUpdateWiFiNetwork(
                    ssid=bytes(self.matter_test_config.wifi_ssid, "utf-8"),
                    credentials=bytes(self.matter_test_config.wifi_passphrase, "utf-8"),
                ),
                self.th1,
                self.dut_node_id,
                0,
                3000,
            )
            self.network_id = bytes(self.matter_test_config.wifi_ssid, "utf-8")
        elif dut_commission_type == self.ble_thread_commission_bit:
            self.print_test_steps("Send AddOrUpdateThreadNetwork command")
            await self.send_single_cmd(
                Clusters.NetworkCommissioning.Commands.AddOrUpdateThreadNetwork(
                    operationalDataset=self.matter_test_config.thread_operational_dataset
                ),
                self.th1,
                self.dut_node_id,
                0,
                3000,
            )
            x_panid = extract_extended_panid(
                self.matter_test_config.thread_operational_dataset
            )
            self.network_id = bytes.fromhex(x_panid)
        if dut_commission_type != self.on_network_commission_bit:
            self.print_test_steps("Send ConnectNetwork command")
            connect_network_response = await self.send_single_cmd(
                Clusters.NetworkCommissioning.Commands.ConnectNetwork(
                    networkID=self.network_id
                ),
                self.th1,
                self.dut_node_id,
                0,
                3000,
            )
            if (
                Clusters.NetworkCommissioning.Enums.NetworkCommissioningStatusEnum.kSuccess
                != connect_network_response.networkingStatus
            ):
                raise IterationError(
                    f"Failed Iteration as connecting to network Failed reason: {connect_network_response}"
                )

    async def read_networks_attribute(self, *args, **kwargs):
        """
        Read Networks Attribute from NetworkCommissioning
        """
        self.print_test_steps(
            "Read Networks (0x0001) from Netwrorking cluster (0x0031)"
        )
        await self.read_single_attribute(
            self.th1,
            self.dut_node_id,
            0,
            Clusters.NetworkCommissioning.Attributes.Networks,
        )

    async def send_announceotaprovider_command(self, *args, **kwargs):
        """
        Send AnnounceOTAProvider (0x0000) from OTA Software Update Requestor Cluster
        """
        self.print_test_steps(
            "Send AnnounceOTAProvider (0x0000) from OTA Software Update Requestor Cluster "
        )
        try:
            await self.send_single_cmd(
                dev_ctrl=self.th1,
                node_id=self.dut_node_id,
                timedRequestTimeoutMs=3000,
                cmd=Clusters.OtaSoftwareUpdateRequestor.Commands.AnnounceOTAProvider(
                    providerNodeID=self.th1.nodeId,
                    vendorID=0xFFF1,
                    announcementReason=Clusters.OtaSoftwareUpdateRequestor.Enums.AnnouncementReasonEnum.kSimpleAnnouncement,
                    endpoint=2,
                ),
            )
        except Exception as e:
            log.error(f"AnnounceOTAProvider is not implemented : {e}")

    async def read_vendorid_attribute(self, *args, **kwargs):
        """
        Read VendorID from Basic Information(0x0028)
        """
        self.print_test_steps("Read VendorID from Basic Information(0x0028)")
        await self.read_single_attribute(
            self.th1, self.dut_node_id, 0, Clusters.BasicInformation.Attributes.VendorID
        )

    async def read_productid_attribute(self, *args, **kwargs):
        """
        Read ProductID from Basic Information(0x0028)
        """
        self.print_test_steps("Read ProductID from Basic Information(0x0028)")
        await self.read_single_attribute(
            self.th1,
            self.dut_node_id,
            0,
            Clusters.BasicInformation.Attributes.ProductID,
        )

    async def read_commissionedfabrics_attribute(self, *args, **kwargs):
        """
        Read CommissionedFabrics from Node Operational Credential clusters(0x003E)
        """
        self.print_test_steps(
            "Read CommissionedFabrics from Node Operational Credential clusters(0x003E)"
        )

        await self.read_single_attribute(
            self.th1,
            self.dut_node_id,
            0,
            Clusters.OperationalCredentials.Attributes.CommissionedFabrics,
        )

    async def read_supportedFabrics_attribute(self, *args, **kwargs):
        """
        Read SupportedFabrics from Node Operational Credential clusters(0x003E)
        """
        self.print_test_steps(
            "Read SupportedFabrics from Node Operational Credential clusters(0x003E)"
        )

        await self.read_single_attribute(
            self.th1,
            self.dut_node_id,
            0,
            Clusters.OperationalCredentials.Attributes.SupportedFabrics,
        )

    async def read_locationcapability_attribute(self, *args, **kwargs):
        """
        Read LocationCapability from General Commissioning(0x0030)
        """
        self.print_test_steps(
            "Read LocationCapability from General Commissioning(0x0030)"
        )
        await self.read_single_attribute(
            self.th1,
            self.dut_node_id,
            0,
            Clusters.GeneralCommissioning.Attributes.LocationCapability,
        )

    async def read_windowstatus_attribute(self, *args, **kwargs):
        """
        Read WindowStatus from AdministratorCommissioning
        """
        self.print_test_steps("Read WindowStatus from AdministratorCommissioning")
        await self.read_single_attribute(
            self.th1,
            self.dut_node_id,
            0,
            Clusters.AdministratorCommissioning.Attributes.WindowStatus,
        )

    async def read_serialnumber_attribute(self, *args, **kwargs):
        """
        Read SerialNumber from Basic Information(0x0028)
        """
        self.print_test_steps("Read SerialNumber from Basic Information(0x0028)")
        await self.read_single_attribute(
            self.th1,
            self.dut_node_id,
            0,
            Clusters.BasicInformation.Attributes.SerialNumber,
        )

    async def send_setdefaultntp_command(self, *args, **kwargs):
        """
        Send SetTimeZone (list of timezonestruct) from  TimeSync(0x0038)
        """
        try:
            self.print_test_steps(
                "Send SetDefaultNTP (UTCTime, 2 as SecondsGranularity)"
            )
            await self.send_single_cmd(
                Clusters.TimeSynchronization.Commands.SetDefaultNTP(
                    defaultNTP="time.google.com"
                ),
                self.th1,
                self.dut_node_id,
                0,
            )
        except Exception as e:
            log.error(e)

    async def write_operation_on_acl_cluster(self, *args, **kwargs):
        """
        Write ACL (0x0000) attribute with the write_data in the kwargs
        """
        self.print_test_steps("Write ACL (0x0000) attribute ")
        write_data_for_acl = kwargs["write_data_for_acl"]
        admin = kwargs.get("admin", self.th1)
        dut_node_id = kwargs.get("dut_node_id", self.dut_node_id)
        enpoint = 0
        await admin.WriteAttribute(
            dut_node_id,
            [
                (enpoint, Clusters.AccessControl.Attributes.Acl([])),
                (enpoint, Clusters.AccessControl.Attributes.Acl(write_data_for_acl)),
            ],
            timedRequestTimeoutMs=3000,
        )

    async def read_acl_attribute(self, *args, **kwargs):
        """
        Read ACL (0x0000) attribute from ACL (0x001f)
        """
        self.print_test_steps("Read ACL (0x0000) attribute from ACL (0x001f) ")
        admin = kwargs.get("admin", self.th1)
        dut_node_id = kwargs.get("dut_node_id", self.dut_node_id)
        await self.read_single_attribute(
            dev_ctrl=admin,
            node_id=dut_node_id,
            endpoint=0,
            attribute=Clusters.AccessControl.Attributes.Acl,
        )

    async def read_serial_number_attribute(self, *args, **kwargs):
        # Read Serial Number Attrib (0x000F) from Basic Information Cluster (0x28)
        self.print_test_steps(
            "Read Serial Number Attrib (0x000F) from Basic Information Cluster (0x28)"
        )
        admin = kwargs.get("admin", self.th1)
        dut_node_id = kwargs.get("dut_node_id", self.dut_node_id)
        await self.read_single_attribute(
            dev_ctrl=admin,
            node_id=dut_node_id,
            endpoint=0,
            attribute=Clusters.BasicInformation.Attributes.SerialNumber,
        )

    async def read_partsList_attribute(self, *args, **kwargs):
        """
        Read PartsList (0x0003) from Descriptor Cluster (0x001d)
        """
        self.print_test_steps(
            "Read PartsList (0x0003) from Descriptor Cluster (0x001d)"
        )
        admin = kwargs.get("admin", self.th1)
        dut_node_id = kwargs.get("dut_node_id", self.dut_node_id)
        partslist = await self.read_single_attribute(
            dev_ctrl=admin,
            node_id=dut_node_id,
            endpoint=0,
            attribute=Clusters.Descriptor.Attributes.PartsList,
        )
        return partslist

    async def read_server_list_attribute_for_different_endpoints(
        self, endpoints: list, *args, **kwargs
    ):
        """
        Read ServerList (0x0001) from Descriptor Cluster (0x001d) on list of ENDPOINT
        """
        self.print_test_steps(
            "Read ServerList (0x0001) from Descriptor Cluster (0x001d) on list of ENDPOINT"
        )
        for endpoint in endpoints:
            await self.read_single_attribute(
                dev_ctrl=self.th1,
                node_id=self.dut_node_id,
                endpoint=endpoint,
                attribute=Clusters.Descriptor.Attributes.ServerList,
            )

    async def update_fabric_label(self, *args, **kwargs):
        """
        Send UpdateFabricLabel CMD (0x9) from using Node {dut_node_id} Operational Credentials Cluster (0x003e)
        """
        admin = kwargs.get("admin", self.th1)
        dut_node_id = kwargs.get("dut_node_id", self.dut_node_id)
        self.print_test_steps(
            f"Send UpdateFabricLabel CMD (0x9) from using Node {dut_node_id} Operational Credentials Cluster (0x003e)"
        )
        update_fabric_label_response = await self.send_single_cmd(
            dev_ctrl=admin,
            node_id=dut_node_id,
            timedRequestTimeoutMs=3000,
            cmd=Clusters.OperationalCredentials.Commands.UpdateFabricLabel(
                label="MyHome"
            ),
        )

    def subscription_cleanup(self, *args, **kwargs):
        """
        Shutdown all the subcription passed in args
        """
        for subscription in args:
            subscription.Shutdown()

    async def cleanup_and_unpair_sessions(self):
        """
        Unpair all commissioned controller and close their sessions
        """
        try:
            if not self.use_test_event_trigger_factory_reset:
                for controller_object, nodeid in self.list_of_commissioned_controller:
                    await self.unpair_dut(controller=controller_object, node_id=nodeid)
                    controller_object.CloseBLEConnection()

        except Exception as e:
            log.error(f"Failed to cleanup the sessions :{e}")
            raise IterationError(e)

        finally:
            self.list_of_commissioned_controller.clear()

    def close_session(self, *args, **kwargs):
        """
        Close the Controllers session
        """
        th = kwargs.get("admin", self.th1)
        node_id = kwargs.get("node_id", self.dut_node_id)
        th.ExpireSessions(node_id)
        th.CloseBLEConnection()
        th.CloseBLEConnection()
