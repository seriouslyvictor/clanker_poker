import { useState } from 'react';
import type { Settings } from './types';
import { THEMES } from '@/lib/constants';
import { useGameStream } from '../hooks/useGameStream';
import Game from './Game';
import IdleScreen from './IdleScreen';

const DEFAULT_SETTINGS: Settings = { tempo: 'normal', voice: 'balanced', atmosphere: 'felt' };

export default function PokerApp() {
  const [settings] = useState<Settings>(DEFAULT_SETTINGS);
  const { gameState, reasoning, connectionState, gameRunning, lastWinner } = useGameStream();

  const handleStart = async (): Promise<void> => {
    const _base = import.meta.env.VITE_API_URL ?? 'http://localhost:8000';
    const url = new URL('/api/game/start', _base).toString();
    try {
      await fetch(url, { method: 'POST' });
    } catch (err) {
      console.error('[PokerApp] Failed to start game:', err);
      throw err;
    }
  };

  const theme = THEMES[settings.atmosphere] ?? THEMES.felt;

  if (gameRunning === null) {
    return (
      <div style={{
        display: 'flex',
        height: '100vh',
        alignItems: 'center',
        justifyContent: 'center',
        background: theme.tableBg,
        fontFamily: 'var(--font-rajdhani), sans-serif',
        fontWeight: 700,
        fontSize: 18,
        letterSpacing: '-0.04em',
        color: 'rgba(255,255,255,0.4)',
      }}>
        CONNECTING...
      </div>
    );
  }

  if (gameRunning === false) {
    return <IdleScreen theme={theme} lastWinner={lastWinner} onStart={handleStart} />;
  }

  return <Game theme={theme} gameState={gameState} reasoning={reasoning} connectionState={connectionState} />;
}
