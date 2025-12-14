"use client";

import { useAppDispatch, useAppSelector } from "@/app/redux";
import { setIsDarkMode, setIsSidebarCollapsed } from "@/state";
import { Bell, Menu, Moon, Settings, Sun, Search, User } from "lucide-react";
import React from "react";

const Navbar = () => {
  const dispatch = useAppDispatch();
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

  return (
    <div className="flex justify-between items-center w-full mb-6 bg-white/50 backdrop-blur-md rounded-2xl border border-white/30 shadow-lg shadow-black/5 px-4 py-3">
      {/* Left Side */}
      <div className="flex items-center gap-3">
        <button
          className="p-2 hover:bg-white/60 rounded-xl transition-all duration-200"
          onClick={toggleSidebar}
        >
          <Menu className="w-5 h-5 text-neutral-600" />
        </button>
        <div className="relative hidden md:block">
          <input
            type="search"
            placeholder="Search..."
            className="input pl-10 pr-4 py-2 w-64 lg:w-80"
          />
          <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
            <Search className="text-neutral-400" size={18} />
          </div>
        </div>
      </div>

      {/* Right Side */}
      <div className="flex items-center gap-2">
        <div className="hidden md:flex items-center gap-2">
          <button
            onClick={toggleDarkMode}
            className="p-2 hover:bg-white/60 rounded-xl transition-all duration-200"
          >
            {isDarkMode ? (
              <Sun className="text-primary-500" size={20} />
            ) : (
              <Moon className="text-neutral-600" size={20} />
            )}
          </button>

          <div className="relative">
            <button className="p-2 hover:bg-white/60 rounded-xl transition-all duration-200">
              <Bell className="text-neutral-600" size={20} />
            </button>
            <span className="absolute -top-0.5 -right-0.5 w-4 h-4 text-[10px] font-bold text-white bg-gradient-to-r from-red-400 to-red-500 rounded-full flex items-center justify-center shadow-sm">
              3
            </span>
          </div>

          <div className="h-6 w-px bg-white/40 mx-2" />

          <div className="flex items-center gap-2 px-3 py-1.5 hover:bg-white/60 rounded-xl transition-all duration-200 cursor-pointer">
            <div className="w-8 h-8 bg-gradient-to-br from-primary-400 to-primary-600 rounded-full flex items-center justify-center text-white shadow-md shadow-primary-500/25">
              <User size={16} />
            </div>
            <span className="text-sm font-medium text-neutral-700">Achii</span>
          </div>
        </div>

        <button className="p-2 hover:bg-white/60 rounded-xl transition-all duration-200">
          <Settings className="text-neutral-600" size={20} />
        </button>
      </div>
    </div>
  );
};

export default Navbar;
