"use client";

import React, { createContext, useContext, useEffect, useState } from "react";

type Mode = "dark" | "light";
type Dir = "safe" | "bold";

interface ThemeContextType {
  mode: Mode;
  dir: Dir;
  toggleMode: () => void;
  setDir: (d: Dir) => void;
}

const ThemeContext = createContext<ThemeContextType | undefined>(undefined);

export const ThemeProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [mode, setMode] = useState<Mode>("dark");
  const [dir, setDirState] = useState<Dir>("safe");

  useEffect(() => {
    const savedMode = (localStorage.getItem("nba_mode") as Mode) || "dark";
    const savedDir = (localStorage.getItem("nba_dir") as Dir) || "safe";
    setMode(savedMode);
    setDirState(savedDir);
    document.documentElement.setAttribute("data-mode", savedMode);
    document.documentElement.setAttribute("data-dir", savedDir);
  }, []);

  const toggleMode = () => {
    const next: Mode = mode === "dark" ? "light" : "dark";
    setMode(next);
    localStorage.setItem("nba_mode", next);
    document.documentElement.setAttribute("data-mode", next);
  };

  const setDir = (d: Dir) => {
    setDirState(d);
    localStorage.setItem("nba_dir", d);
    document.documentElement.setAttribute("data-dir", d);
  };

  return (
    <ThemeContext.Provider value={{ mode, dir, toggleMode, setDir }}>
      {children}
    </ThemeContext.Provider>
  );
};

export const useTheme = () => {
  const ctx = useContext(ThemeContext);
  if (!ctx) throw new Error("useTheme must be used within ThemeProvider");
  return ctx;
};
