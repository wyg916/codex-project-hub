import { Navigate, Route, Routes } from 'react-router-dom'
import { OverviewPage } from './pages/OverviewPage'
import { ProjectDashboard } from './pages/ProjectDashboard'

export function App() {
  return (
    <Routes>
      <Route path="/" element={<OverviewPage />} />
      <Route path="/projects/:projectId" element={<ProjectDashboard />} />
      <Route path="/projects/:projectId/*" element={<ProjectDashboard />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
