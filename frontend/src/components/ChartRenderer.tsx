import {
  Bar,
  BarChart,
  Cell,
  Legend,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { ChartSuggestion } from "@/lib/api";

type ChartRendererProps = {
  columns: string[];
  rows: Array<Array<unknown>>;
  suggestion: ChartSuggestion;
};

const COLORS = ["#5B8CFF", "#65D6AD", "#FFB36B", "#F46E6E", "#9C7CFF"];

function toDataObjects(columns: string[], rows: Array<Array<unknown>>) {
  return rows.map((row) =>
    Object.fromEntries(columns.map((col, idx) => [col, row[idx]]))
  );
}

export function ChartRenderer({ columns, rows, suggestion }: ChartRendererProps) {
  const { chart_type, x_field, y_field, series_field } = suggestion;
  const data = toDataObjects(columns, rows);

  if (!x_field || !y_field || chart_type === "table") {
    return null;
  }

  if (chart_type === "donut") {
    return (
      <div className="chart-card">
        <ResponsiveContainer width="100%" height={320}>
          <PieChart>
            <Pie
              data={data}
              dataKey={y_field}
              nameKey={x_field}
              innerRadius={70}
              outerRadius={120}
              paddingAngle={3}
            >
              {data.map((_, index) => (
                <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
              ))}
            </Pie>
            <Tooltip />
            <Legend />
          </PieChart>
        </ResponsiveContainer>
      </div>
    );
  }

  if (chart_type === "line") {
    return (
      <div className="chart-card">
        <ResponsiveContainer width="100%" height={320}>
          <LineChart data={data}>
            <XAxis dataKey={x_field} />
            <YAxis />
            <Tooltip />
            <Legend />
            <Line type="monotone" dataKey={y_field} stroke="#5B8CFF" strokeWidth={2} />
          </LineChart>
        </ResponsiveContainer>
      </div>
    );
  }

  if (chart_type === "stacked_bar" && series_field) {
    const grouped: Record<string, Record<string, number>> = {};
    const seriesValues = new Set<string>();

    data.forEach((row) => {
      const xValue = String(row[x_field]);
      const seriesValue = String(row[series_field]);
      const yValue = Number(row[y_field] ?? 0);

      if (!grouped[xValue]) {
        grouped[xValue] = {};
      }
      grouped[xValue][seriesValue] = (grouped[xValue][seriesValue] ?? 0) + yValue;
      seriesValues.add(seriesValue);
    });

    const stackedData = Object.entries(grouped).map(([key, values]) => ({
      [x_field]: key,
      ...values,
    }));

    return (
      <div className="chart-card">
        <ResponsiveContainer width="100%" height={320}>
          <BarChart data={stackedData}>
            <XAxis dataKey={x_field} />
            <YAxis />
            <Tooltip />
            <Legend />
            {Array.from(seriesValues).map((series, index) => (
              <Bar
                key={series}
                dataKey={series}
                stackId="stack"
                fill={COLORS[index % COLORS.length]}
              />
            ))}
          </BarChart>
        </ResponsiveContainer>
      </div>
    );
  }

  if (chart_type === "bar") {
    return (
      <div className="chart-card">
        <ResponsiveContainer width="100%" height={320}>
          <BarChart data={data}>
            <XAxis dataKey={x_field} />
            <YAxis />
            <Tooltip />
            <Legend />
            <Bar dataKey={y_field} fill="#5B8CFF" radius={[6, 6, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    );
  }

  return null;
}
