export interface BacktestPayload {
    strategy_name: string;
    meta_id: string[];
    algorithm: string | undefined;
    startDate: string;
    endDate: string;
}

export interface BacktestResult {
    weights: string;
    nav: string;
    metrics: string;
}

export const BacktestFetcher = async (
    payload: BacktestPayload,
    setBacktestResult: (result: BacktestResult | null) => void
) => {
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

        const result: BacktestResult = await response.json();
        setBacktestResult(result);
    } catch (error) {
        console.error('Error running backtest:', error);
        setBacktestResult(null);
    }
};


export const SaveStrategy = async (strategyData: BacktestPayload) => {
    try {
        const response = await fetch(`${process.env.NEXT_PUBLIC_API_BASE_URL}/backtest/savestrategy`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(strategyData),
        });

        if (!response.ok) {
            throw new Error('Failed to save strategy');
        }

        const data = await response.json();
        console.log('Save successful:', data);
    } catch (error) {
        console.error('Error saving data:', error);
    }
};


export const ClearStrategy = async () => {
    try {
        const response = await fetch(`${process.env.NEXT_PUBLIC_API_BASE_URL}/backtest/clearstrategy`, {
            method: 'POST',
        });

        if (!response.ok) {
            throw new Error('Failed to clear strategy');
        }

        const data = await response.json();
        console.log('Clear successful:', data);
    } catch (error) {
        console.error('Error clearing data:', error);
    }
}
