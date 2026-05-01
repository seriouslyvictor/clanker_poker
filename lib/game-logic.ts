import { SUITS, RANKS, RANK_V } from './constants';

export type Card = { s: string; r: string };
export type ActionType = 'fold' | 'call' | 'raise' | 'check';
export type Action = { t: ActionType; a: number };

export const mkDeck = (): Card[] =>
  SUITS.flatMap(s => RANKS.map(r => ({ s, r })));

export const shuffle = (d: Card[]): Card[] => {
  const a = [...d];
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
};

export function evalStrength(hole: Card[], comm: Card[] = []): number {
  if (!hole || hole.length < 2) return 20;
  const all = [...hole, ...comm];
  const vals = all.map(c => RANK_V[c.r] ?? 10);
  const suits = all.map(c => c.s);
  const rc: Record<number, number> = {};
  vals.forEach(v => { rc[v] = (rc[v] ?? 0) + 1; });
  const sc: Record<string, number> = {};
  suits.forEach(s => { sc[s] = (sc[s] ?? 0) + 1; });
  const counts = Object.values(rc).sort((a, b) => b - a);
  const maxSuit = Math.max(...Object.values(sc));
  let b = 0;
  if (counts[0] === 4) b = 90;
  else if (counts[0] === 3 && counts[1] === 2) b = 80;
  else if (maxSuit >= 5) b = 72;
  else if (counts[0] === 3) b = 62;
  else if (counts[0] === 2 && counts[1] === 2) b = 50;
  else if (counts[0] === 2) b = 34;
  else b = Math.max(...vals) * 1.4;
  return Math.min(b + (Math.random() * 8 - 4), 100);
}

export function handName(s: number): string {
  if (s > 89) return 'Four of a Kind';
  if (s > 79) return 'Full House';
  if (s > 71) return 'Flush';
  if (s > 61) return 'Three of a Kind';
  if (s > 49) return 'Two Pair';
  if (s > 33) return 'One Pair';
  return 'High Card';
}

export function decideAction(str: number, bet = 50): Action {
  if (str > 70) return { t: 'raise', a: bet * 2 };
  if (str > 40) return { t: 'call', a: bet };
  return Math.random() < Math.max(0, (42 - str) / 42)
    ? { t: 'fold', a: 0 }
    : { t: 'call', a: bet };
}
