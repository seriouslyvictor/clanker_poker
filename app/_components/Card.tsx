'use client';

import type { Card as CardType } from '@/lib/game-logic';

interface CardProps {
  card?: CardType;
  faceDown?: boolean;
  cardBack?: string;
  style?: React.CSSProperties;
}

export default function Card({ card, faceDown, cardBack, style = {} }: CardProps) {
  if (!card && !faceDown) {
    return (
      <div style={{
        width: 58, height: 82, borderRadius: 7,
        border: '2px dashed rgb(45,58,59)',
        ...style,
      }} />
    );
  }

  if (faceDown) {
    const bg = cardBack?.startsWith('url(')
      ? cardBack
      : `url(${cardBack ?? '/assets/deck-red.png'}) center / cover no-repeat`;
    return (
      <div style={{
        width: 58, height: 82, borderRadius: 7,
        background: bg,
        border: '2.5px solid rgba(255,255,255,0.18)',
        boxShadow: '2px 4px 0px 0px rgba(0,0,0,0.55), 1px 0 0 rgba(255,255,255,0.08)',
        imageRendering: 'pixelated',
        ...style,
      }} />
    );
  }

  const isRed = card!.s === '♥' || card!.s === '♦';
  const col = isRed ? '#cc2200' : '#111827';

  return (
    <div style={{
      width: 58, height: 82, borderRadius: 7,
      background: '#fffef5',
      border: '2.5px solid #d1d5db',
      boxShadow: '2px 4px 0px 0px rgba(0,0,0,0.55)',
      padding: '4px 5px',
      position: 'relative',
      display: 'flex',
      flexDirection: 'column',
      ...style,
    }}>
      <div style={{ fontSize: 13, fontWeight: 800, color: col, lineHeight: 1, fontFamily: 'Georgia,serif' }}>{card!.r}</div>
      <div style={{ fontSize: 11, color: col, lineHeight: 1, fontFamily: 'Georgia,serif' }}>{card!.s}</div>
      <div style={{
        position: 'absolute', top: '50%', left: '50%',
        transform: 'translate(-50%,-50%)',
        fontSize: 32, color: col, opacity: 0.10,
        fontFamily: 'Georgia,serif', userSelect: 'none',
      }}>{card!.s}</div>
      <div style={{
        position: 'absolute', bottom: 4, right: 5,
        fontSize: 13, fontWeight: 800, color: col,
        transform: 'rotate(180deg)', lineHeight: 1,
        fontFamily: 'Georgia,serif',
      }}>{card!.r}</div>
    </div>
  );
}
