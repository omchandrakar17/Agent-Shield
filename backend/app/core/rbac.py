"""Role-based access control — enforced server-side."""

from enum import Enum


class Role(str, Enum):
    PLATFORM_ADMIN = "PLATFORM_ADMIN"
    ORG_OWNER = "ORG_OWNER"
    SECURITY_ADMIN = "SECURITY_ADMIN"
    AGENT_ADMIN = "AGENT_ADMIN"
    APPROVER = "APPROVER"
    AUDITOR = "AUDITOR"
    VIEWER = "VIEWER"


class Permission(str, Enum):
    ORG_MANAGE = "org:manage"
    USER_MANAGE = "user:manage"
    AGENT_READ = "agent:read"
    AGENT_WRITE = "agent:write"
    TOOL_READ = "tool:read"
    TOOL_WRITE = "tool:write"
    POLICY_READ = "policy:read"
    POLICY_WRITE = "policy:write"
    RUNTIME_EXECUTE = "runtime:execute"
    APPROVAL_DECIDE = "approval:decide"
    AUDIT_READ = "audit:read"
    SECURITY_MANAGE = "security:manage"
    KILL_SWITCH = "kill_switch:manage"
    ANALYTICS_READ = "analytics:read"


ROLE_PERMISSIONS: dict[Role, set[Permission]] = {
    Role.PLATFORM_ADMIN: set(Permission),
    Role.ORG_OWNER: {
        Permission.ORG_MANAGE,
        Permission.USER_MANAGE,
        Permission.AGENT_READ,
        Permission.AGENT_WRITE,
        Permission.TOOL_READ,
        Permission.TOOL_WRITE,
        Permission.POLICY_READ,
        Permission.POLICY_WRITE,
        Permission.RUNTIME_EXECUTE,
        Permission.APPROVAL_DECIDE,
        Permission.AUDIT_READ,
        Permission.SECURITY_MANAGE,
        Permission.KILL_SWITCH,
        Permission.ANALYTICS_READ,
    },
    Role.SECURITY_ADMIN: {
        Permission.POLICY_READ,
        Permission.POLICY_WRITE,
        Permission.AUDIT_READ,
        Permission.SECURITY_MANAGE,
        Permission.KILL_SWITCH,
        Permission.APPROVAL_DECIDE,
        Permission.AGENT_READ,
        Permission.TOOL_READ,
        Permission.ANALYTICS_READ,
    },
    Role.AGENT_ADMIN: {
        Permission.AGENT_READ,
        Permission.AGENT_WRITE,
        Permission.TOOL_READ,
        Permission.TOOL_WRITE,
        Permission.POLICY_READ,
        Permission.RUNTIME_EXECUTE,
        Permission.AUDIT_READ,
    },
    Role.APPROVER: {
        Permission.APPROVAL_DECIDE,
        Permission.AUDIT_READ,
        Permission.AGENT_READ,
        Permission.TOOL_READ,
        Permission.POLICY_READ,
        Permission.ANALYTICS_READ,
    },
    Role.AUDITOR: {
        Permission.AUDIT_READ,
        Permission.AGENT_READ,
        Permission.TOOL_READ,
        Permission.POLICY_READ,
        Permission.ANALYTICS_READ,
    },
    Role.VIEWER: {
        Permission.AGENT_READ,
        Permission.TOOL_READ,
        Permission.POLICY_READ,
        Permission.ANALYTICS_READ,
    },
}


def role_has_permission(role: str, permission: Permission) -> bool:
    try:
        r = Role(role)
    except ValueError:
        return False
    return permission in ROLE_PERMISSIONS.get(r, set())
