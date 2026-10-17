import { Link } from 'react-router';
import { api } from '../api/client';
import { useApi } from '../lib/useApi';

const FEATURES = [
  {
    title: 'Adaptive question selection',
    body: 'Each question is chosen to be the most informative one for your current estimate, while rotating across the topics you picked.',
  },
  {
    title: 'Honest uncertainty',
    body: 'You get an ability estimate with a 95% interval, not a single number that hides how much the test actually knows.',
  },
  {
    title: 'Topic-level diagnosis',
    body: 'See where you are strong and where you lose points, with a warning when a topic has too few questions to judge.',
  },
  {
    title: 'Actionable study plan',
    body: 'Recommendations cite the exact questions you missed. An AI plan is used when available, with a rule-based plan as a fallback.',
  },
];

export function LandingPage() {
  const [topics] = useApi(api.topics, 'topics');
  const totalQuestions =
    topics.status === 'success' ? topics.data.reduce((n, t) => n + t.question_count, 0) : null;

  return (
    <div className="stack stack-lg">
      <section className="hero">
        <div>
          <span className="eyebrow">GRE quantitative and verbal diagnostic</span>
          <h1>Find out where your GRE preparation really stands.</h1>
          <p className="lead">
            A computerized adaptive test that adjusts to every answer. In 10 to 20 questions it estimates your
            ability, shows how certain that estimate is, and turns your mistakes into a focused study plan.
          </p>
          <div className="button-row">
            <Link to="/start" className="button button-primary button-large">
              Start a diagnostic
            </Link>
            <a href="#how-it-works" className="button button-ghost">
              How it works
            </a>
          </div>
        </div>
        <aside className="card hero-panel" aria-label="Assessment at a glance">
          <h2 style={{ fontSize: '1.2rem' }}>At a glance</h2>
          <div className="stat-row">
            <span className="muted">Length</span>
            <strong>10, 15 or 20 questions</strong>
          </div>
          <div className="stat-row">
            <span className="muted">Time limit</span>
            <strong>None</strong>
          </div>
          <div className="stat-row">
            <span className="muted">Topics</span>
            <strong>
              {topics.status === 'success' ? topics.data.map((t) => t.name).join(', ') : 'Loading...'}
            </strong>
          </div>
          <div className="stat-row">
            <span className="muted">Question bank</span>
            <strong>{totalQuestions === null ? 'Loading...' : `${totalQuestions} items`}</strong>
          </div>
          <div className="stat-row">
            <span className="muted">Account required</span>
            <strong>No</strong>
          </div>
        </aside>
      </section>

      <section aria-labelledby="features-heading">
        <h2 id="features-heading">What you get</h2>
        <div className="grid grid-features" style={{ marginTop: 16 }}>
          {FEATURES.map((feature) => (
            <article key={feature.title} className="card feature">
              <h3>{feature.title}</h3>
              <p>{feature.body}</p>
            </article>
          ))}
        </div>
      </section>

      <section
        id="how-it-works"
        aria-labelledby="how-heading"
        className="grid grid-2"
        style={{ alignItems: 'start' }}
      >
        <div>
          <h2 id="how-heading">How adaptive assessment works</h2>
          <ol className="steps stack" style={{ marginTop: 20 }}>
            <li>
              <strong>Start in the middle.</strong>
              <p className="muted">
                Everyone begins at an average ability estimate with wide uncertainty, so the first question is
                of medium difficulty.
              </p>
            </li>
            <li>
              <strong>Update after every answer.</strong>
              <p className="muted">
                A correct answer moves the estimate up, an incorrect one moves it down. Surprising answers
                move it more than expected ones, and the uncertainty narrows as evidence accumulates.
              </p>
            </li>
            <li>
              <strong>Ask the most useful next question.</strong>
              <p className="muted">
                The engine picks the item that best separates nearby ability levels, while balancing topics so
                each one is represented.
              </p>
            </li>
            <li>
              <strong>Stop when the answer is clear.</strong>
              <p className="muted">
                The test ends at your chosen length, or earlier once the estimate is precise enough.
              </p>
            </li>
          </ol>
        </div>
        <div className="card">
          <h3>The model behind it</h3>
          <p className="muted">
            Scoring uses the two-parameter logistic item response model. The chance of answering an item
            correctly depends on your ability &theta;, the item difficulty b, and how sharply the item
            discriminates, a:
          </p>
          <p
            className="formula"
            aria-label="P of correct equals 1 over 1 plus e to the minus a times theta minus b"
          >
            P(correct) = 1 / (1 + e<sup>&minus;a(&theta; &minus; b)</sup>)
          </p>
          <p className="muted">
            Your estimate is the posterior mean of &theta; given every answer, with a standard normal prior
            that keeps results sensible even after all-correct or all-incorrect runs.
          </p>
          <p className="small muted" style={{ marginBottom: 0 }}>
            Item parameters are provisional expert estimates, not calibrated on large response samples. Treat
            results as a diagnostic indication, not an official GRE score.
          </p>
        </div>
      </section>

      <section className="card" style={{ textAlign: 'center' }}>
        <h2>Ready to see where you stand?</h2>
        <p className="muted">It takes about 15 minutes. Your progress is saved if you need to step away.</p>
        <Link to="/start" className="button button-primary button-large">
          Choose topics and begin
        </Link>
      </section>
    </div>
  );
}
