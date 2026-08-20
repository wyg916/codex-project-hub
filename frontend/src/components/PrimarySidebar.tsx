import { Link, useLocation } from 'react-router-dom'

const items = [
  { to: '/', icon: '⌂', label: '项目总览' },
  { to: '#topology', icon: '⌘', label: '动态拓扑' },
  { to: '#branches', icon: '⑂', label: '分支列表' },
  { to: '#worktrees', icon: '▱', label: '工作树' },
  { to: '#tests', icon: '✓', label: '测试报告' },
  { to: '#alerts', icon: '△', label: '异常监控' },
]

export function PrimarySidebar() {
  const location = useLocation()
  return (
    <nav className="primary-sidebar" aria-label="主导航">
      <Link className="brand-mark" to="/" aria-label="Codex Project Hub">C</Link>
      <div className="nav-items">
        {items.map((item) => {
          const content = <><span className="nav-icon">{item.icon}</span><span>{item.label}</span></>
          return item.to.startsWith('#') ? (
            <a key={item.label} className="nav-item" href={item.to}>{content}</a>
          ) : (
            <Link key={item.label} className={`nav-item ${location.pathname === '/' ? 'active' : ''}`} to={item.to}>{content}</Link>
          )
        })}
      </div>
      <div className="nav-footer"><span className="nav-icon">⚙</span><span>设置</span></div>
    </nav>
  )
}
