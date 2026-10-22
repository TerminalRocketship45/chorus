import { Link } from "react-router-dom";
import { Icon } from "./Icon";

/** The gear that opens Settings; sits in the navigation bar's right slot. */
export function SettingsButton({ className = "" }: { className?: string }) {
  return (
    <Link to="/settings" className={`gear ${className}`.trim()} aria-label="Settings">
      <Icon name="gear" size={24} />
    </Link>
  );
}
