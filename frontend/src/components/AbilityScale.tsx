import { formatTheta } from '../lib/format';

const MIN = -3;
const MAX = 3;
const WIDTH = 600;
const BANDS = [
  { from: -3, to: -1, fill: 'var(--band-1)', label: 'Foundational', range: 'below −1' },
  { from: -1, to: 0, fill: 'var(--band-2)', label: 'Developing', range: '−1 to 0' },
  { from: 0, to: 1, fill: 'var(--band-3)', label: 'Proficient', range: '0 to +1' },
  { from: 1, to: 3, fill: 'var(--band-4)', label: 'Advanced', range: 'above +1' },
];

const x = (theta: number) => ((Math.min(MAX, Math.max(MIN, theta)) - MIN) / (MAX - MIN)) * WIDTH;

/** Ability estimate as a point on the logit scale, with its 95% interval and the band zones. */
export function AbilityScale({ theta, low, high }: { theta: number; low: number; high: number }) {
  return (
    <figure className="scale">
      <svg
        viewBox={`0 -4 ${WIDTH} 56`}
        role="img"
        aria-label={`Ability estimate ${formatTheta(theta)}, 95% interval ${formatTheta(low)} to ${formatTheta(high)}`}
      >
        {BANDS.map((band) => (
          <rect
            key={band.label}
            x={x(band.from)}
            y={10}
            width={x(band.to) - x(band.from)}
            height={18}
            fill={band.fill}
          />
        ))}
        <line
          x1={x(low)}
          x2={x(high)}
          y1={19}
          y2={19}
          stroke="var(--ink)"
          strokeWidth={3}
          strokeLinecap="round"
        />
        <line x1={x(low)} x2={x(low)} y1={12} y2={26} stroke="var(--ink)" strokeWidth={2} />
        <line x1={x(high)} x2={x(high)} y1={12} y2={26} stroke="var(--ink)" strokeWidth={2} />
        <circle cx={x(theta)} cy={19} r={8} fill="var(--primary)" stroke="var(--surface)" strokeWidth={3} />
        {[-3, -2, -1, 0, 1, 2, 3].map((tick) => (
          <text key={tick} x={x(tick)} y={46} textAnchor="middle" fontSize={12} fill="var(--ink-muted)">
            {tick > 0 ? `+${tick}` : tick}
          </text>
        ))}
      </svg>
      <figcaption>
        <div className="scale-labels">
          {BANDS.map((band) => (
            <span key={band.label}>{band.label}</span>
          ))}
        </div>
        <div className="legend scale-legend">
          {BANDS.map((band) => (
            <span key={band.label}>
              <span className="legend-swatch" style={{ background: band.fill }} />
              {band.label}: {band.range}
            </span>
          ))}
        </div>
      </figcaption>
    </figure>
  );
}
