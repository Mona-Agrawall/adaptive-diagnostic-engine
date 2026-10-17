import type { TrajectoryPoint } from '../api/types';
import { formatTheta } from '../lib/format';

const W = 640;
const H = 240;
const PAD = { top: 12, right: 16, bottom: 32, left: 40 };
const Y_MIN = -3.5;
const Y_MAX = 3.5;

/** Ability estimate after each answer, with a shaded 95% interval. */
export function TrajectoryChart({ points }: { points: TrajectoryPoint[] }) {
  const last = points.at(-1)?.position ?? 1;
  const xs = (position: number) => PAD.left + (position / Math.max(1, last)) * (W - PAD.left - PAD.right);
  const ys = (theta: number) =>
    PAD.top +
    ((Y_MAX - Math.min(Y_MAX, Math.max(Y_MIN, theta))) / (Y_MAX - Y_MIN)) * (H - PAD.top - PAD.bottom);

  const upper = points.map((p) => `${xs(p.position)},${ys(p.theta + 1.96 * p.se)}`);
  const lower = [...points].reverse().map((p) => `${xs(p.position)},${ys(p.theta - 1.96 * p.se)}`);
  const line = points.map((p) => `${xs(p.position)},${ys(p.theta)}`).join(' ');
  const description = points
    .map((p) =>
      p.position === 0
        ? `Start: ${formatTheta(p.theta)}`
        : `After question ${p.position}: ${formatTheta(p.theta)}`,
    )
    .join('; ');

  return (
    <figure className="chart">
      <svg
        viewBox={`0 0 ${W} ${H}`}
        role="img"
        aria-label={`Ability estimate after each answer. ${description}`}
      >
        {[-3, -2, -1, 0, 1, 2, 3].map((tick) => (
          <g key={tick}>
            <line
              x1={PAD.left}
              x2={W - PAD.right}
              y1={ys(tick)}
              y2={ys(tick)}
              stroke="var(--border)"
              strokeDasharray={tick === 0 ? undefined : '3 4'}
            />
            <text x={PAD.left - 8} y={ys(tick) + 4} textAnchor="end" fontSize={11} fill="var(--ink-muted)">
              {tick > 0 ? `+${tick}` : tick}
            </text>
          </g>
        ))}
        <polygon points={[...upper, ...lower].join(' ')} fill="var(--primary)" opacity={0.14} />
        <polyline
          points={line}
          fill="none"
          stroke="var(--primary)"
          strokeWidth={2.5}
          strokeLinejoin="round"
        />
        {points.map((p) => (
          <circle key={p.position} cx={xs(p.position)} cy={ys(p.theta)} r={3.5} fill="var(--primary)" />
        ))}
        {points.map((p) => (
          <text
            key={`label-${p.position}`}
            x={xs(p.position)}
            y={H - 10}
            textAnchor="middle"
            fontSize={11}
            fill="var(--ink-muted)"
          >
            {p.position === 0 ? 'Start' : p.position}
          </text>
        ))}
      </svg>
      <figcaption className="legend">
        <span>
          <span className="legend-swatch" style={{ background: 'var(--primary)' }} />
          Estimate
        </span>
        <span>
          <span className="legend-swatch" style={{ background: 'var(--primary)', opacity: 0.3 }} />
          95% interval
        </span>
        <span>Horizontal axis: question number</span>
      </figcaption>
    </figure>
  );
}
