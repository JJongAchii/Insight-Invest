import React from 'react'

const Searchbar = () => {
  return (
    <div className='flex flex-wrap gap-3'>
        <input type='search' 
            placeholder='Search Strategies...' 
            className="flex-grow min-w-[150px] md:min-w-[200px] pl-3 pr-4 py-2 border-2 border-gray-300 bg-white rounded-lg focus:outline-none focus:border-blue-500"
        />
        <button className="px-3 py-2 border-2 border-gray-300 rounded-lg hover:bg-blue-100">
            Name
        </button>
        <button className="px-3 py-2 border-2 border-gray-300 rounded-lg hover:bg-blue-100">
            Returns
        </button>
        <button className="px-3 py-2 border-2 border-gray-300 rounded-lg hover:bg-blue-100">
            Vol
        </button>
    </div>
  )
}

export default Searchbar