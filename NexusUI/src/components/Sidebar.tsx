import { useState } from 'react';
import { NavLink, useNavigate } from 'react-router';
import {
  Search, FileText, Layers, Brain, BarChart2, GitBranch,
  FlaskConical, Settings, ChevronLeft, ChevronRight,
  Zap, ChevronsUpDown, User, Plus
} from 'lucide-react';

const NAV = [
  { label: 'Research', to: '/', icon: Brain, exact: true },
  { label: 'Sources', to: '/sources', icon: FileText },
  { label: 'Research Runs', to: '/jobs', icon: Zap },
  { label: 'Evidence', to: '/evidence', icon: Search },
  { label: 'Reports', to: '/reports', icon: Layers },
  { label: 'Research Graph', to: '/graph', icon: GitBranch },
  { label: 'Evaluation', to: '/evaluation', icon: FlaskConical },
];

const BOTTOM = [
  { label: 'Settings', to: '/settings', icon: Settings },
];

export default function Sidebar({ onCmd }: { onCmd: () => void }) {
  const [collapsed, setCollapsed] = useState(false);
  const navigate = useNavigate();

  return (
    <aside
      style={{
        width: collapsed ? 56 : 224,
        transition: 'width 220ms cubic-bezier(0.4,0,0.2,1)',
        background: '#111116',
        borderRight: '1px solid #1e1e26',
        display: 'flex',
        flexDirection: 'column',
        flexShrink: 0,
        overflow: 'hidden',
      }}
    >
      {/* Logo */}
      <div style={{
        padding: collapsed ? '18px 0' : '18px 16px',
        borderBottom: '1px solid #1e1e26',
        display: 'flex',
        alignItems: 'center',
        gap: 10,
        justifyContent: collapsed ? 'center' : 'flex-start',
        flexShrink: 0,
      }}>
        <div style={{
          width: 24, height: 24, borderRadius: 5,
          background: 'linear-gradient(135deg, #3b9eff 0%, #7c5af0 100%)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          flexShrink: 0,
        }}>
          <span style={{ color: '#fff', fontSize: 11, fontWeight: 700, letterSpacing: -0.5 }}>N</span>
        </div>
        {!collapsed && (
          <div>
            <div style={{ fontWeight: 700, fontSize: 13.5, letterSpacing: -0.3, color: '#f0ede8', lineHeight: 1 }}>
              NEXUS
            </div>
            <div style={{ fontSize: 10, color: '#55535d', letterSpacing: 0.3, marginTop: 2 }}>
              Agentic Research Engine
            </div>
          </div>
        )}
      </div>

      {/* Workspace switcher */}
      {!collapsed && (
        <div style={{ padding: '8px 10px', borderBottom: '1px solid #1e1e26', flexShrink: 0 }}>
          <button style={{
            width: '100%', padding: '6px 8px',
            background: '#1e1e27', border: '1px solid #2c2c3a',
            borderRadius: 5, cursor: 'pointer',
            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
            color: '#f0ede8',
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
              <div style={{
                width: 16, height: 16, borderRadius: 3,
                background: '#3b9eff22', border: '1px solid #3b9eff44',
                fontSize: 9, color: '#3b9eff', display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 700,
              }}>R</div>
              <span style={{ fontSize: 12, fontWeight: 500 }}>Research Lab</span>
            </div>
            <ChevronsUpDown size={12} color="#55535d" />
          </button>
        </div>
      )}

      {/* Navigation */}
      <nav style={{ flex: 1, padding: '8px 0', overflowY: 'auto' }}>
        {/* New research shortcut */}
        <div style={{ padding: collapsed ? '4px 8px' : '4px 10px', marginBottom: 4 }}>
          <button
            onClick={() => navigate('/')}
            style={{
              width: '100%', padding: collapsed ? '7px' : '7px 10px',
              background: 'linear-gradient(135deg, rgba(59,158,255,0.12) 0%, rgba(124,90,240,0.06) 100%)',
              border: '1px solid rgba(59,158,255,0.2)',
              borderRadius: 6, cursor: 'pointer',
              display: 'flex', alignItems: 'center', justifyContent: collapsed ? 'center' : 'flex-start',
              gap: 7, color: '#3b9eff',
            }}
          >
            <Plus size={13} />
            {!collapsed && <span style={{ fontSize: 12, fontWeight: 600 }}>New Research</span>}
          </button>
        </div>

        {/* Cmd palette */}
        {!collapsed && (
          <div style={{ padding: '4px 10px', marginBottom: 4 }}>
            <button
              onClick={onCmd}
              style={{
                width: '100%', padding: '6px 10px',
                background: '#1e1e27', border: '1px solid #1e1e26',
                borderRadius: 5, cursor: 'pointer',
                display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                color: '#55535d',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <Search size={11} />
                <span style={{ fontSize: 11.5 }}>Search or run command</span>
              </div>
              <span style={{
                fontSize: 9.5, fontFamily: 'var(--font-mono, monospace)',
                background: '#2c2c3a', padding: '2px 5px', borderRadius: 3,
                color: '#55535d', border: '1px solid #1e1e26',
              }}>⌘K</span>
            </button>
          </div>
        )}

        <div style={{ height: 4 }} />

        {NAV.map(({ label, to, icon: Icon, exact }) => (
          <NavLink
            key={to}
            to={to}
            end={exact}
            style={({ isActive }) => ({
              display: 'flex', alignItems: 'center',
              gap: 9, padding: collapsed ? '8px 16px' : '7px 18px',
              margin: '1px 0', cursor: 'pointer', textDecoration: 'none',
              justifyContent: collapsed ? 'center' : 'flex-start',
              borderRadius: 0,
              background: isActive ? 'rgba(59,158,255,0.08)' : 'transparent',
              color: isActive ? '#3b9eff' : '#8b8897',
              borderLeft: isActive ? '2px solid #3b9eff' : '2px solid transparent',
              transition: 'all 120ms ease',
            })}
          >
            {({ isActive }) => (
              <>
                <Icon size={15} style={{ flexShrink: 0 }} color={isActive ? '#3b9eff' : '#55535d'} />
                {!collapsed && (
                  <span style={{ fontSize: 13, fontWeight: isActive ? 500 : 400 }}>{label}</span>
                )}
              </>
            )}
          </NavLink>
        ))}
      </nav>

      {/* Bottom */}
      <div style={{ borderTop: '1px solid #1e1e26', flexShrink: 0 }}>
        {BOTTOM.map(({ label, to, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            style={({ isActive }) => ({
              display: 'flex', alignItems: 'center',
              gap: 9, padding: collapsed ? '10px 16px' : '10px 18px',
              cursor: 'pointer', textDecoration: 'none',
              justifyContent: collapsed ? 'center' : 'flex-start',
              color: isActive ? '#3b9eff' : '#55535d',
            })}
          >
            {({ isActive }) => (
              <>
                <Icon size={14} color={isActive ? '#3b9eff' : '#55535d'} />
                {!collapsed && <span style={{ fontSize: 13 }}>{label}</span>}
              </>
            )}
          </NavLink>
        ))}

        {/* User + collapse */}
        <div style={{
          display: 'flex', alignItems: 'center',
          padding: collapsed ? '10px 16px' : '10px 14px',
          justifyContent: collapsed ? 'center' : 'space-between',
        }}>
          {!collapsed && (
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <div style={{
                width: 24, height: 24, borderRadius: '50%',
                background: '#252533', border: '1px solid #2c2c3a',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
              }}>
                <User size={12} color="#8b8897" />
              </div>
              <div>
                <div style={{ fontSize: 12, fontWeight: 500, color: '#f0ede8', lineHeight: 1.2 }}>A. Researcher</div>
                <div style={{ fontSize: 10, color: '#55535d' }}>researcher@lab.ai</div>
              </div>
            </div>
          )}
          <button
            onClick={() => setCollapsed(!collapsed)}
            style={{
              background: 'none', border: 'none', cursor: 'pointer',
              padding: 4, borderRadius: 4, color: '#55535d',
              display: 'flex', alignItems: 'center',
            }}
          >
            {collapsed ? <ChevronRight size={14} /> : <ChevronLeft size={14} />}
          </button>
        </div>
      </div>
    </aside>
  );
}
