'use client';

import { useEffect, useRef } from 'react';
import type { Player, ReasoningEntry } from './types';
import StakeChip from './StakeChip';
import { STAKE_MAP } from '@/lib/constants';

interface HistoryPopoverProps {
  player: Player;
  entries: ReasoningEntry[];
  onClose: () => void;
}

const actionColor = (a: string) =>
  a === 'fold' ? 'rgb(239,70,55)' : a === 'raise' ? 'rgb(250,140,1)' : 'rgb(1,139,246)';

export default function HistoryPopover({ player, entries, onClose }: HistoryPopoverProps) {
  const scrollRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, []);
  const myEntries = entries.filter(e => e.playerId === player.id);
  const stakeColor = STAKE_MAP[player.id] ?? 'white';

  return (
    <div
      style={{ position: 'fixed', inset: 0, zIndex: 200, display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'rgba(0,0,0,0.75)' }}
      onClick={onClose}
    >
      <div onClick={e => e.stopPropagation()} style={{
        background: 'rgb(24,36,38)',
        border: '5px solid rgb(30,44,44)',
        borderRadius: 16,
        width: 440, maxHeight: '72vh',
        display: 'flex', flexDirection: 'column',
        boxShadow: `0 8px 0 0 rgb(15,22,23), 0 0 40px ${player.color}33`,
        animation: 'popoverIn 0.25s cubic-bezier(0.34,1.56,0.64,1) both',
      }}>
        {/* Header */}
        <div style={{
          padding: '11px 16px',
          background: 'rgb(37,45,48)',
          borderBottom: '3px solid rgb(18,28,30)',
          borderRadius: '11px 11px 0 0',
          display: 'flex', alignItems: 'center', gap: 10, flexShrink: 0,
        }}>
          <div style={{
            width: 32, height: 32, borderRadius: 8,
            background: player.color,
            boxShadow: '0 4px 0 0 rgba(0,0,0,0.5)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontFamily: 'var(--font-rajdhani), sans-serif',
            fontWeight: 700, fontSize: 13, color: '#fff', letterSpacing: '-0.03em', flexShrink: 0,
          }}>
            {player.name.slice(0, 3).toUpperCase()}
          </div>
          <div style={{ flex: 1 }}>
            <div style={{ fontFamily: 'var(--font-rajdhani), sans-serif', fontWeight: 700, fontSize: 20, letterSpacing: '-0.04em', color: '#fff', lineHeight: 1 }}>{player.name}</div>
            <div style={{ fontFamily: 'var(--font-rajdhani), sans-serif', fontWeight: 600, fontSize: 14, letterSpacing: '-0.02em', color: 'rgba(255,255,255,0.38)', marginTop: 1 }}>{player.org} · Reasoning Log</div>
          </div>
          <button onClick={onClose} style={{
            background: 'rgb(239,70,55)', border: 'none',
            borderRadius: 10, padding: '5px 11px', cursor: 'pointer',
            fontFamily: 'var(--font-rajdhani), sans-serif',
            fontWeight: 700, fontSize: 16, color: '#fff',
            boxShadow: '0 4px 0 0 rgb(140,30,15)', letterSpacing: '-0.03em',
          }}>✕</button>
        </div>

        {/* Entries */}
        <div ref={scrollRef} style={{ overflowY: 'auto', padding: '12px 14px', display: 'flex', flexDirection: 'column', gap: 12 }}>
          {myEntries.length === 0
            ? <div style={{ fontFamily: 'var(--font-rajdhani), sans-serif', fontWeight: 600, fontSize: 18, color: 'rgba(255,255,255,0.25)', textAlign: 'center', padding: '24px 0', letterSpacing: '-0.02em' }}>No reasoning yet this round.</div>
            : myEntries.map((e, i) => (
              <div key={e.id} style={{ animation: `slideIn 0.2s ease-out ${i * 0.03}s both` }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 5 }}>
                  <span style={{
                    fontFamily: 'var(--font-rajdhani), sans-serif', fontWeight: 700, fontSize: 13, letterSpacing: '-0.02em',
                    padding: '2px 10px', borderRadius: 8,
                    background: 'rgb(37,45,48)', border: '2px solid rgb(55,68,71)',
                    color: 'rgba(255,255,255,0.7)',
                    boxShadow: '0 2px 0 0 rgba(0,0,0,0.4)',
                  }}>{e.phase}</span>
                  {e.action && (
                    <span style={{
                      fontFamily: 'var(--font-rajdhani), sans-serif', fontWeight: 700, fontSize: 14, letterSpacing: '-0.02em',
                      padding: '2px 10px', borderRadius: 8,
                      background: actionColor(e.action),
                      boxShadow: '0 3px 0 0 rgba(0,0,0,0.45)',
                      color: '#fff', marginLeft: 'auto',
                    }}>
                      {e.action.toUpperCase()}{e.amount > 0 ? ` +${e.amount}` : ''}
                    </span>
                  )}
                </div>
                <div style={{
                  fontFamily: 'var(--font-vt323), monospace', fontSize: 15, lineHeight: 1.6,
                  color: 'rgba(255,255,255,0.75)',
                  whiteSpace: 'pre-wrap', wordBreak: 'break-word',
                  borderLeft: `3px solid ${player.color}55`, paddingLeft: 10,
                  background: 'rgba(0,0,0,0.2)', borderRadius: '0 6px 6px 0', padding: '6px 10px',
                }}>{e.text}</div>
              </div>
            ))
          }
        </div>
        <div style={{ padding: '8px 14px', borderTop: '2px solid rgb(18,28,30)', display: 'flex', justifyContent: 'center' }}>
          <StakeChip label={player.chips.toLocaleString()} stakeColor={stakeColor} size="sm" />
        </div>
      </div>
    </div>
  );
}
