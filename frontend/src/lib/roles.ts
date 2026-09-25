/**
 * Roles and the groups the backend route guards use (backend/app/core/roles.py).
 * The UI only hides what a role cannot do; the server is what enforces it.
 * Keep these lists identical to the backend's.
 */

export const fieldRoles = ["technician", "supervisor"];
export const approverRoles = ["supervisor", "manager"];
export const adminRoles = ["manager"];

export const roleLabel: Record<string, string> = {
  technician: "Technician",
  supervisor: "Supervisor",
  manager: "Manager",
};

export function hasRole(role: string | undefined, group: string[]): boolean {
  return role !== undefined && group.includes(role);
}
