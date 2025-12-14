import React, { useMemo, useState } from 'react';
import { useFetchAlgorithmsQuery, useFetchTickersQuery } from "@/state/api";
import Select, { SingleValue, MultiValue } from "react-select";
import DatePicker from "react-datepicker";
import "react-datepicker/dist/react-datepicker.css";
import { BacktestPayload } from "./BacktestFetcher";

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

interface SetStrategyProps {
    onRunBacktest: (payload: BacktestPayload) => void;
}

const SetStrategy: React.FC<SetStrategyProps> = ({ onRunBacktest }) => {
    const { data } = useFetchTickersQuery({});
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

    const handleIsoCodeChange = (newValue: SingleValue<SelectOption>) => {
        setSelectedIsoCode(newValue);
    };

    const handleSecurityTypeChange = (newValue: SingleValue<SelectOption>) => {
        setSelectedSecurityType(newValue);
    };

    const handleAlgorithmChange = (newValue: SingleValue<SelectOption>) => {
        setSelectedAlgorithm(newValue);
    };

    const handleTickersChange = (newValue: MultiValue<SelectOption>) => {
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
        <div className='card-modern'>
            <div className='flex items-center gap-3 mb-6'>
                <div className="w-10 h-10 bg-gradient-to-r from-purple-500 to-pink-600 rounded-xl flex items-center justify-center">
                    <span className="text-white text-xl font-bold">⚙️</span>
                </div>
                <h3 className='text-xl font-bold text-gray-800'>
                    Strategy Configuration
                </h3>
            </div>

            <div className='bg-gradient-to-br from-gray-50 to-blue-50 rounded-xl p-6 space-y-6'>
                {/* Strategy Name */}
                <div>
                    <h4 className='text-sm font-semibold text-gray-700 mb-2'>
                        Strategy Name
                    </h4>
                    <input
                        type='text'
                        placeholder='Enter your strategy name...'
                        className='input-modern w-full'
                        onChange={(e) => setStrategyName(e.target.value)}
                    />
                </div>

                {/* Filters */}
                <div className='grid grid-cols-1 md:grid-cols-3 gap-4'>
                    <div>
                        <h4 className='text-sm font-semibold text-gray-700 mb-2'>
                            Country
                        </h4>
                        <Select<SelectOption>
                            options={isoCodeOptions}
                            placeholder="Select Country..."
                            onChange={handleIsoCodeChange}
                            styles={{
                                control: (base) => ({
                                    ...base,
                                    borderRadius: '0.75rem',
                                    borderWidth: '2px',
                                    borderColor: '#e5e7eb',
                                    padding: '0.25rem',
                                    boxShadow: 'none',
                                    '&:hover': {
                                        borderColor: '#93c5fd',
                                    },
                                }),
                            }}
                        />
                    </div>
                    <div>
                        <h4 className='text-sm font-semibold text-gray-700 mb-2'>
                            Security Type
                        </h4>
                        <Select<SelectOption>
                            options={securityTypeOptions}
                            placeholder="Select Type..."
                            onChange={handleSecurityTypeChange}
                            styles={{
                                control: (base) => ({
                                    ...base,
                                    borderRadius: '0.75rem',
                                    borderWidth: '2px',
                                    borderColor: '#e5e7eb',
                                    padding: '0.25rem',
                                    boxShadow: 'none',
                                    '&:hover': {
                                        borderColor: '#93c5fd',
                                    },
                                }),
                            }}
                        />
                    </div>
                    <div>
                        <h4 className='text-sm font-semibold text-gray-700 mb-2'>
                            Tickers
                        </h4>
                        <Select<SelectOption, true>
                            closeMenuOnSelect={false}
                            isMulti
                            options={tickerOptions}
                            placeholder="Select tickers..."
                            onChange={handleTickersChange}
                            styles={{
                                control: (base) => ({
                                    ...base,
                                    borderRadius: '0.75rem',
                                    borderWidth: '2px',
                                    borderColor: '#e5e7eb',
                                    padding: '0.25rem',
                                    boxShadow: 'none',
                                    '&:hover': {
                                        borderColor: '#93c5fd',
                                    },
                                }),
                            }}
                        />
                    </div>
                </div>

                {/* Algorithm */}
                <div>
                    <h4 className='text-sm font-semibold text-gray-700 mb-2'>
                        Choose Algorithm
                    </h4>
                    <Select<SelectOption>
                        placeholder="Select algorithm"
                        options={algorithmOptions}
                        onChange={handleAlgorithmChange}
                        styles={{
                            control: (base) => ({
                                ...base,
                                borderRadius: '0.75rem',
                                borderWidth: '2px',
                                borderColor: '#e5e7eb',
                                padding: '0.25rem',
                                boxShadow: 'none',
                                '&:hover': {
                                    borderColor: '#93c5fd',
                                },
                            }),
                        }}
                    />
                </div>

                {/* Dates */}
                <div className='grid grid-cols-1 md:grid-cols-2 gap-4'>
                    <div>
                        <h4 className='text-sm font-semibold text-gray-700 mb-2'>
                            Start Date
                        </h4>
                        <DatePicker
                            selected={startDate}
                            onChange={(date) => setStartDate(date || new Date())}
                            placeholderText="Select start date"
                            className='input-modern w-full'
                        />
                    </div>
                    <div>
                        <h4 className='text-sm font-semibold text-gray-700 mb-2'>
                            End Date
                        </h4>
                        <DatePicker
                            selected={endDate}
                            onChange={(date) => setEndDate(date || new Date())}
                            placeholderText="Select end date"
                            className='input-modern w-full'
                        />
                    </div>
                </div>

                {/* Run Button */}
                <div className='flex justify-end pt-4'>
                    <button
                        className='btn-primary'
                        onClick={handleButtonClick}
                    >
                        🚀 Run Backtest
                    </button>
                </div>
            </div>
        </div>
    );
};

export default SetStrategy;
