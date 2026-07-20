"use client";

import React, { useMemo } from "react";
import { ThemeProvider, createTheme } from "@mui/material/styles";
import { useAppSelector } from "@/app/redux";

/**
 * Bridges the redux dark-mode flag into MUI's theme so DataGrid & friends
 * render with the correct palette mode.
 */
const MuiThemeBridge = ({ children }: { children: React.ReactNode }) => {
  const isDarkMode = useAppSelector((state) => state.global.isDarkMode);

  const theme = useMemo(
    () =>
      createTheme({
        palette: { mode: isDarkMode ? "dark" : "light" },
      }),
    [isDarkMode]
  );

  return <ThemeProvider theme={theme}>{children}</ThemeProvider>;
};

export default MuiThemeBridge;
