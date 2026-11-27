import Link from "next/link";
import NewsFeed from "./NewsFeed";
import styles from "../home/marketBriefing.module.css";

export const metadata = { title: "주요 뉴스 · Insight Invest" };

export default async function NewsPage({ searchParams }: PageProps<"/news">) {
  const { item } = await searchParams;
  return <div className={styles.page}>
    <header className={styles.masthead}>
      <div>
        <h1>주요 뉴스</h1>
        <p>
          원문을 확인해 정리한 시장·경제·기업 소식입니다. 긴급으로 분류된 뉴스는 알림을 켠 기기로도 보냅니다.{" "}
          <Link className={styles.textLink} href="/actions?tab=alerts">알림 설정</Link>
        </p>
      </div>
    </header>
    <NewsFeed itemId={typeof item === "string" ? item : undefined} />
  </div>;
}
