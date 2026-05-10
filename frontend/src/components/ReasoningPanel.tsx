import { useEffect, useRef } from 'react';
import type { Player, ReasoningEntry } from './types';
import StakeChip from './StakeChip';
import { STAKE_COLORS, STAKE_MAP } from '@/lib/constants';

interface ReasoningPanelProps {
  entries: ReasoningEntry[];
  players: Player[];
  phase: string;
}

const actionColor = (a: string) =>
  a === 'fold' ? 'rgb(239,70,55)' : a === 'raise' ? 'rgb(250,140,1)' : 'rgb(1,139,246)';

export default function ReasoningPanel({ entries, players, phase }: ReasoningPanelProps) {
  const scrollRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [entries]);

  const pm = Object.fromEntries(players.map(p => [p.id, p]));

  return (
    <div style={{
      width: 300, flexShrink: 0,
      background: 'rgb(45,58,59)',
      borderRight: '5px solid rgb(30,44,44)',
      display: 'flex', flexDirection: 'column', height: '100vh',
      position: 'relative',
    }}>
      {/* Header box */}
      <div style={{ margin: '10px 10px 0', background: 'rgb(24,36,38)', borderRadius: 14, boxShadow: '0 4px 0 0 rgba(0,0,0,0.45)', overflow: 'hidden' }}>
        <div style={{ padding: '9px 14px 8px', background: 'rgb(37,45,48)', borderBottom: '3px solid rgb(18,28,30)' }}>
          <div style={{ fontFamily: 'var(--font-rajdhani), sans-serif', fontWeight: 700, fontSize: 22, letterSpacing: '-0.04em', color: 'rgb(255,215,102)', lineHeight: 1 }}>AI REASONING</div>
          <div style={{ fontFamily: 'var(--font-rajdhani), sans-serif', fontWeight: 600, fontSize: 14, letterSpacing: '-0.02em', color: 'rgba(255,255,255,0.3)', marginTop: 2 }}>Live thought stream</div>
        </div>

        {/* Player list */}
        <div style={{ padding: '8px 12px', display: 'flex', flexDirection: 'column', gap: 5 }}>
          {players.map(p => {
            const sc = STAKE_COLORS[STAKE_MAP[p.id] ?? 'white'];
            return (
              <div key={p.id} style={{ display: 'flex', alignItems: 'center', gap: 8, opacity: p.isFolded ? 0.35 : 1, transition: 'opacity 0.3s' }}>
                <div style={{
                  width: 10, height: 10, borderRadius: '50%',
                  background: sc.bg,
                  boxShadow: p.isActive ? `0 0 8px ${sc.bg}` : `0 2px 0 0 ${sc.shadow}`,
                  flexShrink: 0, transition: 'box-shadow 0.3s',
                }} />
                <span style={{ fontFamily: 'var(--font-rajdhani), sans-serif', fontWeight: 700, fontSize: 16, letterSpacing: '-0.03em', color: '#fff', flex: 1, lineHeight: 1 }}>{p.name}</span>
                <StakeChip label={p.chips.toLocaleString()} stakeColor={STAKE_MAP[p.id] ?? 'white'} size="sm" />
                {p.isFolded && (
                  <span style={{
                    fontFamily: 'var(--font-rajdhani), sans-serif', fontWeight: 700, fontSize: 13, letterSpacing: '-0.02em',
                    padding: '1px 7px', borderRadius: 6,
                    background: 'rgb(239,70,55)', boxShadow: '0 2px 0 0 rgb(140,30,15)', color: '#fff',
                  }}>OUT</span>
                )}
                {p.isActive && !p.isFolded && (
                  <div style={{ width: 8, height: 8, borderRadius: '50%', background: sc.bg, boxShadow: `0 0 8px ${sc.bg}`, animation: 'pulseGlow 1s ease-in-out infinite', ['--c' as string]: sc.bg }} />
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* Phase badge */}
      <div style={{ margin: '8px 10px' }}>
        <div style={{
          background: 'rgb(250,140,1)', borderRadius: 12,
          boxShadow: '0 4px 0 0 rgb(160,85,0)',
          padding: '6px 14px',
          fontFamily: 'var(--font-rajdhani), sans-serif', fontWeight: 700, fontSize: 18, letterSpacing: '-0.04em',
          color: '#fff', textAlign: 'center',
        }}>{phase}</div>
      </div>

      {/* Feed */}
      <div ref={scrollRef} style={{ flex: 1, overflowY: 'auto', overflowX: 'hidden', padding: '6px 10px 10px', display: 'flex', flexDirection: 'column', gap: 10 }}>
        {entries.length === 0 && (
          <div style={{ fontFamily: 'var(--font-rajdhani), sans-serif', fontWeight: 600, fontSize: 18, letterSpacing: '-0.02em', color: 'rgba(255,255,255,0.2)', textAlign: 'center', paddingTop: 28 }}>Dealing cards...</div>
        )}
        {entries.map(e => {
          const p = pm[e.playerId];
          if (!p) return null;
          const sc = STAKE_COLORS[STAKE_MAP[p.id] ?? 'white'];
          return (
            <div key={e.id} style={{ background: 'rgb(24,36,38)', borderRadius: 12, boxShadow: '0 3px 0 0 rgba(0,0,0,0.45)', overflow: 'hidden', animation: 'slideIn 0.22s ease-out both' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 7, padding: '6px 10px 5px', background: 'rgb(37,45,48)', borderBottom: '2px solid rgb(18,28,30)' }}>
                <div style={{
                  width: 22, height: 22, borderRadius: 6, background: sc.bg,
                  boxShadow: `0 2px 0 0 ${sc.shadow}`,
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  fontFamily: 'var(--font-rajdhani), sans-serif', fontWeight: 700, fontSize: 10, color: sc.text, flexShrink: 0, letterSpacing: '-0.02em',
                }}>{p.name.slice(0, 2).toUpperCase()}</div>
                <span style={{ fontFamily: 'var(--font-rajdhani), sans-serif', fontWeight: 700, fontSize: 15, letterSpacing: '-0.03em', color: '#fff' }}>{p.name}</span>
                <span style={{
                  fontFamily: 'var(--font-rajdhani), sans-serif', fontWeight: 700, fontSize: 12, letterSpacing: '-0.02em',
                  padding: '1px 7px', borderRadius: 6,
                  background: 'rgb(45,58,59)', border: '2px solid rgb(55,70,72)',
                  color: 'rgba(255,255,255,0.5)', marginLeft: 'auto',
                }}>{e.phase}</span>
              </div>
              <div style={{ padding: '7px 10px 8px' }}>
                <div style={{ fontFamily: 'var(--font-vt323), monospace', fontSize: 14, lineHeight: 1.6, color: 'rgba(255,255,255,0.75)', whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
                  {e.text}{e.streaming && <span style={{ color: sc.bg, animation: 'blink 0.55s infinite' }}> █</span>}
                </div>
                {e.action && (
                  <div style={{
                    marginTop: 6,
                    display: 'inline-flex', alignItems: 'center',
                    background: actionColor(e.action),
                    borderRadius: 8, boxShadow: '0 3px 0 0 rgba(0,0,0,0.4)',
                    padding: '3px 12px',
                    fontFamily: 'var(--font-rajdhani), sans-serif', fontWeight: 700, fontSize: 14, letterSpacing: '-0.03em', color: '#fff',
                  }}>
                    ▶ {e.action.toUpperCase()}{e.amount > 0 ? ` ${e.amount}` : ''}
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
