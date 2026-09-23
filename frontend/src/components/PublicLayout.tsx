import { useState, type ReactNode } from "react";
import { Link, NavLink } from "react-router-dom";
import { ShieldIcon } from "./icons";

export function PublicLayout({ children }: { children: ReactNode }) {
  const [menuOpen, setMenuOpen] = useState(false);

  return (
    <div className="site">
      <header className="site-header">
        <Link to="/" className="site-brand" onClick={() => setMenuOpen(false)}>
          <span className="site-logo"><ShieldIcon size={18} /></span>
          <strong>AgentShield</strong>
        </Link>

        <button
          type="button"
          className="site-menu-btn"
          aria-expanded={menuOpen}
          aria-controls="site-nav"
          onClick={() => setMenuOpen((open) => !open)}
        >
          {menuOpen ? "Close" : "Menu"}
        </button>

        <nav id="site-nav" className={menuOpen ? "site-nav open" : "site-nav"} aria-label="Main navigation">
          <NavLink to="/" end onClick={() => setMenuOpen(false)}>Home</NavLink>
          <NavLink to="/how-it-works" onClick={() => setMenuOpen(false)}>How It Works</NavLink>
          <NavLink to="/security" onClick={() => setMenuOpen(false)}>Security</NavLink>
          <NavLink to="/docs" onClick={() => setMenuOpen(false)}>Documentation</NavLink>
        </nav>

        <div className="site-actions">
          <Link to="/login" className="site-signin" onClick={() => setMenuOpen(false)}>Sign In</Link>
          <Link to="/register" className="btn-primary site-cta" onClick={() => setMenuOpen(false)}>Get Started</Link>
        </div>
      </header>

      <main>{children}</main>

      <footer className="site-footer">
        <div className="site-wrap site-footer-grid">
          <div>
            <strong>AgentShield</strong>
            <p>Runtime security and authorization for AI agents.</p>
          </div>
          <div>
            <span>Product</span>
            <Link to="/">Home</Link>
            <Link to="/how-it-works">How It Works</Link>
            <Link to="/security">Security</Link>
            <Link to="/docs">Documentation</Link>
          </div>
          <div>
            <span>Account</span>
            <Link to="/login">Sign In</Link>
            <Link to="/register">Get Started</Link>
          </div>
          <div>
            <span>Resources</span>
            <Link to="/docs">Documentation</Link>
            <Link to="/security">Architecture</Link>
          </div>
        </div>
        <div className="site-wrap site-footer-bottom">
          © 2026 AgentShield · AI Agent Runtime Security Platform
        </div>
      </footer>
    </div>
  );
}
