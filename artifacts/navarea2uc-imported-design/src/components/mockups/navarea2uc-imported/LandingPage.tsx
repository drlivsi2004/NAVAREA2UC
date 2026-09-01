import './LandingPage.css';
import { useEffect, useState, type CSSProperties } from 'react';
import {
  ArrowRight,
  CircleDot,
  Download,
  Layers3,
  Maximize2,
  Menu,
  Printer,
  Route,
  ShieldCheck,
  Table2,
  X,
} from 'lucide-react';

type EcdisPreview = {
  title: string;
  mode: string;
  src: string;
  alt: string;
};

export function LandingPage() {
  const [menuOpen, setMenuOpen] = useState(false);
  const [selectedPreview, setSelectedPreview] = useState<EcdisPreview | null>(null);
  const assetBase = import.meta.env.BASE_URL;
  const bannerPath = `${assetBase}images/site-banner-uploaded-master-4k.png`;
  const quickReferencePdfPath = `${assetBase}NAVAREA2UC-ECDIS-Quick-Reference.pdf`;
  const ecdisPreviews: EcdisPreview[] = [
    {
      title: 'Export case 01',
      mode: 'Furuno ECDIS',
      src: `${assetBase}images/ecdis-exports/ecdis-export-overview.png`,
      alt: 'Furuno ECDIS export case 01 with a dense NAV overlay and multiple UserChart objects',
    },
    {
      title: 'Export case 02',
      mode: 'Furuno ECDIS',
      src: `${assetBase}images/ecdis-exports/ecdis-export-black-sea.png`,
      alt: 'Furuno ECDIS export case 02 showing NAV and UserChart overlays',
    },
    {
      title: 'Export case 03',
      mode: 'Furuno ECDIS',
      src: `${assetBase}images/ecdis-exports/ecdis-export-coastal-approach.png`,
      alt: 'Furuno ECDIS export case 03 showing detailed ENC data and NAV objects',
    },
  ];
  const exportLogicRows = [
    {
      element: 'i',
      name: 'Information / status notice',
      colorName: 'Orange',
      status: 'Warning',
      mark: 'information',
      colorTone: 'orange',
      statusTone: 'warning',
      meaning: 'Light unlit, reported depths, moorings, communication or service notices.',
    },
    {
      element: 'i',
      name: 'Drifting hazard',
      colorName: 'Red',
      status: 'Danger',
      mark: 'drifting',
      colorTone: 'red',
      statusTone: 'danger',
      meaning: 'Drifting objects or hazards, shown with the separate (i) symbol.',
    },
    {
      element: 'i',
      name: 'Offshore activity / deployment',
      colorName: 'Blue',
      status: 'Non-danger',
      mark: 'offshore',
      colorTone: 'blue',
      statusTone: 'non-danger',
      meaning: 'An offshore operation or deployment notice shown as an information symbol.',
    },
    {
      element: 'triangle',
      name: 'Active / established navigation buoy',
      colorName: 'Yellow',
      status: 'Non-danger',
      mark: 'buoy',
      colorTone: 'yellow',
      statusTone: 'non-danger',
      meaning: 'An active, established navigation buoy or other aid at one position.',
    },
    {
      element: 'triangle',
      name: 'Degraded / missing navigation aid',
      colorName: 'Orange',
      status: 'Warning',
      mark: 'degraded',
      colorTone: 'orange',
      statusTone: 'warning',
      meaning: 'A navigation aid reported degraded, missing, unlit or otherwise changed from its established state.',
    },
    {
      element: 'triangle',
      name: 'Isolated danger buoy',
      colorName: 'Red',
      status: 'Danger',
      mark: 'isolated-danger',
      colorTone: 'red',
      statusTone: 'danger',
      meaning: 'A red isolated-danger mark at a hazard position.',
    },
    {
      element: 'diamond',
      name: 'Offshore structure',
      colorName: 'Blue',
      status: 'Non-danger',
      mark: 'platform',
      colorTone: 'blue',
      statusTone: 'non-danger',
      meaning: 'FPSO, FSO, MODU, offshore rig, platform or drillship.',
    },
    {
      element: 'diamond',
      name: 'Pilot station',
      colorName: 'Magenta',
      status: 'Non-danger',
      mark: 'pilot',
      colorTone: 'magenta',
      statusTone: 'non-danger',
      meaning: 'A pilot station shown with a magenta diamond.',
    },
    {
      element: 'diamond',
      name: 'Security incident',
      colorName: 'Red',
      status: 'Danger',
      mark: 'security',
      colorTone: 'red',
      statusTone: 'danger',
      meaning: 'Piracy, armed robbery or another security incident at a reported position.',
    },
    {
      element: 'point',
      name: 'Danger point',
      colorName: 'Red',
      status: 'Danger',
      mark: 'danger',
      colorTone: 'red',
      statusTone: 'danger',
      meaning: 'Wreck, obstruction, aground vessel, derelict, submerged object or iceberg marker.',
    },
    {
      element: 'Line',
      name: 'Navigation or operational line',
      colorName: 'Orange',
      status: 'Warning',
      mark: 'line',
      colorTone: 'orange',
      statusTone: 'warning',
      meaning: 'Recommended route, trackline, cable, pipeline, channel or survey line.',
    },
    {
      element: 'Line',
      name: 'Danger line',
      colorName: 'Red',
      status: 'Danger',
      mark: 'iceberg',
      colorTone: 'red',
      statusTone: 'danger',
      meaning: 'An iceberg danger trackline or another explicitly dangerous operational line.',
    },
    {
      element: 'Area',
      name: 'Non-danger area',
      colorName: 'Orange',
      status: 'Warning',
      mark: 'area',
      colorTone: 'orange',
      statusTone: 'warning',
      meaning: 'Survey, work, anchorage, waiting, holding, temporary-stay or no-anchoring area.',
    },
    {
      element: 'Area',
      name: 'Danger area',
      colorName: 'Red',
      status: 'Danger',
      mark: 'firing',
      colorTone: 'red',
      statusTone: 'danger',
      meaning: 'War-risk, mine-danger, firing, military, prohibited, exclusion or other hazard area.',
    },
    {
      element: 'Circle',
      name: 'Scientific / survey radius',
      colorName: 'Orange',
      status: 'Warning',
      mark: 'survey-circle',
      colorTone: 'orange',
      statusTone: 'warning',
      meaning: 'Scientific or survey activity with a published centre and distance.',
    },
    {
      element: 'Circle',
      name: 'Radius warning',
      colorName: 'Red',
      status: 'Danger',
      mark: 'circle',
      colorTone: 'red',
      statusTone: 'danger',
      meaning: 'A warning, rocket-launch or explosives radius with a published center and distance.',
    },
  ];

  function closeMenu() {
    setMenuOpen(false);
  }

  useEffect(() => {
    if (!selectedPreview) return;

    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setSelectedPreview(null);
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => {
      document.body.style.overflow = previousOverflow;
      window.removeEventListener('keydown', handleKeyDown);
    };
  }, [selectedPreview]);

  return (
    <main className="navarea2uc-landing">
      <div className="navarea2uc-container" id="top">
        <section
          className="navarea2uc-hero"
          aria-labelledby="hero-title"
          style={
            {
              '--navarea2uc-banner-texture': `url("${bannerPath}")`,
            } as CSSProperties
          }
        >
          <div className="navarea2uc-hero-banner">
            <img
              src={bannerPath}
              srcSet={`${bannerPath} 4096w`}
              sizes="(max-width: 1200px) 100vw, 1180px"
              alt="NAVAREA2UC chart view with routes, navigation marks and safety areas"
            />
            <header className="navarea2uc-banner-header">
              <button
                className="navarea2uc-menu-toggle"
                type="button"
                aria-label={menuOpen ? 'Close navigation menu' : 'Open navigation menu'}
                aria-controls="site-navigation"
                aria-expanded={menuOpen}
                title={menuOpen ? 'Close menu' : 'Open menu'}
                onClick={() => setMenuOpen((open) => !open)}
              >
                {menuOpen ? <X size={21} /> : <Menu size={21} />}
              </button>
              <nav
                id="site-navigation"
                className={`navarea2uc-nav${menuOpen ? ' is-open' : ''}`}
                aria-label="Main navigation"
              >
                <a href="#capabilities" onClick={closeMenu}>
                  Capabilities
                </a>
                <a href="#logic" onClick={closeMenu}>
                  Export logic
                </a>
                <a href="#ecdis-proof" onClick={closeMenu}>
                  Export result
                </a>
                <a href="#roadmap" onClick={closeMenu}>
                  Roadmap
                </a>
                <a href="#release" onClick={closeMenu}>
                  Release
                </a>
                <a
                  className="navarea2uc-nav-download"
                  href="https://github.com/drlivsi2004/NAVAREA2UC/releases/latest/download/NAVAREA2UC.exe"
                  target="_blank"
                  rel="noopener noreferrer"
                  onClick={closeMenu}
                >
                  <Download size={15} />
                  Download Windows EXE
                </a>
                <a href="mailto:support@navarea2uc.com" onClick={closeMenu}>
                  Support
                </a>
              </nav>
            </header>
          </div>

          <div className="navarea2uc-hero-copy">
            <div className="navarea2uc-eyebrow">
              <span className="navarea2uc-eyebrow-dot" />
              ECDIS USERCHART CONVERTER
            </div>
            <h1 id="hero-title">
              FROM MARITIME NOTICES
              <span>TO CHART-READY DATA.</span>
            </h1>
            <p className="navarea2uc-hero-text">
              Any source. Any format. Any ECDIS. A safety-first NAVAREA parser
              that turns navigational warnings into structured UserChart
              objects without silently changing the source geometry.
            </p>
            <div className="navarea2uc-buttons">
              <a
                href="#release"
                className="navarea2uc-btn navarea2uc-btn-primary"
              >
                View release
                <ArrowRight size={16} />
              </a>
              <a
                href="mailto:support@navarea2uc.com"
                className="navarea2uc-btn navarea2uc-btn-secondary"
              >
                Contact support
              </a>
            </div>
            <div className="navarea2uc-hero-note">
              <ShieldCheck size={16} />
              Built for reviewable, deterministic chart preparation
            </div>
          </div>
        </section>

        <section className="navarea2uc-trust-row" aria-label="Product guarantees">
          <span>RAW SOURCE PRESERVED</span>
          <span>EXPLICIT GEOMETRY FIRST</span>
          <span>MODERN + LEGACY XML</span>
          <span>NO SILENT REPAIR</span>
        </section>

        <section
          className="navarea2uc-proof"
          id="ecdis-proof"
          aria-labelledby="ecdis-proof-title"
        >
          <div className="navarea2uc-proof-heading">
            <div>
              <div className="navarea2uc-eyebrow">READY-TO-REVIEW EXPORT</div>
              <h2 id="ecdis-proof-title">
                The result is the
                <span>export itself.</span>
              </h2>
            </div>
            <p>
              These are real UserChart imports on Furuno ECDIS — not a simulated
              map view. Open any export to inspect how NAV overlays, danger zones
              and navigation objects sit on the working chart.
            </p>
          </div>
          <div className="navarea2uc-proof-grid">
            {ecdisPreviews.map((preview) => (
              <button
                key={preview.src}
                className="navarea2uc-proof-card"
                type="button"
                onClick={() => setSelectedPreview(preview)}
                aria-label={`Open ${preview.title} ${preview.mode} preview`}
              >
                <span className="navarea2uc-proof-image-wrap">
                  <img
                    src={preview.src}
                    alt={preview.alt}
                    loading="lazy"
                  />
                  <span className="navarea2uc-proof-open">
                    <Maximize2 size={15} />
                    Open preview
                  </span>
                </span>
                <span className="navarea2uc-proof-card-meta">
                  <span>
                    <strong>{preview.title}</strong>
                    <small>{preview.mode}</small>
                  </span>
                  <span className="navarea2uc-proof-meta-tag">
                    FURUNO / USERCHART 1.3
                  </span>
                </span>
              </button>
            ))}
          </div>
          <div className="navarea2uc-proof-note">
            <ShieldCheck size={15} />
            <span>Click an export to inspect the imported chart at full size.</span>
          </div>
        </section>

        <section className="navarea2uc-logic" id="logic" aria-labelledby="logic-title">
          <div className="navarea2uc-section-heading navarea2uc-logic-heading">
            <div>
              <div className="navarea2uc-eyebrow">
                <Table2 size={13} />
                VISUAL LANGUAGE
              </div>
              <h2 id="logic-title">
                Read the chart
                <span>at a glance.</span>
              </h2>
            </div>
            <p>
              A plain-language legend for the symbols, colours and shapes in the
              NAVAREA2UC export — made for people, not parser logs.
            </p>
          </div>
          <div className="navarea2uc-logic-panel">
            <div className="navarea2uc-logic-topline">
              <div>
                <span className="navarea2uc-logic-kicker">NAVAREA2UC / V1.3.0</span>
                  <strong>Engine output quick reference</strong>
              </div>
              <span className="navarea2uc-logic-status">
                <ShieldCheck size={14} />
                REVIEWABLE BY DESIGN
              </span>
            </div>
              <ul className="navarea2uc-logic-list">
                  {exportLogicRows.map((row) => (
                    <li key={row.name} className="navarea2uc-logic-list-item">
                      <span className={`navarea2uc-object-mark ${row.mark}`} aria-hidden="true">
                        <span />
                      </span>
                      <div className="navarea2uc-logic-list-copy">
                        <div className="navarea2uc-logic-list-summary">
                          <strong>Element ({row.element})</strong>
                          <span className="navarea2uc-logic-list-name">{row.name}</span>
                          <span className={`navarea2uc-color-chip ${row.colorTone}`}>
                            <span />
                            {row.colorName}
                          </span>
                          <span className={`navarea2uc-danger-chip ${row.statusTone}`}>
                            {row.status}
                          </span>
                        </div>
                        <p>{row.meaning}</p>
                      </div>
                    </li>
                  ))}
              </ul>
              <div className="navarea2uc-logic-rules">
                <strong>Safety rules</strong>
                <span>Circle only when the source publishes both a centre and a radius.</span>
                <span>FROM / TO movement stays as separate points — no invented route.</span>
                <span>Operation-only text without usable geometry creates no chart object.</span>
                <span>Colours and styles shown are the author's default settings; users can change the colour code and styles at their discretion.</span>
              </div>
              <div className="navarea2uc-logic-actions">
                <button
                  className="navarea2uc-print-button"
                  type="button"
                  onClick={() => window.print()}
                >
                  <Printer size={14} />
                  Print / Save PDF
                </button>
                <a
                  className="navarea2uc-pdf-link"
                  href={quickReferencePdfPath}
                  download
                >
                  <Download size={14} />
                  Download PDF
                </a>
              </div>
          </div>
        </section>

        <section
          className="navarea2uc-section"
          id="capabilities"
          aria-labelledby="capabilities-title"
        >
          <div className="navarea2uc-section-heading">
            <div>
              <div className="navarea2uc-eyebrow">CORE CAPABILITIES</div>
              <h2 id="capabilities-title">
                Clear output from
                <span>messy source text.</span>
              </h2>
            </div>
            <p>
              Every warning stays traceable from its original notice to the
                object you import into ECDIS.
            </p>
          </div>
          <div className="navarea2uc-feature-grid">
            <article className="navarea2uc-feature-card">
              <div className="navarea2uc-feature-icon blue">
                <Layers3 size={21} />
              </div>
              <h3>Structured extraction</h3>
              <p>
                Detects messages, source boundaries, encoding and provenance
                before processing the navigation content.
              </p>
              <div className="navarea2uc-feature-tag">SOURCE-AWARE</div>
            </article>
            <article className="navarea2uc-feature-card">
              <div className="navarea2uc-feature-icon teal">
                <Route size={21} />
              </div>
              <h3>Geometry you can trust</h3>
              <p>
                Supports Area, Line and Circle while preserving coordinate
                order and flagging ambiguous or incomplete geometry.
              </p>
              <div className="navarea2uc-feature-tag">GEOMETRY-SAFE</div>
            </article>
            <article className="navarea2uc-feature-card">
              <div className="navarea2uc-feature-icon violet">
                <CircleDot size={21} />
              </div>
              <h3>ECDIS-ready export</h3>
              <p>
                Creates modern and legacy UserChart XML with descriptions,
                labels, styles and compatibility-aware object splitting.
              </p>
              <div className="navarea2uc-feature-tag">ECDIS-READY</div>
            </article>
          </div>
        </section>

        <section className="navarea2uc-roadmap" id="roadmap" aria-labelledby="roadmap-title">
          <div className="navarea2uc-roadmap-heading">
            <div>
              <div className="navarea2uc-eyebrow">ROADMAP</div>
              <h2 id="roadmap-title">
                From a stable core
                <span>to a complete intake platform.</span>
              </h2>
            </div>
            <p>
              The product grows in deliberate layers: validate the conversion
              engine first, then make it easier to integrate, review and use.
            </p>
          </div>
          <div className="navarea2uc-roadmap-grid">
            <article className="navarea2uc-roadmap-item active">
              <span>01</span>
              <h3>Stable core</h3>
              <p>Validated NAVAREA parsing and ECDIS UserChart XML export.</p>
              <strong>Current</strong>
            </article>
            <article className="navarea2uc-roadmap-item">
              <span>02</span>
              <h3>Core API</h3>
              <p>A dependable interface for integrations and batch workflows.</p>
              <strong>Next</strong>
            </article>
            <article className="navarea2uc-roadmap-item">
              <span>03</span>
              <h3>Web platform</h3>
              <p>Upload, review and export from one browser-based workspace.</p>
              <strong>Planned</strong>
            </article>
            <article className="navarea2uc-roadmap-item">
              <span>04</span>
              <h3>Mobile-friendly intake</h3>
              <p>Lightweight source capture for the workflows that come after.</p>
              <strong>Later</strong>
            </article>
          </div>
        </section>

        <section className="navarea2uc-release" id="release" aria-labelledby="release-title">
          <div>
            <div className="navarea2uc-eyebrow">RELEASE TRACK</div>
            <h2 id="release-title">
              Core is ready.
              <span>Operational validation is next.</span>
            </h2>
            <p>
              v1.3.0 has passed automated corpus and geometry validation. The
              final release step is a Windows build followed by a real ECDIS
              import test.
            </p>
          </div>
          <a
            className="navarea2uc-release-link"
            href="https://github.com/drlivsi2004/NAVAREA2UC/releases/latest/download/NAVAREA2UC.exe"
            target="_blank"
            rel="noopener noreferrer"
          >
            <Download size={17} />
            Download Windows EXE
          </a>
        </section>

        <footer className="navarea2uc-footer">
          <div className="navarea2uc-footer-brand">
            <span
              className="navarea2uc-wordmark navarea2uc-wordmark-footer"
              aria-label="NAVAREA2UC"
            >
              <span>NAVAREA</span>
              <strong>2</strong>
              <span>UC</span>
            </span>
          </div>
          <span>Any Source. Any Format. Any ECDIS.</span>
          <a href="mailto:support@navarea2uc.com">
            support@navarea2uc.com
          </a>
          <span>© 2026 NAVAREA2UC</span>
        </footer>
      </div>
      {selectedPreview && (
        <div
          className="navarea2uc-lightbox"
          role="dialog"
          aria-modal="true"
          aria-labelledby="ecdis-lightbox-title"
          onClick={() => setSelectedPreview(null)}
        >
          <div
            className="navarea2uc-lightbox-panel"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="navarea2uc-lightbox-topline">
              <div>
                <div className="navarea2uc-eyebrow">ECDIS PROOF</div>
                <h2 id="ecdis-lightbox-title">
                  {selectedPreview.title}
                  <span>{selectedPreview.mode}</span>
                </h2>
              </div>
              <button
                className="navarea2uc-lightbox-close"
                type="button"
                aria-label="Close preview"
                onClick={() => setSelectedPreview(null)}
              >
                <X size={20} />
              </button>
            </div>
            <div className="navarea2uc-lightbox-image-wrap">
              <img src={selectedPreview.src} alt={selectedPreview.alt} />
            </div>
            <div className="navarea2uc-lightbox-footer">
              <span>FURUNO ECDIS · USERCHART v1.3</span>
              <span>Click outside or press Esc to close</span>
            </div>
          </div>
        </div>
      )}
    </main>
  );
}