import { Link } from "react-router-dom";
import { PublicLayout } from "../components/PublicLayout";

const flow = [
  { title: "AI agent requests a tool", text: "The agent proposes a protected action such as a refund, update, or deletion." },
  { title: "AgentShield intercepts the request", text: "The call never reaches the real tool until the gateway finishes evaluation." },
  { title: "Identity and validation", text: "The agent is authenticated and the tool arguments are checked against the expected schema." },
  { title: "Permissions, policy, and risk", text: "Scopes, organization rules, and risk thresholds decide whether the action can proceed." },
  { title: "Decision", text: "The gateway returns ALLOW, REQUIRE APPROVAL, or BLOCK." },
  { title: "Execution and audit", text: "Only an allowed or approved request executes. The decision and result are recorded." },
];

export function HowItWorksPage() {
  return (
    <PublicLayout>
      <section className="site-band page-hero">
        <div className="site-wrap">
          <p className="site-kicker">HOW IT WORKS</p>
          <h1>How AgentShield Controls AI Actions</h1>
          <p className="lede">
            AI agents request tools and protected actions. AgentShield intercepts those requests,
            validates the context, and enforces the authorization decision before execution.
          </p>
        </div>
      </section>

      <section className="site-light">
        <div className="site-wrap site-steps vertical">
          {flow.map((step, index) => (
            <div key={step.title} className="site-step">
              <article>
                <span>{String(index + 1).padStart(2, "0")}</span>
                <h3>{step.title}</h3>
                <p>{step.text}</p>
              </article>
              {index < flow.length - 1 ? <div className="site-step-arrow" aria-hidden="true">↓</div> : null}
            </div>
          ))}
        </div>
      </section>

      <section className="site-light alt">
        <div className="site-wrap site-examples">
          <article className="site-example">
            <h3>Possible decisions</h3>
            <p><strong className="ok">ALLOW</strong> — the protected tool can execute.</p>
            <p><strong>REQUIRE APPROVAL</strong> — the action pauses until an authorized person approves the exact request.</p>
            <p><strong className="block">BLOCK</strong> — the protected tool is not executed.</p>
            <Link to="/security" className="text-link">Review the security model</Link>
          </article>
          <article className="site-example">
            <h3>Unauthorized action</h3>
            <ol className="after">
              <li>The agent requests a forbidden or out-of-scope tool</li>
              <li>The permission check fails</li>
              <li>Decision: BLOCK</li>
              <li>The real tool is not executed</li>
              <li>A security event is recorded</li>
            </ol>
          </article>
        </div>
      </section>
    </PublicLayout>
  );
}
