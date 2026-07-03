/** CSV export utility. */

/**
 * Convert an array of objects to CSV string.
 * @param data - Array of objects to export.
 * @param columns - Column definitions with key and label.
 * @returns CSV string content.
 */
export function toCSV(data: Record<string, any>[], columns: { key: string; label: string }[]): string {
  const header = columns.map(c => `"${c.label}"`).join(',')
  const rows = data.map(row =>
    columns.map(c => {
      const val = row[c.key]
      if (val === null || val === undefined) return ''
      const str = String(val).replace(/"/g, '""')
      return `"${str}"`
    }).join(',')
  )
  return '\uFEFF' + [header, ...rows].join('\n') // BOM for Excel UTF-8 compatibility
}

/**
 * Trigger a browser download of a CSV file.
 */
export function downloadCSV(content: string, filename: string) {
  const blob = new Blob([content], { type: 'text/csv;charset=utf-8;' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

/**
 * Export data as CSV and trigger download.
 */
export function exportToCSV(
  data: Record<string, any>[],
  columns: { key: string; label: string }[],
  filename: string,
) {
  const csv = toCSV(data, columns)
  downloadCSV(csv, filename)
}

/**
 * Get current timestamp string for filename.
 */
export function timestampSuffix(): string {
  const d = new Date()
  return `${d.getFullYear()}${String(d.getMonth()+1).padStart(2,'0')}${String(d.getDate()).padStart(2,'0')}_${String(d.getHours()).padStart(2,'0')}${String(d.getMinutes()).padStart(2,'0')}`
}
