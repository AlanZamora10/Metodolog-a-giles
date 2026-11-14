import { Navigate, Outlet, Route, Routes, useLocation } from 'react-router-dom';
import { AuthProvider, useAuth } from './context/AuthContext';
import { CursoProvider } from './context/CursoContext';
import { ChatProvider } from './context/ChatContext';
import { AppShell } from './components/layout/AppShell';
import { LoginPage } from './pages/LoginPage';
import { DashboardPage } from './pages/DashboardPage';
import { EstudiantesPage } from './pages/EstudiantesPage';
import { EstudianteDetallePage } from './pages/EstudianteDetallePage';
import { AlertasPage } from './pages/AlertasPage';
import { AgentePage } from './pages/AgentePage';
import { ReportePage } from './pages/ReportePage';

/** Rutas protegidas: sin sesión válida redirige al login recordando el destino. */
function RutaProtegida() {
  const { usuario } = useAuth();
  const location = useLocation();
  if (!usuario) return <Navigate to="/login" replace state={{ desde: location.pathname + location.search }} />;
  // Los proveedores de datos viven sólo mientras hay sesión: al cerrar sesión se descartan.
  return (
    <CursoProvider key={usuario.email}>
      <ChatProvider>
        <Outlet />
      </ChatProvider>
    </CursoProvider>
  );
}

export function AppRoutes() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route element={<RutaProtegida />}>
        <Route element={<AppShell />}>
          <Route path="/dashboard" element={<DashboardPage />} />
          <Route path="/estudiantes" element={<EstudiantesPage />} />
          <Route path="/estudiantes/:idNumber" element={<EstudianteDetallePage />} />
          <Route path="/alertas" element={<AlertasPage />} />
          <Route path="/agente" element={<AgentePage />} />
          <Route path="/reporte" element={<ReportePage />} />
        </Route>
      </Route>
      <Route path="*" element={<Navigate to="/dashboard" replace />} />
    </Routes>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <AppRoutes />
    </AuthProvider>
  );
}
