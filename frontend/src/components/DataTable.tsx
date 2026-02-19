type DataTableProps = {
  columns: string[];
  rows: Array<Array<unknown>>;
};

export function DataTable({ columns, rows }: DataTableProps) {
  if (columns.length === 0) {
    return <div className="empty-state">No data to display.</div>;
  }

  return (
    <div className="table-wrapper">
      <table>
        <thead>
          <tr>
            {columns.map((col) => (
              <th key={col}>{col}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, rowIndex) => (
            <tr key={`${rowIndex}-${row.length}`}>
              {row.map((value, colIndex) => (
                <td key={`${rowIndex}-${colIndex}`}>
                  {value === null || value === undefined ? "-" : String(value)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
