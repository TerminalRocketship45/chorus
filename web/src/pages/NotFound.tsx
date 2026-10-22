import { Link } from "react-router-dom";
import { Screen } from "../components/Screen";

export function NotFound() {
  return (
    <Screen title="Page not found" large back={{ label: "Home", to: "/" }}>
      <Link to="/" className="btn btn--filled btn--block">
        Go home
      </Link>
    </Screen>
  );
}
