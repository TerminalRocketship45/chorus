import { Link } from "react-router-dom";
import { APP_NAME } from "../content/app";

export function Header() {
  return (
    <nav className="app-header" aria-label="Main">
      <Link to="/" aria-label={`${APP_NAME} home`}>
        {APP_NAME}
      </Link>
    </nav>
  );
}
