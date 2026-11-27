/** @type {import('next').NextConfig} */
const nextConfig = {
  // 뉴스 화면의 이전 주소. 저장해 둔 링크와 알림이 선택한 글(?item=)과 함께 새 주소로 열린다.
  redirects: async () => [{ source: "/feed", destination: "/news", permanent: false }],
};

module.exports = nextConfig;
