"use client";

import Link from "next/link";
import { useEffect, useState } from "react";


const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:8000";


export default function ProjectsPage() {
  const [projects, setProjects] = useState([]);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [creating, setCreating] = useState(false);
  const [status, setStatus] = useState({ message: "Loading projects...", kind: "" });

  async function loadProjects() {
    try {
      const response = await fetch(`${API_BASE_URL}/projects`);
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const data = await response.json();
      setProjects(data);
      setStatus({
        message: data.length ? `${data.length} Project(s).` : "No projects yet.",
        kind: "success",
      });
    } catch (error) {
      console.error("Unable to load Projects", error);
      setStatus({
        message: "Unable to load Projects. Check PostgreSQL and FastAPI.",
        kind: "error",
      });
    }
  }

  useEffect(() => {
    loadProjects();
  }, []);

  async function createProject(event) {
    event.preventDefault();
    setCreating(true);
    setStatus({ message: "Creating Project...", kind: "" });
    try {
      const response = await fetch(`${API_BASE_URL}/projects`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: name.trim(),
          description: description.trim() || null,
        }),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.detail || `HTTP ${response.status}`);
      setName("");
      setDescription("");
      await loadProjects();
    } catch (error) {
      console.error("Unable to create Project", error);
      setStatus({ message: `Unable to create Project: ${error.message}`, kind: "error" });
    } finally {
      setCreating(false);
    }
  }

  return (
    <main>
      <nav>
        <Link href="/">Literature Search</Link>
      </nav>
      <h1>Research Projects</h1>

      <form onSubmit={createProject}>
        <div className="field">
          <label htmlFor="name">Project name</label>
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
        <button type="submit" disabled={creating}>
          {creating ? "Creating..." : "Create Project"}
        </button>
      </form>

      <p className={`status ${status.kind}`} role="status">
        {status.message}
      </p>

      <section className="cards" aria-label="Project list">
        {projects.map((project) => (
          <article className="card" key={project.id}>
            <h2>
              <Link href={`/projects/${project.id}`}>{project.name}</Link>
            </h2>
            <p>{project.description || "No description."}</p>
            <p className="muted">
              {project.paper_count} saved paper(s) · Created{" "}
              {new Date(project.created_at).toLocaleString()}
            </p>
          </article>
        ))}
      </section>
    </main>
  );
}
