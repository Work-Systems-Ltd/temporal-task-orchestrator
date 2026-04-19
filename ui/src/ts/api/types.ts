export interface AssigneeOption {
  slug: string;
  label: string;
}

export interface AssigneesResponse {
  users: AssigneeOption[];
  groups: AssigneeOption[];
}

export interface SubmitResult {
  ok: boolean;
  gone?: boolean;
  errors?: Record<string, string[]>;
}

export interface ReassignResult {
  ok: boolean;
  assigned_user: string;
  assigned_group: string;
}
