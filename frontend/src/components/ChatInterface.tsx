"use client";

import { useState } from "react";
import { askQuestion, uploadDocument } from "../lib/api";

type Source = {
  text: string;
  score: number;
  document_name: string;
};

export default function ChatInterface() {
  const [file, setFile] = useState<File | null>(null);
  const [uploaded, setUploaded] = useState(false);
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState("");
  const [sources, setSources] = useState<Source[]>([]);
  const [loading, setLoading] = useState(false);

  async function handleAsk() {
    if (!file) {
      setAnswer("Please upload a PDF or TXT file first.");
      return;
    }

    if (!question.trim()) {
      setAnswer("Please type a question about your document.");
      return;
    }

    setLoading(true);
    setAnswer("");
    setSources([]);

    try {
      if (!uploaded) {
        await uploadDocument(file);
        setUploaded(true);
      }

      const result = await askQuestion(question);
      setAnswer(result.answer);
      setSources(result.sources || []);
    } catch (error: any) {
      setAnswer(`Error: ${error.message}`);
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="appCard">
      <div className="panelHeader">
        <div>
          <p className="eyebrow">Document Assistant</p>
          <h2>Upload. Ask. Understand.</h2>
        </div>
        <div className={uploaded ? "status successStatus" : "status"}>
          {uploaded ? "Document Ready" : "Waiting for Upload"}
        </div>
      </div>

      <div className="uploadArea">
        <div className="uploadIcon">??</div>
        <h3>Upload Your Document</h3>
        <p>Supports PDF and TXT files</p>

        <label className="fileButton">
          Choose File
          <input
            type="file"
            accept=".pdf,.txt"
            onChange={(e) => {
              setFile(e.target.files?.[0] || null);
              setUploaded(false);
              setAnswer("");
              setSources([]);
            }}
          />
        </label>

        {file && <p className="fileName">Selected: {file.name}</p>}
      </div>

      <div className="questionBox">
        <label>Ask a question</label>
        <textarea
          placeholder="Example: Give me key points from this document..."
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
        />

        <button onClick={handleAsk} disabled={loading}>
          {loading ? "Analyzing document..." : "Ask AI"}
        </button>
      </div>

      {answer && (
        <div className="answerBox">
          <div className="answerTitle">
            <span>?</span>
            <h3>AI Answer</h3>
          </div>
          <p>{answer}</p>
        </div>
      )}

      {sources.length > 0 && (
        <div className="sourcesBox">
          <h3>Retrieved Sources</h3>

          {sources.map((source, index) => (
            <div key={index} className="sourceItem">
              <div>
                <strong>{source.document_name}</strong>
                <small>Similarity Score: {source.score.toFixed(3)}</small>
              </div>
              <p>{source.text.slice(0, 350)}...</p>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
