import React, { useMemo, useState } from 'react';
import { useFetchAlgorithmsQuery, useFetchTickersQuery } from "@/state/api";
import Select, { SingleValue, MultiValue, ActionMeta } from "react-select";
import DatePicker from "react-datepicker";
import "react-datepicker/dist/react-datepicker.css";

interface TickerData {
    iso_code: string;
    security_type: string;
    meta_id: string;
    ticker: string;
}

interface AlgorithmData {
    strategy: string;
    strategy_name: string;
}

interface SelectOption {
    value: string;
    label: string;
}

const SetStrategy = ({ onRunBacktest }: { onRunBacktest: any }) => {
    const { data, isLoading, error } = useFetchTickersQuery({});
    const { data: algorithmData } = useFetchAlgorithmsQuery({});
    const [startDate, setStartDate] = useState(new Date("2000-01-01"));
    const [endDate, setEndDate] = useState(new Date());
    const [selectedIsoCode, setSelectedIsoCode] = useState<SelectOption | null>(null);
    const [selectedSecurityType, setSelectedSecurityType] = useState<SelectOption | null>(null);
    const [selectedTickers, setSelectedTickers] = useState<SelectOption[]>([]);
    const [selectedAlgorithm, setSelectedAlgorithm] = useState<SelectOption | null>(null);
    const [strategyName, setStrategyName] = useState("");

    const isoCodeOptions = useMemo(() => (
        data ? Array.from(new Set(data.map((item: TickerData) => item.iso_code))).map(code => ({
            value: code,
            label: code
        } as SelectOption)) : []
    ), [data]);

    const securityTypeOptions = useMemo(() => (
        data ? Array.from(new Set(data.map((item: TickerData) => item.security_type))).map(type => ({
            value: type,
            label: type
        } as SelectOption)) : []
    ), [data]);

    const tickerOptions = useMemo(() => (
        data
        ? data
            .filter((item: TickerData) =>
                (!selectedIsoCode || item.iso_code === selectedIsoCode.value) &&
                (!selectedSecurityType || item.security_type === selectedSecurityType.value)
            )
            .map((item: TickerData) => ({
                value: item.meta_id,
                label: item.ticker
            }))
        : []
    ), [data, selectedIsoCode, selectedSecurityType]);

    const algorithmOptions = useMemo(() => (
        algorithmData ? algorithmData.map((alg: AlgorithmData) => ({
            value: alg.strategy,
            label: alg.strategy_name
        })) : []
    ), [algorithmData]);

    const handleIsoCodeChange = (newValue: SingleValue<SelectOption>, _: ActionMeta<SelectOption>) => {
        setSelectedIsoCode(newValue);
    };

    const handleSecurityTypeChange = (newValue: SingleValue<SelectOption>, _: ActionMeta<SelectOption>) => {
        setSelectedSecurityType(newValue);
    };

    const handleAlgorithmChange = (newValue: SingleValue<SelectOption>, _: ActionMeta<SelectOption>) => {
        setSelectedAlgorithm(newValue);
    };

    const handleTickersChange = (newValue: MultiValue<SelectOption>, _: ActionMeta<SelectOption>) => {
        setSelectedTickers(newValue as SelectOption[]);
    };

    const handleButtonClick = () => {
        const payload = {
            strategy_name: strategyName,
            meta_id: selectedTickers.map((meta_id) => meta_id.value),
            algorithm: selectedAlgorithm?.value,
            startDate: startDate.toISOString().split("T")[0],
            endDate: endDate.toISOString().split("T")[0],
        };
        onRunBacktest(payload);
    };


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
                    <Select<SelectOption>
                        options={isoCodeOptions}
                        placeholder="Select Country..."
                        onChange={handleIsoCodeChange}
                    />
                </div>
                <div>
                    <h4 className='text-md font-semibold'>
                        Security Type
                    </h4>
                    <Select<SelectOption>
                        options={securityTypeOptions}
                        placeholder="Select Type..."
                        onChange={handleSecurityTypeChange}
                    />
                </div>
                <div>
                    <h4 className='text-md font-semibold'>
                        Tickers
                    </h4>
                    <Select<SelectOption, true>
                        closeMenuOnSelect={false}
                        isMulti
                        options={tickerOptions}
                        placeholder="Select tickers..."
                        onChange={handleTickersChange}
                    />
                </div>
            </div>
            <div className='flex gap-3 px-5 py-5'>
                <div>
                    <h4 className='text-md font-semibold'>
                        Choose Algorithm
                    </h4>
                    <Select<SelectOption>
                        placeholder="Select algorithm"
                        options={algorithmOptions}
                        onChange={handleAlgorithmChange}
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
                        onChange={(date) => setStartDate(date || new Date())}
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
                        onChange={(date) => setEndDate(date || new Date())}
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
};

export default SetStrategy;
