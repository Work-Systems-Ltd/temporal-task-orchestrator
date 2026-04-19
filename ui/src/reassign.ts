interface AssigneeOption {
  slug: string;
  label: string;
}

interface AssigneesResponse {
  users: AssigneeOption[];
  groups: AssigneeOption[];
}

// Cache assignees so we only fetch once
let assigneesCache: AssigneesResponse | null = null;

async function fetchAssignees(): Promise<AssigneesResponse> {
  if (assigneesCache) return assigneesCache;
  const res = await fetch("/api/assignees");
  assigneesCache = await res.json();
  return assigneesCache!;
}

interface ReassignPickerData {
  open: boolean;
  value: string;
  search: string;
  options: AssigneeOption[];
  filtered: AssigneeOption[];
  toggle(): void;
  assign(slug: string): void;
  close(): void;
  // internal
  _field: string;
  _otherValue: string;
  _workflowId: string;
  $refs: Record<string, HTMLElement>;
  $nextTick(fn: () => void): void;
  $dispatch(event: string): void;
}

function reassignPicker(
  workflowId: string,
  field: "user" | "group",
  currentValue: string,
  otherValue: string,
): ReassignPickerData {
  return {
    open: false,
    value: currentValue,
    search: "",
    options: [],
    _field: field,
    _otherValue: otherValue,
    _workflowId: workflowId,

    get filtered(): AssigneeOption[] {
      if (!this.search) return this.options;
      const q = this.search.toLowerCase();
      return this.options.filter((o) => o.label.toLowerCase().includes(q));
    },

    toggle() {
      this.open = !this.open;
      if (this.open) {
        fetchAssignees().then((d) => {
          this.options = field === "user" ? d.users : d.groups;
        });
        this.$nextTick(() => {
          const input = this.$refs.searchInput as HTMLInputElement | undefined;
          if (input) input.focus();
        });
      } else {
        this.search = "";
      }
    },

    assign(slug: string) {
      const body: Record<string, string> = {};
      body[`assigned_${this._field}`] = slug;
      body[this._field === "user" ? "assigned_group" : "assigned_user"] =
        this._otherValue;

      fetch(`/tasks/${this._workflowId}/reassign`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      }).then(() => {
        this.value = slug;
        this.open = false;
        this.search = "";
      });
    },

    close() {
      this.open = false;
      this.search = "";
    },
  } as ReassignPickerData;
}

// Expose to window for Alpine x-data
(window as Record<string, unknown>).reassignPicker = reassignPicker;
