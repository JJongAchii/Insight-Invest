import type { NextApiRequest, NextApiResponse } from 'next'


export default async function handler(req: NextApiRequest, res: NextApiResponse) {
    if (req.method === 'GET') {
      try {
        // FastAPI의 /stocks/ 엔드포인트로 GET 요청
        const response = await fetch("http://localhost:8000/meta/");
        const data = await response.json();
  
        res.status(200).json(data); // 클라이언트에 데이터 반환
      } catch (error) {
        console.error(error);
        res.status(500).json({ error: "Failed to fetch stock data" });
      }
    } else {
      res.setHeader('Allow', ['GET']);
      res.status(405).end(`Method ${req.method} Not Allowed`);
    }
  }
  