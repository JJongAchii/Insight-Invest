"use client"

import { useAppDispatch, useAppSelector } from '@/app/redux';
import { setIsSidebarCollapsed } from '@/state';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import React, { useState } from 'react';
import { IoHome, IoMenu, IoSearch, IoBarChart, IoTelescope, IoChevronDown } from "react-icons/io5";
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
            <div onClick={onClick} className={`
                cursor-pointer flex items-center
                ${isCollapsed ? "justify-center py-4 mx-2" : "justify-start px-6 py-3.5 mx-3"}
                ${isDropdown ? "ml-12 px-4" : ""}
                rounded-xl
                transition-all duration-300
                group
                ${isActive
                    ? "bg-gradient-to-r from-blue-500 to-indigo-600 text-white shadow-lg"
                    : "text-gray-600 hover:bg-gradient-to-r hover:from-blue-50 hover:to-indigo-50 hover:text-blue-600"
                }
                ${!isActive && "hover:shadow-md"}
                gap-3
            `}>
                <Icon className={`
                    w-5 h-5
                    transition-all duration-300
                    ${isActive ? "text-white scale-110" : "text-gray-600 group-hover:text-blue-600 group-hover:scale-110"}
                `}/>
                <span className={`
                    ${isCollapsed ? "hidden": "block"}
                    font-semibold text-sm
                    transition-all duration-300
                    ${isActive ? "text-white" : "text-gray-700 group-hover:text-blue-600"}
                `}>
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

    const [isBacktestDropdownOpen, setIsBacktestDropdownOpen] = useState(false);

    const toggleSidebar = () => {
        dispatch(setIsSidebarCollapsed(!isSidebarCollapsed))
    };

    const toggleBacktestDropdown = () => {
        setIsBacktestDropdownOpen(!isBacktestDropdownOpen);
    };

    const sidebarClassNames = `fixed flex flex-col ${
        isSidebarCollapsed ? "w-0 md:w-20" : "w-72 md:w-72"
    } bg-white/95 backdrop-blur-xl transition-all duration-300 overflow-hidden h-full shadow-2xl border-r border-gray-100 z-40`;

    return (
        <div className={sidebarClassNames}>
            {/* TOP LOGO */}
            <div className={`flex justify-between md:justify-center items-center pt-8 pb-6 ${
                    isSidebarCollapsed ? "px-2" : "px-6"
            } border-b border-gray-100`}>
                <Link href="/home">
                    <div className="cursor-pointer hover:scale-105 transition-transform duration-300">
                        <Image
                            src={logo}
                            alt="Logo"
                            className="w-full h-auto"
                        />
                    </div>
                </Link>
                <button
                    className='md:hidden p-2 bg-gradient-to-r from-blue-500 to-indigo-600 text-white rounded-xl hover:shadow-lg transition-all duration-300'
                    onClick={toggleSidebar}
                >
                    <IoMenu className='w-5 h-5'/>
                </button>
            </div>

            {/* Links */}
            <div className='flex-grow mt-6 space-y-1'>
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

                {/* Backtest section with dropdown */}
                <div>
                    <div onClick={toggleBacktestDropdown} className={`
                        cursor-pointer flex items-center
                        ${isSidebarCollapsed ? "justify-center py-4 mx-2" : "justify-between px-6 py-3.5 mx-3"}
                        rounded-xl
                        transition-all duration-300
                        text-gray-600 hover:bg-gradient-to-r hover:from-blue-50 hover:to-indigo-50 hover:text-blue-600
                        hover:shadow-md
                        group
                    `}>
                        <div className="flex items-center gap-3">
                            <IoBarChart className={`
                                w-5 h-5
                                transition-all duration-300
                                text-gray-600 group-hover:text-blue-600 group-hover:scale-110
                            `}/>
                            <span className={`
                                ${isSidebarCollapsed ? "hidden": "block"}
                                font-semibold text-sm
                                transition-all duration-300
                                text-gray-700 group-hover:text-blue-600
                            `}>
                                Backtest
                            </span>
                        </div>
                        {!isSidebarCollapsed && (
                            <IoChevronDown className={`
                                w-4 h-4 transition-transform duration-300
                                ${isBacktestDropdownOpen ? "rotate-180" : ""}
                            `}/>
                        )}
                    </div>

                    {isBacktestDropdownOpen && !isSidebarCollapsed && (
                        <div className="space-y-1 mt-1">
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
                </div>

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
            <div className={`${isSidebarCollapsed ? "hidden" : "block"} mb-8 px-6`}>
                <div className="bg-gradient-to-r from-blue-500 to-indigo-600 rounded-xl p-4 text-white text-center">
                    <p className='text-xs font-medium mb-1'>Insight Invest</p>
                    <p className='text-xs opacity-80'>&copy; 2024 Achii</p>
                </div>
            </div>
        </div>
    );
}

export default Sidebar;
