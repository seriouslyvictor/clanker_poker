import { useState } from 'react'
import { THEMES } from '@/lib/constants'

interface IdleScreenProps {
  theme: (typeof THEMES)[keyof typeof THEMES]
  lastWinner: { name: string; org: string; hand: string } | null
  onStart: () => Promise<void>
}

export default function IdleScreen({ theme, lastWinner, onStart }: IdleScreenProps) {
  const [isStarting, setIsStarting] = useState(false)

  const handleStart = async () => {
    setIsStarting(true)
    try {
      await onStart()
      // isStarting stays true — PokerApp will unmount IdleScreen when gameRunning flips to true
    } catch {
      setIsStarting(false)
    }
  }

  return (
    <div style={{
      position: 'relative',
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
      height: '100vh',
      background: theme.tableBg,
      overflow: 'hidden',
    }}>
      {/* Felt texture overlay — matches Game.tsx pattern */}
      <div style={{
        position: 'absolute', inset: 0, pointerEvents: 'none',
        backgroundImage: `repeating-linear-gradient(0deg,${theme.tex} 0px,${theme.tex} 1px,transparent 1px,transparent 5px),repeating-linear-gradient(90deg,${theme.tex} 0px,${theme.tex} 1px,transparent 1px,transparent 5px)`,
      }} />

      {/* Top spacer */}
      <div style={{ height: 48 }} />

      {/* Branding block */}
      <div style={{ textAlign: 'center', zIndex: 1 }}>
        <div style={{
          fontFamily: 'var(--font-press-start), monospace',
          fontSize: 20,
          color: 'rgb(255,215,102)',
          marginBottom: 16,
          lineHeight: 1.5,
        }}>
          ♠ IA POKER BATTLEGROUND ♠
        </div>
        <div style={{
          fontFamily: 'var(--font-rajdhani), sans-serif',
          fontWeight: 700,
          fontSize: 18,
          letterSpacing: '-0.04em',
          color: 'rgba(255,255,255,0.4)',
        }}>
          WATCH AI MODELS BATTLE IT OUT
        </div>
      </div>

      {/* Gap */}
      <div style={{ height: 32 }} />

      {/* Last-result callout — conditional */}
      {lastWinner !== null && (
        <div style={{
          background: 'rgb(24,36,38)',
          border: '3px solid rgb(255,215,102)',
          borderRadius: 14,
          padding: '16px 32px',
          textAlign: 'center',
          zIndex: 1,
        }}>
          <div style={{
            fontFamily: 'var(--font-rajdhani), sans-serif',
            fontWeight: 700,
            fontSize: 28,
            letterSpacing: '-0.04em',
            color: 'rgb(255,215,102)',
            lineHeight: 1.1,
          }}>
            {lastWinner.org}&apos;s {lastWinner.name}
          </div>
          <div style={{
            fontFamily: 'var(--font-rajdhani), sans-serif',
            fontWeight: 700,
            fontSize: 18,
            letterSpacing: '-0.04em',
            color: 'rgb(255,215,102)',
            marginTop: 4,
          }}>
            won with {lastWinner.hand}
          </div>
        </div>
      )}

      {/* Gap */}
      <div style={{ height: 32 }} />

      {/* START A GAME button */}
      <button
        className="bal-btn bal-btn-orange"
        disabled={isStarting}
        onClick={handleStart}
        style={{
          fontSize: 20,
          height: 52,
          padding: '0 32px',
          opacity: isStarting ? 0.5 : 1,
          cursor: isStarting ? 'not-allowed' : 'pointer',
          zIndex: 1,
        }}
      >
        {isStarting ? 'STARTING...' : 'START A GAME'}
      </button>

      {/* Cold-start hint — only when no last winner */}
      <div style={{ height: 16 }} />
      {lastWinner === null && (
        <div style={{
          fontFamily: 'var(--font-rajdhani), sans-serif',
          fontWeight: 700,
          fontSize: 14,
          letterSpacing: '-0.03em',
          color: 'rgba(255,255,255,0.25)',
          zIndex: 1,
        }}>
          Be the first viewer to start a game
        </div>
      )}
    </div>
  )
}
