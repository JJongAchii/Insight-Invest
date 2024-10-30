import { useFetch } from '@/state/api';
import React from 'react'

const RelativeInfo = ({ selectedData }) => {

    const { data, loading, error } = useFetch(`${process.env.NEXT_PUBLIC_API_BASE_URL}/price`);

    return (
        <div className="row-span-3 xl:row-span-6 bg-white">
            Dynamic Relative Information(Example Code)
            
            <ul>
                {selectedData.map((item) => (
                    <li key={item.meta_id}>
                        <p>Ticker: {item.ticker}</p>
                        <p>Name: {item.name}</p>
                        <p>Market Cap: {item.marketcap}</p>
                        {/* 필요한 항목 추가 */}
                    </li>
                ))}
            </ul>
            
        </div>
    );
}

export default RelativeInfo