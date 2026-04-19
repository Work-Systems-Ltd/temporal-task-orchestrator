/** Column definitions for workflow/task list tables. */
export const ALL_COLUMNS = [
  "id",
  "type",
  "started",
  "stopped",
  "duration",
  "status",
  "queue",
  "run_id",
  "events",
  "parent",
] as const;

export const DEFAULT_COLUMNS: string[] = ["id", "type", "started", "duration", "status"];

export const COL_STORAGE_KEY = "wf-visible-cols";
