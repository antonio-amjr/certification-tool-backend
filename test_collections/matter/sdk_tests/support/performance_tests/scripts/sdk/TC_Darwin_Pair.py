#
#
#  Copyright (c) 2023 Project CHIP Authors
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#  http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#
import datetime
import logging
import os
import random
import sys

import chip.clusters as Clusters

sys.path.insert(
    0,
    os.path.abspath(
        os.path.join(os.path.dirname(os.path.realpath(__file__)), "../../../")
    ),
)
from chip.clusters.Types import NullValue
from chip.testing.decorators import async_test_body
from chip.testing.timeoperations import utc_time_in_matter_epoch

from .library.base_test_classes.matter_qa_base_test_class import (
    MatterQABaseTestCaseClass,
)
from .library.base_test_classes.test_results_record import TestResultEnums
from .library.helper_libs.augmented_matter_test_base import run_augmented_matter_tests
from .library.helper_libs.pairing_flow_functions import PairingFlowFunctions

log = logging.getLogger("base_tc")


class TC_Darwin_Pair(PairingFlowFunctions):
    def __init__(self, *args):
        # Todo move this into some meta data
        self.test_suite_name = "StressTestSuite"
        self.tc_name = "Darwin_Pair"
        self.tc_id = "stress_1_6"
        super().__init__(*args)
        self.manual_code = self.get_manual_pairing_code()
        self.track_test_step = True
        # This varbile indicates the commissioning status of the TH2

    def pics_TC_pair_unpair(self) -> list[str]:
        return ["STRESS.S"]

    def desc_TC_pair_unpair(self) -> str:
        return "#.#.#. [TC-Pair_Unpair] Stress Test "

    def create_2nd_controller(self):
        """
        create a second controller object to be used later in the pairing flow
        """
        th2_certificate_authority = (
            self.certificate_authority_manager.NewCertificateAuthority()
        )
        th2_fabric_admin = th2_certificate_authority.NewFabricAdmin(
            vendorId=0xFFF1, fabricId=self.th1.fabricId + 1
        )
        log.info(f"The 2nd fabric is {self.th1.fabricId + 1}")
        self.dutNodeIdOn2ndFabric = self.dut_node_id + 1
        self.th2NodeId = self.th1.nodeId + 1
        self.th2 = th2_fabric_admin.NewController(nodeId=self.th2NodeId)
        self.th2.name = "2nd Commissioner"

    async def read_basicinformation_attributes(self, *args, **kwargs):
        self.print_test_steps("Read Breadcrumb from General Commissioning(0x0030)")
        await self.read_single_attribute(
            self.th1,
            self.dut_node_id,
            0,
            Clusters.GeneralCommissioning.Attributes.Breadcrumb,
        )

        self.print_test_steps(
            "Read BasicCommissioningInfo from General Commissioning(0x0030)"
        )
        await self.read_single_attribute(
            self.th1,
            self.dut_node_id,
            0,
            Clusters.GeneralCommissioning.Attributes.BasicCommissioningInfo,
        )

        self.print_test_steps(
            "Read RegulatoryConfig from General Commissioning(0x0030)"
        )
        await self.read_single_attribute(
            self.th1,
            self.dut_node_id,
            0,
            Clusters.GeneralCommissioning.Attributes.RegulatoryConfig,
        )

        self.print_test_steps(
            "Read LocationCapability from General Commissioning(0x0030)"
        )
        await self.read_single_attribute(
            self.th1,
            self.dut_node_id,
            0,
            Clusters.GeneralCommissioning.Attributes.LocationCapability,
        )

        self.print_test_steps("Read VendorID from Basic Information(0x0028)")
        await self.read_single_attribute(
            self.th1, self.dut_node_id, 0, Clusters.BasicInformation.Attributes.VendorID
        )

        self.print_test_steps("Read ProductID from Basic Information(0x0028)")
        await self.read_single_attribute(
            self.th1,
            self.dut_node_id,
            0,
            Clusters.BasicInformation.Attributes.ProductID,
        )

        self.print_test_steps(
            "Read ConnectMaxTimeSeconds from Netwrorking cluster (0x0031)"
        )
        await self.read_single_attribute(
            self.th1,
            self.dut_node_id,
            0,
            Clusters.NetworkCommissioning.Attributes.ConnectMaxTimeSeconds,
        )

        self.print_test_steps("Read All attributes from  TimeSync(0x0038)")
        await self.th1.ReadAttribute(
            self.dut_node_id, [(0, Clusters.TimeSynchronization)], fabricFiltered=True
        )

    async def read_icdclustermgmt_attributes(self, *args, **kwargs):
        self.print_test_steps(
            "Read SupportsConcurrentConnection from General Commissioning(0x0030)"
        )
        await self.read_single_attribute(
            self.th1,
            self.dut_node_id,
            0,
            Clusters.GeneralCommissioning.Attributes.SupportsConcurrentConnection,
        )

        self.print_test_steps("Read IdleModeDuration from ICDClusterMgmt (0x0046)")
        await self.read_single_attribute(
            self.th1,
            self.dut_node_id,
            0,
            Clusters.IcdManagement.Attributes.IdleModeDuration,
        )

        self.print_test_steps("Read ActiveModeDuration from ICDClusterMgmt (0x0046)")
        await self.read_single_attribute(
            self.th1,
            self.dut_node_id,
            0,
            Clusters.IcdManagement.Attributes.ActiveModeDuration,
        )

        self.print_test_steps("Read ActiveModeThreshold from ICDClusterMgmt (0x0046)")
        await self.read_single_attribute(
            self.th1,
            self.dut_node_id,
            0,
            Clusters.IcdManagement.Attributes.ActiveModeThreshold,
        )

        self.print_test_steps(
            "Read UserActiveModeTriggerInstruction from ICDClusterMgmt (0x0046)"
        )
        await self.read_single_attribute(
            self.th1,
            self.dut_node_id,
            0,
            Clusters.IcdManagement.Attributes.UserActiveModeTriggerInstruction,
        )

    async def read_descriptor_cluster_attributes(self, *args, **kwargs):
        await self.read_partsList_attribute()
        await self.read_serverlist_attribute()

    async def read_networking_cluster_atrributes(self, *args, **kwargs):
        await self.read_network_commissiong_featuremap_attribute()
        await self.read_basicinformation_attributes()
        await self.read_icdclustermgmt_attributes()

    async def send_timesyncronization_commands(self, *args, **kwargs):
        await self.send_setregulatoryconfig_command(
            newregulatoryconfig=Clusters.GeneralCommissioning.Enums.RegulatoryLocationTypeEnum.kIndoor,
            countrycode="XX",
            breadcrumb=5,
        )
        await self.send_setutctime_command(
            utctime=utc_time_in_matter_epoch(),
            granularity=Clusters.TimeSynchronization.Enums.GranularityEnum.kSecondsGranularity,
        )
        await self.send_settimezone_command(
            timezone=[
                Clusters.Objects.TimeSynchronization.Structs.TimeZoneStruct(
                    offset=7200, validAt=0
                )
            ]
        )
        await self.send_setdstoffset_command(
            dstoffset=[
                Clusters.Objects.TimeSynchronization.Structs.DSTOffsetStruct(
                    offset=0, validStarting=0, validUntil=NullValue
                )
            ]
        )

    @async_test_body
    async def test_TC_darwin_pair_unpair(self):
        self.perform_initial_factory_reset()  # Perform initial factory reset as per the configuration
        self.print_step(0, "Device Factory Reset completed and Commission Ready")
        self.create_2nd_controller()

        @MatterQABaseTestCaseClass.iterate_tc(
            iterations=self.test_config.general_configs.number_of_iterations
        )
        async def tc_darwin_pair_unpair(*args, **kwargs):
            if self.do_factory_reset_every_iteration():
                await self.perform_factory_reset_dut()  # perform factory reset on DUT before starting the pairing operation
            time_before_starting_pairing = datetime.datetime.now()
            await self.generate_and_update_default_node_id(0)
            async with self.PaseSession(
                pairing_class_object_reference=self
            ) as pase_session:
                # pairing operation with DUT begins.
                log.info("TH1 has been established the pase session with the DUT")
                await self.read_descriptor_cluster_attributes()
                await self.read_networking_cluster_atrributes()
                await self.send_armfailsafe_command(
                    expirylengthseconds=60, breadcrumb=4
                )
                await self.send_timesyncronization_commands()
                # Connect_network function will add or update the network based on their commissioning type
                await self.connect_network(dut_commission_type=self.dut_commission_type)
                await self.send_certificatechainrequest_command(
                    certificatetype=Clusters.Objects.OperationalCredentials.Enums.CertificateChainTypeEnum.kPAICertificate
                )
                await self.send_certificatechainrequest_command(
                    certificatetype=Clusters.Objects.OperationalCredentials.Enums.CertificateChainTypeEnum.kDACCertificate
                )

                await self.send_attestationrequest_command(nonce=random.randbytes(32))
                await self.send_armfailsafe_command(
                    expirylengthseconds=60, breadcrumb=14
                )
                chainForAddNOC = await self.send_csrequest_command(
                    nonce=random.randbytes(32),
                    updatenoc=False,
                    admin=self.th1,
                    dut_node_id=self.dut_node_id,
                    endpoint=0,
                )
                await self.send_addtrustedrootcertificate_command(
                    chainForAddNOC=chainForAddNOC
                )
                await self.send_addnoc_command(
                    chainForAddNOC=chainForAddNOC, admin_nodeid=self.th1.nodeId
                )

            async with self.CaseSession(
                pairing_class_object_reference=self,
                failure_handler=self.cleanup_and_unpair_sessions,
            ) as case_session:
                await self.send_commissioningcomplete_command(
                    admin=self.th1, dut_node_id=self.dut_node_id, endpoint=0
                )
                self.list_of_commissioned_controller.append(
                    (self.th1, self.dut_node_id)
                )

                subject_1_id = self.th1.nodeId
                subject_2_id = self.th2.nodeId
                write_data_for_acl = [
                    Clusters.AccessControl.Structs.AccessControlEntryStruct(
                        privilege=Clusters.AccessControl.Enums.AccessControlEntryPrivilegeEnum.kAdminister,
                        authMode=Clusters.AccessControl.Enums.AccessControlEntryAuthModeEnum.kCase,
                        subjects=[subject_1_id, subject_2_id],
                        targets=NullValue,
                    )
                ]
                await self.write_operation_on_acl_cluster(
                    admin=self.th1,
                    dut_node_id=self.dut_node_id,
                    write_data_for_acl=write_data_for_acl,
                )
                await self.read_acl_attribute(
                    admin=self.th1, dut_node_id=self.dut_node_id
                )
                th1_subscription = await self.send_subscriberequest(
                    admin=self.th1,
                    dut_node_id=self.dut_node_id,
                    minintervalfloorseconds=0,
                    maxintervalceilingseconds=258,
                )
                await self.read_fabric_attribute(
                    admin=self.th1, dut_node_id=self.dut_node_id
                )
                await self.send_armfailsafe_command(
                    expirylengthseconds=30, breadcrumb=0
                )
                csrForAddNOC = await self.th1.SendCommand(
                    self.dut_node_id,
                    0,
                    Clusters.OperationalCredentials.Commands().CSRRequest(
                        CSRNonce=os.urandom(32)
                    ),
                )
                chainForAddNOC2 = await self.th2.IssueNOCChain(
                    csrForAddNOC, self.dutNodeIdOn2ndFabric
                )
                await self.send_addtrustedrootcertificate_command(
                    chainForAddNOC=chainForAddNOC2
                )
                await self.send_addnoc_command(
                    chainForAddNOC=chainForAddNOC2, admin_nodeid=self.th2NodeId
                )
                await self.send_commissioningcomplete_command(
                    admin=self.th2, dut_node_id=self.dutNodeIdOn2ndFabric, endpoint=0
                )
                # Since the TH2 is commissioned, this variable is updated to the True
                self.list_of_commissioned_controller.append(
                    (self.th2, self.dutNodeIdOn2ndFabric)
                )
                await self.read_serial_number_attribute(
                    admin=self.th2, dut_node_id=self.dutNodeIdOn2ndFabric
                )
                partslist = await self.read_partsList_attribute(
                    admin=self.th1, dut_node_id=self.dut_node_id
                )
                await self.read_server_list_attribute_for_different_endpoints(
                    endpoints=partslist
                )
                await self.update_fabric_label(
                    admin=self.th1, dut_node_id=self.dut_node_id
                )
                await self.read_fabric_attribute(
                    admin=self.th1, dut_node_id=self.dut_node_id
                )
                th2_subscription = await self.send_subscriberequest(
                    admin=self.th2,
                    dut_node_id=self.dutNodeIdOn2ndFabric,
                    minintervalfloorseconds=0,
                    maxintervalceilingseconds=258,
                )
                await self.write_operation_on_acl_cluster(
                    admin=self.th2,
                    dut_node_id=self.dutNodeIdOn2ndFabric,
                    write_data_for_acl=write_data_for_acl,
                )

                await self.write_defaultotaproviders_attribute(
                    provider_node_id=self.th2.nodeId
                )
                await self.update_fabric_label(
                    admin=self.th2, dut_node_id=self.dutNodeIdOn2ndFabric
                )
                await self.read_fabric_attribute(
                    admin=self.th2, dut_node_id=self.dutNodeIdOn2ndFabric
                )
                time_after_pairing_completed = datetime.datetime.now()
                pairing_duration = (
                    time_after_pairing_completed - time_before_starting_pairing
                ).total_seconds()
                self.analytics_dict.update({"pairing_duration": pairing_duration})
                await self.fetch_analytics_from_dut()
                self.subscription_cleanup(th1_subscription, th2_subscription)
            # To cleanup the sessions and unpair the dut for both controllers
            self.delay_between_stress_test_operations()
            await self.cleanup_and_unpair_sessions()
            self.update_iteration_result(
                iteration_result=TestResultEnums.TEST_RESULT_PASS
            )

        await tc_darwin_pair_unpair(self)


if __name__ == "__main__":
    run_augmented_matter_tests(test_class=TC_Darwin_Pair)
if __name__ == "__main__":
    run_augmented_matter_tests(test_class=TC_Darwin_Pair)
