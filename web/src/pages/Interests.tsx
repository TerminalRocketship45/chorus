import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import type { Interest } from "../types/api";
import { ApiRequestError, getInterests, updateStudent } from "../lib/api";
import { useAppState } from "../context/AppContext";
import { Screen } from "../components/Screen";
import { Icon } from "../components/Icon";

/** Edit interests after onboarding: PATCH for a student, local state for a nickname-less reader. */
export function Interests() {
  const navigate = useNavigate();
  const app = useAppState();
  const [list, setList] = useState<Interest[] | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [selected, setSelected] = useState<string[]>(app.interests);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [retry, setRetry] = useState(0);

  useEffect(() => {
    let cancelled = false;
    setLoadError(null);
    getInterests()
      .then((l) => {
        if (!cancelled) setList(l);
      })
      .catch(() => {
        if (!cancelled) setLoadError("Chorus couldn't load the interests list. Please try again.");
      });
    return () => {
      cancelled = true;
    };
  }, [retry]);

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
      <p className="lede" style={{ marginTop: -12 }}>
        Pick one or more. New passages are written about the things you choose.
      </p>
      {loadError && (
        <div className="notice notice--error" role="alert">
          <Icon name="warning" size={20} />
          <div className="notice__body">
            <span>{loadError}</span>
            <button type="button" className="btn btn--plain" style={{ minHeight: 32, padding: 0 }} onClick={() => setRetry((n) => n + 1)}>
              Try again
            </button>
          </div>
        </div>
      )}
      {!list && !loadError && (
        <p className="footnote" role="status">
          Loading…
        </p>
      )}
      {list && (
        <div className="chips" role="group" aria-label="Interests">
          {list.map((item) => (
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
      )}
      {saveError && (
        <div className="notice notice--error" role="alert">
          <Icon name="warning" size={20} />
          <span>{saveError}</span>
        </div>
      )}
      {selected.length === 0 && list && <p className="footnote">Choose at least one.</p>}
    </Screen>
  );
}
