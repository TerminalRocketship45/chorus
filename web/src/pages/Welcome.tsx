import { Link } from "react-router-dom";
import { APP_NAME, APP_TAGLINE } from "../content/app";

export function Welcome() {
  return (
    <div className="page stack stack--loose" style={{ textAlign: "center" }}>
      <div className="stack stack--tight">
        <h1>{APP_NAME}</h1>
        <p style={{ fontSize: "1.2rem" }}>{APP_TAGLINE}</p>
      </div>
      <div className="stack">
        <Link to="/onboarding" className="btn btn-primary btn-large btn-block">
          Start reading
        </Link>
        <Link to="/teacher" className="btn btn-secondary btn-block">
          Teacher / parent view
        </Link>
      </div>
    </div>
  );
}
