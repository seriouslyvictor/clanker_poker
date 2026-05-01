'use client';

import { STAKE_COLORS } from '@/lib/constants';

interface StakeChipProps {
  label: string;
  stakeColor?: string;
  size?: 'sm' | 'md' | 'lg';
}

export default function StakeChip({ label, stakeColor = 'blue', size = 'md' }: StakeChipProps) {
  const sc = STAKE_COLORS[stakeColor] ?? STAKE_COLORS.blue;
  const h = size === 'sm' ? 28 : size === 'lg' ? 44 : 34;
  const fs = size === 'sm' ? 13 : size === 'lg' ? 20 : 16;
  return (
    <div style={{
      display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
      height: h, padding: `0 ${h * 0.45}px`,
      borderRadius: h / 2,
      background: sc.bg,
      boxShadow: `0 ${size === 'sm' ? 3 : 4}px 0 0 ${sc.shadow}`,
      border: sc.border ? `2px solid ${sc.border}` : undefined,
      fontFamily: 'var(--font-rajdhani), sans-serif',
      fontWeight: 700, fontSize: fs,
      letterSpacing: '-0.04em', color: sc.text,
      whiteSpace: 'nowrap',
      animation: 'chipFloat 2.2s ease-in-out infinite',
    }}>{label}</div>
  );
}
