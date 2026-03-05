import { Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import DealDesk from './pages/DealDesk'
import Companies from './pages/Companies'
import Settings from './pages/Settings'
import Ops from './pages/Ops'

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Layout />}>
        <Route index element={<DealDesk />} />
        <Route path="companies" element={<Companies />} />
        <Route path="ops" element={<Ops />} />
        <Route path="settings" element={<Settings />} />
      </Route>
    </Routes>
  )
}
