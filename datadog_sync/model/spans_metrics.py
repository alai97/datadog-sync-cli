# Unless explicitly stated otherwise all files in this repository are licensed
# under the 3-clause BSD style license (see LICENSE).
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2019 Datadog, Inc.
from typing import Optional, List, Dict

from datadog_sync.utils.base_resource import BaseResource, ResourceConfig
from datadog_sync.utils.custom_client import CustomClient


class SpansMetrics(BaseResource):
    resource_type = "spans_metrics"
    resource_config = ResourceConfig(
        base_path="/api/v2/apm/config/metrics",
    )
    # Additional SpansMetrics specific attributes

    def get_resources(self, client: CustomClient) -> List[Dict]:
        resp = client.get(self.resource_config.base_path).json()

        return resp["data"]

    def import_resource(self, _id: Optional[str] = None, resource: Optional[Dict] = None) -> None:
        if _id:
            source_client = self.config.source_client
            resource = source_client.get(self.resource_config.base_path + f"/{_id}").json()["data"]

        self.resource_config.source_resources[resource["id"]] = resource

    def pre_resource_action_hook(self, _id, resource: Dict) -> None:
        pass

    def pre_apply_hook(self) -> None:
        pass

    def create_resource(self, _id: str, resource: Dict) -> None:
        destination_client = self.config.destination_client
        payload = {"data": resource}
        resp = destination_client.post(self.resource_config.base_path, payload).json()

        self.resource_config.destination_resources[_id] = resp["data"]

    def update_resource(self, _id: str, resource: Dict) -> None:
        destination_client = self.config.destination_client
        payload = {"data": resource}
        resp = destination_client.patch(
            self.resource_config.base_path + f"/{self.resource_config.destination_resources[_id]['id']}",
            payload,
        ).json()

        self.resource_config.destination_resources[_id] = resp["data"]

    def delete_resource(self, _id: str) -> None:
        destination_client = self.config.destination_client
        destination_client.delete(
            self.resource_config.base_path + f"/{self.resource_config.destination_resources[_id]['id']}"
        )

    def connect_id(self, key: str, r_obj: Dict, resource_to_connect: str) -> Optional[List[str]]:
        pass
