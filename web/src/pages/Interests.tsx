import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { ApiRequestError, updateStudent } from "../lib/api";
import { useAppState } from "../context/AppContext";
import { Screen } from "../components/Screen";
import { INTERESTS } from "../content/interests";
import { Icon } from "../components/Icon";

/** Edit interests after onboarding: PATCH for a student, local state for a nickname-less reader. */
export function Interests() {
  const navigate = useNavigate();
  const app = useAppState();
  const [selected, setSelected] = useState<string[]>(app.interests);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  function toggle(code: string) {
    setSelected((cur) => (cur.includes(code) ? cur.filter((c) => c !== code) : [...cur, code]));
  }

  async function save() {
    setSaving(true);
    setSaveError(null);
    try {
      if (app.studentId !== null) {
        await updateStudent(app.studentId, { interests: selected });
      }
      app.setInterests(selected);
      navigate("/passages");
    } catch (err) {
      setSaveError(
        err instanceof ApiRequestError && err.status === 404
          ? "Chorus can't find your saved name any more. Your interests are kept on this device."
          : "Couldn't save your interests. Please try again."
      );
      if (err instanceof ApiRequestError && err.status === 404) app.setInterests(selected);
    } finally {
      setSaving(false);
    }
  }

  const changed = selected.length !== app.interests.length || selected.some((c) => !app.interests.includes(c));

  return (
    <Screen
      title="Interests"
      large
      back={{ label: "Passages", to: "/passages" }}
      bottom={
        <button
          type="button"
          className="btn btn--filled btn--block"
          disabled={saving || selected.length === 0 || !changed}
          onClick={save}
        >
          {saving ? "Saving…" : "Save"}
        </button>
      }
    >
      <div className="chips" role="group" aria-label="Interests">
        {INTERESTS.map((item) => (
          <button
            key={item.code}
            type="button"
            className="chip"
            aria-pressed={selected.includes(item.code)}
            onClick={() => toggle(item.code)}
          >
            {selected.includes(item.code) && <Icon name="check" size={16} strokeWidth={3} />}
            {item.label}
          </button>
        ))}
      </div>
      {saveError && (
        <div className="notice notice--error" role="alert">
          <Icon name="warning" size={20} />
          <span>{saveError}</span>
        </div>
      )}
      {selected.length === 0 && <p className="footnote">Choose at least one.</p>}
    </Screen>
  );
}
