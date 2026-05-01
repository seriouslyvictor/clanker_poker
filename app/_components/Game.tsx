'use client';

import { useState, useEffect, useRef } from 'react';
import type { GameState, Player, Settings } from './types';
import type { Card as CardType } from '@/lib/game-logic';
import { mkDeck, shuffle, evalStrength, handName, decideAction } from '@/lib/game-logic';
import { MODELS, THEMES, TEMPO_MULT } from '@/lib/constants';
import Card from './Card';
import PlayerSeat from './PlayerSeat';
import ReasoningPanel from './ReasoningPanel';
import StakeChip from './StakeChip';
import GoldCrownChip from './GoldCrownChip';
import ConfettiBurst from './ConfettiBurst';

interface GameProps {
  initChips: Record<string, number>;
  tempoRef: React.MutableRefObject<string>;
  voiceRef: React.MutableRefObject<string>;
  theme: (typeof THEMES)[keyof typeof THEMES];
  onEnd: (finalChips: Record<string, number>) => void;
}

const PHASE_DISPLAY: Record<string, string> = {
  DEALING: 'DEALING', 'PRE-FLOP': 'PRE-FLOP',
  FLOP: 'THE FLOP', TURN: 'THE TURN', RIVER: 'THE RIVER',
  SHOWDOWN: 'SHOWDOWN', WINNER: 'WINNER!',
};

async function fetchReasoning(modelId: string, handStr: string, strength: number, phase: string, voice: string, action: string): Promise<string> {
  try {
    const res = await fetch('/api/reasoning', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ modelId, handStr, strength, phase, voice, action }),
    });
    const data = await res.json();
    return data.text ?? '';
  } catch {
    return `${phase}: ${handStr} — ${action.toUpperCase()}`;
  }
}

