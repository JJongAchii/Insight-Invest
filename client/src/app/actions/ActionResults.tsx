import type { ActionResultMetric, ActionResultSummary } from "@/state/api";
import styles from "./actionResults.module.css";

const STATUS = {
  released: "발표값 확인",
  partial: "일부 결과 확인",
  scheduled: "발표 전 참고",
  pending: "결과 반영 대기",
  unavailable: "수치 확인 불가",
};

function valueLabel(value: number | null, unit: string, signed = false) {
  if (value == null || !Number.isFinite(value)) return "—";
  const sign = signed && value > 0 ? "+" : "";
  const format = (number: number, digits = 2) => new Intl.NumberFormat("en-US", {
    maximumFractionDigits: digits,
  }).format(number);
  if (unit === "USD") {
    const scale = Math.abs(value) >= 1e12 ? 1e12 : Math.abs(value) >= 1e9 ? 1e9 : Math.abs(value) >= 1e6 ? 1e6 : 1;
    const suffix = scale === 1e12 ? "T" : scale === 1e9 ? "B" : scale === 1e6 ? "M" : "";
    return `${sign}$${format(value / scale)}${suffix}`;
  }
  if (unit === "USD/주") return `${sign}$${format(value)}`;
  return `${sign}${format(value)}${unit.startsWith("%") ? "" : " "}${unit}`;
}

function periodLabel(value: string | null, frequency: ActionResultMetric["frequency"]) {
  if (!value) return null;
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) return value;
  const [year, month] = value.split("-");
  return frequency === "quarterly" ? `${year}년 ${Math.ceil(Number(month) / 3)}분기` : `${year}.${month}`;
}

export default function ActionResults({ summary }: { summary: ActionResultSummary }) {
  if (!summary.metrics.length) return null;
  return <section className={styles.summary} aria-label="발표 수치 요약">
    <div className={styles.heading}>
      <span>{STATUS[summary.status]}</span>
      <span>{summary.source}</span>
    </div>
    {summary.metrics.map((metric) => {
      const compareEstimate = metric.comparison === "estimate";
      const actualPeriod = periodLabel(metric.actual_period, metric.frequency);
      const previousPeriod = periodLabel(metric.previous_period, metric.frequency);
      const pending = metric.status === "scheduled" ? "발표 전" : metric.status === "unavailable" ? "확인 불가" : "반영 대기";
      return <div className={styles.metric} key={metric.label}>
        <div className={styles.name}>
          <strong>{metric.label}</strong>
          {actualPeriod && <span>관측 {actualPeriod}</span>}
        </div>
        <dl className={`${styles.values} ${compareEstimate ? styles.earnings : ""}`}>
          <div className={styles.actual}>
            <dt>발표값</dt>
            <dd>{metric.actual == null ? <span className={styles.missing}>{pending}</span> : valueLabel(metric.actual, metric.unit)}</dd>
          </div>
          <div>
            <dt>예상치</dt>
            <dd>{metric.estimate == null ? <span className={styles.missing}>미제공</span> : valueLabel(metric.estimate, metric.unit)}</dd>
          </div>
          {!compareEstimate && <div>
            <dt>{metric.status === "released" ? "이전값" : "최근값"}</dt>
            <dd>{metric.previous == null ? <span className={styles.missing}>미제공</span> : valueLabel(metric.previous, metric.unit)}</dd>
            {previousPeriod && <small>{previousPeriod}</small>}
          </div>}
          <div>
            <dt>{compareEstimate ? "예상 대비" : "이전 대비"}</dt>
            <dd>{metric.difference == null ? <span className={styles.missing}>{metric.note ? "비교 보류" : "—"}</span> : valueLabel(metric.difference, metric.difference_unit, true)}</dd>
          </div>
        </dl>
        {metric.note && <p className={styles.note}>{metric.note}</p>}
      </div>;
    })}
    <div className={styles.footnote}>
      <p>{summary.note}</p>
      <span>수치 확인 {new Intl.DateTimeFormat("ko-KR", {
        month: "short", day: "numeric", hour: "2-digit", minute: "2-digit", timeZone: "Asia/Seoul",
      }).format(new Date(summary.available_at))} KST</span>
    </div>
  </section>;
}
