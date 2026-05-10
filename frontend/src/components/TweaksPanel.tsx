import { useState, useEffect, useRef } from 'react';
import type { Settings } from './types';
import { STAKE_COLORS } from '@/lib/constants';

interface TweaksPanelProps {
  settings: Settings;
  onChange: (key: keyof Settings, val: string) => void;
  visible: boolean;
  onClose: (hidden: boolean) => void;
}

interface SegOption { v: string; l: string; sub: string }

function Seg({ id, label, options, value, stakeColor, onChange }: {
  id: keyof Settings; label: string; options: SegOption[];
  value: string; stakeColor: string;
  onChange: (key: keyof Settings, val: string) => void;
}) {
  const sc = STAKE_COLORS[stakeColor] ?? STAKE_COLORS.blue;
  return (
    <div style={{ marginBottom: 16 }}>
      <div style={{ fontFamily: 'var(--font-rajdhani), sans-serif', fontWeight: 700, fontSize: 13, letterSpacing: '-0.02em', color: 'rgba(255,255,255,0.45)', marginBottom: 7, textTransform: 'uppercase' }}>{label}</div>
      <div style={{ display: 'flex', gap: 5 }}>
        {options.map(o => {
          const active = value === o.v;
          return (
            <button key={o.v} onClick={() => onChange(id, o.v)} style={{
              flex: 1, padding: '6px 4px',
              fontFamily: 'var(--font-rajdhani), sans-serif', fontWeight: 700, fontSize: 14, letterSpacing: '-0.03em',
              background: active ? sc.bg : 'rgb(37,45,48)',
              border: `2px solid ${active ? sc.bg : 'rgb(55,68,71)'}`,
              borderRadius: 10, color: active ? sc.text : 'rgba(255,255,255,0.4)',
              cursor: 'pointer', lineHeight: 1.2,
              boxShadow: active ? `0 4px 0 0 ${sc.shadow}` : '0 3px 0 0 rgba(0,0,0,0.5)',
            }}>
              {o.l}
              <div style={{ fontFamily: 'var(--font-rajdhani), sans-serif', fontWeight: 600, fontSize: 11, opacity: 0.65, letterSpacing: '-0.01em' }}>{o.sub}</div>
            </button>
          );
        })}
      </div>
    </div>
  );
}

export default function TweaksPanel({ settings, onChange, visible, onClose }: TweaksPanelProps) {
  const [pos, setPos] = useState({ x: 0, y: 0 });
  const drag = useRef<{ ox: number; oy: number } | null>(null);

  useEffect(() => {
    setPos({ x: window.innerWidth - 290, y: window.innerHeight - 420 });
  }, []);

  useEffect(() => {
    const mm = (e: MouseEvent) => {
      if (drag.current) setPos({ x: e.clientX - drag.current.ox, y: e.clientY - drag.current.oy });
    };
    const mu = () => { drag.current = null; };
    window.addEventListener('mousemove', mm);
    window.addEventListener('mouseup', mu);
    return () => { window.removeEventListener('mousemove', mm); window.removeEventListener('mouseup', mu); };
  }, []);

  if (!visible) return null;

  return (
    <div style={{
      position: 'fixed', left: pos.x, top: pos.y, width: 272, zIndex: 500,
      background: 'rgb(24,36,38)',
      border: '5px solid rgb(30,44,44)',
      borderRadius: 16,
      boxShadow: '0 8px 0 0 rgba(0,0,0,0.6), 0 12px 40px rgba(0,0,0,0.7)',
      animation: 'tweakSlideUp 0.3s cubic-bezier(0.34,1.56,0.64,1) both',
      userSelect: 'none',
    }}>
      <div
        onMouseDown={e => { drag.current = { ox: e.clientX - pos.x, oy: e.clientY - pos.y }; }}
        style={{
          padding: '9px 14px 8px',
          background: 'rgb(37,45,48)',
          borderBottom: '3px solid rgb(18,28,30)',
          borderRadius: '11px 11px 0 0',
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          cursor: 'grab',
        }}
      >
        <span style={{ fontFamily: 'var(--font-rajdhani), sans-serif', fontWeight: 700, fontSize: 20, letterSpacing: '-0.04em', color: 'rgb(255,215,102)', lineHeight: 1 }}>TWEAKS</span>
        <button onClick={() => onClose(true)} style={{
          background: 'rgb(239,70,55)', border: 'none',
          borderRadius: 8, padding: '4px 10px', cursor: 'pointer',
          fontFamily: 'var(--font-rajdhani), sans-serif', fontWeight: 700, fontSize: 15, color: '#fff',
          boxShadow: '0 3px 0 0 rgb(140,30,15)', letterSpacing: '-0.03em',
        }}>✕</button>
      </div>

      <div style={{ padding: '12px 12px 10px' }}>
        <Seg id="tempo" label="Tempo" value={settings.tempo} stakeColor="orange" onChange={onChange} options={[
          { v:'cinematic', l:'Cinematic', sub:'slow & tense' },
          { v:'normal',    l:'Normal',    sub:'balanced'    },
          { v:'turbo',     l:'Turbo',     sub:'lightning'   },
        ]} />
        <Seg id="voice" label="AI Voice" value={settings.voice} stakeColor="purple" onChange={onChange} options={[
          { v:'analytical', l:'Analytical', sub:'data only' },
          { v:'balanced',   l:'Balanced',   sub:'natural'   },
          { v:'theatrical', l:'Theatrical', sub:'unhinged'  },
        ]} />
        <Seg id="atmosphere" label="Atmosphere" value={settings.atmosphere} stakeColor="green" onChange={onChange} options={[
          { v:'felt', l:'Felt', sub:'classic' },
          { v:'neon', l:'Neon', sub:'cyber'   },
          { v:'noir', l:'Noir', sub:'gritty'  },
        ]} />
        <div style={{ fontFamily: 'var(--font-rajdhani), sans-serif', fontWeight: 600, fontSize: 13, color: 'rgba(255,255,255,0.2)', textAlign: 'center', marginTop: 2, letterSpacing: '-0.01em' }}>
          changes apply next turn
        </div>
      </div>
    </div>
  );
}
