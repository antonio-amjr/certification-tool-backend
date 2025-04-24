#
# Copyright (c) 2023 Project CHIP Authors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

from typing import Any

from faker import Faker
from sqlalchemy.orm import Session

from app.models import TestCollectionMetadata

fake = Faker()


def random_test_collection_metadata_dict(
    name: str | None = None,
    path: str | None = None,
    version: str | None = None,
    source_hash: str | None = None,
) -> dict[str, Any]:
    collection_metadata_dict: dict[str, Any] = {}

    if name is None:
        name = fake.text(max_nb_chars=20)
    if path is None:
        path = fake.text(max_nb_chars=20)
    if version is None:
        version = fake.bothify(text="#.##.##")
    if source_hash is None:
        source_hash = fake.sha256(raw_output=False)

    collection_metadata_dict["name"] = name
    collection_metadata_dict["path"] = path
    collection_metadata_dict["version"] = version
    collection_metadata_dict["source_hash"] = source_hash

    return collection_metadata_dict


def create_random_test_collection_metadata(
    db: Session, **kwargs: Any
) -> TestCollectionMetadata:
    test_collection_metadata = TestCollectionMetadata(
        **random_test_collection_metadata_dict(**kwargs)
    )
    db.add(test_collection_metadata)
    db.commit()
    return test_collection_metadata
