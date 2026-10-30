export function StaticValve() {
  return (
    <svg viewBox="0 0 400 300" className="h-full w-full" aria-hidden="true">
      <defs>
        <linearGradient id="sv-m" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#b8c3d1" />
          <stop offset=".5" stopColor="#6b7686" />
          <stop offset="1" stopColor="#2f3742" />
        </linearGradient>
      </defs>
      <rect x="10" y="180" width="380" height="36" rx="4" fill="url(#sv-m)" />
      <rect x="120" y="170" width="14" height="56" rx="2" fill="#3a4452" />
      <rect x="266" y="170" width="14" height="56" rx="2" fill="#3a4452" />
      <ellipse cx="200" cy="198" rx="70" ry="56" fill="url(#sv-m)" />
      <rect x="180" y="110" width="40" height="40" rx="4" fill="#3a4452" />
      <rect x="196" y="76" width="8" height="40" fill="#9aa7b8" />
      <ellipse cx="200" cy="70" rx="80" ry="18" fill="#2a323d" stroke="#4fd8eb" strokeOpacity=".7" />
      <path d="M120 70 a80 46 0 0 1 160 0" fill="#323c48" />
      <line x1="10" y1="198" x2="390" y2="198" stroke="#4fd8eb" strokeWidth="2" className="flow-line" />
      {[[60, 172], [340, 172], [250, 60]].map(([x, y]) => (
        <circle key={x} cx={x} cy={y} r="6" fill="#4fd8eb" className="pulse-dot" />
      ))}
    </svg>
  );
}
