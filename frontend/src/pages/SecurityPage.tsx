import { PublicLayout } from "../components/PublicLayout";

const controls = [
  { title: "Runtime Authorization", text: "Every protected tool request is evaluated before execution." },
  { title: "Least-Privilege Access", text: "Agents receive access only to permitted tools and actions." },
  { title: "Policy Enforcement", text: "Server-side policies determine whether an action can proceed." },
  { title: "Human Approval", text: "Sensitive actions can require explicit human authorization." },
  { title: "RBAC", text: "Users receive permissions according to their assigned organizational role." },
  { title: "Tenant Isolation", text: "Organizations and their resources are isolated at the backend level." },
  { title: "Auditability", text: "Security decisions and executions are persistently recorded." },
  { title: "Kill Switch", text: "Authorized administrators can disable protected activity during incidents." },
  { title: "Input Validation", text: "Tool arguments are validated before execution." },
];

export function SecurityPage() {
  return (
    <PublicLayout>
      <section className="site-band page-hero">
        <div className="site-wrap">
          <p className="site-kicker">SECURITY MODEL</p>
          <h1>Security Controls for AI-Driven Operations</h1>
          <p className="lede">
            AgentShield adds an independent control layer between AI decision-making and real-world execution.
          </p>
        </div>
      </section>

      <section className="site-band architecture">
        <div className="site-wrap">
          <div className="arch">
            <div>AI Agent</div>
            <span>↓</span>
            <div className="core">AgentShield Runtime Gateway</div>
            <span>↓</span>
            <div className="arch-row">
              <em>Identity</em><em>Permission</em><em>Validation</em><em>Policy</em><em>Risk</em><em>Approval</em>
            </div>
            <span>↓</span>
            <div>Decision · ALLOW / REQUIRE APPROVAL / BLOCK</div>
            <span>↓</span>
            <div>Protected Tools &amp; APIs</div>
            <span>↓</span>
            <div>Audit / Trace / Events</div>
          </div>
          <p className="arch-note">
            AgentShield does not assume the model will safely decide when a tool call is permitted.
            Protected actions are evaluated by a server-side security layer using identity, permission scopes,
            validation, policy rules, and risk checks.
          </p>
        </div>
      </section>

      <section className="site-light">
        <div className="site-wrap site-cards three">
          {controls.map((item) => (
            <article key={item.title}>
              <h3>{item.title}</h3>
              <p>{item.text}</p>
            </article>
          ))}
        </div>
      </section>
    </PublicLayout>
  );
}
