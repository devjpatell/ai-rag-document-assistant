import ChatInterface from "../components/ChatInterface";

export default function Home() {
  return (
    <main className="page">
      <section className="hero">
        <div className="heroBadge">AI-Powered Document Intelligence</div>

        <h1>
          Chat With Your Documents Using <span>RAG AI</span>
        </h1>

        <p>
          Upload PDFs or text files and ask questions instantly. This project uses
          document retrieval, AI-powered reasoning, and a full-stack workflow designed
          for real-world portfolio and resume impact.
        </p>

        <div className="heroStats">
          <div>
            <strong>PDF/TXT</strong>
            <small>Document Upload</small>
          </div>
          <div>
            <strong>RAG</strong>
            <small>Context Retrieval</small>
          </div>
          <div>
            <strong>CI/CD</strong>
            <small>GitHub Ready</small>
          </div>
        </div>
      </section>

      <ChatInterface />
    </main>
  );
}
