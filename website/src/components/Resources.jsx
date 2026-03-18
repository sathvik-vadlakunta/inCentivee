import { FileText, Download } from 'lucide-react'
import Button from './Button'
import './Resources.css'

export default function Resources() {
  return (
    <section className="resources section" id="resources">
      <div className="resources-inner container">
        <div className="resources-header">
          <div className="resources-icon-badge">
            <FileText size={24} strokeWidth={2.5} />
          </div>
          <h2 className="resources-title">Resources</h2>
          <p className="resources-subtitle">
            Explore our latest presentation on building financial confidence.
          </p>
        </div>

        <div className="resources-embed-wrapper">
          <object
            data="/Financial Literacy.pdf"
            type="application/pdf"
            className="resources-embed"
            aria-label="Financial education presentation"
          >
            <div className="resources-fallback">
              <FileText size={48} strokeWidth={2} />
              <p>
                Your browser doesn't support embedded PDFs.
              </p>
              <Button
                variant="primary"
                icon={Download}
                href="/Financial Literacy.pdf"
                target="_blank"
                rel="noopener noreferrer"
              >
                Download Presentation
              </Button>
            </div>
          </object>
        </div>

        <div className="resources-download-bar">
          <Button
            variant="secondary"
            icon={Download}
            href="/Financial Literacy.pdf"
            target="_blank"
            rel="noopener noreferrer"
          >
            Download PDF
          </Button>
        </div>
      </div>
    </section>
  )
}
