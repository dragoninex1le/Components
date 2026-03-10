"""DynamoDB repository for Role, RolePermission, and UserRole entities.

Implements the three core entities of Porth's role-based access control (RBAC) system:
- Role: collections of permissions scoped to a tenant
- RolePermission: join entity linking roles to permissions
- UserRole: join entity linking users to roles

Supports role management (create, update, delete), permission assignment, and user-role
assignment. Includes special logic for system roles (undeletable) and admin role seeding.

The single-table design for porth-roles uses multiple PK patterns:
  - Roles: PK=TENANT#{tenant_id}, SK=ROLE#{role_id}
  - RolePermissions: PK=ROLE#{role_id}, SK=PERM#{permission_key}
  - UserRoles: PK=USER#{user_id}#TENANT#{tenant_id}, SK=ROLE#{role_id}
  - UserRole listing: GSI1 gsi1pk=TENANT#{tenant_id}, gsi1sk=USERROLE#{user_id}
"""

from __future__ import annotations

from typing import Any

from boto3.dynamodb.conditions import Key

from porth_common.config import TABLE_PORTH_ROLES
from porth_common.events.publisher import EventPublisher
from porth_common.models.role import Role, RolePermission, UserRole
from porth_common.repositories.base import BaseRepository, generate_id, utc_now


