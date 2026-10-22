import { createContext, useContext, useMemo, useState, type ReactNode } from "react";
import type { GradeBand } from "../types/api";
import { loadTopic, saveTopic } from "../lib/generated";
import { clearReader, loadStoredReader, saveGradeBand, saveHomeLanguage, saveStudent } from "../lib/storage";

interface AppState {
  gradeBand: GradeBand | null;
  homeLanguage: string | null;
  studentId: number | null;
  studentName: string | null;
  topic: string;
  setGradeBand: (band: GradeBand) => void;
  setHomeLanguage: (code: string) => void;
  setTopic: (topic: string) => void;
  setStudent: (id: number, name: string) => void;
  /** Lets a different reader take over this device without the old one's info lingering. */
  switchReader: () => void;
}

const AppContext = createContext<AppState | null>(null);

export function AppProvider({ children }: { children: ReactNode }) {
  const initial = loadStoredReader();
  const [gradeBand, setGradeBandState] = useState<GradeBand | null>(initial.gradeBand);
  const [homeLanguage, setHomeLanguageState] = useState<string | null>(initial.homeLanguage);
  const [studentId, setStudentId] = useState<number | null>(initial.studentId);
  const [studentName, setStudentName] = useState<string | null>(initial.studentName);
  const [topic, setTopicState] = useState<string>(loadTopic());

  const value = useMemo<AppState>(
    () => ({
      gradeBand,
      homeLanguage,
      studentId,
      studentName,
      topic,
      setGradeBand: (band) => {
        saveGradeBand(band);
        setGradeBandState(band);
      },
      setHomeLanguage: (code) => {
        saveHomeLanguage(code);
        setHomeLanguageState(code);
      },
      setTopic: (value) => {
        saveTopic(value);
        setTopicState(value);
      },
      setStudent: (id, name) => {
        saveStudent(id, name);
        setStudentId(id);
        setStudentName(name);
      },
      switchReader: () => {
        clearReader();
        setGradeBandState(null);
        setHomeLanguageState(null);
        setStudentId(null);
        setStudentName(null);
        setTopicState("");
      },
    }),
    [gradeBand, homeLanguage, studentId, studentName, topic]
  );

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>;
}

export function useAppState(): AppState {
  const ctx = useContext(AppContext);
  if (!ctx) throw new Error("useAppState must be used inside AppProvider");
  return ctx;
}
