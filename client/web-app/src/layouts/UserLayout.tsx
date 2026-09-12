import { Outlet, Link } from 'react-router-dom'

export default function UserLayout() {
  return (
    <div className="user-layout">
      <header className="user-header">
        <Link to="/">SocialMind AI</Link>
      </header>
      <main>
        <Outlet />
      </main>
    </div>
  )
}
