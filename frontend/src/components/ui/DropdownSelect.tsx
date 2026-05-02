"use client";
import React, { useEffect, useRef, useState } from "react";
import { I } from "@/components/Icons";

type Option = {
  value: string;
  label: string;
};

interface DropdownSelectProps {
  value: string;
  options: Option[];
  onChange: (value: string) => void;
  minWidth?: number;
  ariaLabel?: string;
}

export function DropdownSelect({
  value,
  options,
  onChange,
  minWidth = 190,
  ariaLabel = "Selection",
}: DropdownSelectProps) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const selected = options.find((option) => option.value === value) ?? options[0];

  useEffect(() => {
    if (!open) return;

    const onPointerDown = (event: PointerEvent) => {
      if (!ref.current?.contains(event.target as Node)) {
        setOpen(false);
      }
    };
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false);
    };

    document.addEventListener("pointerdown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("pointerdown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [open]);

  return (
    <div ref={ref} className="dropdown-select" style={{ position: "relative", minWidth }}>
      <button
        type="button"
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-label={ariaLabel}
        onClick={() => setOpen((current) => !current)}
        style={{
          width: "100%",
          height: 42,
          borderRadius: 999,
          border: "1px solid var(--border)",
          background: open ? "var(--bg-inset)" : "var(--bg-elev)",
          color: "var(--text)",
          padding: "0 42px 0 16px",
          fontSize: 13,
          fontWeight: 600,
          textAlign: "left",
          cursor: "pointer",
          boxShadow: open ? "var(--shadow-float)" : "var(--shadow-card)",
          transition: "background 0.16s ease, border-color 0.16s ease, box-shadow 0.16s ease",
          position: "relative",
        }}
      >
        <span style={{ display: "block", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
          {selected?.label ?? "Selection"}
        </span>
        <I.ChevronDown
          size={15}
          style={{
            position: "absolute",
            right: 8,
            top: 6,
            width: 28,
            height: 28,
            padding: 7,
            borderRadius: 999,
            background: "var(--bg-inset)",
            border: "1px solid var(--border)",
            color: "var(--text-soft)",
            transform: open ? "rotate(180deg)" : "none",
            transition: "transform 0.16s ease",
          }}
        />
      </button>

      {open && (
        <div
          role="listbox"
          style={{
            position: "absolute",
            zIndex: 120,
            top: "calc(100% + 8px)",
            right: 0,
            minWidth: "100%",
            maxHeight: 280,
            overflowY: "auto",
            padding: 6,
            borderRadius: 18,
            border: "1px solid var(--border)",
            background: "var(--bg-elev)",
            boxShadow: "var(--shadow-float)",
          }}
        >
          {options.map((option) => {
            const active = option.value === value;
            return (
              <button
                key={option.value}
                type="button"
                role="option"
                aria-selected={active}
                onClick={() => {
                  onChange(option.value);
                  setOpen(false);
                }}
                style={{
                  width: "100%",
                  minHeight: 36,
                  border: "none",
                  borderRadius: 12,
                  background: active ? "var(--bg-inset)" : "transparent",
                  color: active ? "var(--text)" : "var(--text-soft)",
                  padding: "0 10px",
                  fontSize: 13,
                  fontWeight: active ? 700 : 500,
                  textAlign: "left",
                  cursor: "pointer",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  gap: 12,
                }}
              >
                <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{option.label}</span>
                {active && <I.Check size={14} style={{ flexShrink: 0, color: "var(--good)" }} />}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