export default function Game({ initChips, tempoRef, voiceRef, theme, onEnd }: GameProps) {
  const mounted = useRef(true);
  useEffect(() => () => { mounted.current = false; }, []);

  const [gs, setGs] = useState<GameState>({
    phase: 'DEALING', pot: 75, communityCards: [],
    players: MODELS.map(m => ({
      ...m,
      chips: initChips[m.id] ?? 1000,
      holeCards: [],
      action: null, bet: 0, isFolded: false, isActive: false, isWinner: false,
    })),
    showCards: false, reasoning: [], winner: null, winnerHand: '',
  });
  const gsRef = useRef(gs);
  gsRef.current = gs;

  const upd = (fn: ((s: GameState) => GameState) | Partial<GameState>) =>
    new Promise<void>(res => {
      if (!mounted.current) return res();
      setGs(s => typeof fn === 'function' ? fn(s) : { ...s, ...fn });
      setTimeout(res, 30);
    });

  const wait = (ms: number) =>
    new Promise<void>(r => setTimeout(r, ms * (TEMPO_MULT[tempoRef.current as keyof typeof TEMPO_MULT] ?? 1)));

  const stream = async (eid: string, text: string) => {
    for (let c = 5; c <= text.length; c += 5) {
      if (!mounted.current) return;
      setGs(s => ({ ...s, reasoning: s.reasoning.map(e => e.id === eid ? { ...e, text: text.slice(0, c) } : e) }));
      await new Promise(r => setTimeout(r, 18 * (TEMPO_MULT[tempoRef.current as keyof typeof TEMPO_MULT] ?? 1)));
    }
    setGs(s => ({ ...s, reasoning: s.reasoning.map(e => e.id === eid ? { ...e, text, streaming: false } : e) }));
    await new Promise(r => setTimeout(r, 20));
  };

  const runBetting = async (phaseName: string, community: CardType[], betAmt: number, currentFolded: Set<number>) => {
    const folded = new Set(currentFolded);
    if (4 - folded.size <= 1) return folded;

    for (let i = 0; i < 4; i++) {
      if (!mounted.current) return folded;
      if (folded.has(i)) continue;

      const player = gsRef.current.players[i];
      const model = MODELS[i];
      const str = evalStrength(player.holeCards, community);
      const act = decideAction(str, betAmt);

      await upd(s => ({ ...s, players: s.players.map((p, pi) => ({ ...p, isActive: pi === i, action: pi === i ? null : p.action })) }));

      const eid = `${model.id}-${phaseName}-${Date.now()}`;
      setGs(s => ({ ...s, reasoning: [...s.reasoning, { id: eid, playerId: model.id, text: '', phase: phaseName, streaming: true, action: null, amount: 0 }] }));
      await new Promise(r => setTimeout(r, 30));

      const handStr = player.holeCards.map(c => `${c.r}${c.s}`).join(' ');
      const txt = await fetchReasoning(model.id, handStr, str, phaseName, voiceRef.current, act.t);
      await stream(eid, txt);
      await wait(350);

      if (act.t === 'fold') folded.add(i);

      setGs(s => {
        const nr = s.reasoning.map(e => e.id === eid ? { ...e, action: act.t, amount: act.a, streaming: false } : e);
        const np = s.players.map((p, pi) => pi !== i ? p : {
          ...p,
          action: act.t,
          isFolded: act.t === 'fold',
          isActive: false,
          bet: act.t !== 'fold' ? act.a : p.bet,
          chips: act.t !== 'fold' ? p.chips - act.a : p.chips,
        });
        return { ...s, reasoning: nr, players: np, pot: s.pot + (act.t !== 'fold' ? act.a : 0) };
      });
      await wait(650);
    }

    setGs(s => ({ ...s, players: s.players.map(p => ({ ...p, isActive: false })) }));
    return folded;
  };

  const finish = async (folded: Set<number>, revComm: CardType[]) => {
    let winner = -1, maxStr = -1;
    for (let i = 0; i < 4; i++) {
      if (folded.has(i)) continue;
      const s = evalStrength(gsRef.current.players[i].holeCards, revComm);
      if (s > maxStr) { maxStr = s; winner = i; }
    }
    const pot = gsRef.current.pot;
    await upd(s => ({ ...s, phase: 'SHOWDOWN', showCards: true, players: s.players.map(p => ({ ...p, isActive: false, action: null })) }));
    await wait(1400);

    if (winner >= 0) {
      const hname = handName(maxStr);
      setGs(s => {
        const weid = `win-${Date.now()}`;
        return {
          ...s, phase: 'WINNER', winner, winnerHand: hname,
          players: s.players.map((p, i) => ({ ...p, chips: i === winner ? p.chips + s.pot : p.chips, isWinner: i === winner })),
          pot: 0,
          reasoning: [...s.reasoning, { id: weid, playerId: MODELS[winner].id, text: `🏆 WINNER! Pot of ${pot} claimed with ${hname}!`, phase: 'RESULT', streaming: false, action: null, amount: 0 }],
        };
      });
      setTimeout(() => {
        if (!mounted.current) return;
        onEnd(Object.fromEntries(gsRef.current.players.map(p => [p.id, p.chips])));
      }, 5000);
    }
  };

  useEffect(() => {
    (async () => {
      const deck = shuffle(mkDeck());
      const hands = MODELS.map((_, i) => [deck[i * 2], deck[i * 2 + 1]]);
      const comm = deck.slice(8, 13);

      await upd(s => ({ ...s, players: s.players.map((p, i) => ({ ...p, holeCards: hands[i] })), communityCards: [], phase: 'PRE-FLOP' }));
      await wait(700);

      let folded = await runBetting('PRE-FLOP', [], 50, new Set());
      if (!mounted.current) return;
      if (4 - folded.size <= 1) { await finish(folded, []); return; }

      await upd(s => ({ ...s, phase: 'FLOP', communityCards: comm.slice(0, 3), players: s.players.map(p => ({ ...p, action: null, bet: 0 })) }));
      await wait(900);
      folded = await runBetting('FLOP', comm.slice(0, 3), 60, folded);
      if (!mounted.current) return;
      if (4 - folded.size <= 1) { await finish(folded, comm.slice(0, 3)); return; }

      await upd(s => ({ ...s, phase: 'TURN', communityCards: comm.slice(0, 4), players: s.players.map(p => ({ ...p, action: null, bet: 0 })) }));
      await wait(900);
      folded = await runBetting('TURN', comm.slice(0, 4), 80, folded);
      if (!mounted.current) return;
      if (4 - folded.size <= 1) { await finish(folded, comm.slice(0, 4)); return; }

      await upd(s => ({ ...s, phase: 'RIVER', communityCards: comm, players: s.players.map(p => ({ ...p, action: null, bet: 0 })) }));
      await wait(900);
      folded = await runBetting('RIVER', comm, 100, folded);
      if (!mounted.current) return;
      await finish(folded, comm);
    })();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const { players, communityCards, pot, phase, showCards, reasoning, winner, winnerHand } = gs;
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
                <StakeChip label={`+${reasoning.find(e => e.phase === 'RESULT')?.text.match(/\d+/)?.[0] ?? '?'}`} stakeColor="gold" size="sm" />
              </div>

              <div style={{ fontFamily: 'var(--font-rajdhani), sans-serif', fontWeight: 600, fontSize: 14, letterSpacing: '-0.02em', color: 'rgba(255,255,255,0.2)' }}>Next round in 5s...</div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
