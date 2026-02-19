"use client";

import { useRef, useState } from "react";

type DataSourceDropzoneProps = {
  disabled: boolean;
  onUploadCsv: (file: File) => void;
  onUploadSqlite: (file: File) => void;
};

function pickHandler(
  file: File,
  onUploadCsv: (file: File) => void,
  onUploadSqlite: (file: File) => void
): string | null {
  const name = file.name.toLowerCase();
  if (name.endsWith(".csv")) {
    onUploadCsv(file);
    return null;
  }
  if (
    name.endsWith(".db") ||
    name.endsWith(".sqlite") ||
    name.endsWith(".sqlite3")
  ) {
    onUploadSqlite(file);
    return null;
  }
  return "Unsupported file type. Upload a CSV or SQLite file.";
}

export function DataSourceDropzone({
  disabled,
  onUploadCsv,
  onUploadSqlite,
}: DataSourceDropzoneProps) {
  const [isDragging, setIsDragging] = useState(false);
  const [hint, setHint] = useState<string | null>(null);
  const csvRef = useRef<HTMLInputElement>(null);
  const sqliteRef = useRef<HTMLInputElement>(null);

  return (
    <section
      className={`upload-stage${isDragging ? " dragging" : ""}`}
      onDragOver={(event) => {
        event.preventDefault();
        if (!disabled) setIsDragging(true);
      }}
      onDragLeave={(event) => {
        event.preventDefault();
        setIsDragging(false);
      }}
      onDrop={(event) => {
        event.preventDefault();
        setIsDragging(false);
        if (disabled) return;

        const file = event.dataTransfer.files?.[0];
        if (!file) return;
        const maybeError = pickHandler(file, onUploadCsv, onUploadSqlite);
        setHint(maybeError);
      }}
    >
      <div className="upload-stage-icon" aria-hidden="true">
        <span />
      </div>
      <h3>Drop Your Data Source Here</h3>
      <p>
        Drag and drop a CSV or SQLite file, or choose one manually to begin
        querying.
      </p>
      <div className="upload-stage-actions">
        <button
          type="button"
          className="upload-cta csv"
          disabled={disabled}
          onClick={() => csvRef.current?.click()}
        >
          Upload CSV
        </button>
        <button
          type="button"
          className="upload-cta sqlite"
          disabled={disabled}
          onClick={() => sqliteRef.current?.click()}
        >
          Upload SQLite
        </button>
      </div>
      <p className="upload-stage-footnote">
        Supported: <code>.csv</code>, <code>.db</code>, <code>.sqlite</code>,{" "}
        <code>.sqlite3</code>
      </p>
      {hint && <p className="upload-stage-hint">{hint}</p>}
      <input
        ref={csvRef}
        type="file"
        accept=".csv"
        hidden
        disabled={disabled}
        onChange={(event) => {
          const file = event.target.files?.[0];
          if (!file) return;
          setHint(pickHandler(file, onUploadCsv, onUploadSqlite));
        }}
      />
      <input
        ref={sqliteRef}
        type="file"
        accept=".db,.sqlite,.sqlite3"
        hidden
        disabled={disabled}
        onChange={(event) => {
          const file = event.target.files?.[0];
          if (!file) return;
          setHint(pickHandler(file, onUploadCsv, onUploadSqlite));
        }}
      />
    </section>
  );
}
