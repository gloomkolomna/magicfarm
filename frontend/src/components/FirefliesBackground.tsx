import { useEffect, useRef } from 'react';

interface Firefly {
  x: number;
  y: number;
  vx: number;
  vy: number;
  r: number;
  o: number;
  life: number;
  maxLife: number;
  swayPhase: number;
  swaySpeed: number;
  swayAmp: number;
  blinkPhase: number;
  blinkSpeed: number;
}

export default function FirefliesBackground() {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    const canvas = canvasRef.current;
    if (!canvas || reduceMotion) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    let w = 0;
    let h = 0;
    let dpr = 1;
    const flies: Firefly[] = [];
    const MAX = 60;

    const resize = () => {
      dpr = Math.min(window.devicePixelRatio || 1, 2);
      w = window.innerWidth;
      h = window.innerHeight;
      canvas.width = Math.floor(w * dpr);
      canvas.height = Math.floor(h * dpr);
      canvas.style.width = `${w}px`;
      canvas.style.height = `${h}px`;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    };
    resize();
    window.addEventListener('resize', resize);

    const spawn = (anywhere: boolean) => {
      if (flies.length >= MAX) return;
      flies.push({
        x: Math.random() * w,
        y: anywhere ? Math.random() * h : h + 20,
        vx: (Math.random() - 0.5) * 0.4,
        vy: -(Math.random() * 0.9 + 0.25),
        r: Math.random() * 2.6 + 1.4,
        o: Math.random() * 0.5 + 0.5,
        life: 0,
        maxLife: Math.random() * 320 + 200,
        swayPhase: Math.random() * Math.PI * 2,
        swaySpeed: 0.008 + Math.random() * 0.02,
        swayAmp: 0.25 + Math.random() * 0.6,
        blinkPhase: Math.random() * Math.PI * 2,
        blinkSpeed: 0.02 + Math.random() * 0.05,
      });
    };
    for (let i = 0; i < 20; i++) spawn(true);

    let animId = 0;
    const tick = () => {
      ctx.clearRect(0, 0, w, h);
      if (Math.random() < 0.18) spawn(false);

      for (let i = flies.length - 1; i >= 0; i--) {
        const f = flies[i];
        f.life++;
        f.swayPhase += f.swaySpeed;
        f.blinkPhase += f.blinkSpeed;
        f.x += f.vx + Math.sin(f.swayPhase) * f.swayAmp;
        f.y += f.vy;

        const t = f.life / f.maxLife;
        const fade = t < 0.1 ? t / 0.1 : t > 0.85 ? (1 - t) / 0.15 : 1;
        const blink = 0.55 + 0.45 * Math.sin(f.blinkPhase);
        const alpha = Math.max(0, f.o * fade * blink);

        ctx.beginPath();
        ctx.arc(f.x, f.y, f.r * 3, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(255, 200, 0, ${alpha * 0.1})`;
        ctx.fill();

        ctx.beginPath();
        ctx.arc(f.x, f.y, f.r, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(255, 220, 120, ${alpha})`;
        ctx.fill();

        ctx.beginPath();
        ctx.arc(f.x, f.y, f.r * 0.4, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(255, 245, 200, ${Math.min(1, alpha * 1.3)})`;
        ctx.fill();

        if (f.life >= f.maxLife || f.y < -20) flies.splice(i, 1);
      }
      animId = requestAnimationFrame(tick);
    };
    tick();

    return () => {
      cancelAnimationFrame(animId);
      window.removeEventListener('resize', resize);
    };
  }, []);

  return (
    <canvas
      ref={canvasRef}
      aria-hidden="true"
      style={{ position: 'fixed', inset: 0, zIndex: 5, pointerEvents: 'none' }}
    />
  );
}
