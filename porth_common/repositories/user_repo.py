"""DynamoDB repository for User entity.

Implements User persistence in Porth's single-table design. Supports:
- JIT (just-in-time) user creation/updates via external_id + org_id + tenant_id
- Email-based lookups within a tenant
- Listing users by organization+tenant
- User suspension and reactivation
- Event publishing for user lifecycle changes

The single-table design stores users with:
  - PK: USER#{id}, SK: METADATA (main access: get by user_id)
  - GSI1: gsi1pk=EXT#{external_id}#ORG#{org_id}#TENANT#{tenant_id}, gsi1sk=METADATA (JIT upsert)
  - GSI2: gsi2pk=EMAIL#{email}#TENANT#{tenant_id}, gsi2sk=METADATA (email lookup)
  - GSI3: gsi3pk=ORG#{org_id}#TENANT#{tenant_id}, gsi3sk=USER#{id} (list by org+tenant)
"""

from __future__ import annotations

from typing import Any

from boto3.dynamodb.conditions import Key

from porth_common.config import TABLE_PORTH_USERS
from porth_common.events.publisher import EventPublisher
from porth_common.models.user import User
from porth_common.repositories.base import BaseRepository, generate_id, utc_now


class UserRepository(BaseRepository):
    """Repository for managing User entities in DynamoDB.

    Persistence layer for users in Porth's multi-tenant system. Users are the leaf
    level in the Organization → Tenant → User hierarchy. This repository handles:
    - JIT provisioning: create or update users based on identity provider data
    - Email-based lookups within a tenant (for duplicate prevention)
    - Organization+tenant listing (for admin dashboards)
    - User suspension/reactivation
    - Event publishing for user lifecycle changes

    Single-table design with "porth-users" table supporting four access patterns:
    - Main: PK: USER#{id}, SK: METADATA (get user by internal ID)
    - JIT: GSI1 with composite key (external_id, org_id, tenant_id) for upsert
    - Email: GSI2 with email+tenant_id for duplicate checking
    - Listing: GSI3 with org_id+tenant_id to list all users in an environment

    JIT Provisioning:
    The upsert_by_external_id method enables just-in-time user creation from JWT claims.
    External ID + Org ID + Tenant ID forms a composite unique key across IdP and
    organization/tenant scope. First login creates user; subsequent logins update profile.
    """

    def __init__(
        self,
        table_name: str = TABLE_PORTH_USERS,
        dynamodb_resource=None,
        event_publisher: EventPublisher | None = None,
    ):
        super().__init__(table_name, dynamodb_resource)
        self._event_publisher = event_publisher or EventPublisher()

    def create(self, user_data: dict[str, Any]) -> User:
        """Create a new user.

        Args:
            user_data: Dictionary with user fields (external_id, email, organization_id, tenant_id, etc.)
                      Do not include id, created_at, or updated_at

        Returns:
            Created User entity

        Publishes:
            User.created event
        """
        user_id = generate_id()
        now = utc_now()
        external_id = user_data["external_id"]
        email = user_data["email"]
        org_id = user_data["organization_id"]
        tenant_id = user_data["tenant_id"]

        user_data_with_id = {
            "id": user_id,
            "created_at": now,
            "updated_at": now,
            **user_data,
        }

        item = {
            "PK": f"USER#{user_id}",
            "SK": "METADATA",
            "gsi1pk": f"EXT#{external_id}#ORG#{org_id}#TENANT#{tenant_id}",
            "gsi1sk": "METADATA",
            "gsi2pk": f"EMAIL#{email}#TENANT#{tenant_id}",
            "gsi2sk": "METADATA",
            "gsi3pk": f"ORG#{org_id}#TENANT#{tenant_id}",
            "gsi3sk": f"USER#{user_id}",
            **user_data_with_id,
        }

        self._put_item(item)

        user = User(**user_data_with_id)

        self._event_publisher.publish(
            entity_type="User",
            action="created",
            entity_id=user_id,
            after=user.model_dump(),
            metadata={
                "organization_id": org_id,
                "tenant_id": tenant_id,
                "external_id": external_id,
            },
        )

        return user

    def get_by_id(self, user_id: str) -> User | None:
        """Get a user by ID.

        Args:
            user_id: User ID (UUID)

        Returns:
            User if found, None otherwise
        """
        item = self._get_item({"PK": f"USER#{user_id}", "SK": "METADATA"})
        if not item:
            return None

        # Remove DynamoDB metadata fields
        user_data = {k: v for k, v in item.items() if not k.startswith("gsi")}
        user_data.pop("PK", None)
        user_data.pop("SK", None)

        return User(**user_data)

    def upsert_by_external_id(
        self,
        external_id: str,
        org_id: str,
        tenant_id: str,
        user_data: dict[str, Any],
    ) -> tuple[User, bool]:
        """Create or update a user based on external_id + org_id + tenant_id (JIT provisioning).

        The upsert key is: external_id + org_id + tenant_id. This enables just-in-time
        user provisioning where the first login creates the user and subsequent logins
        update profile fields from the identity provider.

        Args:
            external_id: User ID from identity provider (e.g., from JWT 'sub' claim)
            org_id: Organization ID (sequential integer)
            tenant_id: Tenant ID (sequential integer)
            user_data: Dictionary with user fields to create/update
                      Must include email. Should not include id, created_at, updated_at

        Returns:
            Tuple of (User entity, is_new) where is_new=True if user was created

        Publishes:
            User.created or User.updated event depending on whether it's new
        """
        # Try to find existing user
        existing_items = self._query_gsi(
            index_name="gsi1",
            key_condition=Key("gsi1pk").eq(
                f"EXT#{external_id}#ORG#{org_id}#TENANT#{tenant_id}"
            )
            & Key("gsi1sk").eq("METADATA"),
        )

        if existing_items:
            # User exists, update it
            existing_item = existing_items[0]
            user_id = existing_item["PK"].split("#")[1]

            # Get current state for event
            current_user = self.get_by_id(user_id)

            # Update timestamp
            update_dict = user_data.copy()
            update_dict["updated_at"] = utc_now()

            # Handle email change in GSI2
            if "email" in user_data:
                old_email = existing_item["email"]
                new_email = user_data["email"]
                if old_email != new_email:
                    update_dict["gsi2pk"] = f"EMAIL#{new_email}#TENANT#{tenant_id}"

            updated_item = self._update_item(
                {"PK": f"USER#{user_id}", "SK": "METADATA"},
                update_dict,
            )

            # Remove DynamoDB metadata fields
            user_result_data = {
                k: v for k, v in updated_item.items() if not k.startswith("gsi")
            }
            user_result_data.pop("PK", None)
            user_result_data.pop("SK", None)

            user = User(**user_result_data)

            self._event_publisher.publish(
                entity_type="User",
                action="updated",
                entity_id=user_id,
                before=current_user.model_dump() if current_user else None,
                after=user.model_dump(),
                metadata={
                    "organization_id": org_id,
                    "tenant_id": tenant_id,
                    "external_id": external_id,
                },
            )

            return user, False
        else:
            # User doesn't exist, create it
            user_id = generate_id()
            now = utc_now()
            email = user_data["email"]

            user_data_with_id = {
                "id": user_id,
                "external_id": external_id,
                "organization_id": org_id,
                "tenant_id": tenant_id,
                "created_at": now,
                "updated_at": now,
                **user_data,
            }

            item = {
                "PK": f"USER#{user_id}",
                "SK": "METADATA",
                "gsi1pk": f"EXT#{external_id}#ORG#{org_id}#TENANT#{tenant_id}",
                "gsi1sk": "METADATA",
                "gsi2pk": f"EMAIL#{email}#TENANT#{tenant_id}",
                "gsi2sk": "METADATA",
                "gsi3pk": f"ORG#{org_id}#TENANT#{tenant_id}",
                "gsi3sk": f"USER#{user_id}",
                **user_data_with_id,
            }

            self._put_item(item)

            user = User(**user_data_with_id)

            self._event_publisher.publish(
                entity_type="User",
                action="created",
                entity_id=user_id,
                after=user.model_dump(),
                metadata={
                    "organization_id": org_id,
                    "tenant_id": tenant_id,
                    "external_id": external_id,
                },
            )

            return user, True

    def get_by_email_and_tenant(
        self, email: str, tenant_id: str
    ) -> User | None:
        """Get a user by email within a specific tenant.

        Args:
            email: User email address
            tenant_id: Tenant ID (sequential integer)

        Returns:
            User if found, None otherwise
        """
        items = self._query_gsi(
            index_name="gsi2",
            key_condition=Key("gsi2pk").eq(f"EMAIL#{email}#TENANT#{tenant_id}")
            & Key("gsi2sk").eq("METADATA"),
        )

        if not items:
            return None

        item = items[0]
        user_data = {k: v for k, v in item.items() if not k.startswith("gsi")}
        user_data.pop("PK", None)
        user_data.pop("SK", None)

        return User(**user_data)

    def list_by_org_and_tenant(
        self, org_id: str, tenant_id: str
    ) -> list[User]:
        """List all users for an organization and tenant.

        Args:
            org_id: Organization ID (sequential integer)
            tenant_id: Tenant ID (sequential integer)

        Returns:
            List of User entities
        """
        items = self._query_gsi(
            index_name="gsi3",
            key_condition=Key("gsi3pk").eq(f"ORG#{org_id}#TENANT#{tenant_id}")
            & Key("gsi3sk").begins_with("USER#"),
        )

        users = []
        for item in items:
            user_data = {k: v for k, v in item.items() if not k.startswith("gsi")}
            user_data.pop("PK", None)
            user_data.pop("SK", None)
            users.append(User(**user_data))

        return users

    def update(self, user_id: str, updates: dict[str, Any]) -> User | None:
        """Update a user.

        Args:
            user_id: User ID (UUID)
            updates: Dictionary of fields to update (do not include id, created_at)

        Returns:
            Updated User entity, or None if not found

        Publishes:
            User.updated event
        """
        # Get the current user first
        current_user = self.get_by_id(user_id)
        if not current_user:
            return None

        # Update the updated_at timestamp
        updates["updated_at"] = utc_now()

        # Handle email change in GSI2
        update_dict = updates.copy()
        if "email" in updates:
            tenant_id = current_user.tenant_id
            new_email = updates["email"]
            update_dict["gsi2pk"] = f"EMAIL#{new_email}#TENANT#{tenant_id}"

        updated_item = self._update_item(
            {"PK": f"USER#{user_id}", "SK": "METADATA"},
            update_dict,
        )

        # Remove DynamoDB metadata fields
        user_data = {k: v for k, v in updated_item.items() if not k.startswith("gsi")}
        user_data.pop("PK", None)
        user_data.pop("SK", None)

        user = User(**user_data)

        self._event_publisher.publish(
            entity_type="User",
            action="updated",
            entity_id=user_id,
            before=current_user.model_dump(),
            after=user.model_dump(),
            metadata={
                "organization_id": current_user.organization_id,
                "tenant_id": current_user.tenant_id,
                "external_id": current_user.external_id,
            },
        )

        return user

    def suspend(self, user_id: str) -> User | None:
        """Suspend a user.

        Args:
            user_id: User ID (UUID)

        Returns:
            Updated User entity with suspended status, or None if not found

        Publishes:
            User.updated event
        """
        return self.update(
            user_id,
            {
                "status": "suspended",
                "suspended_at": utc_now(),
            },
        )

    def reactivate(self, user_id: str) -> User | None:
        """Reactivate a suspended user.

        Args:
            user_id: User ID (UUID)

        Returns:
            Updated User entity with active status, or None if not found

        Publishes:
            User.updated event
        """
        return self.update(
            user_id,
            {
                "status": "active",
                "suspended_at": None,
            },
        )
