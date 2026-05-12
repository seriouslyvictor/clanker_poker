import { useState } from 'react';
import type { Settings } from './types';
import { THEMES } from '@/lib/constants';
import { useGameStream } from '../hooks/useGameStream';
import Game from './Game';
import TweaksPanel from './TweaksPanel';
import IdleScreen from './IdleScreen';

const DEFAULT_SETTINGS: Settings = { tempo: 'normal', voice: 'balanced', atmosphere: 'felt' };

export default function PokerApp() {
  const [settings, setSettings] = useState<Settings>(DEFAULT_SETTINGS);
  const [tweaksVisible, setTweaksVisible] = useState(false);
  const { gameState, reasoning, connectionState, gameRunning, lastWinner } = useGameStream();

  const onChange = (key: keyof Settings, val: string) => {
    setSettings(prev => ({ ...prev, [key]: val }));
  };

  const handleStart = async (): Promise<void> => {
    const _base = import.meta.env.VITE_API_URL ?? 'http://localhost:8000';
    const url = new URL('/api/game/start', _base).toString();
    try {
      await fetch(url, { method: 'POST' });
      // On success: game_status { running: true } arrives via SSE → gameRunning flips → PokerApp re-renders
    } catch (err) {
      console.error('[PokerApp] Failed to start game:', err);
      throw err; // propagate so IdleScreen can reset isStarting
    }
  };

  const theme = THEMES[settings.atmosphere] ?? THEMES.felt;

  // Route on gameRunning state (per D-03)
  if (gameRunning === null) {
    // Connecting — no game_status received yet from SSE
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

  return (
    <>
      <button
        onClick={() => setTweaksVisible(v => !v)}
        style={{
          position: 'fixed', bottom: 16, right: 16, zIndex: 400,
          background: tweaksVisible ? 'rgb(250,140,1)' : 'rgb(37,45,48)',
          border: `2px solid ${tweaksVisible ? 'rgb(250,140,1)' : 'rgb(55,68,71)'}`,
          borderRadius: 12,
          boxShadow: tweaksVisible ? '0 4px 0 0 rgb(160,85,0)' : '0 4px 0 0 rgba(0,0,0,0.5)',
          padding: '8px 18px',
          fontFamily: 'var(--font-rajdhani), sans-serif',
          fontWeight: 700, fontSize: 16, letterSpacing: '-0.03em',
          color: '#fff', cursor: 'pointer',
        }}
      >
        TWEAKS
      </button>

      <Game theme={theme} gameState={gameState} reasoning={reasoning} connectionState={connectionState} />

      <TweaksPanel
        settings={settings}
        onChange={onChange}
        visible={tweaksVisible}
        onClose={hidden => setTweaksVisible(!hidden)}
      />
    </>
  );
}
