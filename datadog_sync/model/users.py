# Unless explicitly stated otherwise all files in this repository are licensed
# under the 3-clause BSD style license (see LICENSE).
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2019 Datadog, Inc.

from typing import Optional, List, Dict

from requests import HTTPError

from datadog_sync.utils.base_resource import BaseResource, ResourceConfig
from datadog_sync.utils.custom_client import paginated_request, CustomClient
from datadog_sync.utils.resource_utils import check_diff


class Users(BaseResource):
    resource_type = "users"
    resource_config = ResourceConfig(
        resource_connections={"roles": ["relationships.roles.data.id"]},
        base_path="/api/v2/users",
        non_nullable_attr=["attributes.name"],
        excluded_attributes=[
            "id",
            "attributes.created_at",
            "attributes.title",
            "attributes.status",
            "attributes.verified",
            "attributes.service_account",
            "attributes.handle",
            "attributes.icon",
            "attributes.modified_at",
            "relationships.org",
        ],
    )
    # Additional Users specific attributes
    roles_path: str = "/api/v2/roles/{}/users"
    remote_destination_users: Dict[str, Dict] = dict()

    def get_resources(self, client: CustomClient) -> List[Dict]:
        try:
            resp = paginated_request(client.get)(self.resource_config.base_path)
        except HTTPError as e:
            raise e

        return resp

    def import_resource(self, resource: Dict) -> None:
        if resource["attributes"]["disabled"]:
            return

        self.resource_config.source_resources[resource["id"]] = resource

    def pre_resource_action_hook(self, resource: Dict) -> None:
        pass

    def pre_apply_hook(self, resources: Dict[str, Dict]) -> Optional[list]:
        self.remote_destination_users = self.get_remote_destination_users()
        return None

    def create_resource(self, _id: str, resource: Dict) -> None:
        if resource["attributes"]["email"] in self.remote_destination_users:
            self.resource_config.destination_resources[_id] = self.remote_destination_users[
                resource["attributes"]["email"]
            ]

            self.update_resource(_id, resource)
            return

        destination_client = self.config.destination_client
        resource["attributes"].pop("disabled", None)
        try:
            resp = destination_client.post(self.resource_config.base_path, {"data": resource})
        except HTTPError as e:
            raise e

        self.resource_config.destination_resources[_id] = resp.json()["data"]

    def update_resource(self, _id: str, resource: Dict) -> None:
        destination_client = self.config.destination_client

        diff = check_diff(self.resource_config, self.resource_config.destination_resources[_id], resource)
        if diff:
            self.update_user_roles(self.resource_config.destination_resources[_id]["id"], diff)
            resource["id"] = self.resource_config.destination_resources[_id]["id"]
            resource.pop("relationships", None)

            try:
                resp = destination_client.patch(
                    self.resource_config.base_path + f"/{self.resource_config.destination_resources[_id]['id']}",
                    {"data": resource},
                )
            except HTTPError as e:
                raise e

            self.resource_config.destination_resources[_id] = resp.json()["data"]

    def connect_id(self, key, r_obj, resource_to_connect):
        super(Users, self).connect_id(key, r_obj, resource_to_connect)

    def get_remote_destination_users(self):
        remote_user_obj = {}
        destination_client = self.config.destination_client
        remote_users = self.get_resources(destination_client)

        for user in remote_users:
            remote_user_obj[user["attributes"]["email"]] = user

        return remote_user_obj

    def update_user_roles(self, _id, diff):
        for k, v in diff.items():
            if k == "iterable_item_added":
                for key, value in diff["iterable_item_added"].items():
                    if "roles" in key:
                        self.add_user_to_role(_id, value["id"])
            # elif k == "iterable_item_removed":
            #     for key, value in diff["iterable_item_removed"].items():
            #         if "roles" in key:
            #             self.remove_user_from_role(_id, value["id"])
            elif k == "values_changed":
                for key, value in diff["values_changed"].items():
                    if "roles" in key:
                        # self.remove_user_from_role(_id, value["old_value"])
                        self.add_user_to_role(_id, value["new_value"])

    def add_user_to_role(self, user_id, role_id):
        destination_client = self.config.destination_client
        payload = {"data": {"id": user_id, "type": "users"}}
        try:
            destination_client.post(self.roles_path.format(role_id), payload)
        except HTTPError as e:
            self.config.logger.error("error adding user: %s to role %s: %s", user_id, role_id, e)

    def remove_user_from_role(self, user_id, role_id):
        destination_client = self.config.destination_client
        payload = {"data": {"id": user_id, "type": "users"}}
        try:
            destination_client.delete(self.roles_path.format(role_id), payload)
        except HTTPError as e:
            self.config.logger.error("error removing user: %s from role %s: %s", user_id, role_id, e)
