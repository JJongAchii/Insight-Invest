import { createApi, fetchBaseQuery } from "@reduxjs/toolkit/query/react";
import { useEffect, useState } from 'react';


export const api = createApi({
  baseQuery: fetchBaseQuery({ baseUrl: process.env.NEXT_PUBLIC_API_BASE_URL }),
  reducerPath: "api",
  tagTypes: [],
  endpoints: (build) => ({}),
});


export const useFetch = (url) => {
    const [data, setData] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    useEffect(() => {
        async function fetchData() {
            try {
                const res = await fetch(url);
                if (!res.ok) throw new Error(`Error: ${res.status}`);
                const result = await res.json();
                setData(result);
            } catch (err) {
                setError(err.message);
            } finally {
                setLoading(false);
            }
        }
        fetchData();
    }, [url]);

    return { data, loading, error };
};


export const {} = api;
