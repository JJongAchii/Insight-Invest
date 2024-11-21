"use client"

import { useAppDispatch, useAppSelector } from '@/app/redux';
import { setIsSidebarCollapsed } from '@/state';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import React, { useState } from 'react';
import { IoHome, IoMenu, IoSearch, IoBarChart, IoTelescope } from "react-icons/io5";
import { HiOutlineLightBulb } from "react-icons/hi";
import { FcAlphabeticalSortingAz } from "react-icons/fc";
import { FaRunning } from "react-icons/fa";
import { IconType } from 'react-icons'; 
import logo from '@/images/logo.png';
import Image from 'next/image';


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
    const isActive =
        pathname === href || (pathname === "/" && href === "/home") ;
    
    return (
        <Link href={href}>
            <div onClick={onClick} className={`cursor-pointer flex items-center ${
                isCollapsed ? "justify-center py-4" : "justify-start px-8 py-4"
            }
            hover:text-blue-500 hover:bg-blue-100 gap-3 transition-colors ${
                isActive ? "bg-blue-200 text-white" : ""
            }
            ${isDropdown ? "pl-12" : ""}  // 하위 디렉토리일 경우 들여쓰기 적용
            `}>
                    <Icon className='w-6 h-6 !text-gray-700'/>
                    <span className={`${isCollapsed ? "hidden": "block"} font-medium text-gray-700`}>
                        {label}
                    </span>
            </div>
        </Link>
    );
}

const Sidebar = () => {

    const dispatch = useAppDispatch();
    const isSidebarCollapsed = useAppSelector(
        (state) => state.global.isSidebarCollapsed
    );

    // Backtest 하위 디렉토리 표시 상태
    const [isBacktestDropdownOpen, setIsBacktestDropdownOpen] = useState(false);

    const toggleSidebar = () => {
        dispatch(setIsSidebarCollapsed(!isSidebarCollapsed))
    };

    const toggleBacktestDropdown = () => {
        setIsBacktestDropdownOpen(!isBacktestDropdownOpen);
    };

    const sidebarClassNames = `fixed flex flex-col ${
        isSidebarCollapsed ? "w-0 md:w-16" : "w-72 md:w-64"
    } bg-white transition-all duration-300 overflow-hidden h-full shadow-md z-40`;

    return (
        <div className={sidebarClassNames}>
            {/* TOP LOGO */}
            <div className={`flex justify-between md:justify-normal items-center pt-5 ${
                    isSidebarCollapsed ? "px-0" : "px-3"
            }`}>
                <Link href="/home">
                    <div className="cursor-pointer">
                        <Image 
                            src={logo} 
                            alt="Logo" 
                            className="w-full h-auto"
                        />
                    </div>
                </Link>
                <button 
                    className='md:hidden px-3 py-3 bg-gray-100 rounded-full hover:bg-blue-100'
                    onClick={toggleSidebar}
                >
                    <IoMenu className='w-4 h-4'/>
                </button>
            </div>

            {/* Links */}
            <div className='flex-grow mt-8'>
                <SidebarLink 
                    href="/home"
                    icon={IoHome}
                    label="Home"
                    isCollapsed={isSidebarCollapsed}
                />
                <SidebarLink 
                    href="/regime"
                    icon={IoTelescope}
                    label="Regime"
                    isCollapsed={isSidebarCollapsed}
                />                
                {/* Backtest 탭과 드롭다운 */}
                <SidebarLink 
                    href="/backtest/simulation"
                    icon={IoBarChart}
                    label="Backtest"
                    isCollapsed={isSidebarCollapsed}
                    onClick={toggleBacktestDropdown}
                />
                {isBacktestDropdownOpen && !isSidebarCollapsed && (
                    <div>
                        <SidebarLink 
                            href="/backtest/simulation"
                            icon={FaRunning}
                            label="Simulation"
                            isCollapsed={isSidebarCollapsed}
                            isDropdown
                        />
                        <SidebarLink 
                            href="/backtest/strategy_list"
                            icon={FcAlphabeticalSortingAz}
                            label="Strategy List"
                            isCollapsed={isSidebarCollapsed}
                            isDropdown
                        />
                    </div>
                )}
                <SidebarLink 
                    href="/stocksearch"
                    icon={IoSearch}
                    label="Stock Search"
                    isCollapsed={isSidebarCollapsed}
                />
                <SidebarLink 
                    href="/insight"
                    icon={HiOutlineLightBulb}
                    label="Insight"
                    isCollapsed={isSidebarCollapsed}
                />
            </div>

            {/* FOOTER */}
            <div className={`${isSidebarCollapsed ? "hidden" : "block"} mb-10`}>
                <p className='text-center text-xs text-gray-500'>&copy; 2024 Achii</p>
            </div>
        </div>
    );
}

export default Sidebar;
