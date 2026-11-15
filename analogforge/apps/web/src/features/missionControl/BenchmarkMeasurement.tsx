import type { BenchmarkRow } from '../../api/visualization';
import { benchmarkText, readableQuantity } from './tour';

/** A display scale for one receipt-owned value and its accepted contract limits. */
export function BenchmarkMeasurement({ row, simplified = false }: { row: BenchmarkRow; simplified?: boolean }) {
  const { measurement, requirement } = row;
  const value = measurement.value;
  if (value === null || !Number.isFinite(value)) return null;
  const limits = [requirement.lower, requirement.upper].filter((item): item is number => item !== null && Number.isFinite(item));
  const low = Math.min(0, value, ...limits), high = Math.max(0, value, ...limits);
  const span = high - low || 1; const minimum = low < 0 ? low - span * .08 : 0; const maximum = high + span * .12;
  const x = (item: number) => 34 + ((item - minimum) / (maximum - minimum)) * 432;
  const unit = measurement.unit === 'none' || measurement.unit === '1' ? '' : measurement.unit ?? '';
  const text = readableQuantity(value, unit, simplified);
  const references = [...new Set(limits)];
  return <figure className="mc-measurement" data-testid="benchmark-measurement-chart" data-evidence-id={measurement.comparison_evidence_id ?? undefined}>
    <svg viewBox="0 0 500 96" role="img" aria-label={`${requirement.label}: measured ${text}. Accepted rule: ${benchmarkText(requirement, simplified)}.`}>
      <line className="mc-measurement-axis" x1="34" x2="466" y1="46" y2="46"/>
      {references.map(limit => <g key={limit}><line className="mc-measurement-limit" x1={x(limit)} x2={x(limit)} y1="25" y2="64"/><title>Accepted limit: {readableQuantity(limit, unit, simplified)}</title><text x={x(limit)} y="82" textAnchor="middle">{readableQuantity(limit, simplified && unit === 'fraction' ? unit : '', simplified)}</text></g>)}
      <circle className="mc-measurement-value" cx={x(value)} cy="46" r="5"/>
      <text className="mc-measurement-label" x={x(value)} y="15" textAnchor="middle">{text}</text>
      <text x="34" y="94" textAnchor="start">{minimum === 0 && !references.includes(0) ? '0' : ''}</text>
    </svg>
    <figcaption><span>● Measured value</span>{references.length > 0 && <span>┆ Accepted limit{references.length === 1 ? '' : 's'}</span>}<span>{measurement.support_scale_m} m comparison support</span></figcaption>
  </figure>;
}
