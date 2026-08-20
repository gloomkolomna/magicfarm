import { useEffect } from 'react';

const EMOJIS = ['💗', '💕', '💖'];

interface Props {
  x: number;
  y: number;
}

export default function HeartsBurst({ x, y }: Props) {
  useEffect(() => {
    const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (reduceMotion) return;

    const host = document.createElement('div');
    host.style.cssText = 'position:fixed;inset:0;z-index:1000;pointer-events:none;';
    document.body.appendChild(host);

    const anims: Animation[] = [];
    const COUNT = 14;
    for (let i = 0; i < COUNT; i++) {
      const el = document.createElement('span');
      el.textContent = EMOJIS[Math.floor(Math.random() * EMOJIS.length)];
      const size = 14 + Math.random() * 16;
      el.style.cssText = `position:fixed;left:${x - size / 2}px;top:${y - size / 2}px;font-size:${size}px;line-height:1;will-change:transform,opacity;`;
      const dx = (Math.random() - 0.5) * 160;
      const dy = -(90 + Math.random() * 190);
      const rot = (Math.random() - 0.5) * 80;
      const anim = el.animate(
        [
          { transform: 'translate(0px, 0px) scale(0.5) rotate(0deg)', opacity: 0 },
          { transform: `translate(${dx * 0.25}px, ${dy * 0.3}px) scale(1.1) rotate(${rot * 0.4}deg)`, opacity: 1, offset: 0.3 },
          { transform: `translate(${dx}px, ${dy}px) scale(0.9) rotate(${rot}deg)`, opacity: 0 },
        ],
        { duration: 900 + Math.random() * 500, easing: 'cubic-bezier(0.2, 0.6, 0.4, 1)' },
      );
      host.appendChild(el);
      anims.push(anim);
    }

    const timer = window.setTimeout(() => host.remove(), 1600);
    return () => {
      window.clearTimeout(timer);
      anims.forEach((a) => a.cancel());
      host.remove();
    };
  }, [x, y]);

  return null;
}
