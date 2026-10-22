import { createContext, useContext, useMemo, useState, type ReactNode } from "react";
import type { GradeBand } from "../types/api";
import { clearReader, loadStoredReader, saveGradeBand, saveHomeLanguage, saveInterests, saveStudent } from "../lib/storage";

interface AppState {
  gradeBand: GradeBand | null;
  homeLanguage: string | null;
  studentId: number | null;
  studentName: string | null;
  interests: string[];
  setGradeBand: (band: GradeBand) => void;
  setHomeLanguage: (code: string) => void;
  setInterests: (codes: string[]) => void;
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
  const [interests, setInterestsState] = useState<string[]>(initial.interests);

  const value = useMemo<AppState>(
    () => ({
      gradeBand,
      homeLanguage,
      studentId,
      studentName,
      interests,
      setGradeBand: (band) => {
        saveGradeBand(band);
        setGradeBandState(band);
      },
      setHomeLanguage: (code) => {
        saveHomeLanguage(code);
        setHomeLanguageState(code);
      },
      setInterests: (codes) => {
        saveInterests(codes);
        setInterestsState(codes);
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
        setInterestsState([]);
      },
    }),
    [gradeBand, homeLanguage, studentId, studentName, interests]
  );

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>;
}

export function useAppState(): AppState {
  const ctx = useContext(AppContext);
  if (!ctx) throw new Error("useAppState must be used inside AppProvider");
  return ctx;
}
