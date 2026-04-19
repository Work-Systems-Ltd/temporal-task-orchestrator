import { fetchAssignees, fetchGroups, reassignTask } from "./api/tasks";
import type { AssigneeOption } from "./api/types";

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
      return this.options.filter((o: AssigneeOption) =>
        o.label.toLowerCase().includes(q),
      );
    },

    toggle() {
      if (this.open) {
        this.open = false;
        this.search = "";
        activePickerId = null;
        return;
      }

      if (activePickerId && activePickerId !== pickerId) {
        window.dispatchEvent(new CustomEvent("reassign-close"));
      }

      this.open = true;
      activePickerId = pickerId;

      if (field === "user") {
        fetchAssignees(otherValue || undefined).then((d) => {
          this.options = d.users;
        });
      } else {
        fetchGroups().then((groups) => {
          this.options = groups;
        });
      }

      (this as any).$nextTick(() => {
        const input = (this as any).$refs.searchInput as
          | HTMLInputElement
          | undefined;
        if (input) input.focus();
      });
    },

    assign(slug: string) {
      const user = field === "user" ? slug : otherValue;
      const group = field === "group" ? slug : otherValue;

      reassignTask(workflowId, user, group).then(() => {
        this.value = slug;
        this.open = false;
        this.search = "";
        activePickerId = null;

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

    handleGroupChanged(
      event: CustomEvent<{ workflowId: string; group: string }>,
    ) {
      if (field === "user" && event.detail.workflowId === workflowId) {
        otherValue = event.detail.group;
        if (this.value) {
          this.value = "";
          reassignTask(workflowId, "", event.detail.group);
        }
      }
    },
  };
}

(window as Record<string, unknown>).reassignPicker = reassignPicker;
