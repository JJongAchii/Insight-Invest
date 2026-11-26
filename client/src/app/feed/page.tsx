import { ReporterFeed } from "../home/MarketDesk";
import styles from "../home/marketBriefing.module.css";

export const metadata = { title: "속보 피드 · Insight Invest" };

export default async function FeedPage({ searchParams }: PageProps<"/feed">) {
  const { item } = await searchParams;
  return <div className={styles.page}>
    <header className={styles.masthead}><h1>속보 피드</h1></header>
    <ReporterFeed itemId={typeof item === "string" ? item : undefined} />
  </div>;
}
