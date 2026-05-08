import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { useAuthStore } from './store/authStore'
import { AuraProvider } from './components/aura/AuraContext'
import AuraCompanion from './components/aura/AuraCompanion'
import Landing from './pages/Landing'
import Login from './pages/Login'
import Register from './pages/Register'
import Dashboard from './pages/Dashboard'
import CloudConnect from './pages/CloudConnect'
import GraphView from './pages/GraphView'
import Prediction from './pages/Prediction'
import Propagation from './pages/Propagation'
import Healing from './pages/Healing'
import Timeline from './pages/Timeline'
import Profile from './pages/Profile'
import WarRoom from './pages/WarRoom'
import DriftDetection from './pages/DriftDetection'
import RCAView from './pages/RCAView'
import FinOps from './pages/FinOps'
import Security from './pages/Security'
import VerifyOTP from './pages/VerifyOTP'
import Settings from './pages/Settings'
import DemoControl from './pages/DemoControl'
import Layout from './components/layout/Layout'

function ProtectedRoute({ children }) {
  const { token } = useAuthStore()
  if (!token) return <Navigate to="/login" replace />
  return children
}

function PublicRoute({ children }) {
  const { token } = useAuthStore()
  if (token) return <Navigate to="/dashboard" replace />
  return children
}

export default function App() {
  return (
    <AuraProvider>
      <BrowserRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
        <Routes>
          <Route path="/" element={<Landing />} />
          <Route path="/login" element={<Login />} />
          <Route path="/register" element={<Register />} />
          <Route path="/verify-otp" element={<VerifyOTP />} />
          <Route element={<ProtectedRoute><Layout /></ProtectedRoute>}>
            <Route path="/dashboard" element={<Dashboard />} />
            <Route path="/connect" element={<CloudConnect />} />
            <Route path="/graph" element={<GraphView />} />
            <Route path="/prediction" element={<Prediction />} />
            <Route path="/propagation" element={<Propagation />} />
            <Route path="/healing" element={<Healing />} />
            <Route path="/timeline" element={<Timeline />} />
            <Route path="/profile" element={<Profile />} />
            <Route path="/war-room" element={<WarRoom />} />
            <Route path="/drift" element={<DriftDetection />} />
            <Route path="/rca" element={<RCAView />} />
            <Route path="/finops" element={<FinOps />} />
            <Route path="/security" element={<Security />} />
            <Route path="/settings" element={<Settings />} />
            <Route path="/demo"     element={<DemoControl />} />
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
        <AuraCompanionWrapper />
      </BrowserRouter>
    </AuraProvider>
  )
}



function AuraCompanionWrapper() {
  const { token } = useAuthStore()
  if (!token) return null
  return <AuraCompanion />
}