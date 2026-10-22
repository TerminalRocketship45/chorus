import { useEffect, useRef } from "react";
import { createPortal } from "react-dom";
import { CONFETTI_COUNT, CONFETTI_SECONDS, makeConfettiPieces } from "../lib/confetti";
import { overlayRoot } from "./Overlay";

/** A short, quiet burst of small pieces falling from the top. Removes itself when it ends. */
export function Confetti({ onDone }: { onDone: () => void }) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const doneRef = useRef(onDone);
  doneRef.current = onDone;

  useEffect(() => {
    const canvas = canvasRef.current;
    const ctx = canvas?.getContext("2d");
    if (!canvas || !ctx) {
      doneRef.current();
      return;
    }
    const host = canvas.parentElement as HTMLElement;
    const w = host.clientWidth || window.innerWidth;
    const h = host.clientHeight || window.innerHeight;
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    canvas.width = w * dpr;
    canvas.height = h * dpr;
    ctx.scale(dpr, dpr);

    const css = getComputedStyle(document.documentElement);
    const palette = ["--accent", "--confetti-2", "--confetti-3"].map((v) => css.getPropertyValue(v).trim() || "#0a62c9");
    const pieces = makeConfettiPieces(CONFETTI_COUNT, w);
    const total = CONFETTI_SECONDS + 0.35;
    let raf = 0;
    let start = 0;

    const frame = (now: number) => {
      if (!start) start = now;
      const t = (now - start) / 1000;
      ctx.clearRect(0, 0, w, h);
      for (const p of pieces) {
        const age = t - p.delay;
        if (age < 0) continue;
        const life = Math.min(1, age / CONFETTI_SECONDS);
        const x = p.x + p.vx * age + Math.sin(age * p.swayRate) * p.sway;
        const y = p.y + p.vy * age + 120 * age * age;
        ctx.save();
        ctx.globalAlpha = life < 0.65 ? 0.9 : Math.max(0, (1 - life) / 0.35) * 0.9;
        ctx.translate(x, y);
        ctx.rotate(p.rot + p.vr * age);
        ctx.fillStyle = palette[p.colour];
        ctx.beginPath();
        ctx.roundRect ? ctx.roundRect(-p.w / 2, -p.h / 2, p.w, p.h, 1.5) : ctx.rect(-p.w / 2, -p.h / 2, p.w, p.h);
        ctx.fill();
        ctx.restore();
      }
      if (t < total) raf = requestAnimationFrame(frame);
      else doneRef.current();
    };
    raf = requestAnimationFrame(frame);
    return () => cancelAnimationFrame(raf);
  }, []);

  return createPortal(
    <div className="confetti" aria-hidden="true">
      <canvas ref={canvasRef} className="confetti__canvas" />
    </div>,
    overlayRoot()
  );
}
