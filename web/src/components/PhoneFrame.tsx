import { useEffect, useRef, type ReactNode } from "react";
import { useLocation } from "react-router-dom";

const DEVICE_H = 864;
const DEVICE_W = 410;
const MARGIN = 24;

/**
 * On wide, tall viewports the app renders inside a modern-phone-shaped frame
 * (CSS in global.css, gated by a media query). On real phones and narrow
 * windows the wrappers are inert and the page scrolls as normal. The scroll
 * container carries `data-scroll-root` so Screen can follow its scrolling.
 */
export function PhoneFrame({ children }: { children: ReactNode }) {
  const deviceRef = useRef<HTMLDivElement | null>(null);
  const scrollRef = useRef<HTMLDivElement | null>(null);
  const { pathname } = useLocation();

  useEffect(() => {
    const fit = () => {
      const s = Math.min(1, (window.innerHeight - MARGIN) / DEVICE_H, (window.innerWidth - MARGIN) / DEVICE_W);
      deviceRef.current?.style.setProperty("--device-scale", String(Math.max(0.5, s)));
    };
    fit();
    window.addEventListener("resize", fit);
    return () => window.removeEventListener("resize", fit);
  }, []);

  useEffect(() => {
    scrollRef.current?.scrollTo(0, 0);
  }, [pathname]);

  return (
    <div className="stage">
      <div className="device" ref={deviceRef}>
        <div className="device__screen">
          <div className="device__chrome statusbar" aria-hidden="true">
            <span className="statusbar__time">9:41</span>
            <span className="statusbar__icons">
              <svg width="18" height="12" viewBox="0 0 18 12" fill="currentColor">
                <rect x="0" y="8" width="3" height="4" rx="1" />
                <rect x="5" y="5.5" width="3" height="6.5" rx="1" />
                <rect x="10" y="3" width="3" height="9" rx="1" />
                <rect x="15" y="0" width="3" height="12" rx="1" />
              </svg>
              <svg width="26" height="12" viewBox="0 0 26 12" fill="none">
                <rect x="0.5" y="0.5" width="22" height="11" rx="3.5" stroke="currentColor" opacity="0.4" />
                <rect x="2" y="2" width="19" height="8" rx="2.2" fill="currentColor" />
                <path d="M24 4v4c.8-.3 1.5-1.1 1.5-2S24.8 4.3 24 4z" fill="currentColor" opacity="0.45" />
              </svg>
            </span>
          </div>
          <span className="device__chrome island" aria-hidden="true" />
          <div className="device__scroll" ref={scrollRef} data-scroll-root>
            {children}
          </div>
          <span className="device__chrome home-indicator" aria-hidden="true" />
        </div>
      </div>
    </div>
  );
}
