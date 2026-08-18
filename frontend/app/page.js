"use client";

import Link from "next/link";
import { useEffect, useState } from "react";


const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:8000";


function MetadataRow({ label, children, value }) {
  return (
    <>
      <dt>{label}</dt>
      <dd>{children || value || "Not available"}</dd>
    </>
  );
}


export default function LiteratureSearchPage() {
  const [query, setQuery] = useState("");
  const [source, setSource] = useState("pubmed");
  const [projects, setProjects] = useState([]);
  const [projectId, setProjectId] = useState("");
  const [results, setResults] = useState([]);
  const [status, setStatus] = useState({ message: "Ready to search.", kind: "" });
  const [searching, setSearching] = useState(false);
  const [savingKey, setSavingKey] = useState(null);
  const [saveMessages, setSaveMessages] = useState({});

  useEffect(() => {
    async function loadProjects() {
      try {
        const response = await fetch(`${API_BASE_URL}/projects`);
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        setProjects(await response.json());
      } catch (error) {
        console.error("Unable to load projects", error);
        setProjects([]);
      }
    }
    loadProjects();
  }, []);

  async function handleSearch(event) {
    event.preventDefault();
    const trimmedQuery = query.trim();
    if (!trimmedQuery) {
      setStatus({ message: "Please enter research keywords.", kind: "error" });
      return;
    }

    setSearching(true);
    setResults([]);
    setSaveMessages({});
    setStatus({ message: "Searching literature...", kind: "" });
    const params = new URLSearchParams({ q: trimmedQuery, source, limit: "10" });

    try {
      const response = await fetch(`${API_BASE_URL}/api/literature/search?${params}`);
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const data = await response.json();
      setResults(data.results);
      if (!data.results.length) {
        setStatus({ message: "No literature found. Try different keywords.", kind: "" });
        return;
      }
      const warningText = data.warnings.length ? ` ${data.warnings.join(" ")}` : "";
      setStatus({
        message: `Found ${data.count} result(s).${warningText}`,
        kind: "success",
      });
    } catch (error) {
      console.error("Literature search failed", error);
      setStatus({
        message: "Unable to retrieve literature. Please try again.",
        kind: "error",
      });
    } finally {
      setSearching(false);
    }
  }

  async function testBackend() {
    setStatus({ message: "Connecting to backend...", kind: "" });
    try {
      const response = await fetch(`${API_BASE_URL}/health`);
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const data = await response.json();
      setStatus({
        message: `Backend response: ${JSON.stringify(data)}`,
        kind: "success",
      });
    } catch (error) {
      console.error("Backend connection failed", error);
      setStatus({ message: "Unable to connect to backend.", kind: "error" });
    }
  }

  async function savePaper(item) {
    const itemKey = `${item.source}-${item.id}`;
    if (!projectId) {
      setSaveMessages((current) => ({
        ...current,
        [itemKey]: "Select a Project first.",
      }));
      return;
    }

    setSavingKey(itemKey);
    setSaveMessages((current) => ({ ...current, [itemKey]: "Saving..." }));
    try {
      const response = await fetch(`${API_BASE_URL}/projects/${projectId}/papers`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          source: item.source,
          external_id: item.id,
          title: item.title,
          abstract: item.abstract,
          authors: item.authors,
          journal: item.journal,
          publication_year: item.year,
          doi: item.doi,
          url: item.url,
        }),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.detail || `HTTP ${response.status}`);
      setSaveMessages((current) => ({
        ...current,
        [itemKey]: data.created ? "Saved." : "Already saved in this Project.",
      }));
    } catch (error) {
      console.error("Unable to save paper", error);
      setSaveMessages((current) => ({
        ...current,
        [itemKey]: `Save failed: ${error.message}`,
      }));
    } finally {
      setSavingKey(null);
    }
  }

  return (
    <main>
      <nav>
        <Link href="/projects">Projects</Link>
      </nav>
      <h1>AI Research Assistant</h1>

      <form onSubmit={handleSearch}>
        <div className="controls">
          <div>
            <label htmlFor="question">Research Question / Keywords</label>
            <input
              id="question"
              type="search"
              placeholder="e.g. CRISPR cancer therapy"
              required
              value={query}
              onChange={(event) => setQuery(event.target.value)}
            />
          </div>
          <div>
            <label htmlFor="source">Source</label>
            <select id="source" value={source} onChange={(event) => setSource(event.target.value)}>
              <option value="pubmed">PubMed</option>
              <option value="openalex">OpenAlex</option>
              <option value="all">All</option>
            </select>
          </div>
        </div>

        <div className="actions">
          <button type="submit" disabled={searching}>
            {searching ? "Searching..." : "Search Literature"}
          </button>
          <button className="secondary" type="button" onClick={testBackend}>
            Test Backend
          </button>
        </div>

        <div className="save-controls">
          <div>
            <label htmlFor="project-select">Save search results to Project</label>
            <select
              id="project-select"
              value={projectId}
              onChange={(event) => setProjectId(event.target.value)}
            >
              <option value="">
                {projects.length ? "Select a Project" : "Create a Project first"}
              </option>
              {projects.map((project) => (
                <option key={project.id} value={project.id}>
                  {project.name}
                </option>
              ))}
            </select>
          </div>
          <Link className="button-link secondary-link" href="/projects">
            Manage Projects
          </Link>
        </div>
      </form>

      <p className={`status ${status.kind}`} role="status" aria-live="polite">
        {status.message}
      </p>

      <section className="results" aria-label="Literature results">
        {results.map((item) => {
          const itemKey = `${item.source}-${item.id}`;
          return (
            <article className="result-card" key={itemKey}>
              <h2>{item.title || "Untitled article"}</h2>
              <dl>
                <MetadataRow
                  label="Authors"
                  value={item.authors.length ? item.authors.join(", ") : null}
                />
                <MetadataRow
                  label="Published"
                  value={item.publication_date || item.year?.toString()}
                />
                <MetadataRow label="Journal" value={item.journal} />
                <MetadataRow
                  label="Database"
                  value={item.source === "pubmed" ? "PubMed" : "OpenAlex"}
                />
                <MetadataRow label="DOI">
                  {item.doi ? (
                    <a
                      href={`https://doi.org/${item.doi}`}
                      target="_blank"
                      rel="noopener noreferrer"
                    >
                      {item.doi}
                    </a>
                  ) : null}
                </MetadataRow>
              </dl>
              <details>
                <summary>Abstract</summary>
                <p>{item.abstract || "No abstract available."}</p>
              </details>
              <div className="save-paper">
                <button
                  type="button"
                  disabled={savingKey === itemKey}
                  onClick={() => savePaper(item)}
                >
                  Save to Project
                </button>
                <span className="save-message">{saveMessages[itemKey] || ""}</span>
              </div>
            </article>
          );
        })}
      </section>
    </main>
  );
}
