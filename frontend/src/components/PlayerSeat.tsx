import { useState } from 'react';
import type { Player, ReasoningEntry } from './types';
import Card from './Card';
import ActionStamp from './ActionStamp';
import StakeChip from './StakeChip';
import GoldCrownChip from './GoldCrownChip';
import ConfettiBurst from './ConfettiBurst';
import HistoryPopover from './HistoryPopover';
import { STAKE_MAP } from '@/lib/constants';

interface PlayerSeatProps {
  player: Player;
  showCards: boolean;
  reasoning: ReasoningEntry[];
}

export default function PlayerSeat({ player, showCards, reasoning }: PlayerSeatProps) {
  const [histOpen, setHistOpen] = useState(false);
  const { isActive, isFolded } = player;
  const stakeColor = STAKE_MAP[player.id] ?? 'white';

  return (
    <>
      <div style={{
        display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 9,
        padding: '13px 14px', borderRadius: 16,
        background: isActive ? `${player.color}18` : 'rgba(24,36,38,0.92)',
        border: `3px solid ${isActive ? player.color : isFolded ? 'rgb(30,44,44)' : 'rgb(45,58,59)'}`,
        ['--c' as string]: player.color,
        boxShadow: isActive
          ? `0 0 28px ${player.color}55, 0 6px 0 0 rgba(0,0,0,0.6)`
          : player.isWinner
          ? '0 0 40px #ffd16699, 0 6px 0 0 rgba(0,0,0,0.6)'
          : '0 6px 0 0 rgba(0,0,0,0.5)',
        transition: 'border-color 0.3s, box-shadow 0.3s',
        minWidth: 180, opacity: isFolded ? 0.45 : 1, position: 'relative',
        animation: player.isWinner ? 'winnerPulse 1.8s ease-in-out infinite' : 'none',
      }}>
        {player.isWinner && (
          <div style={{ position: 'absolute', top: -26, left: '50%', transform: 'translateX(-50%)', animation: 'crownBounce 1.4s ease-in-out infinite', zIndex: 10 }}>
            <GoldCrownChip label="WINNER" size="md" />
            <ConfettiBurst />
          </div>
        )}

        {/* Name row */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, width: '100%' }}>
          <div style={{
            width: 38, height: 38, borderRadius: 10,
            background: player.color,
            boxShadow: `0 4px 0 0 rgba(0,0,0,0.55), 0 0 10px ${player.color}66`,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontFamily: 'var(--font-rajdhani), sans-serif',
            fontWeight: 700, fontSize: 13, letterSpacing: '-0.03em',
            color: '#fff', flexShrink: 0,
          }}>
            {player.name.replace(/[^A-Z0-9]/gi, '').slice(0, 3).toUpperCase()}
          </div>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ fontFamily: 'var(--font-rajdhani), sans-serif', fontWeight: 700, fontSize: 17, letterSpacing: '-0.04em', color: '#fff', lineHeight: 1, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{player.name}</div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 5, marginTop: 2 }}>
              <div style={{ fontFamily: 'var(--font-rajdhani), sans-serif', fontWeight: 600, fontSize: 13, letterSpacing: '-0.02em', color: 'rgba(255,255,255,0.38)', whiteSpace: 'nowrap' }}>{player.org}</div>
              <button
                onClick={() => setHistOpen(true)}
                title="View full reasoning history"
                style={{
                  background: 'rgb(37,45,48)',
                  border: '2px solid rgb(55,68,71)',
                  borderRadius: 6, padding: '1px 7px', cursor: 'pointer',
                  fontFamily: 'var(--font-rajdhani), sans-serif',
                  fontWeight: 700, fontSize: 13, letterSpacing: '-0.02em',
                  color: 'rgba(255,255,255,0.55)', lineHeight: 1.3,
                  boxShadow: '0 2px 0 0 rgba(0,0,0,0.5)', flexShrink: 0,
                }}
                onMouseEnter={e => { (e.currentTarget as HTMLButtonElement).style.background = 'rgb(55,68,71)'; (e.currentTarget as HTMLButtonElement).style.color = '#fff'; }}
                onMouseLeave={e => { (e.currentTarget as HTMLButtonElement).style.background = 'rgb(37,45,48)'; (e.currentTarget as HTMLButtonElement).style.color = 'rgba(255,255,255,0.55)'; }}
              >LOG</button>
            </div>
          </div>
          {isActive && (
            <div style={{
              width: 9, height: 9, borderRadius: '50%',
              background: player.color,
              boxShadow: `0 0 8px ${player.color}`,
              animation: 'pulseGlow 1.1s ease-in-out infinite',
              flexShrink: 0, ['--c' as string]: player.color,
            }} />
          )}
        </div>

        {/* Cards */}
        <div style={{ display: 'flex', gap: 6, position: 'relative' }}>
          {[0, 1].map(i => (
            <Card
              key={i}
              card={player.holeCards[i]}
              cardBack={player.deck}
              faceDown={player.holeCards[i] ? (!showCards && !player.isWinner) : false}
              style={{
                opacity: isFolded ? 0.35 : 1,
                filter: isFolded ? 'grayscale(70%)' : 'none',
                animation: player.holeCards[i] ? `dealCard 0.35s ease-out ${i * 0.12}s both` : 'none',
              }}
            />
          ))}
          <ActionStamp action={player.action} />
        </div>

        {/* Chips */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 7, animation: player.isWinner ? 'crownBounce 1.4s ease-in-out 0.2s infinite' : 'none' }}>
          {player.isWinner
            ? <GoldCrownChip label={player.chips.toLocaleString()} size="sm" />
            : <StakeChip label={player.chips.toLocaleString()} stakeColor={stakeColor} size="sm" />
          }
        </div>

        {player.bet > 0 && !isFolded && (
          <div style={{
            position: 'absolute', bottom: -20,
            fontFamily: 'var(--font-vt323), monospace', fontSize: 15,
            color: '#ffd166', background: 'rgba(0,0,0,0.75)',
            padding: '1px 8px', borderRadius: 4,
            border: '1px solid rgba(255,215,102,0.3)',
          }}>BET {player.bet}</div>
        )}
      </div>

      {histOpen && (
        <HistoryPopover player={player} entries={reasoning} onClose={() => setHistOpen(false)} />
      )}
    </>
  );
}
