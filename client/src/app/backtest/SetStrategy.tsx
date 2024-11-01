import React, { useMemo, useState } from 'react'
import { useFetch } from "@/state/api";
import Select from "react-select"
import DatePicker from "react-datepicker";
import "react-datepicker/dist/react-datepicker.css";


const SetStrategy = ({ onRunBacktest  }) => {
    const { data, loading, error } = useFetch(`${process.env.NEXT_PUBLIC_API_BASE_URL}/meta/tickers`);
    const [startDate, setStartDate] = useState(new Date("2000-01-01"));
    const [endDate, setEndDate] = useState(new Date());
    const [selectedIsoCode, setSelectedIsoCode] = useState(null);
    const [selectedSecurityType, setSelectedSecurityType] = useState(null);
    const [selectedTickers, setSelectedTickers] = useState([]);
    const [selectedAlgorithm, setSelectedAlgorithm] = useState(null);
    const [strategyName, setStrategyName] = useState("");

    const isoCodeOptions = useMemo(() => (
        data ? Array.from(new Set(data.map(item => item.iso_code))).map(code => ({
            value: code,
            label: code
        })) : []
    ), [data])

    const securityTypeOptions = useMemo(() => (
        data ? Array.from(new Set(data.map(item => item.security_type))).map(type => ({
            value: type,
            label: type
        })) : []
    ), [data])

    const tickerOptions = useMemo(() => (
        data 
        ? data
            .filter(item =>
                (!selectedIsoCode || item.iso_code == selectedIsoCode.value) &&
                (!selectedSecurityType || item.security_type == selectedSecurityType.value)
            )
            .map((item) => ({
                value: item.meta_id,
                label: item.ticker
            })) 
        : []
    ), [data, selectedIsoCode, selectedSecurityType]);

    const handleButtonClick = () => {
        const payload = {
            strategy_name: strategyName,
            meta_id: selectedTickers.map((meta_id) => meta_id.value),
            algorithm: selectedAlgorithm?.value,
            startDate: startDate.toISOString().split("T")[0],
            endDate: endDate.toISOString().split("T")[0],
        }
        onRunBacktest(payload);
    }
        


    return (
        <div className='flex flex-col bg-white shadow-md rounded-2xl pb-12'>
            <div className='flex gap-3 px-5 py-5'>
                <div>
                    <h4 className='text-md font-semibold'>
                        Strategy Name
                    </h4>
                    <input 
                        type='text'
                        placeholder='Your Strategy name...'
                        className='w-full px-3 py-3 border border-gray-300 rounded-md text-sm text-gray-500'
                        onChange={(e) => setStrategyName(e.target.value)}
                    />
                </div>
            </div>
            <div className='flex gap-3 px-5 py-5'>
                <div>
                    <h4 className='text-md font-semibold'>
                        Country
                    </h4>
                    <Select 
                        options={isoCodeOptions}
                        placeholder="Select Country..."
                        onChange={setSelectedIsoCode}
                    />
                </div>
                <div>
                    <h4 className='text-md font-semibold'>
                        Security Type
                    </h4>
                    <Select 
                        options={securityTypeOptions}
                        placeholder="Select Security Type..."
                        onChange={setSelectedSecurityType}
                    />
                </div>
                <div>
                    <h4 className='text-md font-semibold'>
                        Tickers
                    </h4>
                    <Select 
                        isMulti
                        options={tickerOptions}
                        placeholder="Select tickers..."
                        onChange={setSelectedTickers}
                    />
                </div>
            </div>
            <div className='flex gap-3 px-5 py-5'>
                <div>
                    <h4 className='text-md font-semibold'>
                        Choose Algorithm
                    </h4>
                    <Select 
                        placeholder="Select algorithm"
                        options={[
                            { value: 'dual_mmt', label: 'Dual Momentum' },
                            { value: 'algorithm2', label: 'Algorithm 2' },
                        ]}
                        onChange={setSelectedAlgorithm}
                    />
                </div>
            </div>
            <div className='flex gap-3 px-5 py-5'>
                <div>
                    <h4 className='text-md font-semibold'>
                        Start Date
                    </h4>
                    <DatePicker 
                        selected={startDate}
                        onChange={(date) => setStartDate(date)}
                        placeholderText="Select start date"
                        className='w-full px-3 py-3 border border-gray-300 rounded-md text-sm text-gray-500'
                    />
                </div>
                <div>
                    <h4 className='text-md font-semibold'>
                        End Date
                    </h4>
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
                    onClick={handleButtonClick}
                >
                    Run backtest
                </button>
            </div>
        </div>
    );
}

export default SetStrategy