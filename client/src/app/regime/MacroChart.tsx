"use client";

import React, { useEffect, useState } from "react";
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
    TooltipItem,
} from "chart.js";

ChartJS.register(
    CategoryScale,
    LinearScale,
    PointElement,
    LineElement,
    Title,
    Tooltip,
    Legend,
    Filler
);

interface MacroData {
    macro_id: string;
    base_date: string;
    value: number;
}

interface MacroChartProps {
    primaryData: MacroData[];
    recessionData: MacroData[];
    primaryLabel: string;
    recessionLabel: string;
    title: string;
    baseline?: number;
    icon?: string;
}

const MacroChart: React.FC<MacroChartProps> = ({
    primaryData,
    recessionData,
    primaryLabel,
    recessionLabel,
    title,
    baseline = 0,
    icon = "📊",
}) => {
    const [pluginsLoaded, setPluginsLoaded] = useState(false);

    useEffect(() => {
        const loadPlugins = async () => {
        const [{ default: annotationPlugin }, { default: zoomPlugin }] = await Promise.all([
            import("chartjs-plugin-annotation"),
            import("chartjs-plugin-zoom"),
        ]);
        ChartJS.register(annotationPlugin, zoomPlugin);
        setPluginsLoaded(true);
        };
        loadPlugins();
    }, []);

    if (!pluginsLoaded) return null;

    const mappedRecessionData = primaryData?.map((primary) => {
        const matchingRecession = recessionData?.find(
        (recession) => recession.base_date === primary.base_date
        );
        return matchingRecession ? matchingRecession.value : null;
    });

    return (
        <div className="card-modern group">
            <div className="flex items-center gap-3 mb-6">
                <div className="w-12 h-12 bg-gradient-to-r from-blue-500 to-indigo-600 rounded-xl flex items-center justify-center shadow-md">
                    <span className="text-white text-2xl">{icon}</span>
                </div>
                <h4 className="text-xl font-bold text-gray-800 group-hover:text-blue-600 transition-colors">{title}</h4>
            </div>
            <div className="bg-gradient-to-br from-gray-50 to-blue-50 rounded-xl p-4">
                <Line
                    data={{
                    labels: primaryData?.map((data) => data.base_date),
                    datasets: [
                        {
                        label: primaryLabel,
                        data: primaryData?.map((data) => data.value),
                        borderColor: "rgb(99, 102, 241)",
                        backgroundColor: "rgba(99, 102, 241, 0.1)",
                        borderWidth: 3,
                        pointRadius: 0,
                        tension: 0.4,
                        yAxisID: "left-axis",
                        },
                        {
                        label: recessionLabel,
                        data: mappedRecessionData,
                        backgroundColor: "rgba(239, 68, 68, 0.15)",
                        borderColor: "rgba(239, 68, 68, 0)",
                        fill: true,
                        tension: 0.4,
                        yAxisID: "right-axis",
                        },
                    ],
                    }}
                    options={{
                    responsive: true,
                    maintainAspectRatio: true,
                    aspectRatio: 3,
                    plugins: {
                        legend: {
                        position: "top",
                        labels: {
                            font: {
                                size: 13,
                                weight: "bold" as const,
                            },
                            padding: 15,
                            usePointStyle: true,
                            pointStyle: "circle",
                        },
                        },
                        tooltip: {
                            backgroundColor: "rgba(255, 255, 255, 0.95)",
                            titleColor: "#1f2937",
                            bodyColor: "#4b5563",
                            borderColor: "#e5e7eb",
                            borderWidth: 1,
                            padding: 12,
                            boxPadding: 6,
                            usePointStyle: true,
                            callbacks: {
                                labelColor: function(context: TooltipItem<'line'>) {
                                    return {
                                        borderColor: context.dataset.borderColor as string,
                                        backgroundColor: context.dataset.borderColor as string,
                                        borderWidth: 2,
                                        borderRadius: 2,
                                    };
                                },
                            }
                        },
                        zoom: {
                            zoom: {
                                wheel: {
                                    enabled: true,
                                },
                                pinch: {
                                    enabled: true,
                                },
                                mode: "x",
                            },
                            pan: {
                                enabled: true,
                                mode: "x",
                            },
                        },
                        annotation: {
                            annotations: {
                                baselineLine: {
                                    type: "line",
                                    yMin: baseline,
                                    yMax: baseline,
                                    borderColor: "rgb(239, 68, 68)",
                                    borderWidth: 2,
                                    borderDash: [5, 5],
                                    label: {
                                        display: true,
                                        position: "end",
                                        backgroundColor: "rgb(239, 68, 68)",
                                        color: "white",
                                        font: {
                                            weight: "bold" as const,
                                        },
                                        padding: 4,
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
                                color: (context) =>
                                context.tick.value === baseline ? "rgba(239, 68, 68, 0.3)" : "rgba(0, 0, 0, 0.05)",
                                lineWidth: (context) => (context.tick.value === baseline ? 2 : 1),
                            },
                            ticks: {
                                font: {
                                    size: 11,
                                },
                                color: "#6b7280",
                            },
                        },
                        "right-axis": {
                            type: "linear",
                            position: "right",
                            grid: {
                                drawOnChartArea: false,
                            },
                            min: 0,
                            max: 1,
                            ticks: { display: false },
                        },
                        x: {
                            grid: {
                                display: false,
                            },
                            ticks: {
                                font: {
                                    size: 11,
                                },
                                color: "#6b7280",
                                maxRotation: 0,
                                autoSkip: true,
                                maxTicksLimit: 10,
                            },
                        },
                    },
                    interaction: { mode: "nearest", intersect: false },
                    }}
                />
            </div>
        </div>
    );
};

export default MacroChart;
