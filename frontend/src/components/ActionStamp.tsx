import type { ActionType } from './types';

const CFG: Record<ActionType, { label: string; bg: string; shadow: string; rot: string }> = {
  fold:  { label: 'FOLD',   bg: 'rgb(239,70,55)',  shadow: 'rgb(140,30,15)',  rot: '-10deg' },
  call:  { label: 'CALL',   bg: 'rgb(1,139,246)',  shadow: 'rgb(0,80,160)',   rot: '-6deg'  },
  raise: { label: 'RAISE!', bg: 'rgb(250,140,1)',  shadow: 'rgb(160,85,0)',   rot: '-12deg' },
  check: { label: 'CHECK',  bg: 'rgb(37,120,95)',  shadow: 'rgb(18,70,55)',   rot: '-8deg'  },
};

export default function ActionStamp({ action }: { action?: ActionType | null }) {
  if (!action) return null;
  const c = CFG[action] ?? CFG.check;
  return (
    <div style={{
      position: 'absolute', top: '50%', left: '50%',
      transform: `translate(-50%,-50%) rotate(${c.rot})`,
      background: c.bg,
      borderRadius: 14,
      padding: '6px 16px',
      fontFamily: 'var(--font-rajdhani), sans-serif',
      fontWeight: 700, fontSize: 20, letterSpacing: '-0.04em',
      color: '#fff',
      zIndex: 20, pointerEvents: 'none', whiteSpace: 'nowrap',
      boxShadow: `0px 5px 0px 0px ${c.shadow}, 0 0 18px ${c.bg}88`,
      animation: 'actionStamp 0.4s cubic-bezier(0.34,1.56,0.64,1) forwards',
      textShadow: '0 1px 3px rgba(0,0,0,0.5)',
    }}>{c.label}</div>
  );
}
