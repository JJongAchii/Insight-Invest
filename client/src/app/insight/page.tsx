'use client';

import React, { useState } from 'react';

const Page = () => {
  const [inputValue, setInputValue] = useState<string>(''); // inputValue는 문자열
  const [long1Result, setLong1Result] = useState<number | null>(null); // long1 result
  const [long2Result, setLong2Result] = useState<number | null>(null); // long2 result
  const [short1Result, setShort1Result] = useState<number | null>(null); // short1 result
  const [short2Result, setShort2Result] = useState<number | null>(null); // short2 result

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value;
    setInputValue(value);

    // 숫자 형식 확인 및 계산
    const numericValue = parseFloat(value);
    if (!isNaN(numericValue)) {
      setLong1Result(numericValue + 0.02);
      setLong2Result(numericValue + 0.02 * 2);
      setShort1Result(numericValue - 0.02);
      setShort2Result(numericValue - 0.02 * 2);
    } else {
      setLong1Result(null);
      setLong2Result(null);
      setShort1Result(null);
      setShort2Result(null);
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '10px' }}>
      {/* long 결과 (위) */}
      <div style={{ display: 'flex', gap: '20px' }}>
        <div style={{ padding: '10px', border: '1px solid #ddd', borderRadius: '5px' }}>
          <p>Long1: {long1Result !== null ? long1Result.toFixed(2) : 'Enter a valid number'}</p>
        </div>
        <div style={{ padding: '10px', border: '1px solid #ddd', borderRadius: '5px' }}>
          <p>Long2: {long2Result !== null ? long2Result.toFixed(2) : 'Enter a valid number'}</p>
        </div>
      </div>

      {/* 입력 필드 */}
      <input
        type="text"
        placeholder="Standard Value"
        value={inputValue}
        onChange={handleInputChange}
        style={{ padding: '10px', border: '1px solid #ddd', borderRadius: '5px' }}
      />

      {/* short 결과 (아래) */}
      <div style={{ display: 'flex', gap: '20px' }}>
        <div style={{ padding: '10px', border: '1px solid #ddd', borderRadius: '5px' }}>
          <p>Short1: {short1Result !== null ? short1Result.toFixed(2) : 'Enter a valid number'}</p>
        </div>
        <div style={{ padding: '10px', border: '1px solid #ddd', borderRadius: '5px' }}>
          <p>Short2: {short2Result !== null ? short2Result.toFixed(2) : 'Enter a valid number'}</p>
        </div>
      </div>
    </div>
  );
};

export default Page;
