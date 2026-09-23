import { Link } from "react-router-dom";
import { PublicLayout } from "../components/PublicLayout";
import { ArrowRightIcon, BotIcon, BookIcon, DatabaseIcon, ShieldIcon } from "../components/icons";

const capabilities = [
  {
    title: "Runtime Authorization",
    text: "Verify agent identity, tool permissions and parameters before protected actions execute.",
    href: "/security",
  },
  {
    title: "Policy Engine",
    text: "Enforce deterministic organization policies, permissions and risk controls.",
    href: "/security",
  },
  {
    title: "Human Approval",
    text: "Pause high-impact actions until an authorized person approves the exact request.",
    href: "/how-it-works",
  },
  {
    title: "Audit & Trace",
    text: "Record decisions, tool calls, approvals and execution results in an auditable trail.",
    href: "/docs",
  },
];

const workflow = [
  { n: "01", title: "AI Agent", text: "The agent plans an action and requests a tool." },
  { n: "02", title: "AgentShield Gateway", text: "The request is intercepted before reaching the real tool." },
  { n: "03", title: "Security Evaluation", text: "Identity, permissions, schema, policy, risk, and execution limits." },
  { n: "04", title: "Decision", text: "ALLOW, REQUIRE APPROVAL, or BLOCK." },
  { n: "05", title: "Tool / API", text: "Only an authorized request reaches the protected system." },
  { n: "06", title: "Audit Trail", text: "The decision and execution are recorded." },
];

const production = [
  { title: "Authentication", text: "Secure agent and user identity" },
  { title: "RBAC", text: "Role-based access control" },
  { title: "Tenant Isolation", text: "Organization-level data separation" },
  { title: "Policy Enforcement", text: "Deterministic server-side rules" },
  { title: "Auditability", text: "Persistent execution history" },
  { title: "Cloud Deployment", text: "Designed for scalable cloud deployment" },
];

const checks = ["Identity Check", "Permission Check", "Policy Check", "Risk Check", "Approval"];
const evalRows = [
  ["Agent identity", "ok"],
  ["Tool permission", "ok"],
  ["Schema validation", "ok"],
  ["Refund policy", "warn"],
  ["Risk threshold", "warn"],
] as const;

