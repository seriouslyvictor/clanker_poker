import { useEffect, useRef, useState } from 'react'
import type { GameState, Player } from './types'
import { STAKE_MAP } from '@/lib/constants'
import StakeChip from './StakeChip'
import GoldCrownChip from './GoldCrownChip'
import ConfettiBurst from './ConfettiBurst'

interface PredictionWidgetProps {
  gameState: GameState
  players: Player[]
}

interface PredictionRecord {
  handId: string
  prediction: string   // playerId
  result: 'correct' | 'wrong' | null
}

interface ResultFlash {
  result: 'correct' | 'wrong'
  playerName: string
}

const PREDICTION_KEY = 'poker_prediction'
const RESULT_DISPLAY_MS = 6000

function loadPrediction(): PredictionRecord | null {
  try {
    const raw = localStorage.getItem(PREDICTION_KEY)
    return raw ? (JSON.parse(raw) as PredictionRecord) : null
  } catch {
    return null
  }
}

function savePrediction(record: PredictionRecord): void {
  localStorage.setItem(PREDICTION_KEY, JSON.stringify(record))
}

export default function PredictionWidget({ gameState, players }: PredictionWidgetProps) {
  const [handId] = useState(() => Date.now().toString())
  const [prediction, setPrediction] = useState<PredictionRecord | null>(() => loadPrediction())
  const [resultFlash, setResultFlash] = useState<ResultFlash | null>(null)
  const prevWinnerRef = useRef<number | null | undefined>(undefined)
  const flashTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => () => {
    if (flashTimerRef.current) clearTimeout(flashTimerRef.current)
  }, [])

  // Reset prediction when a new hand starts (winner transitions from non-null to null)
  useEffect(() => {
    if (
      prevWinnerRef.current !== null &&
      prevWinnerRef.current !== undefined &&
      gameState.winner === null
    ) {
      setPrediction(null)
      localStorage.removeItem(PREDICTION_KEY)
    }
    prevWinnerRef.current = gameState.winner
  }, [gameState.winner])

  // Set result at showdown and latch it for RESULT_DISPLAY_MS so it survives hand reset
  useEffect(() => {
    if (
      gameState.phase === 'showdown' &&
      prediction !== null &&
      prediction.result === null &&
      gameState.winner !== null
    ) {
      const winnerPlayer = gameState.players[gameState.winner]
      const isCorrect = winnerPlayer?.id === prediction.prediction
      const result: 'correct' | 'wrong' = isCorrect ? 'correct' : 'wrong'
      const pickedP = players.find(p => p.id === prediction.prediction)

      const updated: PredictionRecord = { ...prediction, result }
      setPrediction(updated)
      savePrediction(updated)

      setResultFlash({ result, playerName: pickedP?.name ?? prediction.prediction })
      if (flashTimerRef.current) clearTimeout(flashTimerRef.current)
      flashTimerRef.current = setTimeout(() => setResultFlash(null), RESULT_DISPLAY_MS)
    }
  }, [gameState.phase, gameState.winner, prediction, players])

  const handlePick = (playerId: string) => {
    if (prediction !== null) return
    const record: PredictionRecord = { handId, prediction: playerId, result: null }
    setPrediction(record)
    savePrediction(record)
  }

  const pickedPlayer = prediction
    ? players.find(p => p.id === prediction.prediction) ?? null
    : null

  const panelStyle: React.CSSProperties = {
    position: 'absolute',
    bottom: 16,
    right: 16,
    zIndex: 30,
    background: 'rgb(24,36,38)',
    border: '3px solid rgb(45,58,59)',
    borderRadius: 14,
    padding: '8px 16px',
    boxShadow: '0 6px 0 0 rgba(0,0,0,0.5)',
    animation: 'slideIn 0.25s ease-out both',
    minWidth: 140,
  }

  const headerStyle: React.CSSProperties = {
    fontFamily: 'var(--font-rajdhani), sans-serif',
    fontWeight: 700,
    fontSize: 14,
    letterSpacing: '-0.01em',
    color: 'rgba(255,255,255,0.4)',
    marginBottom: 8,
    whiteSpace: 'nowrap',
  }

  const subLabelStyle: React.CSSProperties = {
    fontFamily: 'var(--font-rajdhani), sans-serif',
    fontWeight: 700,
    fontSize: 14,
    letterSpacing: '-0.03em',
    color: 'rgba(255,255,255,0.25)',
    marginTop: 6,
    whiteSpace: 'nowrap',
  }

  // State C — result reveal: shown for RESULT_DISPLAY_MS after showdown, survives hand reset
  // zIndex: 60 puts it above the winner overlay (zIndex: 50)
  if (resultFlash !== null) {
    return (
      <div style={{ ...panelStyle, zIndex: 60 }}>
        {resultFlash.result === 'correct' && (
          <div style={{ position: 'relative', display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
            <ConfettiBurst />
            <GoldCrownChip size="md" label="CORRECT!" />
          </div>
        )}
        {resultFlash.result === 'wrong' && (
          <StakeChip size="md" stakeColor="red" label="WRONG" />
        )}
        <div style={subLabelStyle}>You picked {resultFlash.playerName}</div>
      </div>
    )
  }

  // State B — picked, awaiting result
  if (prediction !== null && pickedPlayer !== null) {
    return (
      <div style={panelStyle}>
        <div style={{ ...headerStyle, color: 'rgba(255,255,255,0.3)' }}>PREDICTED:</div>
        <StakeChip
          size="md"
          label={pickedPlayer.name}
          stakeColor={STAKE_MAP[pickedPlayer.id] ?? 'blue'}
        />
      </div>
    )
  }

  // State A — unpicked
  return (
    <div style={panelStyle}>
      <div style={headerStyle}>WHO WINS THIS HAND?</div>
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
        {players.map(player => (
          <StakeChip
            key={player.id}
            size="md"
            label={player.name.split(' ')[0]}
            stakeColor={STAKE_MAP[player.id] ?? 'blue'}
            onClick={() => handlePick(player.id)}
          />
        ))}
      </div>
    </div>
  )
}
