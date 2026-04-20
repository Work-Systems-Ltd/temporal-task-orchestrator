/**
 * Alpine.js column picker component.
 *
 * Persists column visibility and order in localStorage.
 * Applies changes by toggling display on [data-col] cells.
 */

interface ColState {
  key: string;
  visible: boolean;
}

function columnPicker() {
  return {
    open: false,
    cols: [] as { key: string; label: string; hideable: boolean; visible: boolean }[],
    dragIdx: -1,
    storageKey: "",

    init() {
      const el = this.$el as HTMLElement;
      const defs: { key: string; label: string; hideable: boolean }[] = JSON.parse(
        el.dataset.columns || "[]"
      );
      this.storageKey = `col-picker:${el.dataset.prefix || location.pathname}`;

      // Load saved state
      const saved = this._load();
      const savedMap = new Map(saved.map((s) => [s.key, s.visible]));
      const savedOrder = saved.map((s) => s.key);

      // Build cols in saved order, appending any new columns at the end
      const ordered: typeof this.cols = [];
      const seen = new Set<string>();

      for (const key of savedOrder) {
        const def = defs.find((d) => d.key === key);
        if (def) {
          ordered.push({
            ...def,
            visible: savedMap.get(key) ?? true,
          });
          seen.add(key);
        }
      }
      for (const def of defs) {
        if (!seen.has(def.key)) {
          ordered.push({ ...def, visible: true });
        }
      }

      this.cols = ordered;
      this._apply();
    },

    toggle(key: string) {
      const col = this.cols.find((c) => c.key === key);
      if (col && col.hideable) {
        col.visible = !col.visible;
        this._save();
        this._apply();
      }
    },

    moveUp(idx: number) {
      if (idx <= 0) return;
      const arr = this.cols;
      [arr[idx - 1], arr[idx]] = [arr[idx], arr[idx - 1]];
      this.cols = [...arr];
      this._save();
      this._apply();
    },

    moveDown(idx: number) {
      if (idx >= this.cols.length - 1) return;
      const arr = this.cols;
      [arr[idx], arr[idx + 1]] = [arr[idx + 1], arr[idx]];
      this.cols = [...arr];
      this._save();
      this._apply();
    },

    reset() {
      localStorage.removeItem(this.storageKey);
      location.reload();
    },

    _save() {
      const state: ColState[] = this.cols.map((c) => ({
        key: c.key,
        visible: c.visible,
      }));
      localStorage.setItem(this.storageKey, JSON.stringify(state));
    },

    _load(): ColState[] {
      try {
        return JSON.parse(localStorage.getItem(this.storageKey) || "[]");
      } catch {
        return [];
      }
    },

    _apply() {
      const table = document.querySelector("[data-ws-section] table, .table-container table") as HTMLTableElement | null;
      if (!table) return;

      // Build a map of key → desired index and visibility
      const orderMap = new Map<string, { order: number; visible: boolean }>();
      this.cols.forEach((c, i) => {
        orderMap.set(c.key, { order: i, visible: c.visible });
      });

      // Get all rows (thead + tbody)
      const rows = table.querySelectorAll("tr");

      rows.forEach((row) => {
        const cells = Array.from(row.children) as HTMLElement[];
        // Find cells with data-col attribute
        const colCells = cells.filter((c) => c.dataset.col);
        if (colCells.length === 0) return;

        // Apply visibility
        for (const cell of colCells) {
          const key = cell.dataset.col!;
          const state = orderMap.get(key);
          if (state && !state.visible) {
            cell.style.display = "none";
          } else {
            cell.style.display = "";
          }
        }

        // Reorder: collect data-col cells, sort, re-insert before the last cell (chevron)
        const lastCell = cells[cells.length - 1];
        const hasChevronCol = lastCell && !lastCell.dataset.col;

        const sortable = colCells
          .filter((c) => orderMap.has(c.dataset.col!))
          .sort((a, b) => {
            const oa = orderMap.get(a.dataset.col!)!.order;
            const ob = orderMap.get(b.dataset.col!)!.order;
            return oa - ob;
          });

        for (const cell of sortable) {
          if (hasChevronCol) {
            row.insertBefore(cell, lastCell);
          } else {
            row.appendChild(cell);
          }
        }
      });
    },
  };
}

(window as any).columnPicker = columnPicker;
