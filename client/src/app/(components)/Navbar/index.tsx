"use client";

import { useAppDispatch, useAppSelector } from "@/app/redux";
import { setIsDarkMode, setIsSidebarCollapsed } from "@/state";
import { Menu, Moon, Sun, Search } from "lucide-react";
import { useRouter } from "next/navigation";
import React, { useState } from "react";

const Navbar = () => {
  const dispatch = useAppDispatch();
  const router = useRouter();
  const [query, setQuery] = useState("");
  const isSidebarCollapsed = useAppSelector(
    (state) => state.global.isSidebarCollapsed
  );
  const isDarkMode = useAppSelector((state) => state.global.isDarkMode);

  const toggleSidebar = () => {
    dispatch(setIsSidebarCollapsed(!isSidebarCollapsed));
  };

  const toggleDarkMode = () => {
    dispatch(setIsDarkMode(!isDarkMode));
  };

  const handleSearchKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter" && query.trim()) {
      router.push(`/stocksearch?q=${encodeURIComponent(query.trim())}`);
    }
  };

  return (
    <div className="flex justify-between items-center w-full mb-6 bg-surface rounded-2xl border border-edge shadow-lg shadow-black/20 px-4 py-3">
      {/* Left Side */}
      <div className="flex items-center gap-3">
        <button
          className="p-2 hover:bg-raised rounded-xl transition-all duration-200"
          onClick={toggleSidebar}
        >
          <Menu className="w-5 h-5 text-ink-secondary" />
        </button>
        <div className="relative hidden md:block">
          <input
            type="search"
            placeholder="Search stocks..."
            className="input pl-10 pr-4 py-2 w-64 lg:w-80"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={handleSearchKeyDown}
          />
          <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
            <Search className="text-ink-muted" size={18} />
          </div>
        </div>
      </div>

      {/* Right Side */}
      <div className="flex items-center gap-2">
        <button
          onClick={toggleDarkMode}
          className="p-2 hover:bg-raised rounded-xl transition-all duration-200"
        >
          {isDarkMode ? (
            <Sun className="text-primary-400" size={20} />
          ) : (
            <Moon className="text-ink-secondary" size={20} />
          )}
        </button>
      </div>
    </div>
  );
};

export default Navbar;
