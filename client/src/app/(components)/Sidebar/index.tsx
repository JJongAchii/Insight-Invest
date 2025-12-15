"use client";

import { useAppDispatch, useAppSelector } from "@/app/redux";
import { setIsSidebarCollapsed } from "@/state";
import Link from "next/link";
import { usePathname } from "next/navigation";
import React, { useState } from "react";
import {
  IoHome,
  IoMenu,
  IoSearch,
  IoBarChart,
  IoTelescope,
  IoChevronDown,
  IoNewspaper,
  IoOptions,
} from "react-icons/io5";
import { HiOutlineLightBulb } from "react-icons/hi";
import { FaRunning, FaList } from "react-icons/fa";
import { IconType } from "react-icons";

interface SidebarLinkProps {
  href: string;
  icon: IconType;
  label: string;
  isCollapsed: boolean;
  isDropdown?: boolean;
  onClick?: () => void;
}

const SidebarLink = ({
  href,
  icon: Icon,
  label,
  isCollapsed,
  isDropdown = false,
  onClick,
}: SidebarLinkProps) => {
  const pathname = usePathname();
  const isActive = pathname === href || (pathname === "/" && href === "/home");

  return (
    <Link href={href}>
      <div
        onClick={onClick}
        className={`
          flex items-center gap-3 cursor-pointer
          ${isCollapsed ? "justify-center py-3 mx-2" : "px-4 py-2.5 mx-3"}
          ${isDropdown ? "ml-10" : ""}
          rounded-xl
          transition-all duration-200
          ${
            isActive
              ? "bg-gradient-to-r from-primary-400 to-primary-500 text-white shadow-lg shadow-primary-500/25"
              : "text-neutral-600 hover:bg-white/50 hover:text-neutral-900"
          }
        `}
      >
        <Icon className="w-5 h-5 flex-shrink-0" />
        <span
          className={`
            ${isCollapsed ? "hidden" : "block"}
            text-sm font-medium
          `}
        >
          {label}
        </span>
      </div>
    </Link>
  );
};

const Sidebar = () => {
  const dispatch = useAppDispatch();
  const isSidebarCollapsed = useAppSelector(
    (state) => state.global.isSidebarCollapsed
  );

  const [isBacktestDropdownOpen, setIsBacktestDropdownOpen] = useState(true);

  const toggleSidebar = () => {
    dispatch(setIsSidebarCollapsed(!isSidebarCollapsed));
  };

  const toggleBacktestDropdown = () => {
    setIsBacktestDropdownOpen(!isBacktestDropdownOpen);
  };

  return (
    <div
      className={`
        fixed flex flex-col h-full z-40
        ${isSidebarCollapsed ? "w-0 md:w-16" : "w-60"}
        bg-white/40 backdrop-blur-xl border-r border-white/30
        transition-all duration-200 overflow-hidden
      `}
    >
      {/* Logo */}
      <div
        className={`
          flex items-center justify-between
          ${isSidebarCollapsed ? "px-2 py-4" : "px-4 py-5"}
          border-b border-white/20
        `}
      >
        <Link href="/home" className="flex items-center gap-2">
          <div className="w-8 h-8 bg-gradient-to-br from-primary-400 to-primary-600 rounded-xl flex items-center justify-center shadow-lg shadow-primary-500/25">
            <span className="text-white font-bold text-sm">II</span>
          </div>
          {!isSidebarCollapsed && (
            <span className="font-semibold text-neutral-800">
              Insight Invest
            </span>
          )}
        </Link>
        <button
          className="md:hidden p-1.5 hover:bg-white/50 rounded-lg transition-colors"
          onClick={toggleSidebar}
        >
          <IoMenu className="w-5 h-5 text-neutral-600" />
        </button>
      </div>

      {/* Navigation Links */}
      <nav className="flex-1 py-4 space-y-1">
        <SidebarLink
          href="/home"
          icon={IoHome}
          label="Dashboard"
          isCollapsed={isSidebarCollapsed}
        />
        <SidebarLink
          href="/regime"
          icon={IoTelescope}
          label="Market Regime"
          isCollapsed={isSidebarCollapsed}
        />
        <SidebarLink
          href="/news"
          icon={IoNewspaper}
          label="Economy News"
          isCollapsed={isSidebarCollapsed}
        />

        {/* Backtest Section */}
        <div>
          <div
            onClick={toggleBacktestDropdown}
            className={`
              flex items-center justify-between cursor-pointer
              ${isSidebarCollapsed ? "justify-center py-3 mx-2" : "px-4 py-2.5 mx-3"}
              rounded-xl
              text-neutral-600 hover:bg-white/50 hover:text-neutral-900
              transition-all duration-200
            `}
          >
            <div className="flex items-center gap-3">
              <IoBarChart className="w-5 h-5 flex-shrink-0" />
              {!isSidebarCollapsed && (
                <span className="text-sm font-medium">Backtest</span>
              )}
            </div>
            {!isSidebarCollapsed && (
              <IoChevronDown
                className={`
                  w-4 h-4 transition-transform duration-200
                  ${isBacktestDropdownOpen ? "rotate-180" : ""}
                `}
              />
            )}
          </div>

          {isBacktestDropdownOpen && !isSidebarCollapsed && (
            <div className="mt-1 space-y-1">
              <SidebarLink
                href="/backtest/simulation"
                icon={FaRunning}
                label="Simulation"
                isCollapsed={isSidebarCollapsed}
                isDropdown
              />
              <SidebarLink
                href="/backtest/strategy_list"
                icon={FaList}
                label="Strategies"
                isCollapsed={isSidebarCollapsed}
                isDropdown
              />
            </div>
          )}
        </div>

        <SidebarLink
          href="/optimization"
          icon={IoOptions}
          label="Optimization"
          isCollapsed={isSidebarCollapsed}
        />
        <SidebarLink
          href="/stocksearch"
          icon={IoSearch}
          label="Stock Search"
          isCollapsed={isSidebarCollapsed}
        />
        <SidebarLink
          href="/insight"
          icon={HiOutlineLightBulb}
          label="Insights"
          isCollapsed={isSidebarCollapsed}
        />
      </nav>

      {/* Footer */}
      {!isSidebarCollapsed && (
        <div className="p-4 border-t border-white/20">
          <p className="text-xs text-neutral-400 text-center">
            Insight Invest &copy; 2024
          </p>
        </div>
      )}
    </div>
  );
};

export default Sidebar;
