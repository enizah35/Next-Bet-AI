"use client";
import React, { useState } from "react";

interface CardProps extends React.HTMLAttributes<HTMLDivElement> {
  pad?: number;
  hover?: boolean;
}

export function Card({ children, style, onClick, hover = true, pad = 20, className = "", ...rest }: CardProps) {
  const [h, setH] = useState(false);
  return (
    <div
      className={className}
      onClick={onClick}
      onMouseEnter={() => setH(true)}
      onMouseLeave={() => setH(false)}
      style={{
        background: "var(--bg-elev)",
        border: "1px solid var(--border)",
        borderRadius: 16,
        padding: pad,
        boxShadow: "var(--shadow-card)",
        cursor: onClick ? "pointer" : "default",
        transition: "transform 0.2s ease, border-color 0.2s ease, box-shadow 0.2s ease",
        transform: hover && h && onClick ? "translateY(-2px)" : "none",
        borderColor: hover && h && onClick ? "var(--border-strong)" : undefined,
        ...style,
      }}
      {...rest}
    >
      {children}
    </div>
  );
}
