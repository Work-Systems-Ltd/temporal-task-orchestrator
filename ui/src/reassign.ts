interface AssigneeOption {
  slug: string;
  label: string;
}

interface AssigneesResponse {
  users: AssigneeOption[];
  groups: AssigneeOption[];
}

let assigneesCache: AssigneesResponse | null = null;

async function fetchAssignees(): Promise<AssigneesResponse> {
  if (assigneesCache) return assigneesCache;
  const res = await fetch("/api/assignees");
  assigneesCache = await res.json();
  return assigneesCache!;
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
    dropStyle: "" as string,

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

      // Position dropdown below the trigger button
      const el = (this as any).$el as HTMLElement;
      const btn = el.querySelector("button") as HTMLElement;
      if (btn) {
        const rect = btn.getBoundingClientRect();
        const dropW = 192;
        let left = rect.left;
        if (left + dropW > window.innerWidth - 8) left = window.innerWidth - dropW - 8;
        this.dropStyle = `top:${rect.bottom + 4}px;left:${left}px`;
      }

      this.open = true;
      activePickerId = pickerId;

      fetchAssignees().then((d: AssigneesResponse) => {
        this.options = field === "user" ? d.users : d.groups;
      });

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
      });
    },

    close() {
      if (activePickerId !== pickerId) {
        this.open = false;
        this.search = "";
      }
    },

    handleClose() {
      // Only close if this isn't the one being opened
      this.open = false;
      this.search = "";
    },
  };
}

(window as Record<string, unknown>).reassignPicker = reassignPicker;
