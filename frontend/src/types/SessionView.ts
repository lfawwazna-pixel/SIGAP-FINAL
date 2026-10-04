/* Generated from contracts/models.py. Do not edit manually. */

export type Id = string;
export type Username = string;
export type DisplayName = string;
export type Role = "operator";
/**
 * @minItems 1
 * @maxItems 2
 */
export type Permissions =
  ["monitor:read" | "control:operate"] | ["monitor:read" | "control:operate", "monitor:read" | "control:operate"];
export type ExpiresAt = string;
export type RemainingSeconds = number;
export type CsrfToken = string;

export interface SessionView {
  operator: OperatorView;
  expires_at: ExpiresAt;
  remaining_seconds: RemainingSeconds;
  csrf_token: CsrfToken;
}
export interface OperatorView {
  id: Id;
  username: Username;
  display_name: DisplayName;
  role: Role;
  permissions: Permissions;
}
