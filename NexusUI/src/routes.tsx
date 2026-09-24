import { createBrowserRouter } from 'react-router';
import Layout from './components/Layout';
import ResearchHome from './pages/ResearchHome';
import SourceLibrary from './pages/SourceLibrary';
import DocumentInspector from './pages/DocumentInspector';
import ResearchResult from './pages/ResearchResult';
import ResearchJob from './pages/ResearchJob';
import ResearchGraph from './pages/ResearchGraph';
import Evaluation from './pages/Evaluation';
import Reports from './pages/Reports';
import Evidence from './pages/Evidence';
import Settings from './pages/Settings';

export const router = createBrowserRouter([
  {
    path: '/',
    Component: Layout,
    children: [
      { index: true, Component: ResearchHome },
      { path: 'sources', Component: SourceLibrary },
      { path: 'sources/:id', Component: DocumentInspector },
      { path: 'research/:id', Component: ResearchResult },
      { path: 'jobs', Component: ResearchJob },
      { path: 'evidence', Component: Evidence },
      { path: 'reports', Component: Reports },
      { path: 'graph', Component: ResearchGraph },
      { path: 'evaluation', Component: Evaluation },
      { path: 'settings', Component: Settings },
    ],
  },
]);
