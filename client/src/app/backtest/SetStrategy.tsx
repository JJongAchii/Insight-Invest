import React, { useMemo, useState } from 'react'
import { useFetch } from "@/state/api";
import Select from "react-select"
import DatePicker from "react-datepicker";
import "react-datepicker/dist/react-datepicker.css";


const SetStrategy = () => {
    const { data, loading, error } = useFetch(`${process.env.NEXT_PUBLIC_API_BASE_URL}/meta/tickers`);
    const [startDate, setStartDate] = useState(new Date("2000-01-01"));
    const [endDate, setEndDate] = useState(new Date());
    const [selectedTickers, setSelectedTickers] = useState([]);
    const [selectedAlgorithm, setSelectedAlgorithm] = useState(null);

    const options = useMemo(() => (
        data ? data.map((item) => ({
            value: item.meta_id,
            label: item.ticker
        })) : []
    ), [data]);

    const handleRunBacktest = async() => {
        const payload = {
            tickers: selectedTickers.map((ticker) => ticker.value),
            algorithm: selectedAlgorithm?.value,
            startDate: startDate.toISOString().split("T")[0],
            endDate: endDate.toISOString().split("T")[0],
        }

        try {
            const response = await fetch(`${process.env.NEXT_PUBLIC_API_BASE_URL}/backtest`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(payload)
            });
    
            if (!response.ok) {
                throw new Error('Failed to run backtest');
            }
    
            const data = await response.json();
            console.log("Backtest result:", data);
        } catch (error) {
            console.error("Error running backtest:", error);
        }
    }
        
    return (
        <div className='flex flex-col bg-white shadow-md rounded-2xl pb-12'>
            <div className='flex gap-3 pb-24 px-5 py-5'>
                <div>
                    <h3 className='text-lg font-semibold'> 
                        Set Universe 
                    </h3>
                    <Select 
                        isMulti
                        options={options}
                        placeholder="Select tickers..."
                        onChange={setSelectedTickers}
                    />
                </div>
                <div>
                    <h3 className='text-lg font-semibold'>
                        Choose Algorithm
                    </h3>
                    <Select 
                        placeholder="Select algorithm"
                        options={[
                            { value: 'algorithm1', label: 'Algorithm 1' },
                            { value: 'algorithm2', label: 'Algorithm 2' },
                        ]}
                        onChange={setSelectedAlgorithm}
                    />
                </div>
                <div>
                    <h3 className='text-lg font-semibold'>
                        Start Date
                    </h3>
                    <DatePicker 
                        selected={startDate}
                        onChange={(date) => setStartDate(date)}
                        placeholderText="Select start date"
                        className='w-full px-3 py-3 border border-gray-300 rounded-md text-sm text-gray-500'
                    />
                </div>
                <div>
                    <h3 className='text-lg font-semibold'>
                        End Date
                    </h3>
                    <DatePicker 
                        selected={endDate}
                        onChange={(date) => setEndDate(date)}
                        placeholderText="Select end date"
                        className='w-full px-3 py-3 border border-gray-300 rounded-md text-sm text-gray-500'
                    />
                </div>
            </div>
            <div className='flex px-5'>
                <button 
                    className='px-5 py-3 rounded-md bg-red-300 font-semibold hover:bg-red-500'
                    onClick={handleRunBacktest}
                >
                    Run backtest
                </button>
            </div>
        </div>
    );
}

export default SetStrategy