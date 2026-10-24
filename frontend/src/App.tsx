import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { AppLayout } from "./components/layout/AppLayout";
import { Dashboard } from "./pages/Dashboard";
import { NewEvaluation } from "./pages/NewEvaluation";
import { Evaluations } from "./pages/Evaluations";
import { EvaluationDetail } from "./pages/EvaluationDetail";
import { Runs } from "./pages/Runs";
import { RunDetails } from "./pages/RunDetails";

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<AppLayout />}>
          <Route path="/" element={<Dashboard />} />
          <Route path="/new" element={<NewEvaluation />} />
          <Route path="/evaluations" element={<Evaluations />} />
          <Route path="/evaluations/:evaluationId" element={<EvaluationDetail />} />
          <Route path="/runs" element={<Runs />} />
          <Route path="/runs/:runId" element={<RunDetails />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
