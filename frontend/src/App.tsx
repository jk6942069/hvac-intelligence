import { Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import DealDesk from './pages/DealDesk'
import Companies from './pages/Companies'
import Settings from './pages/Settings'
import Ops from './pages/Ops'
import Login from './pages/Login'
import Register from './pages/Register'
import ResetPassword from './pages/ResetPassword'
import ProtectedRoute from './components/ProtectedRoute'

export default function App() {
  return (
    <Routes>
      {/* Public auth routes */}
      <Route path="/login" element={<Login />} />
      <Route path="/register" element={<Register />} />
      <Route path="/reset-password" element={<ResetPassword />} />

      {/* Protected app routes */}
      <Route
        path="/"
        element={
          <ProtectedRoute>
            <Layout />
          </ProtectedRoute>
        }
      >
        <Route index element={<DealDesk />} />
        <Route path="companies" element={<Companies />} />
        <Route path="ops" element={<Ops />} />
        <Route path="settings" element={<Settings />} />
      </Route>
    </Routes>
  )
}
