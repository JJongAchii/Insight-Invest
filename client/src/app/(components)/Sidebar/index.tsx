"use client";

import { useAppSelector } from "@/app/redux";
import Link from "next/link";
import { usePathname } from "next/navigation";
import React, { useEffect, useState } from "react";
import {
  IoHome,
  IoSearch,
  IoBarChart,
  IoTelescope,
  IoChevronDown,
  IoOptions,
  IoTrendingUp,
  IoBriefcase,
  IoClose,
  IoDocumentText,
  IoShieldCheckmark,
} from "react-icons/io5";
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
    <Link
      href={href}
      onClick={onClick}
      aria-current={isActive ? "page" : undefined}
      className={`
          flex items-center gap-3 cursor-pointer
          ${isCollapsed ? "md:justify-center md:py-3 md:mx-2" : "md:px-4 md:py-2.5 md:mx-3"}
          max-md:px-4 max-md:py-2.5 max-md:mx-3
          ${isDropdown ? "ml-10" : ""}
          rounded-xl
          transition-all duration-200
          ${
            isActive
              ? "bg-gradient-to-r from-primary-400 to-primary-500 text-white shadow-lg shadow-primary-500/25"
              : "text-ink-secondary hover:bg-raised hover:text-ink"
          }
        `}
    >
      <Icon className="w-5 h-5 flex-shrink-0" aria-hidden />
      <span
        className={`
            ${isCollapsed ? "md:hidden" : ""}
            text-sm font-medium
          `}
      >
        {label}
      </span>
    </Link>
  );
};

/** Uppercase section label; hidden entirely when the sidebar is collapsed. */
const SectionHeader = ({
  label,
  isCollapsed,
}: {
  label: string;
  isCollapsed: boolean;
}) => {
  return (
    <p className={`${isCollapsed ? "md:hidden" : ""} px-7 pt-4 pb-1 text-xs uppercase tracking-wider text-ink-muted font-semibold`}>
      {label}
    </p>
  );
};

