/**
 * Alpine.js query builder component for GenericTableView.
 *
 * Reads available fields from the data-fields attribute (JSON),
 * manages filter conditions, and serializes them to URL query params.
 */

interface QueryFieldDef {
  key: string;
  label: string;
  field_type: string;
  enum_values: string[];
}

interface Condition {
  field: string;
  op: string;
  value: string;
}

interface OperatorDef {
  value: string;
  label: string;
}

const OPERATORS: Record<string, OperatorDef[]> = {
  string: [
    { value: "eq", label: "equals" },
    { value: "ne", label: "not equals" },
    { value: "contains", label: "contains" },
    { value: "startswith", label: "starts with" },
    { value: "null", label: "is empty" },
    { value: "notnull", label: "is not empty" },
  ],
  number: [
    { value: "eq", label: "=" },
    { value: "ne", label: "!=" },
    { value: "gt", label: ">" },
    { value: "lt", label: "<" },
    { value: "gte", label: ">=" },
    { value: "lte", label: "<=" },
  ],
  date: [
    { value: "gt", label: "after" },
    { value: "lt", label: "before" },
    { value: "gte", label: "on or after" },
    { value: "lte", label: "on or before" },
    { value: "null", label: "is empty" },
    { value: "notnull", label: "is not empty" },
  ],
  enum: [
    { value: "eq", label: "is" },
    { value: "ne", label: "is not" },
    { value: "in", label: "is any of" },
  ],
};

function queryBuilder() {
  return {
    conditions: [] as Condition[],
    fields: [] as QueryFieldDef[],
    logic: "and",
    open: false,

    init() {
      // Parse field definitions from data attribute
      const el = this.$el as HTMLElement;
      try {
        this.fields = JSON.parse(el.dataset.fields || "[]");
      } catch {
        this.fields = [];
      }

      // Parse existing filter params from URL
      const params = new URLSearchParams(window.location.search);
      const existing = params.getAll("filter");
      existing.forEach((f: string) => {
        const parts = f.split(":");
        if (parts.length >= 2) {
          this.conditions.push({
            field: parts[0],
            op: parts[1],
            value: parts.slice(2).join(":"),
          });
        }
      });
      this.logic = params.get("filter_logic") || "and";
      if (this.conditions.length > 0) this.open = true;
    },

    addCondition() {
      const firstField = this.fields[0]?.key || "";
      this.conditions.push({ field: firstField, op: "eq", value: "" });
    },

    removeCondition(index: number) {
      this.conditions.splice(index, 1);
    },

    getOperators(fieldKey: string): OperatorDef[] {
      const field = this.fields.find((f) => f.key === fieldKey);
      return OPERATORS[field?.field_type || "string"] || OPERATORS.string;
    },

    getFieldType(fieldKey: string): string {
      const field = this.fields.find((f) => f.key === fieldKey);
      return field?.field_type || "string";
    },

    getEnumValues(fieldKey: string): string[] {
      const field = this.fields.find((f) => f.key === fieldKey);
      return field?.enum_values || [];
    },

    apply() {
      const url = new URL(window.location.href);
      // Remove existing filter params
      url.searchParams.delete("filter");
      url.searchParams.delete("filter_logic");
      url.searchParams.delete("page"); // Reset to page 1

      // Add new filter params
      this.conditions.forEach((c: Condition) => {
        if (c.field && c.op) {
          url.searchParams.append("filter", `${c.field}:${c.op}:${c.value}`);
        }
      });
      if (this.logic !== "and") {
        url.searchParams.set("filter_logic", this.logic);
      }
      window.location.href = url.toString();
    },

    clear() {
      this.conditions = [];
      const url = new URL(window.location.href);
      url.searchParams.delete("filter");
      url.searchParams.delete("filter_logic");
      url.searchParams.delete("page");
      window.location.href = url.toString();
    },
  };
}

(window as any).queryBuilder = queryBuilder;
