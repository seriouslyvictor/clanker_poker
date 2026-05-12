import type { GameState, ReasoningEntry } from './types';
import type { ConnectionState } from '../hooks/useGameStream';
import { THEMES } from '@/lib/constants';
import Card from './Card';
import PlayerSeat from './PlayerSeat';
import ReasoningPanel from './ReasoningPanel';
import StakeChip from './StakeChip';
import GoldCrownChip from './GoldCrownChip';
import ConfettiBurst from './ConfettiBurst';

interface GameProps {
  theme: (typeof THEMES)[keyof typeof THEMES];
  gameState: GameState | null;
  reasoning: ReasoningEntry[];
  connectionState: ConnectionState;
}

const PHASE_DISPLAY: Record<string, string> = {
  DEALING: 'DEALING', 'PRE-FLOP': 'PRE-FLOP',
  FLOP: 'THE FLOP', TURN: 'THE TURN', RIVER: 'THE RIVER',
  SHOWDOWN: 'SHOWDOWN', WINNER: 'WINNER!',
};

export default function Game({ theme, gameState, reasoning, connectionState }: GameProps) {
  if (!gameState) {
    return (
      <div style={{
        display: 'flex', height: '100vh', alignItems: 'center', justifyContent: 'center',
        background: theme.tableBg, fontFamily: 'var(--font-rajdhani), sans-serif',
        fontWeight: 700, fontSize: 22, letterSpacing: '-0.04em', color: 'rgba(255,255,255,0.4)',
      }}>
        Connecting to game...
      </div>
    );
  }

  const { players, communityCards, pot, phase, showCards, winner, winnerHand } = gameState;
  const phaseDisplay = PHASE_DISPLAY[phase] ?? phase;

  return (
    <div style={{ display: 'flex', height: '100vh', overflow: 'hidden' }}>
      <ReasoningPanel entries={reasoning} players={players} phase={phaseDisplay} />

      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', background: theme.tableBg, position: 'relative', overflow: 'hidden' }}>
        {/* Felt texture */}
        <div style={{
          position: 'absolute', inset: 0, pointerEvents: 'none',
          backgroundImage: `repeating-linear-gradient(0deg,${theme.tex} 0px,${theme.tex} 1px,transparent 1px,transparent 5px),repeating-linear-gradient(90deg,${theme.tex} 0px,${theme.tex} 1px,transparent 1px,transparent 5px)`,
        }} />

        {/* Top bar */}
        <div style={{
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          padding: '8px 18px',
          background: 'rgb(30,44,44)', borderBottom: '4px solid rgb(18,28,30)',
          position: 'relative', zIndex: 2, flexShrink: 0, gap: 10,
        }}>
          <div style={{ fontFamily: 'var(--font-rajdhani), sans-serif', fontWeight: 700, fontSize: 22, letterSpacing: '-0.05em', color: 'rgb(255,215,102)', lineHeight: 1, textShadow: '0 2px 0 rgba(0,0,0,0.5)', whiteSpace: 'nowrap' }}>
            ♠ IA POKER BATTLEGROUND ♠
          </div>
          <div style={{ background: 'rgb(1,139,246)', borderRadius: 12, boxShadow: '0 4px 0 0 rgb(0,80,160)', padding: '5px 18px', fontFamily: 'var(--font-rajdhani), sans-serif', fontWeight: 700, fontSize: 18, letterSpacing: '-0.04em', color: '#fff', whiteSpace: 'nowrap', flexShrink: 0 }}>
            {phaseDisplay}
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexShrink: 0 }}>
            <span style={{ fontFamily: 'var(--font-rajdhani), sans-serif', fontWeight: 600, fontSize: 15, letterSpacing: '-0.03em', color: 'rgba(255,255,255,0.4)' }}>POT</span>
            <StakeChip label={String(pot)} stakeColor="gold" size="md" />
          </div>
        </div>

        {/* Player grid */}
        <div style={{ flex: 1, display: 'grid', gridTemplateRows: '1fr auto 1fr', gridTemplateColumns: '1fr 1fr', padding: '18px 22px', gap: 14, position: 'relative', zIndex: 1, alignItems: 'stretch' }}>
          <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'flex-start', paddingTop: 6 }}>
            <PlayerSeat player={players[0]} showCards={showCards} reasoning={reasoning} />
          </div>
          <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'flex-start', paddingTop: 6 }}>
            <PlayerSeat player={players[1]} showCards={showCards} reasoning={reasoning} />
          </div>

          {/* Community cards */}
          <div style={{ gridColumn: '1/3', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 10 }}>
            <div style={{
              background: 'rgba(18,28,30,0.7)', border: '3px solid rgb(45,58,59)',
              borderRadius: 60, padding: '14px 32px',
              display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 9,
              boxShadow: 'inset 0 4px 20px rgba(0,0,0,0.5), 0 6px 0 0 rgba(0,0,0,0.4)',
            }}>
              <div style={{ fontFamily: 'var(--font-rajdhani), sans-serif', fontWeight: 700, fontSize: 13, letterSpacing: '-0.01em', color: 'rgba(255,255,255,0.25)' }}>COMMUNITY CARDS</div>
              <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                {[0, 1, 2, 3, 4].map(i => communityCards[i]
                  ? <Card key={i} card={communityCards[i]} cardBack={theme.cardBack} style={{ animation: `communityReveal 0.45s ease-out ${i * 0.1}s both` }} />
                  : <div key={i} style={{ width: 58, height: 82, border: '2px dashed rgb(45,58,59)', borderRadius: 7, background: `${theme.cardBack} center / cover no-repeat`, imageRendering: 'pixelated', opacity: 0.18 }} />
                )}
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <span style={{ fontFamily: 'var(--font-rajdhani), sans-serif', fontWeight: 600, fontSize: 14, letterSpacing: '-0.02em', color: 'rgba(255,255,255,0.3)' }}>POT</span>
                <StakeChip label={String(pot)} stakeColor="gold" size="sm" />
              </div>
            </div>
          </div>

          <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'flex-end', paddingBottom: 6 }}>
            <PlayerSeat player={players[2]} showCards={showCards} reasoning={reasoning} />
          </div>
          <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'flex-end', paddingBottom: 6 }}>
            <PlayerSeat player={players[3]} showCards={showCards} reasoning={reasoning} />
          </div>
        </div>

        {/* Reconnecting overlay — shown when connection drops with a live gameState */}
        {connectionState === 'connecting' && gameState !== null && (
          <div style={{
            position: 'absolute', inset: 0, background: 'rgba(0,0,0,0.65)',
            display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 100,
          }}>
            <div style={{
              background: 'rgb(24,36,38)', border: '3px solid rgb(55,68,71)',
              borderRadius: 14, padding: '18px 36px',
              fontFamily: 'var(--font-rajdhani), sans-serif',
              fontWeight: 700, fontSize: 20, letterSpacing: '-0.04em',
              color: 'rgba(255,255,255,0.55)',
            }}>
              Reconnecting...
            </div>
          </div>
        )}

        {/* Winner overlay */}
        {phase === 'WINNER' && winner !== null && (
          <div style={{ position: 'absolute', inset: 0, background: 'rgba(0,0,0,0.84)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 50 }}>
            <div style={{
              background: 'rgb(24,36,38)',
              border: '5px solid rgb(255,215,102)',
              borderRadius: 20, padding: '36px 56px', textAlign: 'center',
              boxShadow: '0 10px 0 0 rgba(0,0,0,0.7), 0 0 80px rgba(255,215,102,0.35)',
              animation: 'winnerPulse 2s ease-in-out infinite', minWidth: 320,
              position: 'relative', overflow: 'visible',
            }}>
              <ConfettiBurst />
              <div style={{ position: 'absolute', top: 0, left: '30%' }}><ConfettiBurst /></div>
              <div style={{ position: 'absolute', top: 0, left: '70%' }}><ConfettiBurst /></div>

              <div style={{ display: 'flex', justifyContent: 'center', marginBottom: 18, animation: 'crownBounce 1.3s ease-in-out infinite' }}>
                <GoldCrownChip label="WINNER" size="xl" />
              </div>

              <div style={{ fontFamily: 'var(--font-rajdhani), sans-serif', fontWeight: 700, fontSize: 42, letterSpacing: '-0.05em', color: players[winner].color, lineHeight: 1, marginBottom: 4, textShadow: '0 5px 0 rgba(0,0,0,0.55)' }}>
                {players[winner].name}
              </div>
              <div style={{ fontFamily: 'var(--font-rajdhani), sans-serif', fontWeight: 600, fontSize: 18, letterSpacing: '-0.03em', color: 'rgba(255,255,255,0.35)', marginBottom: 20 }}>
                {players[winner].org}
              </div>

              <div style={{ height: 3, background: 'rgb(37,45,48)', borderRadius: 2, marginBottom: 16, boxShadow: '0 2px 0 0 rgb(18,28,30)' }} />

              <div style={{ display: 'flex', justifyContent: 'center', marginBottom: 8, animation: 'crownBounce 1.3s ease-in-out 0.15s infinite' }}>
                <GoldCrownChip label={winnerHand} size="lg" />
              </div>

              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8, marginBottom: 18 }}>
                <span style={{ fontFamily: 'var(--font-rajdhani), sans-serif', fontWeight: 600, fontSize: 16, letterSpacing: '-0.02em', color: 'rgba(255,255,255,0.3)' }}>POT CLAIMED</span>
                <StakeChip label={`+${pot}`} stakeColor="gold" size="sm" />
              </div>

              <div style={{ fontFamily: 'var(--font-rajdhani), sans-serif', fontWeight: 600, fontSize: 14, letterSpacing: '-0.02em', color: 'rgba(255,255,255,0.2)' }}>Next round in 5s...</div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
