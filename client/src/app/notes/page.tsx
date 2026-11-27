import NotesPreview from "./NotesPreview";
import styles from "../home/marketBriefing.module.css";

export const metadata = { title: "장중 노트 · Insight Invest" };

export default function NotesPage() {
  return <div className={styles.page}>
    <header className={styles.masthead}>
      <div>
        <h1>장중 노트</h1>
        <p>홈에 올리기 전 시험 운영 중인 노트입니다. 개장 40분 뒤, 11:00, 13:30, 마감 40분 전, 마감 25분 뒤와 급변할 때 씁니다.</p>
      </div>
    </header>
    <NotesPreview />
  </div>;
}
