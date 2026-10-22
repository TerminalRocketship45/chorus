/** Where full-screen overlays (sheets, confetti) mount: inside the phone frame's screen when there is one. */
export function overlayRoot(): HTMLElement {
  return document.querySelector<HTMLElement>(".device__screen") ?? document.body;
}
