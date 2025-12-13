"use client"

import { useAppDispatch, useAppSelector } from '@/app/redux';
import { setIsDarkMode, setIsSidebarCollapsed } from '@/state';
import { Bell, Menu, Moon, Settings, Sun, Search, User } from 'lucide-react';
import Link from 'next/link';
import React from 'react'

const Navbar = () => {

  const dispatch = useAppDispatch();
  const isSidebarCollapsed = useAppSelector(
      (state) => state.global.isSidebarCollapsed
  );
  const isDarkMode = useAppSelector((state) => state.global.isDarkMode)

  const toggleSidebar = () => {
      dispatch(setIsSidebarCollapsed(!isSidebarCollapsed))
  };

  const toggleDarkMode = () => {
    dispatch(setIsDarkMode(!isDarkMode))
  };

  return (
    <div className='flex justify-between items-center w-full mb-8'>

        {/* LEFT SIDE */}

        <div className='flex justify-between items-center gap-4'>
            <button
              className='px-3 py-3 bg-white/80 backdrop-blur-sm rounded-xl hover:bg-gradient-to-r hover:from-blue-500 hover:to-indigo-600 hover:text-white shadow-md transition-all duration-300 group'
              onClick={toggleSidebar}
            >
                <Menu className='w-5 h-5 text-gray-600 group-hover:text-white transition-colors'/>
            </button>
            <div className='relative hidden md:block'>
                <input type='search'
                        placeholder='Search stocks, strategies, insights...'
                        className='input-modern pl-12 pr-4 py-3 w-80 lg:w-96 bg-white/90 backdrop-blur-sm shadow-md'
                />
                <div className='absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none'>
                  <Search className='text-gray-400' size={20}/>
                </div>
            </div>
        </div>

        {/* RIGHT SIDE */}

        <div className='flex justify-between items-center gap-3'>
          <div className='hidden md:flex justify-between items-center gap-3'>
            <button
              onClick={toggleDarkMode}
              className='p-3 bg-white/80 backdrop-blur-sm rounded-xl hover:bg-gradient-to-r hover:from-blue-500 hover:to-indigo-600 hover:text-white shadow-md transition-all duration-300 group'
            >
              {isDarkMode ? (
                <Sun className='text-gray-600 group-hover:text-white transition-colors' size={20}/>
              ) : (
                <Moon className='text-gray-600 group-hover:text-white transition-colors' size={20}/>
              )}
            </button>
            <div className='relative'>
              <button className='p-3 bg-white/80 backdrop-blur-sm rounded-xl hover:bg-gradient-to-r hover:from-blue-500 hover:to-indigo-600 hover:text-white shadow-md transition-all duration-300 group'>
                <Bell className='text-gray-600 group-hover:text-white transition-colors' size={20}/>
              </button>
              <span className='absolute -top-1 -right-1 inline-flex items-center justify-center w-5 h-5 text-xs font-bold text-white bg-gradient-to-r from-red-500 to-pink-500 rounded-full animate-pulse'>
                3
              </span>
            </div>
            <div className='h-8 w-px bg-gradient-to-b from-transparent via-gray-300 to-transparent mx-2'/>
            <div className='flex items-center gap-3 px-4 py-2 bg-white/80 backdrop-blur-sm rounded-xl shadow-md hover:shadow-lg transition-all duration-300 cursor-pointer group'>
              <div className='w-9 h-9 bg-gradient-to-r from-blue-500 to-indigo-600 rounded-full flex items-center justify-center text-white font-bold shadow-md group-hover:scale-110 transition-transform'>
                <User size={20}/>
              </div>
              <span className='font-semibold text-gray-700 group-hover:text-blue-600 transition-colors'>Achii</span>
            </div>
          </div>
          <Link href="/settings">
            <button className='p-3 bg-white/80 backdrop-blur-sm rounded-xl hover:bg-gradient-to-r hover:from-blue-500 hover:to-indigo-600 hover:text-white shadow-md transition-all duration-300 group'>
              <Settings className='text-gray-600 group-hover:text-white transition-colors' size={20}/>
            </button>
          </Link>
        </div>
    </div>
  );
}

export default Navbar
