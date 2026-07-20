// LoadingSpinner.tsx

import React from 'react';

const LoadingSpinner = () => {
    return (
        <div
            className="fixed inset-0 flex items-center justify-center z-50"
            style={{ background: 'rgba(10, 15, 26, 0.5)' }}
        >
            <div className="loader"></div>
            <style jsx>{`
                .loader {
                    border: 8px solid var(--border);
                    border-top: 8px solid var(--primary);
                    border-radius: 50%;
                    width: 50px;
                    height: 50px;
                    animation: spin 1s linear infinite;
                }

                @keyframes spin {
                    0% {
                        transform: rotate(0deg);
                    }
                    100% {
                        transform: rotate(360deg);
                    }
                }
            `}</style>
        </div>
    );
};

export default LoadingSpinner;
