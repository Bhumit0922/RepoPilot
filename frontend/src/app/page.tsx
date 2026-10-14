
"use client";

import { useEffect, useState } from "react";

type HealthResponse = {
  status: string;
  service: string;
};

export default function Home() {
  const [apiStatus, setApiStatus] = useState(
    "Checking backend..."
  );

  useEffect(() => {
    const apiUrl =
      process.env.NEXT_PUBLIC_API_URL ??
      "http://127.0.0.1:8000";

    fetch(`${apiUrl}/health`)
      .then((response) => {
        if (!response.ok) {
          throw new Error("API request failed");
        }
        return response.json() as Promise<HealthResponse>;
      })
      .then((data) => {
        setApiStatus(
          data.status === "ok"
            ? `Connected to ${data.service}`
            : "Unexpected backend response"
        );
      })
      .catch(() => {
        setApiStatus(
          "Backend unavailable. Start the FastAPI server."
        );
      });
  }, []);

  return (
    <main className="min-h-screen bg-slate-950 px-6 py-16 text-white">
      <div className="mx-auto max-w-5xl">
        <p className="text-sm font-semibold uppercase tracking-[0.25em] text-cyan-400">
          GenAI Engineering Portfolio
        </p>

        <h1 className="mt-5 text-4xl font-bold sm:text-6xl">
          Building AI that solves real problems.
        </h1>

        <p className="mt-5 max-w-2xl text-lg text-slate-300">
          Two end-to-end GenAI applications built for real-world
          use, measurable quality, and reliable engineering.
        </p>

        <div className="mt-10 grid gap-5 md:grid-cols-2">
          <section className="rounded-2xl border border-slate-700 bg-slate-900 p-6">
            <p className="text-sm text-cyan-400">PROJECT 01</p>
            <h2 className="mt-3 text-2xl font-semibold">
              RepoPilot
            </h2>
            <p className="mt-3 leading-7 text-slate-300">
              Understand codebases, investigate software issues,
              retrieve relevant code, and propose fixes with tests.
            </p>
            <p className="mt-5 text-sm text-slate-400">
              AI Software Engineering Agent
            </p>
          </section>

          <section className="rounded-2xl border border-slate-700 bg-slate-900 p-6">
            <p className="text-sm text-violet-400">PROJECT 02</p>
            <h2 className="mt-3 text-2xl font-semibold">
              TenderLens
            </h2>
            <p className="mt-3 leading-7 text-slate-300">
              Analyze tender documents, compare eligibility
              requirements, and generate evidence-backed reports.
            </p>
            <p className="mt-5 text-sm text-slate-400">
              AI Tender Intelligence Platform
            </p>
          </section>
        </div>

        <section className="mt-8 rounded-xl border border-slate-700 p-5">
          <h2 className="font-semibold">Backend connection</h2>
          <p className="mt-2 text-sm text-slate-300" role="status">
            {apiStatus}
          </p>
        </section>

        <footer className="mt-12 text-sm text-slate-500">
          GenAI Portfolio · Development Environment
        </footer>
      </div>
    </main>
  );
}
