'use client';

const COINS = Array.from({ length: 10 }, (_, i) => ({
  x: -40 + i * 9 + Math.sin(i * 1.3) * 12,
  delay: i * 0.07,
  dur: 0.9 + (i % 3) * 0.2,
  color: i % 3 === 0 ? 'rgb(255,215,102)' : i % 3 === 1 ? 'rgb(250,140,1)' : 'rgb(255,240,160)',
  size: 8 + (i % 3) * 4,
}));

export default function ConfettiBurst() {
  return (
    <div style={{ position: 'absolute', top: 0, left: '50%', width: 0, height: 0, pointerEvents: 'none', zIndex: 10 }}>
      {COINS.map((c, i) => (
        <div key={i} style={{
          position: 'absolute',
          left: c.x, top: 0,
          width: c.size, height: c.size,
          borderRadius: '50%',
          background: c.color,
          boxShadow: '0 2px 0 0 rgba(0,0,0,0.3)',
          animation: `confettiFall ${c.dur}s ease-in ${c.delay}s forwards`,
        }} />
      ))}
    </div>
  );
}
