import type { ModelId, VoiceMode, AtmosphereMode, TempoMode } from '@/lib/constants';

export type Card = { s: string; r: string };
export type ActionType = 'fold' | 'call' | 'raise' | 'check';

export interface Player {
  id: ModelId;
  name: string;
  org: string;
  color: string;
  deck: string;
  chips: number;
  holeCards: Card[];
  action: ActionType | null;
  bet: number;
  isFolded: boolean;
  isActive: boolean;
  isWinner: boolean;
}

export interface ReasoningEntry {
  id: string;
  playerId: ModelId;
  text: string;
  phase: string;
  streaming: boolean;
  action: ActionType | null;
  amount: number;
}

export interface GameState {
  phase: string;
  pot: number;
  communityCards: Card[];
  players: Player[];
  showCards: boolean;
  reasoning: ReasoningEntry[];
  winner: number | null;
  winnerHand: string;
  currentBet?: number;
}

export interface GameStatus {
  running: boolean;
  lastWinner?: { name: string; org: string; hand: string } | null;
}

export interface Settings {
  tempo: TempoMode;
  voice: VoiceMode;
  atmosphere: AtmosphereMode;
}

export type { ModelId, VoiceMode, AtmosphereMode, TempoMode };
