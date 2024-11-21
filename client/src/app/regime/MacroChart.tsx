"use client";

import React from "react";
import { Line } from "react-chartjs-2";
import {
    Chart as ChartJS,
    CategoryScale,
    LinearScale,
    PointElement,
    LineElement,
    Title,
    Tooltip,
    Legend,
    Filler,
} from "chart.js";
import annotationPlugin from "chartjs-plugin-annotation";
ChartJS.register(annotationPlugin);
ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Title, Tooltip, Legend, Filler);


interface MacroData {
    macro_id: string;
    base_date: string;
    value: number;
}

interface MacroChartProps {
    primaryData: MacroData[]; // Array of primary data points
    recessionData: MacroData[]; // Array of recession data points
    primaryLabel: string; // Label for primary dataset
    recessionLabel: string; // Label for recession dataset
    title: string; // Chart title
    baseline?: number; // Baseline value (default = 0)
}

const MacroChart: React.FC<MacroChartProps> = ({
    primaryData,
    recessionData,
    primaryLabel,
    recessionLabel,
    title,
    baseline = 0,
}) => {
    
    const mappedRecessionData = primaryData?.map((primary) => {
        const matchingRecession = recessionData?.find((recession) => recession.base_date === primary.base_date);
        return matchingRecession ? matchingRecession.value : null;
    });

    return (
        <div className="flex flex-col bg-white shadow-lg rounded-2xl px-2 py-3 gap-5">
            <h4 className='text-lg font-semibold text-center'>{title}</h4>
            <Line
                data={{
                labels: primaryData?.map((data) => data.base_date),
                datasets: [
                    {
                        label: primaryLabel,
                        data: primaryData?.map((data) => data.value),
                        borderColor: "#2196f3", // Blue line
                        borderWidth: 2,
                        pointRadius: 0,
                        tension: 0.4,
                        yAxisID: "left-axis",
                    },
                    {
                        label: recessionLabel,
                        data: mappedRecessionData,
                        backgroundColor: "rgba(76, 175, 80, 0.2)", // Green area
                        borderColor: "rgba(76, 175, 80, 0)", // Transparent border
                        fill: true,
                        tension: 0.4,
                        yAxisID: "right-axis",
                    },
                ],
                }}
                options={{
                    responsive: true,
                    plugins: {
                        legend: {
                            position: "top",
                            labels: {
                                font: { size: 14 },
                            },
                        },
                        
                        annotation: {
                            annotations: {
                                baselineLine: {
                                    type: "line",
                                    yMin: baseline,
                                    yMax: baseline,
                                    borderColor: "#ff0000",
                                    borderWidth: 2,
                                    label: {
                                        display: true,
                                        position: "end",
                                    },
                                },
                            },
                        },
                    },
                    scales: {
                        "left-axis": {
                            type: "linear",
                            position: "left",
                            grid: {
                                drawOnChartArea: true,
                                color: (context) => (context.tick.value === baseline ? "#ff0000" : "#e0e0e0"),
                                lineWidth: (context) => (context.tick.value === baseline ? 2 : 1),
                            },
                        },
                        "right-axis": {
                            type: "linear",
                            position: "right",
                            grid: {
                                drawOnChartArea: true,
                            },
                            min: 0,
                            max: 1,
                            ticks: { display: false },
                        },
                    },
                    interaction: { mode: "nearest", intersect: false },
                }}
            />
        </div>
    );
};

export default MacroChart;
