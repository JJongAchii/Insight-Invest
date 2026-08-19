Insight Invest의 Next.js 클라이언트이자 개인 접근 게이트/API 프록시다.

## Runtime environment

기존 Vercel 환경 변수 이름과의 무중단 호환을 유지한다. 새 배포에서는 server-only 이름을
권장한다.

```text
API_BASE_URL=<Lambda Function URL>       # fallback: NEXT_PUBLIC_API_BASE_URL
API_KEY=<Lambda X-API-Key>               # fallback: NEXT_PUBLIC_API_KEY
SITE_ACCESS_HASH=<access-code sha256>    # optional; repository default exists
```

`NEXT_PUBLIC_*` fallback을 사용해도 해당 값은 client component에서 참조하지 않으므로 새
브라우저 번들에는 포함되지 않는다. API 요청은 `/api/backend/*`를 통해서만 전달된다.

## Getting Started

First, run the development server:

```bash
npm run dev
# or
yarn dev
# or
pnpm dev
# or
bun dev
```

Open [http://localhost:3000](http://localhost:3000) with your browser to see the result.

You can start editing the page by modifying `app/page.tsx`. The page auto-updates as you edit the file.

This project uses [`next/font`](https://nextjs.org/docs/app/building-your-application/optimizing/fonts) to automatically optimize and load [Geist](https://vercel.com/font), a new font family for Vercel.

## Learn More

To learn more about Next.js, take a look at the following resources:

- [Next.js Documentation](https://nextjs.org/docs) - learn about Next.js features and API.
- [Learn Next.js](https://nextjs.org/learn) - an interactive Next.js tutorial.

You can check out [the Next.js GitHub repository](https://github.com/vercel/next.js) - your feedback and contributions are welcome!

## Deploy on Vercel

The easiest way to deploy your Next.js app is to use the [Vercel Platform](https://vercel.com/new?utm_medium=default-template&filter=next.js&utm_source=create-next-app&utm_campaign=create-next-app-readme) from the creators of Next.js.

Check out our [Next.js deployment documentation](https://nextjs.org/docs/app/building-your-application/deploying) for more details.
