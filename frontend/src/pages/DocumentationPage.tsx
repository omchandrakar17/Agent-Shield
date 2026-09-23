import { Link } from "react-router-dom";
import { PublicLayout } from "../components/PublicLayout";

const docs = [
  { title: "Getting Started", description: "Create an organization, sign in, and open the console.", href: "/register", status: "Available" },
  { title: "Architecture", description: "Agent → AgentShield Gateway → policy evaluation → tool or API → audit.", href: "/security", status: "Available" },
  { title: "How requests are evaluated", description: "Identity, permissions, schema, policy, risk, and human approval.", href: "/how-it-works", status: "Available" },
  { title: "Agents", description: "How AI agents are registered and scoped to tools.", href: "/how-it-works", status: "Available" },
  { title: "Tools", description: "How protected tools and APIs are registered.", href: "/how-it-works", status: "Available" },
  { title: "Policies", description: "How runtime authorization rules are configured.", href: "/security", status: "Available" },
  { title: "Human Approval", description: "How high-impact actions are paused until an authorized person approves the exact request.", href: "/how-it-works", status: "Available" },
  { title: "Audit Logs", description: "How security decisions and execution history are recorded.", href: "/how-it-works", status: "Available" },
];

export function DocumentationPage() {
  return (
    <PublicLayout>
      <section className="site-band page-hero">
        <div className="site-wrap">
          <p className="site-kicker">DOCUMENTATION</p>
          <h1>AgentShield Documentation</h1>
          <p className="lede">
            Understand the architecture, runtime workflow, and security controls that sit between an AI agent and a protected tool.
          </p>
        </div>
      </section>

      <section className="site-light">
        <div className="site-wrap site-cards two">
          {docs.map((doc) => (
            <article key={doc.title}>
              <div className="doc-row">
                <h3>{doc.title}</h3>
                <span>{doc.status}</span>
              </div>
              <p>{doc.description}</p>
              <Link to={doc.href}>Open</Link>
            </article>
          ))}
        </div>
      </section>
    </PublicLayout>
  );
}
