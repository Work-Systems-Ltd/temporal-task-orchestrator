/**
 * Task service — assignee fetching, reassignment, and task submission.
 */

import { get, postJson, postForm } from "./client";
import type {
  AssigneesResponse,
  ReassignResult,
  SubmitResult,
} from "./types";

// Cache groups globally (they don't change within a session)
let groupsCache: AssigneesResponse["groups"] | null = null;

export async function fetchAssignees(
  group?: string,
): Promise<AssigneesResponse> {
  const url = group
    ? `/api/assignees?group=${encodeURIComponent(group)}`
    : "/api/assignees";
  return get<AssigneesResponse>(url);
}

export async function fetchGroups(): Promise<AssigneesResponse["groups"]> {
  if (!groupsCache) {
    const data = await fetchAssignees();
    groupsCache = data.groups;
  }
  return groupsCache;
}

export async function reassignTask(
  workflowId: string,
  assignedUser: string,
  assignedGroup: string,
): Promise<ReassignResult> {
  return postJson<ReassignResult>(`/tasks/${workflowId}/reassign`, {
    assigned_user: assignedUser,
    assigned_group: assignedGroup,
  });
}

export async function submitTask(
  workflowId: string,
  formData: Record<string, string>,
): Promise<SubmitResult> {
  const res = await postForm(`/task/${workflowId}/submit`, formData);
  return res.json();
}
