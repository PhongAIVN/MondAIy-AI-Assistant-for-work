import { Outlet, Link } from 'react-router-dom'

export default function AdminLayout() {
  return (
    <div className="admin-layout">
      <aside className="admin-sidebar">
        <Link to="/admin">Dashboard</Link>
        <Link to="/admin/users">Users</Link>
      </aside>
      <main className="admin-content">
        <Outlet />
      </main>
    </div>
  )
}
