interface AssigneeOption {
  slug: string;
  label: string;
}

interface AssigneesResponse {
  users: AssigneeOption[];
  groups: AssigneeOption[];
}

// Cache groups globally (they don't change with context)
let groupsCache: AssigneeOption[] | null = null;

async function fetchAssignees(group?: string): Promise<AssigneesResponse> {
  const url = group
    ? `/api/assignees?group=${encodeURIComponent(group)}`
    : "/api/assignees";
  const res = await fetch(url);
  return await res.json();
}

async function fetchGroups(): Promise<AssigneeOption[]> {
  if (!groupsCache) {
    const data = await fetchAssignees();
    groupsCache = data.groups;
  }
  return groupsCache;
}

// Track which picker is currently open so only one shows at a time
let activePickerId: string | null = null;

function reassignPicker(
  workflowId: string,
  field: "user" | "group",
  currentValue: string,
  otherValue: string,
) {
  const pickerId = `${workflowId}-${field}`;

  return {
    open: false,
    value: currentValue,
    search: "",
    options: [] as AssigneeOption[],

    get filtered(): AssigneeOption[] {
      if (!this.search) return this.options;
      const q = this.search.toLowerCase();
      return this.options.filter((o: AssigneeOption) => o.label.toLowerCase().includes(q));
    },

    toggle() {
      if (this.open) {
        this.open = false;
        this.search = "";
        activePickerId = null;
        return;
      }

      // Close any other open picker
      if (activePickerId && activePickerId !== pickerId) {
        window.dispatchEvent(new CustomEvent("reassign-close"));
      }

      this.open = true;
      activePickerId = pickerId;

      if (field === "user") {
        // Fetch users scoped to the current group assignment
        fetchAssignees(otherValue || undefined).then((d: AssigneesResponse) => {
          this.options = d.users;
        });
      } else {
        fetchGroups().then((groups: AssigneeOption[]) => {
          this.options = groups;
        });
      }

      (this as any).$nextTick(() => {
        const input = (this as any).$refs.searchInput as HTMLInputElement | undefined;
        if (input) input.focus();
      });
    },

    assign(slug: string) {
      const body: Record<string, string> = {};
      body[`assigned_${field}`] = slug;
      body[field === "user" ? "assigned_group" : "assigned_user"] = otherValue;

      fetch(`/tasks/${workflowId}/reassign`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      }).then(() => {
        this.value = slug;
        this.open = false;
        this.search = "";
        activePickerId = null;

        // When group changes, notify user pickers to refresh
        if (field === "group") {
          window.dispatchEvent(
            new CustomEvent("reassign-group-changed", {
              detail: { workflowId, group: slug },
            }),
          );
        }
      });
    },

    close() {
      if (activePickerId !== pickerId) {
        this.open = false;
        this.search = "";
      }
    },

    handleClose() {
      this.open = false;
      this.search = "";
    },

    // Listen for group changes to update the otherValue reference
    handleGroupChanged(event: CustomEvent<{ workflowId: string; group: string }>) {
      if (field === "user" && event.detail.workflowId === workflowId) {
        otherValue = event.detail.group;
        // Clear user if group changed (user may no longer be in new group)
        if (this.value) {
          this.value = "";
          fetch(`/tasks/${workflowId}/reassign`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              assigned_user: "",
              assigned_group: event.detail.group,
            }),
          });
        }
      }
    },
  };
}

(window as Record<string, unknown>).reassignPicker = reassignPicker;