class RoleRepository(BaseRepository):
    """Repository for managing roles, role permissions, and user-role assignments.

    Persistence layer for Porth's role-based access control (RBAC) system. Handles:
    - Role CRUD operations within a tenant
    - Permission assignment to roles (set operations)
    - User-role assignment within a tenant
    - System role protection (Admin role cannot be deleted)
    - Admin role seeding for new tenants
    - Permission coverage analysis (find orphaned permissions)

    Supports efficient queries:
    - Get roles by tenant
    - Get permissions for a role
    - Get roles for a user+tenant
    - Check user's specific permissions

    Special features:
    - System roles (is_system=True) cannot be deleted
    - Admin role has full permissions; typically created at tenant provisioning
    - Permission assignment is atomic and idempotent
    - User-role assignment is simple add/remove (not idempotent)
    - All changes trigger domain events for downstream consumers
    """

    def __init__(
        self,
        table_name: str = TABLE_PORTH_ROLES,
        dynamodb_resource=None,
        events_client=None,
    ):
        """Initialize the repository.

        Args:
            table_name: DynamoDB table name
            dynamodb_resource: Optional mocked DynamoDB resource for testing
            events_client: Optional mocked EventBridge client for testing
        """
        super().__init__(table_name, dynamodb_resource)
        self._publisher = EventPublisher(client=events_client)

    def create_role(
        self,
        tenant_id: str,
        name: str,
        description: str | None = None,
        is_system: bool = False,
    ) -> Role:
        """Create a new role.

        Args:
            tenant_id: Tenant identifier
            name: Role name
            description: Optional role description
            is_system: If True, role cannot be deleted

        Returns:
            Created Role entity
        """
        role_id = generate_id()
        now = utc_now()

        pk_value = f"TENANT#{tenant_id}"
        sk_value = f"ROLE#{role_id}"

        item: dict[str, Any] = {
            "pk": pk_value,
            "sk": sk_value,
            "id": role_id,
            "tenant_id": tenant_id,
            "name": name,
            "is_system": is_system,
            "created_at": now,
            "updated_at": now,
        }

        if description is not None:
            item["description"] = description

        stored_item = self._put_item(item)

        # Publish create event
        self._publisher.publish(
            entity_type="Role",
            action="created",
            entity_id=role_id,
            after=stored_item,
            metadata={"tenant_id": tenant_id},
        )

        return self._item_to_role(stored_item)

    def get_role(self, tenant_id: str, role_id: str) -> Role | None:
        """Get a role by ID.

        Args:
            tenant_id: Tenant identifier
            role_id: Role identifier

        Returns:
            Role if found, None otherwise
        """
        pk_value = f"TENANT#{tenant_id}"
        sk_value = f"ROLE#{role_id}"

        item = self._get_item({"pk": pk_value, "sk": sk_value})
        return self._item_to_role(item) if item else None

    def list_roles(self, tenant_id: str) -> list[Role]:
        """List all roles for a tenant.

        Args:
            tenant_id: Tenant identifier

        Returns:
            List of roles for the tenant
        """
        pk_value = f"TENANT#{tenant_id}"

        items = self._query(
            key_condition=Key("pk").eq(pk_value),
        )
        return [self._item_to_role(item) for item in items if item]

    def update_role(
        self, tenant_id: str, role_id: str, name: str, description: str | None = None
    ) -> Role:
        """Update a role's name and description.

        The is_system flag cannot be changed via this method.

        Args:
            tenant_id: Tenant identifier
            role_id: Role identifier
            name: New role name
            description: New role description (or None to clear)

        Returns:
            Updated Role entity
        """
        pk_value = f"TENANT#{tenant_id}"
        sk_value = f"ROLE#{role_id}"

        now = utc_now()

        updates: dict[str, Any] = {
            "name": name,
            "updated_at": now,
        }

        if description is not None:
            updates["description"] = description

        # Get the item before update for event publishing
        before_item = self._get_item({"pk": pk_value, "sk": sk_value})

        updated_item = self._update_item({"pk": pk_value, "sk": sk_value}, updates)

        # Publish update event
        self._publisher.publish(
            entity_type="Role",
            action="updated",
            entity_id=role_id,
            after=updated_item,
            before=before_item,
            metadata={"tenant_id": tenant_id},
        )

        return self._item_to_role(updated_item)

    def delete_role(self, tenant_id: str, role_id: str) -> None:
        """Delete a role.

        Cannot delete system roles (is_system=True).

        Args:
            tenant_id: Tenant identifier
            role_id: Role identifier

        Raises:
            ValueError: If the role is a system role
        """
        # Get the role to check if it's a system role
        role = self.get_role(tenant_id, role_id)
        if not role:
            return

        if role.is_system:
            raise ValueError("Cannot delete system role")

        pk_value = f"TENANT#{tenant_id}"
        sk_value = f"ROLE#{role_id}"

        # Store item for event before deletion
        before_item = self._get_item({"pk": pk_value, "sk": sk_value})

        # Delete the role
        self._delete_item({"pk": pk_value, "sk": sk_value})

        # Delete all permissions for this role
        perm_items = self._query(
            key_condition=Key("pk").eq(f"ROLE#{role_id}"),
        )
        for perm_item in perm_items:
            self._delete_item(
                {
                    "pk": f"ROLE#{role_id}",
                    "sk": f"PERM#{perm_item.get('permission_key')}",
                }
            )

        # Publish delete event
        self._publisher.publish(
            entity_type="Role",
            action="deleted",
            entity_id=role_id,
            before=before_item,
            metadata={"tenant_id": tenant_id},
        )

    def set_role_permissions(
        self, role_id: str, permission_keys: list[str], tenant_id: str
    ) -> None:
        """Set all permissions for a role (replaces existing permissions).

        Args:
            role_id: Role identifier
            permission_keys: List of permission keys to assign
            tenant_id: Tenant identifier
        """
        now = utc_now()

        # Delete existing permissions
        existing_perms = self._query(
            key_condition=Key("pk").eq(f"ROLE#{role_id}"),
        )
        for perm_item in existing_perms:
            self._delete_item(
                {
                    "pk": f"ROLE#{role_id}",
                    "sk": f"PERM#{perm_item.get('permission_key')}",
                }
            )

        # Add new permissions
        for perm_key in permission_keys:
            item: dict[str, Any] = {
                "pk": f"ROLE#{role_id}",
                "sk": f"PERM#{perm_key}",
                "role_id": role_id,
                "permission_key": perm_key,
                "tenant_id": tenant_id,
                "assigned_at": now,
            }
            self._put_item(item)

            # Publish permission assignment event
            self._publisher.publish(
                entity_type="RolePermission",
                action="assigned",
                entity_id=f"{role_id}#{perm_key}",
                after=item,
                metadata={"tenant_id": tenant_id, "role_id": role_id},
            )

    def get_role_permissions(self, role_id: str) -> list[str]:
        """Get all permission keys for a role.

        Args:
            role_id: Role identifier

        Returns:
            List of permission keys
        """
        items = self._query(
            key_condition=Key("pk").eq(f"ROLE#{role_id}"),
        )
        return [item.get("permission_key") for item in items if item.get("permission_key")]

    def assign_user_role(self, user_id: str, role_id: str, tenant_id: str) -> UserRole:
        """Assign a role to a user in a tenant.

        Args:
            user_id: User identifier
            role_id: Role identifier
            tenant_id: Tenant identifier

        Returns:
            Created UserRole entity
        """
        now = utc_now()

        pk_value = f"USER#{user_id}#TENANT#{tenant_id}"
        sk_value = f"ROLE#{role_id}"
        gsi1pk_value = f"TENANT#{tenant_id}"
        gsi1sk_value = f"USERROLE#{user_id}"

        item: dict[str, Any] = {
            "pk": pk_value,
            "sk": sk_value,
            "gsi1pk": gsi1pk_value,
            "gsi1sk": gsi1sk_value,
            "user_id": user_id,
            "role_id": role_id,
            "tenant_id": tenant_id,
            "assigned_at": now,
        }

        stored_item = self._put_item(item)

        # Publish user-role assignment event
        self._publisher.publish(
            entity_type="UserRole",
            action="assigned",
            entity_id=f"{user_id}#{role_id}",
            after=stored_item,
            metadata={"tenant_id": tenant_id, "user_id": user_id},
        )

        return self._item_to_user_role(stored_item)

    def get_user_roles(self, user_id: str, tenant_id: str) -> list[str]:
        """Get all role IDs assigned to a user in a tenant.

        Args:
            user_id: User identifier
            tenant_id: Tenant identifier

        Returns:
            List of role IDs
        """
        pk_value = f"USER#{user_id}#TENANT#{tenant_id}"

        items = self._query(
            key_condition=Key("pk").eq(pk_value),
        )
        return [item.get("role_id") for item in items if item.get("role_id")]

    def set_user_roles(
        self, user_id: str, tenant_id: str, role_ids: list[str]
    ) -> None:
        """Set all roles for a user in a tenant (replaces existing roles).

        Args:
            user_id: User identifier
            tenant_id: Tenant identifier
            role_ids: List of role IDs to assign
        """
        now = utc_now()

        pk_value = f"USER#{user_id}#TENANT#{tenant_id}"

        # Delete existing roles
        existing_roles = self._query(
            key_condition=Key("pk").eq(pk_value),
        )
        for role_item in existing_roles:
            self._delete_item(
                {
                    "pk": pk_value,
                    "sk": f"ROLE#{role_item.get('role_id')}",
                }
            )

        # Add new roles
        gsi1pk_value = f"TENANT#{tenant_id}"
        gsi1sk_value = f"USERROLE#{user_id}"

        for role_id in role_ids:
            item: dict[str, Any] = {
                "pk": pk_value,
                "sk": f"ROLE#{role_id}",
                "gsi1pk": gsi1pk_value,
                "gsi1sk": gsi1sk_value,
                "user_id": user_id,
                "role_id": role_id,
                "tenant_id": tenant_id,
                "assigned_at": now,
            }
            self._put_item(item)

            # Publish user-role assignment event
            self._publisher.publish(
                entity_type="UserRole",
                action="assigned",
                entity_id=f"{user_id}#{role_id}",
                after=item,
                metadata={"tenant_id": tenant_id, "user_id": user_id},
            )

    def check_permission(
        self, user_id: str, tenant_id: str, permission_key: str
    ) -> bool:
        """Check if a user has a specific permission in a tenant.

        Checks all roles assigned to the user and returns True if any role
        has the permission.

        Args:
            user_id: User identifier
            tenant_id: Tenant identifier
            permission_key: Permission key to check

        Returns:
            True if user has the permission, False otherwise
        """
        # Get all roles for the user
        role_ids = self.get_user_roles(user_id, tenant_id)

        # For each role, check if it has the permission
        for role_id in role_ids:
            permissions = self.get_role_permissions(role_id)
            if permission_key in permissions:
                return True

        return False

    def get_orphaned_permissions(
        self, tenant_id: str, all_permission_keys: list[str]
    ) -> list[str]:
        """Find permissions not assigned to any role in the tenant.

        Args:
            tenant_id: Tenant identifier
            all_permission_keys: All valid permission keys for comparison

        Returns:
            List of permission keys not assigned to any role
        """
        # Get all roles in tenant
        roles = self.list_roles(tenant_id)

        # Collect all assigned permissions across all roles
        assigned_permissions = set()
        for role in roles:
            permissions = self.get_role_permissions(role.id)
            assigned_permissions.update(permissions)

        # Find orphaned permissions
        orphaned = [
            key for key in all_permission_keys if key not in assigned_permissions
        ]
        return orphaned

    def seed_admin_role(
        self, tenant_id: str, all_permission_keys: list[str]
    ) -> Role:
        """Create an undeletable admin role with all permissions.

        Idempotent: if admin role already exists for tenant, returns it.

        Args:
            tenant_id: Tenant identifier
            all_permission_keys: All permission keys to assign to the admin role

        Returns:
            The admin Role entity
        """
        # Check if admin role already exists
        roles = self.list_roles(tenant_id)
        for role in roles:
            if role.name == "Admin" and role.is_system:
                # Already exists, just ensure all permissions are set
                self.set_role_permissions(role.id, all_permission_keys, tenant_id)
                return role

        # Create new admin role
        admin_role = self.create_role(
            tenant_id=tenant_id,
            name="Admin",
            description="System administrator role with all permissions",
            is_system=True,
        )

        # Assign all permissions to the admin role
        self.set_role_permissions(admin_role.id, all_permission_keys, tenant_id)

        return admin_role

    @staticmethod
    def _item_to_role(item: dict[str, Any] | None) -> Role | None:
        """Convert a DynamoDB item to a Role model.

        Args:
            item: DynamoDB item dictionary

        Returns:
            Role model or None if item is None
        """
        if not item:
            return None

        return Role(
            id=item["id"],
            tenant_id=item["tenant_id"],
            name=item["name"],
            description=item.get("description"),
            is_system=item.get("is_system", False),
            created_at=item["created_at"],
            updated_at=item["updated_at"],
        )

    @staticmethod
    def _item_to_role_permission(item: dict[str, Any] | None) -> RolePermission | None:
        """Convert a DynamoDB item to a RolePermission model.

        Args:
            item: DynamoDB item dictionary

        Returns:
            RolePermission model or None if item is None
        """
        if not item:
            return None

        return RolePermission(
            role_id=item["role_id"],
            permission_key=item["permission_key"],
            tenant_id=item["tenant_id"],
            assigned_at=item["assigned_at"],
        )

    @staticmethod
    def _item_to_user_role(item: dict[str, Any] | None) -> UserRole | None:
        """Convert a DynamoDB item to a UserRole model.

        Args:
            item: DynamoDB item dictionary

        Returns:
            UserRole model or None if item is None
        """
        if not item:
            return None

        return UserRole(
            user_id=item["user_id"],
            role_id=item["role_id"],
            tenant_id=item["tenant_id"],
            assigned_at=item["assigned_at"],
        )
