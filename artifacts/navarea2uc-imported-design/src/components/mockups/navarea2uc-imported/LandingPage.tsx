import './LandingPage.css';

export function LandingPage() {
  return (
    <main className="navarea2uc-landing">
      <div className="navarea2uc-container">
        <a
          href="https://github.com/drlivsi2004/NAVAREA2UC"
          target="_blank"
          rel="noopener noreferrer"
        >
          <img
            src="/__mockup/images/logo.png"
            alt="NAVAREA2UC"
            className="navarea2uc-logo"
          />
        </a>

        <h1>NAVAREA2UC</h1>

        <div className="navarea2uc-tagline">
          From Maritime Notices to User Charts
        </div>

        <div className="navarea2uc-version-label">Current Stable Release</div>
        <div className="navarea2uc-version">v1.2.1</div>

        <div className="navarea2uc-buttons">
          <a
            href="https://github.com/drlivsi2004/NAVAREA2UC/releases/download/v1.2.1/NAVAREA2UC_v1.2.1.exe"
            target="_blank"
            rel="noopener noreferrer"
            className="navarea2uc-btn navarea2uc-btn-download"
          >
            Download
          </a>
          <a
            href="https://github.com/drlivsi2004/NAVAREA2UC/releases/tag/v1.2.1"
            target="_blank"
            rel="noopener noreferrer"
            className="navarea2uc-btn navarea2uc-btn-github"
          >
            GitHub
          </a>
        </div>

        <div className="navarea2uc-divider" />

        <div className="navarea2uc-coming">COMING SOON</div>
        <div className="navarea2uc-next">v1.3.0</div>

        <div className="navarea2uc-features">
          Document Classification Layer
          <br />
          T&amp;P Pipeline
          <br />
          AIO Support
          <br />
          Pre-Arrival Information
        </div>

        <div className="navarea2uc-vision">
          Any Source.
          <br />
          Any Format.
          <br />
          Any ECDIS.
        </div>

        <div className="navarea2uc-footer">NAVAREA2UC © 2026</div>
      </div>
    </main>
  );
}