import { Link } from "react-router-dom";
import { APP_NAME } from "../content/app";

export function Footer() {
  return (
    <footer className="app-footer">
      <p>
        <Link to="/how-it-works">How {APP_NAME} works</Link>
      </p>
      <p>
        {APP_NAME} is not a diagnostic or clinical tool. Recordings are never stored on the
        server.
      </p>
    </footer>
  );
}
