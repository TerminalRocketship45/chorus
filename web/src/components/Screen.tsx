import { useEffect, useRef, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { Icon } from "./Icon";

interface BackProps {
  /** Short name of the screen you return to, shown beside the chevron. */
  label: string;
  to?: string;
  onClick?: () => void;
}

interface ScreenProps {
  title: string;
  /** Large collapsing title (list screens); otherwise the title sits in the bar. */
  large?: boolean;
  back?: BackProps;
  trailing?: ReactNode;
  /** Sticky bottom bar (primary action). */
  bottom?: ReactNode;
  children: ReactNode;
}

/**
 * iOS-style screen: navigation bar with a back chevron, optional large title
 * that collapses into the bar as you scroll, and an optional bottom action bar.
 */
export function Screen({ title, large = false, back, trailing, bottom, children }: ScreenProps) {
  const sentinelRef = useRef<HTMLHeadingElement | null>(null);
  const [titleInBar, setTitleInBar] = useState(false);
  const [scrolled, setScrolled] = useState(false);
  const [pastTitle, setPastTitle] = useState(false);

  useEffect(() => {
    document.title = `${title} · Chorus`;
  }, [title]);

  // The page scrolls on the window on phones and inside the phone frame's
  // screen on desktop; follow whichever is active.
  const headerRef = useRef<HTMLElement | null>(null);

  useEffect(() => {
    const root = headerRef.current?.closest<HTMLElement>("[data-scroll-root]") ?? null;
    const offset = () => Math.max(window.scrollY, root?.scrollTop ?? 0);
    const onScroll = () => {
      const y = offset();
      setScrolled(y > 2);
      setPastTitle(y > 60);
    };
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    root?.addEventListener("scroll", onScroll, { passive: true });
    return () => {
      window.removeEventListener("scroll", onScroll);
      root?.removeEventListener("scroll", onScroll);
    };
  }, []);

  useEffect(() => {
    if (!large) return;
    const el = sentinelRef.current;
    if (!el || typeof IntersectionObserver === "undefined") {
      setTitleInBar(false);
      return;
    }
    const scroller = el.closest<HTMLElement>("[data-scroll-root]");
    const framed = scroller !== null && getComputedStyle(scroller).overflowY === "auto";
    const observer = new IntersectionObserver(([entry]) => setTitleInBar(!entry.isIntersecting), {
      root: framed ? scroller : null,
      rootMargin: "-48px 0px 0px 0px",
    });
    observer.observe(el);
    return () => observer.disconnect();
  }, [large]);

  const backContent = back && (
    <>
      <Icon name="chevronLeft" size={22} strokeWidth={2.4} />
      <span>{back.label}</span>
    </>
  );

  return (
    <>
      <header className="navbar" data-scrolled={scrolled} ref={headerRef}>
        <div className="navbar__inner">
          <div className="navbar__lead">
            {back &&
              (back.to ? (
                <Link className="back" to={back.to} aria-label={`Back to ${back.label}`} onClick={back.onClick}>
                  {backContent}
                </Link>
              ) : (
                <button type="button" className="back" aria-label={`Back to ${back.label}`} onClick={back.onClick}>
                  {backContent}
                </button>
              ))}
          </div>
          <div className="navbar__title" data-visible={large ? titleInBar : pastTitle} aria-hidden={large ? true : undefined}>
            {title}
          </div>
          <div className="navbar__trail">{trailing}</div>
        </div>
      </header>
      <main className={`screen${bottom ? " screen--with-bar" : ""}`}>
        {large && (
          <h1 className="large-title" ref={sentinelRef}>
            {title}
          </h1>
        )}
        {children}
      </main>
      {bottom && <div className="actionbar">{bottom}</div>}
    </>
  );
}
