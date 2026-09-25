"""
EPIC — Roles
Three roles, and the groups the route guards use:
  technician  works the field steps                      (FIELD_ROLES)
  supervisor  works the field steps and approves changes (FIELD_ROLES, APPROVER_ROLES)
  manager     approves changes and administers           (APPROVER_ROLES, ADMIN_ROLES)
The frontend mirrors these groups in frontend/src/lib/roles.ts; keep the two identical.
"""

ROLE_TECHNICIAN = "technician"
ROLE_SUPERVISOR = "supervisor"
ROLE_MANAGER = "manager"

ALL_ROLES = (ROLE_TECHNICIAN, ROLE_SUPERVISOR, ROLE_MANAGER)

# Role groups used by the route guards (require_roles)
FIELD_ROLES = (ROLE_TECHNICIAN, ROLE_SUPERVISOR)
APPROVER_ROLES = (ROLE_SUPERVISOR, ROLE_MANAGER)
ADMIN_ROLES = (ROLE_MANAGER,)