const Sidebar = ({
  isMobileOpen,
  onMobileClose,
}: {
  isMobileOpen: boolean;
  onMobileClose: () => void;
}) => {
  const isSidebarCollapsed = useAppSelector(
    (state) => state.global.isSidebarCollapsed
  );

  const [isResearchDropdownOpen, setIsResearchDropdownOpen] = useState(false);
  const pathname = usePathname();

  useEffect(() => {
    if (isMobileOpen) onMobileClose();
    // pathname 변경에만 반응해 모바일 탐색 후 본문을 즉시 보여준다.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pathname]);

  const toggleResearchDropdown = () => {
    setIsResearchDropdownOpen(!isResearchDropdownOpen);
  };

  return (
    <div
      className={`
        fixed inset-y-0 left-0 flex flex-col z-50 w-60
        ${isMobileOpen ? "translate-x-0" : "-translate-x-full"}
        md:translate-x-0 ${isSidebarCollapsed ? "md:w-16" : "md:w-60"}
        bg-surface border-r border-edge
        transition-all duration-200 overflow-hidden shadow-2xl md:shadow-none
      `}
    >
      {/* Logo */}
      <div
        className={`
          flex items-center justify-between
          ${isSidebarCollapsed ? "md:px-2 md:py-4" : "md:px-4 md:py-5"}
          px-4 py-5
          border-b border-edge
        `}
      >
        <Link href="/home" className="flex items-center gap-2">
          <div className="w-8 h-8 bg-gradient-to-br from-primary-400 to-primary-600 rounded-xl flex items-center justify-center shadow-lg shadow-primary-500/25">
            <span className="text-white font-bold text-sm">II</span>
          </div>
          <span className={`${isSidebarCollapsed ? "md:hidden" : ""} font-semibold text-ink`}>
            Insight Invest
          </span>
        </Link>
        <button
          className="md:hidden p-1.5 hover:bg-raised rounded-lg transition-colors"
          onClick={onMobileClose}
          aria-label="메뉴 닫기"
        >
          <IoClose className="w-5 h-5 text-ink-secondary" />
        </button>
      </div>

      {/* Navigation Links */}
      <nav className="flex-1 overflow-y-auto py-4 space-y-1">
        {/* MARKETS */}
        <SectionHeader label="시장" isCollapsed={isSidebarCollapsed} />
        <SidebarLink
          href="/home"
          icon={IoHome}
          label="대시보드"
          isCollapsed={isSidebarCollapsed}
          onClick={onMobileClose}
        />
        <SidebarLink
          href="/insight"
          icon={IoTrendingUp}
          label="한국 시장 인사이트"
          isCollapsed={isSidebarCollapsed}
          onClick={onMobileClose}
        />
        <SidebarLink
          href="/stocksearch"
          icon={IoSearch}
          label="종목 탐색"
          isCollapsed={isSidebarCollapsed}
          onClick={onMobileClose}
        />
        <SidebarLink
          href="/data-trust"
          icon={IoShieldCheckmark}
          label="데이터 신뢰센터"
          isCollapsed={isSidebarCollapsed}
          onClick={onMobileClose}
        />

        {/* PORTFOLIO */}
        <SectionHeader label="포트폴리오" isCollapsed={isSidebarCollapsed} />
        <SidebarLink
          href="/portfolio"
          icon={IoBriefcase}
          label="포트폴리오"
          isCollapsed={isSidebarCollapsed}
          onClick={onMobileClose}
        />

        <SidebarLink
          href="/journal"
          icon={IoDocumentText}
          label="판단 저널"
          isCollapsed={isSidebarCollapsed}
          onClick={onMobileClose}
        />

        {/* Research Lab: 투자 화면과 연구 도구를 시각적으로 분리한다. */}
        <SectionHeader label="Research Lab" isCollapsed={isSidebarCollapsed} />
        <div>
          <button
            type="button"
            onClick={toggleResearchDropdown}
            aria-expanded={isResearchDropdownOpen}
            className={`
              flex w-auto items-center justify-between cursor-pointer
              ${isSidebarCollapsed ? "md:justify-center md:py-3 md:mx-2" : "md:px-4 md:py-2.5 md:mx-3"}
              max-md:px-4 max-md:py-2.5 max-md:mx-3
              rounded-xl
              text-ink-secondary hover:bg-raised hover:text-ink
              transition-all duration-200
            `}
          >
            <div className="flex items-center gap-3">
              <IoBarChart className="w-5 h-5 flex-shrink-0" />
              <span className={`${isSidebarCollapsed ? "md:hidden" : ""} text-sm font-medium`}>
                Research Lab
              </span>
            </div>
            <IoChevronDown
              className={`
                  ${isSidebarCollapsed ? "md:hidden" : ""}
                  w-4 h-4 transition-transform duration-200
                  ${isResearchDropdownOpen ? "rotate-180" : ""}
                `}
            />
          </button>

          {isResearchDropdownOpen && (
            <div className="mt-1 space-y-1">
              <SidebarLink
                href="/backtest/simulation"
                icon={FaRunning}
                label="백테스트"
                isCollapsed={isSidebarCollapsed}
                isDropdown
                onClick={onMobileClose}
              />
              <SidebarLink
                href="/backtest/strategy_list"
                icon={FaList}
                label="전략 보관함"
                isCollapsed={isSidebarCollapsed}
                isDropdown
                onClick={onMobileClose}
              />
            </div>
          )}
        </div>

        <SidebarLink
          href="/optimization"
          icon={IoOptions}
          label="포트폴리오 최적화"
          isCollapsed={isSidebarCollapsed}
          onClick={onMobileClose}
        />

        {/* MACRO */}
        <SectionHeader label="매크로" isCollapsed={isSidebarCollapsed} />
        <SidebarLink
          href="/regime"
          icon={IoTelescope}
          label="시장 국면"
          isCollapsed={isSidebarCollapsed}
          onClick={onMobileClose}
        />
      </nav>

      {/* Footer */}
      <div className={`${isSidebarCollapsed ? "md:hidden" : ""} p-4 border-t border-edge`}>
          <p className="text-xs text-ink-muted text-center">
            Insight Invest &copy; {new Date().getFullYear()}
          </p>
      </div>
    </div>
  );
};

export default Sidebar;
