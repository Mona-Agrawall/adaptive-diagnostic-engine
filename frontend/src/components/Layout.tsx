import { NavLink, Outlet } from 'react-router';

export function BrandMark() {
  return (
    <svg className="brand-mark" viewBox="0 0 32 32" aria-hidden="true">
      <rect width="32" height="32" rx="8" fill="var(--primary)" />
      <path
        d="M7 22 L13 15 L18 18 L25 9"
        fill="none"
        stroke="var(--on-primary)"
        strokeWidth="2.6"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <circle cx="25" cy="9" r="2.4" fill="#f5b544" />
    </svg>
  );
}

export function Layout() {
  return (
    <>
      <a className="skip-link" href="#main">
        Skip to content
      </a>
      <header className="site-header">
        <div className="container">
          <NavLink to="/" className="brand" aria-label="Adaptive Diagnostic Engine home">
            <BrandMark />
            <span className="brand-text">Adaptive Diagnostic</span>
          </NavLink>
          <nav className="nav" aria-label="Primary">
            <NavLink to="/start">Start</NavLink>
            <NavLink to="/history">History</NavLink>
          </nav>
        </div>
      </header>
      <main id="main" tabIndex={-1}>
        <div className="container">
          <Outlet />
        </div>
      </main>
      <footer className="site-footer">
        <div className="container">
          <span>Adaptive Diagnostic Engine. Estimates are diagnostic, not official GRE scores.</span>
          <a href="/docs">API documentation</a>
        </div>
      </footer>
    </>
  );
}
