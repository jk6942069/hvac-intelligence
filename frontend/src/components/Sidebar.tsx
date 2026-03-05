import { NavLink, useNavigate } from 'react-router-dom'
import {
  LayoutDashboard, Building2, Settings, Terminal, Zap
} from 'lucide-react'

const navItems = [
  { to: '/', icon: LayoutDashboard, label: 'Deal Desk', exact: true },
  { to: '/companies', icon: Building2, label: 'Companies' },
  { to: '/ops', icon: Terminal, label: 'Ops / Pipeline' },
  { to: '/settings', icon: Settings, label: 'Settings' },
]

export default function Sidebar() {
  return (
    <aside className="w-52 flex flex-col h-full bg-navy-800 border-r border-surface-600 shrink-0">
      {/* Logo */}
      <div className="px-4 py-4 border-b border-surface-600">
        <div className="flex items-center gap-2.5">
          <div className="w-7 h-7 rounded-md bg-accent/10 border border-accent/30 flex items-center justify-center">
            <Zap size={14} className="text-accent" />
          </div>
          <div>
            <div className="text-sm font-display font-semibold text-slate-100 leading-none">HVAC Intel</div>
            <div className="text-xs text-slate-500 leading-none mt-0.5 font-mono">Deal Terminal</div>
          </div>
        </div>
      </div>

      {/* Nav */}
      <nav className="flex-1 px-2 py-3 space-y-0.5">
        {navItems.map(({ to, icon: Icon, label, exact }) => (
          <NavLink
            key={to}
            to={to}
            end={exact}
            className={({ isActive }) =>
              `nav-item ${isActive ? 'active' : ''}`
            }
          >
            <Icon size={15} />
            <span className="text-sm">{label}</span>
          </NavLink>
        ))}
      </nav>

      {/* Footer */}
      <div className="px-4 py-3 border-t border-surface-600">
        <div className="terminal-label text-[10px]">v2.0.0 — Deal Flow Engine</div>
        <div className="terminal-label text-[10px] mt-0.5 text-slate-600">
          Ctrl+K to search
        </div>
      </div>
    </aside>
  )
}
