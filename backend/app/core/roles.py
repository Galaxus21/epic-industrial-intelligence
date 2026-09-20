"""
EPIC — Standard Roles and Canonical Role Groupings
Accepted role names (validated in app/api/users.py):
technician, supervisor, safety_officer, area_authority, authorized_person, manager, quality_inspector
Rights come from the route guards: FIELD_ROLES and APPROVER_ROLES below, and manager alone for
administration. The other names authenticate and nothing more.
"""

# Valid individual role names
ROLE_TECHNICIAN = "technician"
ROLE_SUPERVISOR = "supervisor"
ROLE_SAFETY_OFFICER = "safety_officer"
ROLE_AREA_AUTHORITY = "area_authority"
ROLE_AUTHORIZED_PERSON = "authorized_person"
ROLE_MANAGER = "manager"
ROLE_QUALITY_INSPECTOR = "quality_inspector"

ALL_ROLES = (
    ROLE_TECHNICIAN,
    ROLE_SUPERVISOR,
    ROLE_SAFETY_OFFICER,
    ROLE_AREA_AUTHORITY,
    ROLE_AUTHORIZED_PERSON,
    ROLE_MANAGER,
    ROLE_QUALITY_INSPECTOR,
)

# Role groups used by the route guards (require_roles)
APPROVER_ROLES = ("supervisor", "manager")
FIELD_ROLES = ("technician", "supervisor")