export function LandingPage() {
  return (
    <PublicLayout>
      <section className="site-band">
        <div className="site-wrap site-hero">
          <div className="site-hero-copy">
            <p className="site-kicker">AI AGENT SECURITY PLATFORM</p>
            <h1>Control What Your <span>AI Agents</span> Can Do.</h1>
            <p>
              AgentShield acts as a runtime security gateway between AI agents and the tools they use,
              enforcing identity, permissions, policies, validation and human approval before protected actions execute.
            </p>
            <div className="site-hero-actions">
              <Link to="/register" className="btn-primary site-btn">Get Started <ArrowRightIcon /></Link>
              <Link to="/docs" className="site-btn-ghost"><BookIcon size={16} /> View Documentation</Link>
            </div>
          </div>

          <div className="site-product">
            <div className="site-flow">
              <div className="site-flow-node">
                <BotIcon size={18} />
                <strong>AI Agent</strong>
                <span>Plans a tool action</span>
              </div>
              <div className="site-flow-line" aria-hidden="true" />
              <div className="site-flow-node gateway">
                <ShieldIcon size={18} />
                <strong>AgentShield Runtime Gateway</strong>
                <span>Validates · Enforces · Logs</span>
                <div className="site-checks">
                  {checks.map((item) => <em key={item}>{item}</em>)}
                </div>
              </div>
              <div className="site-flow-line" aria-hidden="true" />
              <div className="site-flow-node">
                <DatabaseIcon size={18} />
                <strong>Tools &amp; APIs</strong>
                <span>Protected systems</span>
              </div>
            </div>
            <div className="site-decisions">
              <span className="pill allow">✓ ALLOW</span>
              <span className="pill approval">◷ REQUIRE APPROVAL</span>
              <span className="pill block">⊗ BLOCK</span>
            </div>

            <div className="site-console" aria-label="AgentShield execution console">
              <aside>
                <strong>AgentShield</strong>
                <span className="on">Overview</span>
                <span>Agents</span>
                <span>Policies</span>
                <span>Approvals</span>
                <span>Audit</span>
              </aside>
              <div>
                <p className="site-console-title">Execution Trace</p>
                <ol>
                  <li>User Request<small>Refund order #2481</small></li>
                  <li>Agent Plan<small>issue_refund</small></li>
                  <li className="warn">Policy Check<small>Requires approval</small></li>
                  <li className="warn">Human Approval<small>Pending</small></li>
                  <li className="muted">Tool Execution<small>Not executed</small></li>
                </ol>
              </div>
              <div className="site-decision-card">
                <strong>Decision</strong>
                <b>REQUIRES APPROVAL</b>
                <p>Tool <code>issue_refund</code></p>
                <p>Amount <strong>₹25,000</strong></p>
                <p>Risk <em>HIGH</em></p>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section className="site-light">
        <div className="site-wrap">
          <div className="site-head">
            <p className="site-kicker dark">RUNTIME CONTROLS</p>
            <h2>Security Controls at Runtime</h2>
          </div>
          <div className="site-cards four">
            {capabilities.map((item) => (
              <article key={item.title}>
                <span className="site-icon"><ShieldIcon size={18} /></span>
                <h3>{item.title}</h3>
                <p>{item.text}</p>
                <Link to={item.href}>Learn more <ArrowRightIcon /></Link>
              </article>
            ))}
          </div>
        </div>
      </section>

      <section className="site-light alt">
        <div className="site-wrap">
          <div className="site-head">
            <p className="site-kicker dark">WORKFLOW</p>
            <h2>From AI Decision to Controlled Execution</h2>
          </div>
          <div className="site-steps">
            {workflow.map((step, index) => (
              <div key={step.n} className="site-step">
                <article>
                  <span>{step.n}</span>
                  <h3>{step.title}</h3>
                  <p>{step.text}</p>
                </article>
                {index < workflow.length - 1 ? <div className="site-step-arrow" aria-hidden="true">↓</div> : null}
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="site-light">
        <div className="site-wrap">
          <div className="site-head">
            <p className="site-kicker dark">EXAMPLE</p>
            <h2>See AgentShield in Action</h2>
          </div>
          <div className="site-examples">
            <article className="site-example">
              <h3>High-value refund</h3>
              <p className="quote">“Refund ₹25,000 for order #2481.”</p>
              <pre>{`issue_refund(
  order_id: 2481,
  amount: 25000
)`}</pre>
              <ul>
                {evalRows.map(([label, tone]) => (
                  <li key={label}><span>{label}</span><b className={tone}>{tone === "ok" ? "✓" : "⚠"}</b></li>
                ))}
              </ul>
              <p className="decision-line">Decision: <strong>REQUIRE HUMAN APPROVAL</strong></p>
              <ol className="after">
                <li>Authorized reviewer</li>
                <li>Approves exact request</li>
                <li>Tool executes</li>
                <li>Result recorded</li>
                <li>Audit event created</li>
              </ol>
            </article>
            <article className="site-example compact">
              <h3>Unauthorized tool request</h3>
              <ol className="after">
                <li>Agent requests a tool outside its permission scope</li>
                <li>Permission denied</li>
                <li>Tool is not executed</li>
                <li>Security event recorded</li>
              </ol>
              <p className="decision-line">Decision: <strong className="block">BLOCK</strong></p>
            </article>
          </div>
        </div>
      </section>

      <section className="site-band architecture">
        <div className="site-wrap">
          <div className="site-head light">
            <p className="site-kicker">ARCHITECTURE</p>
            <h2>An Independent Security Layer for AI Agents</h2>
          </div>
          <div className="arch">
            <div>AI Agent</div>
            <span>↓</span>
            <div className="core">AgentShield Runtime Gateway</div>
            <span>↓</span>
            <div className="arch-row">
              <em>Identity</em><em>Permission</em><em>Validation</em><em>Policy</em><em>Risk</em><em>Approval</em>
            </div>
            <span>↓</span>
            <div>Decision</div>
            <span>↓</span>
            <div>Protected Tools &amp; APIs</div>
            <span>↓</span>
            <div>Audit / Trace / Events</div>
          </div>
          <p className="arch-note">
            AgentShield does not rely on the AI model itself to authorize sensitive actions.
            Protected actions are evaluated by server-side security controls before execution.
          </p>
        </div>
      </section>

      <section className="site-light alt">
        <div className="site-wrap">
          <div className="site-head">
            <p className="site-kicker dark">PRODUCTION</p>
            <h2>Built for Production AI Operations</h2>
          </div>
          <div className="site-cards six">
            {production.map((item) => (
              <article key={item.title}>
                <h3>{item.title}</h3>
                <p>{item.text}</p>
              </article>
            ))}
          </div>
        </div>
      </section>

      <section className="site-band cta">
        <div className="site-wrap site-cta-block">
          <h2>Secure AI Actions Before They Reach the Real World.</h2>
          <p>Give AI agents the ability to act without giving them unrestricted authority.</p>
          <div className="site-hero-actions">
            <Link to="/register" className="btn-primary site-btn">Get Started <ArrowRightIcon /></Link>
            <Link to="/docs" className="site-btn-ghost">View Documentation</Link>
          </div>
        </div>
      </section>
    </PublicLayout>
  );
}
