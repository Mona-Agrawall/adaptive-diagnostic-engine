import { Link, Route, Routes } from 'react-router';
import { Layout } from './components/Layout';
import { AssessmentPage } from './pages/AssessmentPage';
import { HistoryPage } from './pages/HistoryPage';
import { LandingPage } from './pages/LandingPage';
import { ResultsPage } from './pages/ResultsPage';
import { SetupPage } from './pages/SetupPage';

function NotFoundPage() {
  return (
    <div className="card empty-state">
      <h1>Page not found</h1>
      <p className="muted">The page you are looking for does not exist.</p>
      <Link to="/" className="button button-primary">
        Go to the home page
      </Link>
    </div>
  );
}

export function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<LandingPage />} />
        <Route path="start" element={<SetupPage />} />
        <Route path="assessment/:id" element={<AssessmentPage />} />
        <Route path="results/:id" element={<ResultsPage />} />
        <Route path="history" element={<HistoryPage />} />
        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  );
}
