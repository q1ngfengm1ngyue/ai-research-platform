"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";


const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:8000";


export default function ProjectDetailPage() {
  const { projectId } = useParams();
  const router = useRouter();
  const [project, setProject] = useState(null);
  const [papers, setPapers] = useState([]);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [status, setStatus] = useState({ message: "Loading Project...", kind: "" });
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);

  const loadProject = useCallback(async () => {
    if (!projectId) return;
    try {
      const [projectResponse, papersResponse] = await Promise.all([
        fetch(`${API_BASE_URL}/projects/${projectId}`),
        fetch(`${API_BASE_URL}/projects/${projectId}/papers`),
      ]);
      if (!projectResponse.ok || !papersResponse.ok) throw new Error("Request failed");
      const projectData = await projectResponse.json();
      const paperData = await papersResponse.json();
      setProject(projectData);
      setPapers(paperData);
      setName(projectData.name);
      setDescription(projectData.description || "");
      setStatus({ message: "Project loaded.", kind: "success" });
    } catch (error) {
      console.error("Unable to load Project", error);
      setStatus({ message: "Unable to load this Project.", kind: "error" });
    }
  }, [projectId]);

  useEffect(() => {
    loadProject();
  }, [loadProject]);

  async function updateProject(event) {
    event.preventDefault();
    setSaving(true);
    try {
      const response = await fetch(`${API_BASE_URL}/projects/${projectId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: name.trim(),
          description: description.trim() || null,
        }),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.detail || `HTTP ${response.status}`);
      await loadProject();
    } catch (error) {
      console.error("Unable to update Project", error);
      setStatus({ message: `Unable to update Project: ${error.message}`, kind: "error" });
    } finally {
      setSaving(false);
    }
  }

  async function removePaper(paperId) {
    try {
      const response = await fetch(
        `${API_BASE_URL}/projects/${projectId}/papers/${paperId}`,
        { method: "DELETE" },
      );
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      await loadProject();
    } catch (error) {
      console.error("Unable to remove paper", error);
      setStatus({ message: "Unable to remove the paper.", kind: "error" });
    }
  }

  async function deleteProject() {
    if (!window.confirm("Delete this Project and all of its saved papers?")) return;
    setDeleting(true);
    try {
      const response = await fetch(`${API_BASE_URL}/projects/${projectId}`, {
        method: "DELETE",
      });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      router.push("/projects");
    } catch (error) {
      console.error("Unable to delete Project", error);
      setStatus({ message: "Unable to delete Project.", kind: "error" });
      setDeleting(false);
    }
  }

  return (
    <main>
      <nav>
        <Link href="/projects">Projects</Link>
        <Link href="/">Literature Search</Link>
      </nav>
      <h1>{project?.name || "Project"}</h1>
      <p>{project?.description || "No description."}</p>
      <p className="muted">{papers.length} saved paper(s)</p>

      <section className="card">
        <h2>Edit Project</h2>
        <form onSubmit={updateProject}>
          <div className="field">
            <label htmlFor="name">Name</label>
            <input
              id="name"
              maxLength={200}
              required
              value={name}
              onChange={(event) => setName(event.target.value)}
            />
          </div>
          <div className="field">
            <label htmlFor="description">Description</label>
            <textarea
              id="description"
              maxLength={5000}
              value={description}
              onChange={(event) => setDescription(event.target.value)}
            />
          </div>
          <div className="actions">
            <button type="submit" disabled={saving}>
              {saving ? "Saving..." : "Save changes"}
            </button>
            <button
              className="danger"
              type="button"
              disabled={deleting}
              onClick={deleteProject}
            >
              {deleting ? "Deleting..." : "Delete Project"}
            </button>
          </div>
        </form>
      </section>

      <p className={`status ${status.kind}`} role="status">
        {status.message}
      </p>
      <h2>Saved Literature</h2>
      <section className="cards" aria-label="Saved papers">
        {papers.map((paper) => (
          <article className="card" key={paper.id}>
            <h3>{paper.title || "Untitled paper"}</h3>
            <div className="paper-meta muted">
              <span>
                {paper.authors.length ? paper.authors.join(", ") : "Authors unavailable"}
              </span>
              <span>{paper.publication_year || "Year unavailable"}</span>
              <span>{paper.source === "pubmed" ? "PubMed" : "OpenAlex"}</span>
            </div>
            <button className="danger" type="button" onClick={() => removePaper(paper.id)}>
              Remove from Project
            </button>
          </article>
        ))}
      </section>
    </main>
  );
}
