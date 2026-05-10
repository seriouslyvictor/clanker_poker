import { useEffect, useRef, useState } from 'react'
import type { GameState, ReasoningEntry } from '../components/types'

export type ConnectionState = 'connecting' | 'open' | 'closed'

export interface GameStream {
  gameState: GameState | null
  reasoning: ReasoningEntry[]
  connectionState: ConnectionState
}

interface ReasoningDelta {
  playerId: string
  phase: string
  delta: string
  done: boolean
}

// URL normalization: new URL('/api/stream', base) prevents double-slash
// if VITE_API_URL is set with a trailing slash (e.g. "http://localhost:8000/").
const _base = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'
const SSE_URL = new URL('/api/stream', _base).toString()

function applyDelta(prev: ReasoningEntry[], delta: ReasoningDelta): ReasoningEntry[] {
  const idx = prev.findIndex(
    r => r.playerId === delta.playerId && r.phase === delta.phase
  )
  if (idx !== -1) {
    const updated = [...prev]
    updated[idx] = {
      ...updated[idx],
      text: updated[idx].text + delta.delta,
      streaming: !delta.done,
    }
    return updated
  }
  const entry: ReasoningEntry = {
    id: `${delta.playerId}-${delta.phase}-${Date.now()}`,
    playerId: delta.playerId as ReasoningEntry['playerId'],
    phase: delta.phase,
    text: delta.delta,
    streaming: !delta.done,
    action: null,
    amount: 0,
  }
  return [...prev, entry]
}

export function useGameStream(): GameStream {
  const [gameState, setGameState] = useState<GameState | null>(null)
  const [reasoning, setReasoning] = useState<ReasoningEntry[]>([])
  const [connectionState, setConnectionState] = useState<ConnectionState>('connecting')
  const prevWinnerRef = useRef<number | null | undefined>(undefined)

  useEffect(() => {
    const es = new EventSource(SSE_URL)

    // onopen fires on initial connect AND after every auto-reconnect.
    es.onopen = () => {
      setConnectionState('open')
    }

    es.addEventListener('game_state', (e: MessageEvent) => {
      try {
        const state: GameState = JSON.parse(e.data as string)
        if (
          prevWinnerRef.current !== null &&
          prevWinnerRef.current !== undefined &&
          state.winner === null
        ) {
          setReasoning([])
        }
        prevWinnerRef.current = state.winner
        setGameState(state)
      } catch (err) {
        console.error('[useGameStream] Failed to parse game_state event:', err)
      }
    })

    es.addEventListener('reasoning', (e: MessageEvent) => {
      try {
        const delta: ReasoningDelta = JSON.parse(e.data as string)
        setReasoning(prev => applyDelta(prev, delta))
      } catch (err) {
        console.error('[useGameStream] Failed to parse reasoning event:', err)
      }
    })

    // reasoning_snapshot: sent on every connect/reconnect — full accumulated deltas.
    // Rebuild from scratch (authoritative) rather than merging with stale state.
    es.addEventListener('reasoning_snapshot', (e: MessageEvent) => {
      try {
        const deltas: ReasoningDelta[] = JSON.parse(e.data as string)
        setReasoning(() => {
          let rebuilt: ReasoningEntry[] = []
          for (const delta of deltas) {
            rebuilt = applyDelta(rebuilt, delta)
          }
          return rebuilt
        })
      } catch (err) {
        console.error('[useGameStream] Failed to parse reasoning_snapshot event:', err)
      }
    })

    es.onerror = () => {
      setConnectionState('connecting')
      // DO NOT call es.close() — native EventSource auto-reconnects on error.
      // Only close in cleanup (return below).
    }

    return () => {
      es.close()
      setConnectionState('closed')
    }
  }, [])

  return { gameState, reasoning, connectionState }
}
