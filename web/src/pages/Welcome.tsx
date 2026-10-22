import { Link } from "react-router-dom";
import { APP_NAME, APP_TAGLINE } from "../content/app";
import { Icon } from "../components/Icon";

export function Welcome() {
  return (
    <main className="welcome">
      <div className="welcome__hero">
        <div className="welcome__mark" aria-hidden="true">
          <Icon name="chorusMark" size={46} strokeWidth={2.4} />
        </div>
        <h1 className="welcome__name">{APP_NAME}</h1>
        <p className="welcome__tag">{APP_TAGLINE}</p>
      </div>
      <div className="welcome__actions">
        <Link to="/onboarding" className="btn btn--filled btn--block">
          Start reading
        </Link>
        <Link to="/teacher" className="btn btn--plain btn--block">
          Teacher / parent view
        </Link>
        <Link to="/how-it-works" className="btn btn--plain btn--block">
          How {APP_NAME} works
        </Link>
        <p className="welcome__fine">
          {APP_NAME} is not a diagnostic or clinical tool. Recordings are never stored on the server.
        </p>
      </div>
    </main>
  );
}
