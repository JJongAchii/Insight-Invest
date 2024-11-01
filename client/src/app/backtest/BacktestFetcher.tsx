import React from 'react';

const BacktestFetcher = async (payload, setBacktestResult) => {
    try {
        const response = await fetch(`${process.env.NEXT_PUBLIC_API_BASE_URL}/backtest`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(payload),
        });

        if (!response.ok) {
            throw new Error('Failed to run backtest');
        }

        const result = await response.json();
        setBacktestResult(result);
    } catch (error) {
        console.error('Error running backtest:', error);
        setBacktestResult(null);
    }
};

export default BacktestFetcher;
