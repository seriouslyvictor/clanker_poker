interface GoldCrownChipProps {
  label: string;
  size?: 'sm' | 'md' | 'lg' | 'xl';
  delay?: number;
}

export default function GoldCrownChip({ label, size = 'lg', delay = 0 }: GoldCrownChipProps) {
  const h = size === 'xl' ? 56 : size === 'lg' ? 44 : size === 'md' ? 34 : 28;
  const fs = size === 'xl' ? 26 : size === 'lg' ? 20 : size === 'md' ? 16 : 13;
  return (
    <div style={{
      display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: 7,
      height: h, padding: `0 ${h * 0.5}px`,
      borderRadius: h / 2,
      background: 'linear-gradient(180deg, rgb(255,230,120) 0%, rgb(255,215,102) 40%, rgb(230,175,30) 100%)',
      animation: `crownGlow 1.6s ease-in-out ${delay}s infinite`,
      border: '2px solid rgb(255,240,160)',
      fontFamily: 'var(--font-rajdhani), sans-serif',
      fontWeight: 700, fontSize: fs,
      letterSpacing: '-0.04em', color: 'rgb(80,50,0)',
      whiteSpace: 'nowrap',
      position: 'relative',
      userSelect: 'none',
    }}>
      <span style={{ fontSize: fs * 0.9, lineHeight: 1, filter: 'drop-shadow(0 1px 2px rgba(0,0,0,0.3))' }}>♛</span>
      {label}
    </div>
  );
}
