interface WorkflowOption {
  key: string;
  label: string;
  description: string;
  input_label: string;
  input_placeholder: string;
  has_input_task: boolean;
}

declare global {
  interface Window {
    __workflows?: WorkflowOption[];
  }
}

function wizardData() {
  return {
    step: 1,
    selectedKey: "",
    selectedLabel: "",
    selectedDesc: "",
    inputLabel: "",
    inputPlaceholder: "",
    inputValue: "",
    submitting: false,
    workflows: [] as WorkflowOption[],
    filterText: "",

    get filteredWorkflows(): WorkflowOption[] {
      if (!this.filterText) return this.workflows;
      const q = this.filterText.toLowerCase();
      return this.workflows.filter(
        (w: WorkflowOption) =>
          w.label.toLowerCase().includes(q) || w.description.toLowerCase().includes(q),
      );
    },

    init() {
      this.workflows = window.__workflows || [];
    },

    selectWorkflow(wf: WorkflowOption) {
      if (wf.has_input_task) {
        window.location.href = "/start/" + wf.key;
        return;
      }
      this.selectedKey = wf.key;
      this.selectedLabel = wf.label;
      this.selectedDesc = wf.description;
      this.inputLabel = wf.input_label;
      this.inputPlaceholder = wf.input_placeholder;
      this.step = 2;
      (this as any).$nextTick(() => {
        const ref = (this as any).$refs.inputField;
        if (ref) ref.focus();
      });
    },
  };
}

(window as Record<string, unknown>).wizardData = wizardData;
