import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "Insight Invest",
    short_name: "Insight",
    description: "시장 흐름과 포트폴리오 판단을 연결하는 개인 투자 인사이트 앱",
    start_url: "/home?source=pwa",
    scope: "/",
    display: "standalone",
    background_color: "#0a0f1a",
    theme_color: "#0a0f1a",
    orientation: "portrait-primary",
    categories: ["finance", "productivity"],
    shortcuts: [
      {
        name: "Action Center",
        short_name: "Actions",
        description: "지금 확인할 투자 Action",
        url: "/actions?source=shortcut",
        icons: [{ src: "/icons/icon-192.png", sizes: "192x192" }],
      },
      {
        name: "My Portfolio",
        short_name: "Portfolio",
        description: "보유 자산과 위험 확인",
        url: "/portfolio?source=shortcut",
        icons: [{ src: "/icons/icon-192.png", sizes: "192x192" }],
      },
      {
        name: "Research Radar",
        short_name: "Research",
        description: "새로 발견한 퀀트 논문과 자료",
        url: "/research?from=shortcut",
        icons: [{ src: "/icons/icon-192.png", sizes: "192x192" }],
      },
    ],
    icons: [
      {
        src: "/icons/icon-192.png",
        sizes: "192x192",
        type: "image/png",
        purpose: "any",
      },
      {
        src: "/icons/icon-512.png",
        sizes: "512x512",
        type: "image/png",
        purpose: "any",
      },
      {
        src: "/icons/icon-512.png",
        sizes: "512x512",
        type: "image/png",
        purpose: "maskable",
      },
    ],
  };
}
