import { Route, Routes } from "react-router-dom";
import { Header } from "./components/Header";
import { Footer } from "./components/Footer";
import { AppProvider } from "./context/AppContext";
import { Welcome } from "./pages/Welcome";
import { Onboarding } from "./pages/Onboarding";
import { PassagePicker } from "./pages/PassagePicker";
import { Read } from "./pages/Read";
import { Results } from "./pages/Results";
import { TeacherView } from "./pages/TeacherView";
import { StudentDetail } from "./pages/StudentDetail";
import { HowItWorks } from "./pages/HowItWorks";
import { NotFound } from "./pages/NotFound";

export function App() {
  return (
    <AppProvider>
      <Header />
      <Routes>
        <Route path="/" element={<Welcome />} />
        <Route path="/onboarding" element={<Onboarding />} />
        <Route path="/passages" element={<PassagePicker />} />
        <Route path="/read/:passageId" element={<Read />} />
        <Route path="/results" element={<Results />} />
        <Route path="/teacher" element={<TeacherView />} />
        <Route path="/teacher/:studentId" element={<StudentDetail />} />
        <Route path="/how-it-works" element={<HowItWorks />} />
        <Route path="*" element={<NotFound />} />
      </Routes>
      <Footer />
    </AppProvider>
  );
}
