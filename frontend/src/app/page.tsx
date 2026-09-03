"use client";

import { useState, useEffect, useRef } from "react";

export default function Home() {
  const [content, setContent] = useState("");
  const [status, setStatus] = useState("Connecting...");
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    // Connect to WebSockets Backend
    const ws = new WebSocket("ws://localhost:8000/ws/default");
    wsRef.current = ws;

    ws.onopen = () => {
      setStatus("Connected (Real-time)");
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === "init" || data.type === "update") {
          if (data.content !== undefined) {
            setContent(data.content);
          }
        }
      } catch (e) {
        console.error("WS Parse Error", e);
      }
    };

    ws.onclose = () => {
      setStatus("Disconnected. Attempting REST fallback...");
      fetch("http://localhost:8000/api/documents/default")
        .then((res) => res.json())
        .then((data) => {
          if (data.content) setContent(data.content);
        })
        .catch((err) => console.error(err));
    };

    return () => {
      ws.close();
    };
  }, []);

  const handleChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    const val = e.target.value;
    setContent(val);

    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(
        JSON.stringify({
          type: "update",
          content: val,
        })
      );
    }
  };

  return (
    <main style={{ minHeight: "100vh", backgroundColor: "#0f172a", color: "#f8fafc", padding: "2rem", fontFamily: "sans-serif" }}>
      <div style={{ maxWidth: "800px", margin: "0 auto" }}>
        <header style={{ display: "flex", justifyContent: "space-between", alignItems: "center", borderBottom: "1px solid #334155", paddingBottom: "1rem", marginBottom: "1.5rem" }}>
          <div>
            <h1 style={{ fontSize: "1.5rem", fontWeight: "bold", color: "#60a5fa", margin: 0 }}>
              Real-time Collaborative Document Editor
            </h1>
            <p style={{ fontSize: "0.875rem", color: "#94a3b8", margin: "0.25rem 0 0 0" }}>Document ID: default</p>
          </div>
          <span style={{ padding: "0.25rem 0.75rem", fontSize: "0.75rem", borderRadius: "9999px", backgroundColor: status.includes("Connected") ? "#166534" : "#854d0e", color: "#f8fafc" }}>
            {status}
          </span>
        </header>

        <div style={{ backgroundColor: "#1e293b", borderRadius: "0.75rem", padding: "1rem", border: "1px solid #334155" }}>
          <textarea
            value={content}
            onChange={handleChange}
            placeholder="Start typing..."
            style={{ width: "100%", height: "450px", backgroundColor: "#020617", color: "#f8fafc", padding: "1rem", borderRadius: "0.5rem", border: "1px solid #1e293b", fontFamily: "monospace", fontSize: "0.9rem", resize: "none" }}
          />
        </div>
      </div>
    </main>
  );
}