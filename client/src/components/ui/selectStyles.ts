import { StylesConfig, GroupBase } from "react-select";

/**
 * Shared react-select styles wired to the design tokens (globals.css).
 * Works in both dark (default) and light themes since it only references CSS vars.
 */
export const tokenSelectStyles: StylesConfig<
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  any,
  boolean,
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  GroupBase<any>
> = {
  control: (base, state) => ({
    ...base,
    borderRadius: "12px",
    borderWidth: "1px",
    borderColor: state.isFocused ? "var(--primary)" : "var(--border)",
    padding: "0.125rem",
    boxShadow: state.isFocused ? "0 0 0 2px rgba(155, 126, 255, 0.2)" : "none",
    "&:hover": {
      borderColor: "var(--border-strong)",
    },
    backgroundColor: "var(--surface-raised)",
    fontSize: "0.875rem",
  }),
  menu: (base) => ({
    ...base,
    backgroundColor: "var(--surface-overlay)",
    border: "1px solid var(--border)",
    borderRadius: "12px",
    overflow: "hidden",
    zIndex: 30,
  }),
  option: (base, state) => ({
    ...base,
    backgroundColor: state.isSelected
      ? "var(--primary)"
      : state.isFocused
        ? "var(--surface-raised)"
        : "transparent",
    color: state.isSelected ? "#ffffff" : "var(--text-primary)",
    fontSize: "0.875rem",
    "&:active": {
      backgroundColor: "var(--surface-raised)",
    },
  }),
  singleValue: (base) => ({
    ...base,
    color: "var(--text-primary)",
  }),
  input: (base) => ({
    ...base,
    color: "var(--text-primary)",
  }),
  multiValue: (base) => ({
    ...base,
    backgroundColor: "var(--surface-overlay)",
    borderRadius: "0.375rem",
  }),
  multiValueLabel: (base) => ({
    ...base,
    color: "var(--text-primary)",
    fontSize: "0.75rem",
    padding: "0.125rem 0.25rem",
  }),
  multiValueRemove: (base) => ({
    ...base,
    color: "var(--text-secondary)",
    "&:hover": {
      backgroundColor: "var(--surface-raised)",
      color: "var(--text-primary)",
    },
  }),
  placeholder: (base) => ({
    ...base,
    color: "var(--text-muted)",
    fontSize: "0.875rem",
  }),
};

/** Variant used when the field is in an error state. */
export const tokenSelectErrorStyles: typeof tokenSelectStyles = {
  ...tokenSelectStyles,
  control: (base, state) => ({
    ...base,
    borderRadius: "12px",
    borderWidth: "1px",
    borderColor: "var(--losses)",
    padding: "0.125rem",
    boxShadow: state.isFocused ? "0 0 0 2px rgba(251, 113, 133, 0.2)" : "none",
    "&:hover": {
      borderColor: "var(--losses)",
    },
    backgroundColor: "var(--surface-raised)",
    fontSize: "0.875rem",
  }),
};
