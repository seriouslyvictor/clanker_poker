'use client';

import { useState } from 'react';
import type { Settings } from './types';
import { THEMES } from '@/lib/constants';
import Game from './Game';
import TweaksPanel from './TweaksPanel';

const DEFAULT_SETTINGS: Settings = { tempo: 'normal', voice: 'balanced', atmosphere: 'felt' };

export default function PokerApp() {
  const [settings, setSettings] = useState<Settings>(DEFAULT_SETTINGS);
  const [tweaksVisible, setTweaksVisible] = useState(false);

  const onChange = (key: keyof Settings, val: string) => {
    setSettings(prev => ({ ...prev, [key]: val }));
  };

  const theme = THEMES[settings.atmosphere] ?? THEMES.felt;

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
        ⚙ TWEAKS
      </button>

      <Game theme={theme} />

      <TweaksPanel
        settings={settings}
        onChange={onChange}
        visible={tweaksVisible}
        onClose={hidden => setTweaksVisible(!hidden)}
      />
    </>
  );
}
