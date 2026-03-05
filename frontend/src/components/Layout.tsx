import { Outlet } from 'react-router-dom'
import Sidebar from './Sidebar'
import CommandPalette from './CommandPalette'

export default function Layout() {
  return (
    <div className="flex h-screen bg-navy-gradient overflow-hidden">
      <Sidebar />
      <main className="flex-1 overflow-hidden">
        <Outlet />
      </main>
      <CommandPalette />
    </div>
  )
}
