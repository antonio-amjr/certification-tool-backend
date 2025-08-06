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
import time

import chip.clusters as Clusters

sys.path.insert(
    0,
    os.path.abspath(
        os.path.join(os.path.dirname(os.path.realpath(__file__)), "../../../")
    ),
)

from chip.clusters.Types import NullValue
from chip.testing.decorators import async_test_body

from .library.base_test_classes.matter_qa_base_test_class import (
    MatterQABaseTestCaseClass,
)
from .library.base_test_classes.test_results_record import TestResultEnums
from .library.helper_libs.augmented_matter_test_base import run_augmented_matter_tests
from .library.helper_libs.pairing_flow_functions import PairingFlowFunctions

log = logging.getLogger("base_tc")


class TC_Android_Pair(PairingFlowFunctions):
    def __init__(self, *args):
        # Todo move this into some meta data
        self.test_suite_name = "StressTestSuite"
        self.tc_name = "Android_Pair_Unpair"
        self.tc_id = "stress_1_7"
        super().__init__(*args)
        self.manual_code = self.get_manual_pairing_code()
        self.track_test_step = True

    def pics_TC_pair_unpair(self) -> list[str]:
        return ["STRESS.S"]

    def desc_TC_pair_unpair(self) -> str:
        return "#.#.#. [TC-Pair_Unpair] Stress Test "

    async def wildcard_read(self, *args, **kwargs):
        # SubscribeRequestMSg , with empty list of attribs and Urgent Events
        self.print_test_steps(
            "Read wildcard for the Cluster = 0x1d, Cluster = 0x28, Cluster = 0x39, Attribute = 0x0000_FFF9, Attribute = 0x0000_FFFB, Attribute = 0x0000_FFFC, Attribute = 0x0000_FFFD."
        )
        try:
            accept_cmd_wildcard = Clusters.Attribute.AttributePath(AttributeId=0xFFF9)
            attr_list_wildcard = Clusters.Attribute.AttributePath(AttributeId=0xFFFB)
            feature_map_wildcard = Clusters.Attribute.AttributePath(AttributeId=0xFFFC)
            cluster_rev_wildcard = Clusters.Attribute.AttributePath(AttributeId=0xFFFD)
            await self.th1.ReadAttribute(
                nodeid=self.dut_node_id,
                attributes=[
                    (Clusters.Descriptor),
                    (Clusters.BasicInformation),
                    (Clusters.BridgedDeviceBasicInformation),
                    accept_cmd_wildcard,
                    attr_list_wildcard,
                    feature_map_wildcard,
                    cluster_rev_wildcard,
                ],
            )
        except Exception as e:
            log.error(f"Cannot Perform read for Reason: {e}")

    @async_test_body
    async def test_TC_Android_pair_unpair(self):
        self.perform_initial_factory_reset()  # Perform initial factory reset as per the configuration
        self.print_step(0, "Device Factory Reset completed and Commission Ready")

        @MatterQABaseTestCaseClass.iterate_tc(
            iterations=self.test_config.general_configs.number_of_iterations
        )
        async def tc_Android_pair_unpair(*args, **kwargs):
            if self.do_factory_reset_every_iteration():
                await self.perform_factory_reset_dut()  # perform factory reset on DUT before starting the pairing operation
            time_before_starting_pairing = datetime.datetime.now()
            await self.generate_and_update_default_node_id(0)

            async with self.PaseSession(
                pairing_class_object_reference=self
            ) as pase_session:
                # pairing operation with DUT begins.
                log.info("TH1 has been established the pase session with the DUT")
                await self.read_serverlist_attribute()
                await self.read_network_commissiong_featuremap_attribute()
                await self.send_armfailsafe_command(
                    expirylengthseconds=120, breadcrumb=1
                )
                await self.read_vendorid_attribute()
                await self.read_productid_attribute()
                await self.read_commissionedfabrics_attribute()
                await self.read_supportedFabrics_attribute()
                await self.read_fabric_attribute()
                await self.send_certificatechainrequest_command(
                    certificatetype=Clusters.Objects.OperationalCredentials.Enums.CertificateChainTypeEnum.kDACCertificate
                )
                await self.read_serverlist_attribute()
                await self.read_network_commissiong_featuremap_attribute()
                await self.send_armfailsafe_command(
                    expirylengthseconds=120, breadcrumb=1
                )
                await self.read_locationcapability_attribute()
                await self.send_setregulatoryconfig_command(
                    newregulatoryconfig=Clusters.GeneralCommissioning.Enums.RegulatoryLocationTypeEnum.kIndoor,
                    countrycode="XX",
                    breadcrumb=1,
                )
                # Connect_network function will add or update the network based on their commissioning type
                await self.connect_network(dut_commission_type=self.dut_commission_type)
                await self.send_certificatechainrequest_command(
                    certificatetype=Clusters.Objects.OperationalCredentials.Enums.CertificateChainTypeEnum.kPAICertificate
                )
                await self.send_attestationrequest_command(nonce=random.randbytes(32))
                chainForAddNOC = await self.send_csrequest_command(
                    nonce=random.randbytes(32), updatenoc=False, endpoint=0
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
                await self.read_windowstatus_attribute()
                await self.read_serialnumber_attribute()
                await self.wildcard_read()
                await self.send_commissioningcomplete_command(endpoint=0)
                self.list_of_commissioned_controller.append(
                    (self.th1, self.dut_node_id)
                )
                th1_subscription = await self.send_subscriberequest(
                    minintervalfloorseconds=0,
                    maxintervalceilingseconds=258,
                )
                await self.send_settimezone_command(
                    timezone=[
                        Clusters.Objects.TimeSynchronization.Structs.TimeZoneStruct(
                            offset=7200, validAt=0
                        )
                    ]
                )
                await self.send_setdefaultntp_command()
                await self.write_defaultotaproviders_attribute()
                await self.send_announceotaprovider_command()
                await self.send_setdstoffset_command(
                    dstoffset=[
                        Clusters.Objects.TimeSynchronization.Structs.DSTOffsetStruct(
                            offset=0, validStarting=0, validUntil=NullValue
                        )
                    ]
                )
                await self.write_defaultotaproviders_attribute()
                time_after_pairing_completed = datetime.datetime.now()
                pairing_duration = (
                    time_after_pairing_completed - time_before_starting_pairing
                ).total_seconds()
                self.analytics_dict.update({"pairing_duration": pairing_duration})
                await self.fetch_analytics_from_dut()
                self.subscription_cleanup(th1_subscription)
            self.delay_between_stress_test_operations()
            await self.cleanup_and_unpair_sessions()
            self.update_iteration_result(
                iteration_result=TestResultEnums.TEST_RESULT_PASS
            )

        await tc_Android_pair_unpair(self)


if __name__ == "__main__":
    run_augmented_matter_tests(test_class=TC_Android_Pair)
if __name__ == "__main__":
    run_augmented_matter_tests(test_class=TC_Android_Pair)
