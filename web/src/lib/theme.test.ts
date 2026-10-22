import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { THEME_KEY, applyThemePref, loadThemePref, parseThemePref, resolveTheme, saveThemePref } from "./theme";

function memoryStorage() {
  const m = new Map<string, string>();
  return {
    getItem: (k: string) => m.get(k) ?? null,
    setItem: (k: string, v: string) => void m.set(k, v),
    removeItem: (k: string) => void m.delete(k),
  };
}

describe("theme preference", () => {
  it("parses only light and dark; anything else is system", () => {
    expect(parseThemePref("light")).toBe("light");
    expect(parseThemePref("dark")).toBe("dark");
    expect(parseThemePref("system")).toBe("system");
    expect(parseThemePref("purple")).toBe("system");
    expect(parseThemePref(null)).toBe("system");
  });

  it("resolves system from the device, explicit choices win", () => {
    expect(resolveTheme("system", true)).toBe("dark");
    expect(resolveTheme("system", false)).toBe("light");
    expect(resolveTheme("light", true)).toBe("light");
    expect(resolveTheme("dark", false)).toBe("dark");
  });

  describe("persistence and application", () => {
    const store = memoryStorage();
    beforeEach(() => {
      (globalThis as unknown as { window: unknown }).window = { localStorage: store, matchMedia: () => ({ matches: false }) };
      const attrs = new Map<string, string>();
      (globalThis as unknown as { document: unknown }).document = {
        documentElement: {
          setAttribute: (k: string, v: string) => attrs.set(k, v),
          removeAttribute: (k: string) => attrs.delete(k),
          getAttribute: (k: string) => attrs.get(k) ?? null,
        },
        querySelectorAll: () => [],
      };
    });
    afterEach(() => {
      delete (globalThis as { window?: unknown }).window;
      delete (globalThis as { document?: unknown }).document;
    });

    it("round-trips through storage", () => {
      expect(loadThemePref()).toBe("system");
      saveThemePref("dark");
      expect(store.getItem(THEME_KEY)).toBe("dark");
      expect(loadThemePref()).toBe("dark");
    });

    it("sets data-theme for explicit choices and clears it for system", () => {
      applyThemePref("dark");
      expect(document.documentElement.getAttribute("data-theme")).toBe("dark");
      applyThemePref("light");
      expect(document.documentElement.getAttribute("data-theme")).toBe("light");
      applyThemePref("system");
      expect(document.documentElement.getAttribute("data-theme")).toBeNull();
    });
  });
});
